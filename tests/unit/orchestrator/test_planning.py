"""Where each clip's thumbnails land. Pure, no filesystem."""

from __future__ import annotations

from pathlib import Path

from meta_still.orchestrator.domain.planning import plan_destinations

OUT = Path("C:/out")


def test_card_plumbing_is_collapsed() -> None:
    videos = [(("CAMERAS", "2026_04_27", "FX3_B", "M4ROOT", "CLIP"), "20260427_B3301.MP4")]

    [clip] = plan_destinations(videos, OUT)

    assert clip.destination == OUT / "CAMERAS/2026_04_27/FX3_B/20260427_B3301"


def test_meaningful_folders_are_kept() -> None:
    videos = [(("MEDIAS", "2025_12_10", "Episodio", "Câmeras separadas"), "MultiCorder1.mp4")]

    [clip] = plan_destinations(videos, OUT)

    assert clip.destination == OUT / "MEDIAS/2025_12_10/Episodio/Câmeras separadas/MultiCorder1"


def test_xdroot_and_dcim_collapse_too() -> None:
    videos = [
        (("FX6_A", "XDROOT", "Clip"), "C0021.MXF"),
        (("DRONE", "DCIM", "100MEDIA"), "DJI_0001.MP4"),
    ]

    plan = plan_destinations(videos, OUT)

    assert plan[0].destination == OUT / "FX6_A/C0021"
    assert plan[1].destination == OUT / "DRONE/100MEDIA/DJI_0001"


def test_clips_sharing_a_name_keep_their_full_paths() -> None:
    """CLIP/C2046.MP4 and SUB/C2046.MP4 would both claim FX3_C/C2046, and the
    second would silently overwrite the first's thumbnails."""
    videos = [
        (("FX3_C", "M4ROOT", "CLIP"), "C2046.MP4"),
        (("FX3_C", "M4ROOT", "SUB"), "C2046.MP4"),
    ]

    plan = plan_destinations(videos, OUT)

    assert plan[0].destination == OUT / "FX3_C/M4ROOT/CLIP/C2046"
    assert plan[1].destination == OUT / "FX3_C/M4ROOT/SUB/C2046"
    assert plan[0].destination != plan[1].destination


def test_only_the_colliding_clips_pay_for_the_collision() -> None:
    videos = [
        (("FX3_C", "M4ROOT", "CLIP"), "C2046.MP4"),
        (("FX3_C", "M4ROOT", "SUB"), "C2046.MP4"),
        (("FX3_C", "M4ROOT", "CLIP"), "C2047.MP4"),
    ]

    plan = plan_destinations(videos, OUT)

    assert plan[2].destination == OUT / "FX3_C/C2047"


def test_planning_is_deterministic_so_a_resumed_run_matches() -> None:
    videos = [
        (("FX3_C", "M4ROOT", "CLIP"), "C2046.MP4"),
        (("FX3_C", "M4ROOT", "SUB"), "C2046.MP4"),
    ]

    assert plan_destinations(videos, OUT) == plan_destinations(videos, OUT)


def test_unsafe_names_are_still_sanitised() -> None:
    videos = [(("Episodio",), "MultiCorder5 - Output 1 - 10-22-47 .mp4")]

    [clip] = plan_destinations(videos, OUT)

    assert clip.destination == OUT / "Episodio/MultiCorder5 - Output 1 - 10-22-47"
