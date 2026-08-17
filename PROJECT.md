# meta-still — Project Reference

> Living reference document. Every architectural decision, contract and roadmap item lands here first,
> then in code. If code and this document disagree, this document is wrong — fix it in the same PR.
>
> Sections marked **BUILT** describe code that exists and is tested. Sections marked **PLANNED**
> describe intent and may still change.

---

## 1. Mission

**meta-still** is a post-production ingest toolchain. Given an external drive (USB HD) full of camera
rushes, it produces a machine-readable and human-readable **summary** of the footage: what was shot,
by which camera, with which technical parameters, plus representative **thumbnails (stills)** for each
clip — and delivers the whole package to a shared **Google Drive** folder.

### Media formats — corrected against real material

The project was scoped around **MXF**. The first real drive (`D:\ABIMED`, 1.7 TB) contains **none**:

| Format | Count | Size | Source |
|---|---|---|---|
| `.MP4` | 318 | 1.6 TB | Sony FX3 (XAVC-S in `M4ROOT/`), MultiCorder, Premiere exports |
| `.WAV` | 327 | 71.7 GB | Zoom F6 field recorder, ISO audio |
| `.MOV` | 2 | 961 MB | graphics/vinheta |
| `.MXF` | **0** | — | — |

So **MP4 is the primary format in practice**, with MXF supported when it appears. This is good news:
MP4 avoids the MXF complications (P2 splitting a clip across video/audio essence files, XDCAM
`Clip/` + `Sub/` proxy pairs) that would otherwise have shaped Module B.

### Why it exists

After a shoot, the post team receives drives with thousands of clips spread over camera-specific folder
trees (`FX3_A`, `FX6`, drone units, …). Before editorial starts, someone must answer: *what is on this
drive, how much of it, in what codec/framerate/colour space, and what does it look like?* Today that is
manual. meta-still automates it.

---

## 2. Scope & status

| # | Feature | Module | Status |
|---|---------|--------|--------|
| 1 | Walk a folder/drive, build a tree, report sizes and extension totals | **A — Mapper** | **BUILT** |
| 2 | Mirror the tree and generate *N* PNG thumbnails per video | **C — Stills** + **Orchestrator** | **BUILT** |
| 3 | Classify files and infer camera labels from paths/filenames | **A — Mapper** | PLANNED (§12) |
| 4 | Extract technical metadata per clip → one JSON per clip | **B — Metadata** | PLANNED |
| 5 | Render a consolidated summary from the per-clip JSONs | **B — Metadata** | PLANNED |
| 6 | Compute white balance of still images | **D — White Balance** | PLANNED |
| 7 | Upload artifacts to a Google Drive folder | **Storage adapter** | PLANNED |

### Out of scope (explicitly, for now)

- Transcoding / proxy generation (only frame extraction).
- NLE project file generation (XML/AAF/EDL) — a plausible v2 module.
- Editing or writing back to the source media. **The source drive is read-only, always.**
- Face/object recognition, transcription, LLM-based content description — possible v2 modules; the
  architecture must not preclude them.

### Hard constraints

All three are **tested requirements**, not aspirations — see §11.

1. **Never write to the source volume.** All output goes to a separate output directory.
2. **Idempotent & resumable.** Re-running over a partially processed drive skips completed work.
   Drives get unplugged mid-run; that is normal, not an error.
3. **Fail per-clip, not per-run.** One corrupt file must not abort a 160-clip ingest.

---

## 3. Glossary

| Term | Meaning |
|------|---------|
| **Volume** | A mounted drive being ingested. |
| **Clip** | One video file. The atomic unit of work. |
| **Card** | A camera card folder structure (`M4ROOT/` for Sony FX3, `XDROOT/` for XDCAM) inside a volume. |
| **ISO** | A per-camera recording made by the switcher/recorder, parallel to the camera's own card. |
| **Camera label** | The device that shot the clip (`FX3_A`, `CAM 1`, …), inferred from path or filename. |
| **Still / Thumbnail** | A PNG extracted from a clip at a given timestamp. |
| **Artifact** | Any file meta-still produces: map, still, clip JSON, summary. |
| **Run** | One execution of the pipeline over one folder. |

---

## 4. Modules

