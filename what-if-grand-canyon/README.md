# What if 5,000 people peed into the Grand Canyon?

`what_if_grand_canyon.mp4`: 1080×1920 (9:16), 30 fps, 1:33, H.264/AAC, −14 LUFS. An animated hypothetical-science explainer. All the artwork is original vector animation drawn in code: no photos, no third-party art.

- **Script:** `script.json` (narration, with spoken forms of the numbers)
- **Maths and sources:** `MATH.md`; rerun the numbers with `python3 math_check.py`
- **Animation:** `template.html`

## Render
```bash
npm install                 # fonts (Fredoka, Inter; OFL-1.1)
python3 run.py              # reuses generated/vo.wav + timeline.json
python3 run.py --regen-voice
python3 run.py --seconds 10 # quick test
```
`run.py` reuses the engine in `../ashoka-explainer/video/src`:
- `build_vo.py` (reads `BEATS_FILE`)
- `render.js` (the page declares `window.REQUIRED_FONTS`)
- `mix.py` (`MUSIC=playful` for the plucked music bed, plus cartoon sound effects)

The Kokoro voice model must be present in `../ashoka-explainer/video/.cache/voices/kokoro` (`run_pipeline.py --fetch-voice` there downloads it).

## Credits
- **Voice:** Kokoro-82M `af_heart`. The weights are Apache-2.0 per the hexgrad/kokoro and kokoro-onnx READMEs, so no credit is required. Every sentence was transcribed with Whisper base.en as an intelligibility check, and all were intelligible.
- **Music and sound effects:** synthesised in `mix.py`.
- **Fonts:** Fredoka and Inter via @fontsource (package metadata: OFL-1.1).
- **Data:** NPS (volume, park area), USGS (Lake Mead evaporation), UN WPP 2024 (population), and voiding-diary studies (pee volume). See `MATH.md`.

## Not to do
The video says "Please don't try this." Keep that line.
