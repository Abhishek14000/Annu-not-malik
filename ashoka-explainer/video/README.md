# Video: "The King Who Apologized in Stone"

`ashoka_explainer.mp4`: 1080×1920 (9:16), 30 fps, 1:31, H.264 and AAC, audio normalised to −14 LUFS.

## What's in this cut
- It follows the fact-checked script in `../SCRIPT.md` beat by beat. The "emotives" beat is cut.
- Captions are burned in and stay above the bottom 20% of the frame (the lowest caption edge is at y = 1480 of 1920).
- The maps are drawn from Natural Earth land data (public domain, from the `world-atlas` npm package). The Mauryan and Kalinga borders are hand-drawn approximations, and the video says "Borders approximate" on screen.
- The Brahmi text is typeset in Noto Sans Brahmi (SIL OFL): 𑀤𑁂𑀯𑀸𑀦𑀁𑀧𑀺𑀬 𑀧𑀺𑀬𑀤𑀲𑀺 (*devānaṃpiya piyadasi*, Ashoka's title). It's typography, not an imitation photo.
- The Rock Edict XIII quote is from S. Dhammika's translation, *The Edicts of King Asoka*, and is credited on screen.
- **The voiceover is a synthetic scratch track.** It uses the Piper `en-us-libritts-high` voice, speaker 414, which was trained on LibriTTS (**CC BY 4.0**). If you keep it, credit it, e.g. "Voice: Piper TTS, LibriTTS (CC BY 4.0)". A human voiceover recorded over the clean VO in `../SCRIPT.md` will sound better.
- The sound effects and the music bed are synthesised in `mix.py`, so no third-party audio is used.
- The fonts are Playfair Display (OFL) and Inter (OFL).

## Photo slots: still to fill
The session that made this video couldn't reach Wikimedia Commons, so the four photo beats show labelled **PHOTO SLOT** cards rather than an unrelated substitute image. To fill them:
1. Download the files listed in `../IMAGES.md` and confirm each licence.
2. Save them as `photos/kalsi.jpg`, `photos/dhauli.jpg`, `photos/pillar.jpg` and `photos/sarnath.jpg`.
3. Fill in each `credit` field in `src/photos.json` (author, licence and "Wikimedia Commons"). The credit is printed on the frame.
4. Re-render. The Kalsi photo is also used behind the Brahmi text in the cold open and the closing loop.

## Re-rendering
The pipeline needs Python with `piper-tts` and `soundfile`, Node with `playwright`, and ffmpeg. Fonts and map data come from npm: `world-atlas@2.0.2`, `d3-geo@3.1.0`, `topojson-client@3.1.0`, `@fontsource/playfair-display` and `@fontsource/noto-sans-brahmi`.
1. `python3 build_vo.py 414` writes `vo/vo.wav` and `timeline.json`. Every visual cue is timed from `timeline.json`.
2. `node map.mjs` writes `map.json`.
3. `python3 build_page.py` writes `page.html`.
4. `node render.js` writes `video_silent.mp4` and `sfx.json`.
5. `python3 mix.py` writes `mix.wav`, then mux the two:
   `ffmpeg -i video_silent.mp4 -i mix.wav -af loudnorm=I=-14:TP=-1.5 -c:v copy -c:a aac -b:a 192k -shortest ashoka_explainer.mp4`

To use a human voiceover, replace step 1's audio and update the sentence times in `timeline.json` so the visuals stay in sync.