Each module is **independently runnable, testable and deployable** — that is the microservice-readiness
requirement, and every module has its own `__main__.py` to prove it.

### A) Video-Files Mapper — **BUILT**

Walks a folder, builds a tree, writes a `.txt` report. Never opens a media file, so a full-drive scan
takes seconds.

- **Input:** a folder path (prompted, or `py -m meta_still.mapper <path> -o <out>`).
- **Output:** `<folder>_map.txt` — header totals, annotated tree, extension table, ignored counts,
  unreadable paths.
- **The extension table is the point.** It is what classification rules get designed from.
- **Ignore rules** are applied during the scan (§6.3), so the map, the counts and the folders created
  downstream all agree with each other.

**Not yet built:** camera-label inference and `inventory.json` (§12).

### B) Metadata-Summary — PLANNED

Extract technical metadata per clip; consolidate many clip JSONs into one summary.

- `extract(clip) -> ClipMetadata` — one JSON per clip.
- `summarize(clips[], profile) -> Summary` — selected fields, grouped/aggregated, rendered.
- **Extraction backend:** an `ExtractorPort` with pluggable adapters (ffprobe / MediaInfo). The domain
  never sees a vendor payload shape; adapters normalise into `ClipMetadata` and keep the raw vendor blob
  under `vendor.*` for forensics.
- **Extension point:** the summary may enrich itself with white-balance data produced by **D**, computed
  on stills produced by **C** — a *pull* over artifact contracts. B does not import C or D.

### C) Stills-Generator — **BUILT**

Produces *N* PNG thumbnails from one video.

- **Sampling:** `duration / (N + 1)`, sampled at the interior boundaries. Sampling at `i/N` instead
  would put the first still on frame zero, which on rushes is a slate, a lens cap or black far more
  often than a useful image — and the last on the tail.
- **Params:** `-n` count (default 5), `--max-edge` long side in pixels (default 1920, `0` = source).
- **Format:** PNG. Lossless matters because Module D measures colour from these pixels. See §12 for the
  size trade-off that was weighed.
- **No colour transform is applied at any step** — S-Log3 stays log. Applying a display LUT would make
  white-balance measurement meaningless. This is a hard requirement on the adapter.
- **Release is guaranteed by a context manager.** A leaked decoder per bad clip exhausts file handles
  long before a 160-clip run finishes; there is a test that forces a mid-batch failure and asserts the
  decoder still closed.

### D) White-Balance — PLANNED

Given an image, estimate its white balance / colour cast.

- **Input:** a PNG path (from C, or any image). **Output:** `{ estimated_temp_k, tint, rgb_gains,
  method, confidence }`.
- **Methods** behind one port: `gray-world` (baseline), `white-patch/retinex`, `percentile-gray`.
- Deliberately generic: it knows about *images*, not about cameras. The most reusable module, and the
  easiest to run as a standalone service.

### Orchestrator — **BUILT**

Composes A and C into the pipeline. **The only layer permitted to import more than one module** —
composing them is its entire job, and it is what keeps A and C ignorant of each other.

Per run it: scans → writes the map → selects video files → for each, mirrors the source path into the
output, creates a folder named after the clip, and calls Module C into it.

- **Resume:** a clip whose folder already holds *N* PNGs is skipped. `--force` overrides.
- **Failure isolation:** any exception is caught per clip, the empty folder is cleaned up, the run
  continues, and failures are listed at the end.
- **Exit code:** `0` for a run that finished, even with unreadable clips. Non-zero only when nothing at
  all came through.

### Shared infrastructure — PLANNED

- **Storage adapter** — `StoragePort` with `LocalFileSystem` and `GoogleDrive` adapters (service
  account). Resumable uploads, retry with backoff, checksum verification.
- **Run/Manifest service** — run ids, per-clip state, richer resume than the current
  folder-already-has-PNGs check.

---

## 5. Architecture

### 5.1 Principles

1. **Clean / hexagonal architecture per module.** Dependencies point inward:
   `interfaces → application → domain`, and `infrastructure` implements ports defined in `core`.
   The domain imports nothing from the outside world — no ffmpeg, no Google SDK, no filesystem.
2. **Modules talk through contracts, never through imports.** They share only `core` (entities + ports)
   and the on-disk artifact formats. The orchestrator is the single deliberate exception.
