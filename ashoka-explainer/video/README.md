# Video pipeline: "The King Who Apologized in Stone"

The deliverable is `ashoka_explainer.mp4`: 1080×1920 (9:16), 30 fps, about 1:31, H.264 with AAC audio, normalised to −14 LUFS. Captions are burned in and stay above the bottom 20% of the frame.

## Quick start
```bash
cd ashoka-explainer/video
pip install -r requirements.txt   # piper-tts is only needed for --regen-voice
npm install                       # fonts and map data (versions pinned in package.json)
python3 run_pipeline.py           # full render; missing photos render as placeholders
```

| Option | What it does |
|---|---|
| `--retrieve` | Runs the optional image search first (see below). |
| `--preview-unverified` | Also shows images that are selected but not yet verified, with an "UNVERIFIED · PREVIEW ONLY" watermark. The output is named `ashoka_explainer_PREVIEW_UNVERIFIED.mp4`. |
| `--seconds N` | Quick test render of the first N seconds, written to `build/` only. |
| `--regen-voice [--fetch-voice]` | Rebuilds the voiceover and timeline (needs piper-tts and the voice model). |
| `--regen-map` | Rebuilds the map geometry. |
| `--install` | Runs `npm install` when `node_modules` is incomplete. |

Each run writes `build/pipeline_report.json` with every stage's status, the output file's check results, each slot's render state and any errors.

## Stages
`preflight → voice → map → [retrieve] → manifest → page → render → mix → mux → verify`

| Stage | Script | Notes |
|---|---|---|
| preflight | `run_pipeline.py` | Checks ffmpeg, Node, Playwright, the npm packages and the Python modules. |
| voice | `src/build_vo.py` | Reuses the committed `generated/vo.wav` and `generated/timeline.json` unless `--regen-voice` is set. |
| map | `src/map.mjs` | Reuses `generated/map.json` unless `--regen-map` is set. |
| retrieve | `src/retrieve_images.py` | Optional. Downloads candidate images only and never selects one. |
| manifest | `src/assets.py report` | Writes `ASSET_MANIFEST.md` and `ASSET_MANIFEST.csv`. |
| page | `src/build_page.py` | Builds `build/page.html` from `src/page.template.html` and applies the render gate to each photo slot. |
| render | `src/render.js` | Captures frames with Playwright and encodes them with ffmpeg. Fails on page errors, fonts that didn't load, images that won't decode, or an ffmpeg error. |
| mix | `src/mix.py` | Mixes the voice with synthesised sound effects and a music bed. |
| mux / verify | `run_pipeline.py` | Muxes video and audio, then checks the resolution, streams, duration (within ±0.3 s of the timeline) and that the audio isn't silent. Copies a full render to `ashoka_explainer.mp4`. |

## Folders: what came from where
| Folder | Contents | In git |
|---|---|---|
| `generated/` | Assets the pipeline made: the voiceover, timeline and map geometry. | yes |
| `assets/manifest.json` | The source of truth for each scene, photo slot, candidate image, licence and attribution. | yes |
| `assets/retrieved/<slot>/` | Images downloaded by the retrieval stage. Each has a `.json` sidecar holding its provider, source URL, image URL and licence **as reported**. | yes, once reviewed |
| `assets/manual/` | Images you add yourself with `src/assets.py add-manual`. | yes |
| placeholders | Not files. `page.template.html` draws them at render time. | n/a |
| `build/` | Scratch files: page, frames, mix and reports. | no |

## Photo slots and the render gate
There are four slots: `kalsi`, `dhauli`, `pillar` and `sarnath` (see `ASSET_MANIFEST.md`). A slot shows a real image **only** when all of these are true:
1. an image is selected and its file exists, unchanged (its sha256 matches);
2. its licence status is `verified`, meaning a named person checked it on the source page;
3. its subject is verified, meaning a named person confirmed it really shows, say, the Kalsi edict.

Otherwise the slot renders as a labelled placeholder. No script can set either verification flag by itself.

Licence status values:
- `unknown`: no licence information was found.
- `reported-unverified`: a provider or the file states a licence, but nobody has checked it.
- `verified`: a person checked it, recorded with their name, the date and how they checked.

### Adding an image you got elsewhere (e.g. Wikimedia Commons on another network)
```bash
python3 src/assets.py add-manual kalsi ~/Downloads/Kalsi.jpg \
  --source-url "https://commons.wikimedia.org/wiki/File:..." --licence "CC BY-SA 4.0"
python3 src/assets.py verify-licence kalsi --licence "CC BY-SA 4.0" \
  --licence-url https://creativecommons.org/licenses/by-sa/4.0/ \
  --attribution "Photo: <author>, CC BY-SA 4.0, via Wikimedia Commons" \
  --by "<your name>" --method "Checked the licence section of the Commons file page"
python3 src/assets.py verify-subject kalsi --by "<your name>" --notes "Commons category: Ashoka Major Rock Edict, Khalsi; matches site photos"
python3 run_pipeline.py
```

### Optional retrieval (Openverse, Internet Archive, Library of Congress)
```bash
python3 run_pipeline.py --retrieve                 # or: python3 src/retrieve_images.py --providers openverse
python3 src/assets.py status                       # see the candidates in each slot
python3 src/assets.py select kalsi openverse:<id>  # then verify-licence and verify-subject as above
```
How retrieval behaves:
- It probes each provider before searching and skips any it can't reach. A proxy policy block is not retried.
- It retries temporary failures (timeouts, dropped connections, 429, 500, 502, 503, 504) with exponential backoff and jitter, and honours `Retry-After` (capped at 60 s).
- It waits at least 2 s between requests to the same host (`--min-interval`).
- It checks each download's content type, size (30 MB max) and that it decodes. Images under 800 px on the short side, and Openverse thumbnails used as a fallback, are flagged `low_resolution`.
- Openverse searches CC BY, BY-SA, CC0 and PDM only. Licences from all three providers are stored as `reported-unverified`.
- Full request logs go to `build/retrieval_report.json`, and a summary of each run is appended to `assets/retrieved/retrieval_log.jsonl`.

## Credits and licences (see `ASSET_MANIFEST.md`)
- **Voice:** Piper `en-us-libritts-high`, speaker 414. The voice's model card states **CC BY 4.0** (trained on LibriTTS). That hasn't been checked against the upstream dataset's licence page. If you keep this voice, credit it.
- **Map:** Natural Earth land data via the `world-atlas` package (the package licence is ISC). Natural Earth describes its data as public domain, which hasn't been checked here. The empire borders are hand-drawn approximations.
- **Fonts:** Playfair Display, Inter and Noto Sans Brahmi from @fontsource. Their package metadata says OFL-1.1.
- **Quote:** S. Dhammika, *The Edicts of King Asoka*, credited on screen.
- **Sound:** synthesised in `src/mix.py`.

## Tests
```bash
python3 -m unittest discover -s tests -v
```
The tests use a mock provider server on localhost and cover retries, `Retry-After`, the rate limit, blocked and unreachable providers, falling back to thumbnails when a download isn't an image, and the review gate. They make no real network calls.
