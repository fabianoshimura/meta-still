# meta-still — Project Reference

> Living reference document. Every architectural decision, contract and roadmap item lands here first,
> then in code. If code and this document disagree, this document is wrong — fix it in the same PR.

---

## 1. Mission

**meta-still** is a post-production ingest toolchain. Given an external drive (USB HD) full of camera
rushes, it produces a machine-readable and human-readable **summary** of the footage: what was shot,
by which camera, with which technical parameters, plus representative **thumbnails (stills)** for each
clip — and delivers the whole package to a shared **Google Drive** folder.

The primary media format is **MXF** (Sony/broadcast wrapper), with other video containers supported
opportunistically.

### Why it exists

After a shoot, the post team receives drives with thousands of clips spread over camera-specific folder
trees (`FX6`, `FX3`, drone units, …). Before editorial starts, someone must answer: *what is on this
drive, how much of it, in what codec/framerate/colour space, and what does it look like?* Today that is
manual. meta-still automates it.

---

## 2. Scope

### In scope (v1)

| # | Feature | Module |
|---|---------|--------|
| 1 | Walk a mounted drive, build a tree (`pstree`-like) of the volume, identify video files (esp. `.MXF`) | **A — Mapper** |
| 2 | Extract technical metadata per video file → one JSON per clip | **B — Metadata** |
| 3 | Generate *N* thumbnails per clip (*N* configurable) as PNG | **C — Stills** |
| 4 | Upload artifacts (JSONs, stills, map, summary) to a Google Drive folder | **Storage adapter** |
| 5 | Compute white balance of still images | **D — White Balance** |
| 6 | Render a consolidated summary from the per-clip JSONs | **B — Metadata** |

### Out of scope (explicitly, for now)

- Transcoding / proxy generation (only frame extraction).
- NLE project file generation (XML/AAF/EDL) — a plausible v2 module.
- Editing or writing back to the source media. **The source drive is read-only, always.**
- Face/object recognition, transcription, LLM-based content description — possible v2 modules; the
  architecture must not preclude them.

### Hard constraints

1. **Never write to the source volume.** All output goes to a separate work directory.
2. **Idempotent & resumable.** Re-running over a partially processed drive must skip completed work,
   not redo or duplicate it. Drives get unplugged mid-run; that is normal, not an error.
3. **Fail per-clip, not per-run.** One corrupt file must not abort a 4000-clip ingest.

---

## 3. Glossary

| Term | Meaning |
|------|---------|
| **Volume** | A mounted drive being ingested. Identified by label + serial, not by drive letter (`D:` is not stable). |
| **Clip** | One video file. The atomic unit of work. |
| **Card / Reel** | A camera card folder structure (e.g. `XDROOT/`, `PRIVATE/M4ROOT/`) inside a volume. |
| **Camera label** | The device that shot the clip (`FX6`, `FX3`, `Mavic-3`, …), inferred from the folder tree. |
| **Still / Thumbnail** | A PNG extracted from a clip at a given timestamp. |
| **Artifact** | Any file meta-still produces: clip JSON, still, map, summary. |
| **Run** | One execution of the pipeline over one volume, with an id and a manifest. |

---

## 4. Modules

Four functional modules plus shared infrastructure. Each module is **independently runnable, testable
and deployable** — that is the microservice-readiness requirement.

### A) Video-Files Mapper

**Responsibility.** Walk the volume, classify files, infer camera labels from the directory structure,
emit a tree map.

- **Input:** a mount path + scan config (extensions, ignore patterns, follow symlinks, max depth).
- **Output:**
  - `map.txt` — human-readable tree (`pstree`/`tree`-style), the artifact you asked for.
  - `inventory.json` — machine-readable list of discovered clips (the contract every other module reads).