3. **The transport is a detail.** A use-case is a plain callable. CLI today, HTTP handler or queue
   consumer tomorrow — a thin adapter, no domain change.
4. **All I/O behind ports.** Filesystem, frame decoding, clock. This is what makes the thing testable
   without a 2 TB drive attached — and in practice the entire test suite runs in under a second.
5. **Configuration over code.** Camera rules, summary profiles, extension lists.

**One deliberate exception to rule 4:** the orchestrator arranges files on disk directly rather than
behind a port. Arranging files on disk is what it is *for*, and pytest's `tmp_path` makes it testable
without one.

### 5.2 Repository layout — actual

```
meta-still/
├─ PROJECT.md
├─ README.md
├─ pyproject.toml
├─ .vscode/launch.json          # three F5 targets: pipeline, mapper, stills
├─ src/meta_still/
│  ├─ __main__.py               # BUILT  the project entry: py -m meta_still
│  ├─ core/                     # shared kernel — the only cross-module dependency
│  │  ├─ errors.py              #   MetaStillError, UnreadableVideo
│  │  ├─ domain/
│  │  │  ├─ tree.py             #   DirectoryNode, FileNode, TreeScan, iter_files()
│  │  │  ├─ media.py            #   VIDEO_EXTENSIONS, is_video()
│  │  │  ├─ ignore.py           #   AppleDouble / OS junk rules
│  │  │  ├─ naming.py           #   safe_name() — Windows-safe path components
│  │  │  └─ structure.py        #   card plumbing collapsed out of output paths
│  │  ├─ ports/
│  │  │  ├─ filesystem.py       #   FileSystemPort
│  │  │  └─ frame_source.py     #   FrameSourcePort, VideoHandle
│  │  └─ interfaces/
│  │     ├─ prompt.py           #   ask() — shared by every composition root
│  │     └─ paths.py            #   label_for()
│  ├─ mapper/                   # A — BUILT
│  │  ├─ domain/                #   report.py, statistics.py, renderer.py
│  │  ├─ application/           #   scan_folder.py
│  │  ├─ infrastructure/        #   os_filesystem.py
│  │  ├─ interfaces/cli.py
│  │  └─ __main__.py
│  ├─ stills/                   # C — BUILT
│  │  ├─ domain/                #   sampling.py, naming.py
│  │  ├─ application/           #   generate_stills.py
│  │  ├─ infrastructure/        #   moviepy_frame_source.py
│  │  ├─ interfaces/cli.py
│  │  └─ __main__.py
│  ├─ orchestrator/             # BUILT
│  │  ├─ domain/                #   planning.py — where each clip's stills go
│  │  ├─ application/           #   ingest_folder.py
│  │  └─ interfaces/cli.py
│  ├─ metadata/                 # B — PLANNED
│  ├─ white_balance/            # D — PLANNED
│  └─ storage/                  # PLANNED  LocalFS + GoogleDrive adapters
└─ tests/unit/{core,mapper,stills,orchestrator}/
```

Each module directory is a candidate for extraction into its own deployable unit **without moving code
between layers** — that is the test of whether the boundary is real.

### 5.3 Concurrency — measured, not assumed

Everything is currently **single-threaded**, and that is a deliberate choice, not an omission.

Measured on real material: **~12 s for 5 stills from a 50 GB clip.** The cost is decoder startup and
seek, essentially independent of file size — ffmpeg seeks by keyframe index rather than reading through
the file. It scales with *N*, not with duration.

Extrapolated to the ABIMED drive (~150–170 real clips): **20–30 minutes, unattended.** Not a bottleneck.

When it becomes one, in order of preference:
1. **Skip what doesn't need doing** — classification (§12) removes `EXPORTS/` and the `._` twins, which
   is most of the runtime, for free.
2. **Swap the adapter** — direct ffmpeg with input seeking (`-ss` before `-i`) avoids moviepy restarting
   its decoder per seek; roughly 3–5×. The port makes this a ~40-line file and nothing else changes.
3. **Parallelise**, and only after measuring. Concurrent seeks on a USB *spinning* disk can thrash the
   heads and finish slower than sequential. On SSD it wins cleanly.

---

## 6. Data contracts

### 6.1 `<folder>_map.txt` (Module A) — **BUILT**

```
meta-still - folder map
============================================================
Root:     D:\ABIMED
Scanned:  2026-08-17 14:34:11
Folders:  345
Files:    987
Size:     1.7 TB
Ignored:  312 files, 0 folders  (._* AppleDouble, .DS_Store, system folders)

TREE
------------------------------------------------------------
D:\ABIMED  [987 files, 1.7 TB]
|-- CAMERAS/  [193 files, 912.3 GB]
|   `-- 2026_04_27/  [46 files, 193.7 GB]
...

EXTENSIONS
------------------------------------------------------------
.MP4                 318         1.6 TB
.WAV                 327        71.7 GB
...

UNREADABLE PATHS (0)
```

ASCII tree characters (`|--`, `` `-- ``), not Unicode box-drawing: Windows terminals and editors still
trip over `├──` depending on codepage. Sizes are decimal (1000-based), matching how drives and cameras
label capacity.

### 6.2 Output layout (Orchestrator) — **BUILT**

The source structure is mirrored, **card plumbing is collapsed out**, and **each clip gets its own
folder**:

```
D:\ABIMED\CAMERAS\2026_04_27\FX3_B\M4ROOT\CLIP\20260427_B3301.MP4      source
                              └──────────────┘ collapsed away

OUTPUT/
├─ ABIMED_map.txt
├─ CAMERAS/2026_04_27/FX3_B/
│  ├─ 20260427_B3301/
│  │  ├─ 20260427_B3301_thumb_1.png
│  │  └─ … (5 total)
│  └─ 20260427_B3302/
└─ MEDIAS/2025_12_10/Episodio/Câmeras separadas/
   └─ MultiCorder1 - Camera 4 - 10 dezembro 2025 - 10-59-15/
      └─ …
```

Folders are created **only where videos actually live** — an `AUDIO/` folder in the source is not
mirrored. Every path component is passed through `safe_name()` (§6.4).

#### Structural folders (`core/domain/structure.py`)

A Sony card writes `FX3_B/M4ROOT/CLIP/C2663.MP4`. `M4ROOT` and `CLIP` are fixed plumbing the camera
creates on every card — they say nothing about the shoot, and reproducing them buries the clip two
levels deeper for no gain. Collapsed:

`M4ROOT`, `CLIP`, `SUB` (Sony XAVC-S) · `XDROOT` (XDCAM) · `DCIM`, `AVCHD`, `BDMV`, `STREAM` (consumer)

**Deliberately excluded: `VIDEO`, `AUDIO`, `CONTENTS`** (Panasonic P2). They are ordinary folder names
that appear in hand-made structures too — this drive has a `CAMERAS/<date>/AUDIO/` that means something.
Collapsing on a generic name risks silently merging folders a person created on purpose. If P2 material
arrives, they need a structural guard, not a name match.