- **Camera-label inference.** A rule table maps path patterns → camera label:
  ```
  **/FX6*/**        -> FX6
  **/FX3*/**        -> FX3
  **/*MAVIC*/**     -> Mavic
  XDROOT/**         -> Sony-XDCAM (family hint)
  ```
  Rules live in **config, not code** (`config/cameras.yaml`), so the operator adds a camera without a
  release. Each label carries a `confidence` and the `rule` that matched, so a wrong guess is auditable.
- **Non-goal:** it does not open media files. Filesystem metadata only — this keeps a full-drive scan
  fast (seconds, not hours) and gives the operator an early answer.

### B) Metadata-Summary

**Responsibility.** Extract technical metadata per clip; consolidate many clip JSONs into one summary.

Two distinct use cases, one module:
- `extract(clip) -> ClipMetadata` — one JSON per clip.
- `summarize(clips[], profile) -> Summary` — selected fields, grouped/aggregated, rendered.

- **Extraction backend:** an *ExtractorPort* with pluggable adapters (ffprobe / MediaInfo / both). The
  domain never sees a vendor payload shape; adapters normalize into `ClipMetadata` and stash the raw
  vendor blob under `vendor.*` for forensics.
- **Summary profiles** define *which* fields appear and how rows are grouped (by camera, by shooting
  day, by card). Profiles are config, not code.
- **Extension point:** the summary may enrich itself with white-balance data produced by **D**, which is
  computed on stills produced by **C**. That is a *pull* over the artifact contracts — B does not import
  C or D. See §6.

### C) Stills-Generator

**Responsibility.** Produce *N* PNG thumbnails per clip.

- **Sampling strategies** (configurable): `evenly-spaced` (default), `first-frame`, `at-timecodes`,
  `scene-change` (v2).
- **Params:** `N`, output resolution / long-edge, PNG bit depth, whether to burn timecode.
- **Output:** `stills/<clip_id>/<index>_<timestamp>.png` + a `stills.json` index per clip.
- **Colour caveat that matters for D:** frame extraction must not apply a display transform (no LUT, no
  tone-mapping) or white balance measurements become meaningless. Log-encoded footage (S-Log3) stays
  log. This is a **hard requirement on the extractor adapter**, and a test asserts it.

### D) White-Balance

**Responsibility.** Given an image, estimate its white balance / colour cast.

- **Input:** a PNG path (from C, or any image).
- **Output:** `{ estimated_temp_k, tint, rgb_gains, method, confidence, sample_region }`.
- **Methods** behind one port: `gray-world` (baseline), `white-patch/retinex`, `percentile-gray`.
  Start with gray-world; it is trivial and honest about its assumptions.
- Deliberately generic: it knows about *images*, not about MXF or cameras. It is the most reusable
  module and the easiest to run as a standalone service.

### Shared infrastructure (not a feature module)

- **Storage adapter** — `StoragePort` with a `LocalFileSystem` adapter and a `GoogleDrive` adapter
  (service account, folder id + credentials from environment). Resumable uploads, retry with backoff,
  per-file checksum verification.
- **Run/Manifest service** — assigns run ids, tracks per-clip state (`pending → done | failed`), enables
  resume.
- **Orchestrator** — composes modules into the pipeline. Locally: an in-process runner. In cloud: a
  queue-driven worker. Same use-cases either way.

---

## 5. Architecture

### 5.1 Principles

1. **Clean / hexagonal architecture per module.** Dependencies point inward:
   `interfaces → application → domain`, and `infrastructure` implements ports defined by `domain`.
   The domain imports nothing from the outside world — no ffmpeg, no Google SDK, no filesystem.
2. **Modules talk through contracts, never through imports.** Module B does not `import` module C.
   They share only `core` (entities + ports) and the on-disk/on-wire artifact schemas.
3. **The transport is a detail.** A use-case is a plain callable. CLI today, HTTP handler or queue
   consumer tomorrow — a thin adapter, no domain change.
4. **All I/O behind ports.** Filesystem, ffprobe, Drive, clock, id generation. This is what makes the
   thing testable without a 2TB drive attached.
5. **Configuration over code.** Camera rules, summary profiles, sampling strategies, extension lists.

### 5.2 Repository layout (proposed)

```
meta-still/
├─ PROJECT.md
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ config/
│  ├─ cameras.yaml            # path-pattern → camera label rules
│  ├─ summary_profiles.yaml   # which fields, how grouped
│  └─ default.yaml            # pipeline defaults (N stills, extensions, concurrency)
├─ src/meta_still/
│  ├─ core/                   # shared kernel — the ONLY cross-module dependency
│  │  ├─ domain/              # Volume, Clip, ClipMetadata, Still, WhiteBalance, RunManifest
│  │  ├─ ports/               # StoragePort, ExtractorPort, FrameSourcePort, ClockPort, EventBus
│  │  └─ errors.py
│  ├─ mapper/                 # A
│  │  ├─ domain/  application/  infrastructure/  interfaces/
│  ├─ metadata/               # B  (same 4-layer shape)
│  ├─ stills/                 # C
│  ├─ white_balance/          # D
│  ├─ storage/                # LocalFS + GoogleDrive adapters
│  ├─ orchestrator/           # pipeline composition, run manifest, resume logic
│  └─ cli/                    # Typer app: the v1 user interface
└─ tests/
   ├─ unit/                   # domain + application, no I/O
   ├─ integration/            # real ffprobe against small fixture media
   └─ fixtures/               # tiny sample MXF/MOV + expected JSON
```

Each module directory is a candidate for extraction into its own deployable unit **without moving code
between layers** — that is the test of whether the boundary is real.

### 5.3 Concurrency

- Mapping: single-threaded walk (I/O bound on directory reads, parallelism rarely helps on spinning USB).
- Metadata + stills: a bounded worker pool. **Default `workers = 4`, configurable.** USB 3 HDDs saturate
  early; unbounded parallelism makes ingest *slower*. Measure before tuning.
- Uploads: separate pool, since it is network-bound, not disk-bound.

---

## 6. Data contracts

The contracts are the API. Everything is versioned with `schema_version` — a breaking change bumps the
major and ships a migration note here.

### `inventory.json` (Module A → everyone)

```json
{
  "schema_version": "1.0",
  "run_id": "2026-08-17T14-03-11Z_VOLSERIAL",
  "volume": { "label": "SHOOT_DAY_03", "serial": "…", "mount_path": "D:\\", "total_bytes": 0 },
  "scanned_at": "2026-08-17T14:03:11Z",
  "clips": [
    {
      "clip_id": "a1b2c3…",
      "relative_path": "FX6_A/XDROOT/Clip/C0021.MXF",
      "size_bytes": 4823400448,
      "mtime": "2026-08-14T09:21:03Z",
      "extension": ".MXF",
      "camera": { "label": "FX6", "confidence": 0.95, "rule": "**/FX6*/**" }
    }
  ],
  "non_video_files": 128,
  "warnings": []
}
```

`clip_id` = stable hash of `(relative_path, size_bytes)`. Stable across runs and across machines —
which is what makes resume and cloud hand-off work. Not the absolute path: drive letters move.

### `clips/<clip_id>.json` (Module B)

```json
{
  "schema_version": "1.0",
  "clip_id": "a1b2c3…",
  "source": { "relative_path": "…", "size_bytes": 0 },
  "camera": { "label": "FX6", "confidence": 0.95 },
  "media": {
    "container": "mxf", "duration_s": 0.0, "fps": 23.976,
    "timecode_start": "10:21:33:04", "width": 3840, "height": 2160,
    "codec": "xavc", "bit_depth": 10, "chroma": "4:2:2",
    "color_primaries": "bt2020", "transfer": "arib-std-b67", "gamma_note": "S-Log3",
    "audio": [ { "channels": 2, "sample_rate": 48000, "codec": "pcm_s24le" } ]
  },
  "stills": [ { "index": 0, "timestamp_s": 12.5, "path": "stills/a1b2c3…/000_12.500.png" } ],
  "white_balance": null,
  "vendor": { "ffprobe": { } },
  "errors": []
}
```