**Not collapsed:** `Video ISO Files/` (Resolve's multicam export convention). It distinguishes the ISO
recordings from the program file one level up, so it carries meaning that card plumbing does not.

#### Collision handling

Collapsing can make two clips claim one folder — `CLIP/C2046.MP4` and `SUB/C2046.MP4` both want
`FX3_C/C2046`, and the second would **silently overwrite** the first's thumbnails. So collapsed paths
are counted first, and **any clip whose folder is contested keeps its full path**:

```
FX3_C/M4ROOT/CLIP/C2046/   <- contested, full path kept
FX3_C/M4ROOT/SUB/C2046/    <- contested, full path kept
FX3_C/C2047/               <- uncontested, still collapsed
```

Only the colliding clips pay for it, and the outcome depends solely on the input — so a resumed run
plans identically and the skip check still finds its folders.

### 6.3 Ignore rules — **BUILT**

Applied during the scan, so map, counts and created folders agree. Counts are **reported, not hidden**:
numbers that do not add up are worse than numbers that are large.

| Pattern | Why |
|---|---|
| `._*` | AppleDouble resource forks. A Mac touched this material, so nearly every real file has a 4 KB twin **carrying the same extension** — which would otherwise be counted as a clip, given a folder, and handed to ffmpeg to fail on. |
| `.DS_Store`, `Thumbs.db`, `desktop.ini` | OS folder metadata |
| `$RECYCLE.BIN`, `System Volume Information`, `.Spotlight-V100`, `.Trashes`, `.fseventsd`, `.TemporaryItems` | system folders |

### 6.4 `safe_name()` — Windows path safety — **BUILT**

Source names come from cameras, recorders and editors, none of which promise anything about Windows
path rules. MultiCorder ends **every** filename with a space (`… 10-22-47 .mp4`).

Windows strips trailing spaces and dots from the *last* component of a path, but not from the middle.
That produces a failure that hides itself:

| Call | `clip ` is… | Result |
|---|---|---|
| `mkdir("…\clip ")` | last component → stripped | creates `clip`, **without** the space |
| `is_dir("…\clip ")` | last component → stripped | **True** — agrees it worked |
| `open("…\clip \thumb.png")` | now a middle component → **not** stripped | `ENOENT` |

Three calls, three different ideas of what the name is. Hence:

| Input | Output |
|---|---|
| `MultiCorder5 - … - 10-22-47 ` | `MultiCorder5 - … - 10-22-47` |
| `clip.`, `clip..` | `clip` |
| `CON`, `NUL`, `COM1`, `LPT9` (any extension) | `CON_`, `NUL_`, … |
| `clip:1?"` | `clip_1__` |
| `"   "`, `"..."` | `unnamed` |

Interior spaces and accents are preserved. **This is Windows-only** — the same names are legal on Linux
and macOS, so this code would pass in a container and fail on the workstation.

*Known limitation:* sanitising is one-directional. `clip .mp4` and `clip.mp4` in one folder would both
claim the folder `clip`. Not present in this material; not solved until it appears.

### 6.5 `inventory.json` (Module A) — PLANNED

The machine-readable contract every later module reads.

```json
{
  "schema_version": "1.0",
  "run_id": "2026-08-17T14-03-11Z_VOLUME",
  "volume": { "label": "ABIMED", "mount_path": "D:\\", "total_bytes": 0 },
  "clips": [
    {
      "clip_id": "a1b2c3…",
      "relative_path": "CAMERAS/2026_04_27/FX3_B/M4ROOT/CLIP/20260427_B3301.MP4",
      "size_bytes": 65066795827,
      "extension": ".MP4",
      "zone": "rushes",
      "camera": { "label": "FX3_B", "confidence": 0.95, "rule": "**/FX3_B/**" }
    }
  ],
  "ignored_files": 312,
  "warnings": []
}
```

`clip_id` = stable hash of `(relative_path, size_bytes)` — stable across runs and machines, which is
what makes resume and cloud hand-off work. Not the absolute path: drive letters move.

### 6.6 `clips/<clip_id>.json` (Module B) — PLANNED

```json
{
  "schema_version": "1.0",
  "clip_id": "a1b2c3…",
  "media": {
    "container": "mp4", "duration_s": 0.0, "fps": 23.976,
    "timecode_start": "10:21:33:04", "width": 3840, "height": 2160,
    "codec": "xavc", "bit_depth": 10, "chroma": "4:2:2",
    "color_primaries": "bt2020", "gamma_note": "S-Log3",
    "audio": [ { "channels": 2, "sample_rate": 48000, "codec": "pcm_s24le" } ]
  },
  "stills": [ { "index": 1, "timestamp_s": 12.5, "path": "…/clip_thumb_1.png" } ],
  "white_balance": null,
  "vendor": { "ffprobe": { } },
  "errors": []
}
```

`stills` and `white_balance` start empty and are filled by C and D. This is how B stays decoupled from
them: it defines the slot, they fill it, nobody imports anybody.

---

## 7. Process flow

### 7.1 Today — **BUILT**

```
   [folder or drive]
          │
          ▼
   ┌──────────────┐
   │  A. Mapper   │────────────────▶  <folder>_map.txt
   └──────────────┘
          │  tree
          ▼
   ┌──────────────────────────────┐
   │  Orchestrator                │  mirror path, folder per clip,
   │  sequential, failure-isolated│  skip clips already done
   └──────────────────────────────┘
          │  one video at a time
          ▼
   ┌──────────────┐
   │  C. Stills   │────────────────▶  <clip>/<clip>_thumb_N.png
   └──────────────┘
```

```
Mapped 5 files -> src_map.txt
7 video files to process
[   1/7] 20260427_B3301.MP4  - 5 stills in 11.8s
[   2/7] BROKEN.MP4  - FAILED: Error opening input files: Invalid data found
...
Done in 1.4 min - C:\…\out
  processed: 6
  skipped:   0 (already had thumbnails)
  failed:    1
```

### 7.2 Target — PLANNED

Classification narrows the work-list before any decoding; B runs beside C per clip; D consumes C's
output per clip; the summary is rendered from the merged JSONs and everything is uploaded.

```
A ─▶ inventory.json ─▶ fan-out over clips ─┬─▶ B. Metadata ─┐
                                            └─▶ C. Stills ──┴─▶ D. WB ─▶ clips/*.json
                                                                            │
                                                        summary.{csv,html} ─┴─▶ Google Drive
```

B and C are independent per clip. D depends on C **for that clip only**, not on the whole stills stage
finishing — no global barriers: clip 160 must not wait on clip 1.

### 7.3 Operator journey

Three F5 targets in `.vscode/launch.json`, each prompting for its paths in the integrated terminal
(`"console": "integratedTerminal"` is required — `input()` cannot read from the debug console):

| Target | Equivalent | Purpose |
|---|---|---|
| meta-still (full pipeline) | `py -m meta_still` | map + thumbnails |
| Mapper only | `py -m meta_still.mapper` | fast answer: what is on this drive? |
| Stills only (one video) | `py -m meta_still.stills` | one clip, for debugging |

Arguments still work (`py -m meta_still "D:\ABIMED" -o C:\out -n 5 --force`) — that path exists so a
scheduler or queue worker can call the same entry point later.

Pasted paths are cleaned: quotes from "Copy as path" are stripped, and so are invisible characters —
the BOM and the U+202A directional mark that the Windows Properties dialog silently prepends. Without
that, a pasted path fails with an error message that looks perfectly correct on screen.

---

## 8. Tech stack

| Concern | Choice | Status | Rationale |
|---|---|---|---|
| Language | **Python 3.14** (floor 3.12) | in use | 3.14.7 in `.venv`; floor left at 3.12 to keep container images flexible |
| Packaging | `pyproject.toml`, setuptools, src layout | in use | `pip install -e ".[dev]"` |
| CLI | **argparse** (stdlib) | in use | zero dependencies while each module has one command; **Typer** when that stops being true |
| Frame extraction | **moviepy 2.1** + **Pillow 11** | in use | reuses working code; `get_frame` → Pillow gives control of format and size |
| Media metadata | **ffprobe** (+ optional MediaInfo) | planned | `C:\ffmpeg\bin` already present |
| Models/validation | **Pydantic v2** | planned | when §6.5/6.6 JSON contracts arrive |
| Config | **YAML** + Pydantic Settings | planned | operator-editable camera rules |
| Drive | `google-api-python-client` + service account | planned | headless-friendly; no OAuth dance in cloud |
| Logging | `print` → **structlog** | planned | JSON in cloud |
| Tests | **pytest** | in use | 49 tests, <1 s, no media decoded |
| Lint/format | **ruff** + **mypy** | planned | enforce layer boundaries mechanically |

Dependencies are added **per module, when that module needs them** — not up front.

**External binaries** (FFmpeg/ffprobe) are a real deployment constraint and drive the hosting decision
in §9 — a plain serverless function will not do.

---

## 9. Phases & deployment

### Phase 1 — Local (current)

Monorepo, single process, CLI, local filesystem. Everything runs on the ingest workstation with the
drive attached. **This is where the modules earn their boundaries.**

### Phase 2 — Cloud

The upstream stages are physically bound to the drive; the downstream ones are not:

- **On-prem/local agent:** A (mapper) and frame extraction — must be where the media is. Uploads stills
  and inventory.
- **Cloud services:** B (summary consolidation), D (white balance), storage orchestration, and any
  future AI enrichment. These take small inputs (JSON, PNGs) and are trivially horizontal.

**Hosting reality check:** FFmpeg-dependent services need a container. Heroku (container stack) or a
container host (Cloud Run / Fly / Render) fits; Vercel functions do not — that lane is for a future web
UI, not for the media workers.

**Django is deliberately not scaffolded.** The v1 is a terminal program; Django's ORM, migrations,
admin and request/response cycle solve problems this project does not have, and the gravitational pull
toward making `Clip` a `models.Model` would invert the dependency direction that makes the rest of this
document work. The decision that actually matters is deferred to Phase 2:

- *Internal tool with a dashboard* → FastAPI + a job queue (arq/RQ) + Postgres.
- *Multi-tenant SaaS* (accounts, orgs, permissions, billing, a non-technical admin) → **Django wins**;
  auth, admin and migrations save months.

The pipeline is long-running and drive-bound, so the web layer will be thin either way — submit a job,
poll status, browse results. Jobs need a queue and workers regardless of framework.

Readiness work carried in Phase 1, at no extra cost:
- Use-cases take dependencies by injection — swapping `LocalFS` for object storage is a wiring change.
- Every stage is a `input artifact → output artifact` function, so it can become a queue consumer.
- No shared mutable state between clips.
- Repository ports before persistence exists, so "JSON files on disk" → Postgres is one new class
  rather than a change to every module.

### Branch strategy

`dev` (current, active development) → `stage` (integration, real drives) → `main`/`prod` (tagged
releases). Feature work branches off `dev`. Contracts in §6 are the compatibility boundary.

> **Note:** branches are managed through **GitHub Desktop**; `git` is not on PATH on the dev
> workstation. Fine for the current workflow — worth knowing when CI, hooks or any tooling that shells
> out to `git` arrives.

---

## 10. Configuration & secrets

`.env` is **never committed**. `.env.example` documents the keys.

| Key | Purpose | Status |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to (or inline) service-account credentials | planned |
| `GDRIVE_FOLDER_ID` | Destination folder id | planned |
| `META_STILL_WORK_DIR` | Default output directory | planned |
| `META_STILL_WORKERS` | Concurrency | planned |
| `FFMPEG_PATH` / `FFPROBE_PATH` | Override binary discovery (Windows) | planned |
| `LOG_LEVEL` | `INFO` default | planned |

`.env` is correctly ignored by `.gitignore:151` (standard Python template, "Environments" block).
Keep it that way — a secret committed once stays in git history permanently, and rewriting history to
remove it is expensive and unreliable. `.env.example` is the committed counterpart: same keys, no values.

> **Housekeeping.** The current `.env` carries keys from an unrelated template (`OPENAI_API_KEY`,
> `SERPER_API_KEY`, `XAI_API_KEY`, `ELEVENLABS_API_KEY`, `OLLAMA_API_KEY`). None are used by
> meta-still. Delete them and replace with the table above.

---

## 11. Testing strategy

**56 tests, under one second, no media decoded.** That is the payoff of the ports: `FileSystemPort` and
`FrameSourcePort` mean the interesting logic never needs a drive or a video file.

| Area | What it proves | Needs media? |
|---|---|---|
| `core` — naming | trailing spaces, dots, reserved device names, illegal characters | No |
| `mapper` — renderer/statistics | tree totals, extension grouping, unreadable-path reporting | No |
| `mapper` — CLI | pasted-path cleaning, folder-as-output, extensionless output | No |
| `stills` — sampling/naming | spacing avoids both ends, index padding, unusable duration rejected | No |
| `stills` — use-case | **decoder released even when a frame read fails** | No (fake port) |
| `orchestrator` — planning | card plumbing collapsed, meaningful folders kept, **name collisions never overwrite**, determinism across runs | No |
| `orchestrator` — pipeline | mirrored structure, `._` never processed, **failure isolation**, **resume**, `--force`, trailing-space clip names | No (fake port) |
| Manual E2E | real 4K clips + a deliberately corrupt MP4 + a `CON.mp4` | Yes |

The three hard constraints in §2 map directly to the tests shown in bold.

**Planned:** integration tests against checked-in fixture media (asserting no LUT is applied), contract
tests validating emitted JSON against its schema version, and `ruff`/`mypy` in CI.

---

## 12. Open decisions

### Deferred by choice

1. **Classification and camera rules.** Designed, not built. The drive needs three matchers, because it
   uses three conventions:

   | Structure | Example | Camera comes from |
   |---|---|---|
   | Camera card | `CAMERAS/2026_04_27/FX3_B/M4ROOT/CLIP/20260427_B3301.MP4` | **folder** → `FX3_B` |
   | Multicam ISO | `MEDIAS/…/Video ISO Files/ABIMED_PGM007_20260427 CAM 1.mp4` | **filename suffix** → `CAM 1` |
   | MultiCorder | `MEDIAS/2025_12_10/…/MultiCorder1 - Camera 4 - ….mp4` | **filename**, different pattern |

   So the engine needs **both path globs and filename regexes**, ordered, first match wins, each result
   carrying the rule that produced it so a wrong label is auditable. Rules in `config/rules.yaml`.

   Plus **zones** — `CAMERAS/` rushes, `MEDIAS/` session, `EXPORTS/` deliverable, `PROJETO/` `ARTES/`
   `TRILHAS/` non-footage — which decide what Module C opens at all.

2. **Open question blocking camera rules:** `2026_04_27` appears in **both** `CAMERAS/` (FX3_A/B/C card
   copies) and `MEDIAS/` (CAM 1–4 ISOs). Are these the same physical cameras recorded two ways? If yes,
   `FX3_A` and `CAM 1` should resolve to one canonical camera and the summary can pair them. Cannot be
   inferred from the tree.

3. **Metadata extractor:** ffprobe alone, or ffprobe + MediaInfo for descriptors ffprobe misses?
4. **Summary output format(s):** CSV/XLSX for editorial, HTML contact sheet for the client, JSON as
   source of truth. Which ship in v1?
5. **Drive layout:** one folder per volume, or a date/project hierarchy? Stills individually or archived?

### Settled

| Decision | Outcome | Reasoning |
|---|---|---|
| Still format | **PNG at 1920 long edge** | full-res 4K PNG is ~16–40 GB for this drive; JPG is lossy input for a colour *measurement*. Both configurable. |
| Output layout | **mirror tree + folder per clip** | nothing mixed; scales if *N* rises |
| Card plumbing | **`M4ROOT`/`CLIP`/… collapsed** out of output paths | they describe the camera, not the shoot |
| Name collisions | **contested clips keep their full path** | silently overwriting a clip's stills is the worst outcome available |
| Sampling | **`duration / (N + 1)`**, N=5 | avoids slates and tails |
| Stills colour | **left log, no LUT** | a display transform would make Module D meaningless |
| `map.txt` format | **annotated**, ASCII | "how much is in there" is the first question anyone asks a map |
| `._*` handling | **skipped at scan level**, count reported | one fix for both the inflated clip count and the junk folders |

---

## 13. Observations from the real material

Things the data taught us that no amount of design would have.

- **Camera clocks lie.** `20210221_A0009.MP4` and `20210225_A0010.MP4` sit in 2026 shoot folders — the
  camera's clock was wrong. **Module B must take dates from metadata, never from filenames.**
- **CAM 4 is broken.** Across *every* shoot date, `CAM 4` ISO files are 76–95 MB against 22–28 GB for
  CAM 1–3. That camera's ISO recording has been failing for months. Exactly the kind of thing a summary
  exists to surface.
- **`Video ISO Files/` and `Audio Source Files/`** are DaVinci Resolve's multicam export structure,
  paired with `.drp` project files — a recognisable layout worth a structural rule later.
- **Encoding:** names like `Câmeras separadas` appear as `CÃ¢meras` if `map.txt` is opened as Latin-1.
  The file is written UTF-8; check the editor's encoding indicator before suspecting the data.

---

## 14. Working agreement

- Build **module by module**. A and C are done; the orchestrator joins them. B and D follow.
- **Discuss before writing code.** Each module starts with a short design note (contract, ports, file
  list) agreed in conversation, then implementation.
- **Each module keeps its own `__main__.py`** — a module you cannot run alone is not a module. The
  composition root stays thin: parse, wire, call, render. Any logic in it means the boundary has leaked.
- Manual runs are for debugging, **not** for testing. Tests are pytest against use-cases with fake
  ports; they run in CI, manual runs do not.
- Contracts (§6) change only by explicit agreement; this document is updated in the same change.

---

*Last updated: 2026-08-17*