`stills` and `white_balance` start `null`/empty and are filled by C and D. This is how B stays
decoupled from them: it defines the slot, they fill it, nobody imports anybody.

### `manifest.json` (Orchestrator)

Per-run state: `clip_id → { mapped, extracted, stills, wb, uploaded }` with timestamps and error
strings. This file *is* the resume mechanism.

---

## 7. Process flow

```
   [USB HD mounted]
          │
          ▼
   ┌──────────────┐   inventory.json
   │  A. Mapper   │──────────────┐        map.txt (human)
   └──────────────┘              │
                                 ▼
                    ┌────────────────────────┐   per-clip, parallel, failure-isolated
                    │  fan-out over clips    │
                    └────────────────────────┘
                         │              │
                         ▼              ▼
                 ┌─────────────┐  ┌──────────────┐
                 │ B. Metadata │  │  C. Stills   │
                 └─────────────┘  └──────────────┘
                         │              │
                         │              ▼
                         │        ┌──────────────┐
                         │        │ D. White Bal │
                         │        └──────────────┘
                         │              │
                         └──────┬───────┘
                                ▼
                     clips/<clip_id>.json  (merged)
                                │
                                ▼
                    ┌────────────────────────┐
                    │  B. Summary renderer   │  summary.{csv,html,json}
                    └────────────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  Storage: Google Drive │
                    └────────────────────────┘
```

B and C are independent per clip and run concurrently. D depends on C for that clip only — not on the
whole stills stage finishing. No global barriers: clip 4000 must not wait on clip 1.

### Operator journey (v1, CLI)

```bash
meta-still scan D:\ --out ./work                     # A only — fast answer: what is on this drive?
meta-still ingest D:\ --out ./work --stills 5        # A → B → C → D → summary
meta-still upload ./work --drive-folder <FOLDER_ID>  # push artifacts
meta-still ingest D:\ --out ./work --resume          # after the drive was unplugged
```

Progress is per-stage with counts and an ETA; failures print a per-clip table at the end and land in
`manifest.json`. Exit code is non-zero only if the *run* failed, not if individual clips did.

---

## 8. Tech stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Your call; strong media/image ecosystem. |
| Packaging | `pyproject.toml`, `uv` or `pip-tools` | Reproducible envs, cloud-friendly. |
| CLI | **Typer** | Type-hint driven, minimal boilerplate. |
| Models/validation | **Pydantic v2** | Contracts in §6 become real, validated types; free JSON Schema. |
| Media metadata | **ffprobe** (+ optional MediaInfo adapter) | One binary for metadata *and* frames. |
| Frame extraction | **FFmpeg** | Industry standard for MXF/XAVC. |
| Imaging | **Pillow** + **NumPy** | White-balance math needs arrays. |
| Config | **YAML** + Pydantic Settings | Operator-editable rules. |
| Drive | `google-api-python-client` + service account | Headless/server-friendly; no OAuth dance in cloud. |
| Logging | **structlog**, JSON in cloud | Grep-able per-clip events. |
| Tests | **pytest** | Fixture media checked in, kept tiny. |
| Lint/format | **ruff** + **mypy** | Enforce the layer boundaries mechanically. |

**External binaries** (FFmpeg/ffprobe) are a real deployment constraint and drive the hosting decision
in §9 — a plain serverless function will not do.

---

## 9. Phases & deployment

### Phase 1 — Local (current)

Monorepo, single process, CLI, local filesystem + Google Drive upload. Everything runs on the ingest
workstation with the drive physically attached. **This is where the modules earn their boundaries.**

### Phase 2 — Cloud

The upstream stages are physically bound to the drive; the downstream ones are not. The split:

- **On-prem/local agent:** A (mapper) and frame extraction — must be where the media is. Uploads
  stills + inventory.
- **Cloud services:** B (summary consolidation), D (white balance), storage orchestration, and any
  future AI enrichment. These take small inputs (JSON, PNGs) and are trivially horizontal.

**Hosting reality check:** FFmpeg-dependent services need a container. Heroku (container stack) or a
container host (Cloud Run / Fly / Render) fits; Vercel functions do not — that lane is for a future
web UI, not for the media workers.

Readiness work carried in Phase 1, at no extra cost:
- Artifacts addressed by **URI**, not path (`file://…` now, `drive://…`/`gs://…` later).
- Use-cases take dependencies by injection — swapping `LocalFS` for object storage is a wiring change.
- Every stage is a pure `input artifact → output artifact` function, so it can become a queue consumer.
- No shared mutable state between clips.

### Branch strategy

`dev` (current, active development) → `stage` (integration, real drives, real Drive folder) →
`main`/`prod` (tagged releases). Feature work branches off `dev`. Contracts in §6 are the compatibility
boundary between branches.

---

## 10. Configuration & secrets

`.env` is **never committed**. `.env.example` documents the keys.

| Key | Purpose |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to (or inline) service-account credentials |
| `GDRIVE_FOLDER_ID` | Destination folder id |
| `META_STILL_WORK_DIR` | Default output directory |
| `META_STILL_WORKERS` | Concurrency |
| `FFMPEG_PATH` / `FFPROBE_PATH` | Override binary discovery (Windows) |
| `LOG_LEVEL` | `INFO` default |

`.env` is correctly ignored by `.gitignore:151` (standard Python template, "Environments" block).
Keep it that way — a secret committed once stays in git history permanently, and rewriting history to
remove it is expensive and unreliable. `.env.example` is the committed counterpart: same keys, no values.

> **Housekeeping.** The current `.env` carries keys from an unrelated template (`OPENAI_API_KEY`,
> `SERPER_API_KEY`, `XAI_API_KEY`, `ELEVENLABS_API_KEY`, `OLLAMA_API_KEY`). None are used by
> meta-still. Delete them and replace with the table above.

---

## 11. Testing strategy

| Layer | What it proves | Needs media? |
|---|---|---|
| Unit — domain | camera-rule matching, clip_id stability, WB math on synthetic swatches | No |
| Unit — application | orchestration order, resume logic, failure isolation (fake ports) | No |
| Integration | ffprobe adapter against checked-in fixture clips; still extraction applies no LUT | Tiny fixtures |
| Contract | every emitted JSON validates against its schema version | No |
| E2E (manual) | a real drive, a real Drive folder, before each `stage` merge | Yes |

The failure-isolation and resume behaviours from §2 are **tested requirements**, not aspirations.

---

## 12. Open decisions

To settle before/while building the relevant module — not blockers for module A.

1. **Summary output format(s):** CSV/XLSX for editorial, HTML contact sheet for the client, JSON as
   source of truth. Which ship in v1?
2. **Metadata extractor:** ffprobe alone, or ffprobe + MediaInfo for broadcast descriptors (UMID, camera
   serial, lens data) that ffprobe misses on MXF?
3. **Thumbnail sampling default:** evenly-spaced across duration vs. fixed offsets. And *N* default — 3? 5?
4. **Stills for white balance:** WB on the delivered thumbnails, or on a separate unprocessed sample?
   (Related: whether stills are colour-managed for viewing or left log.)
5. **Drive layout:** one folder per volume, or a date/project hierarchy? Do stills go up individually or
   as an archive?
6. **`map.txt` format:** literal `tree`-style ASCII, or annotated with per-folder clip counts and sizes?

---

## 13. Working agreement

- Build **module by module**, A → B → C → D, with the storage adapter introduced when A has something
  worth uploading.
- **Discuss before writing code.** Each module starts with a short design note (contract, ports, file
  list) agreed in conversation, then implementation.
- Contracts (§6) change only by explicit agreement; this document is updated in the same change.

---

*Last updated: 2026-08-17*
