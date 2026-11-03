#!/usr/bin/env python3
"""Render "What if 5,000 people peed into the Grand Canyon?" (9:16).

Reuses the engine in ../ashoka-explainer/video/src (build_vo.py, render.js, mix.py).
  python3 run.py                  render with the committed voiceover (generated/)
  python3 run.py --regen-voice    rebuild the voiceover from script.json (Kokoro)
  python3 run.py --seconds 10     quick partial render
"""
import argparse, json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "ashoka-explainer", "video", "src")
KOKORO = os.path.join(HERE, "..", "ashoka-explainer", "video", ".cache", "voices", "kokoro")
GEN, BUILD = os.path.join(HERE, "generated"), os.path.join(HERE, "build")
VOICE_ENV = {"KOKORO_VOICE": "af_heart", "KOKORO_SPEED": "1.0", "GAP_SENT": "0.35", "GAP_BEAT": "0.7", "TAIL": "2.5"}


def run(cmd, env=None, cwd=BUILD):
    r = subprocess.run(cmd, cwd=cwd, env=dict(os.environ, **(env or {})), capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{(r.stdout + r.stderr)[-3000:]}")
    return (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regen-voice", action="store_true"); ap.add_argument("--seconds", type=float); ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    os.makedirs(os.path.join(BUILD, "vo"), exist_ok=True); os.makedirs(GEN, exist_ok=True)
    t0 = time.time()
    if a.regen_voice or not os.path.exists(os.path.join(GEN, "vo.wav")):
        print("== voice"); print(run([sys.executable, os.path.join(ENGINE, "build_vo.py")], env=dict(VOICE_ENV, BEATS_FILE=os.path.join(HERE, "script.json"), KOKORO_DIR=KOKORO)).splitlines()[-1])
        shutil.copyfile(os.path.join(BUILD, "vo", "vo.wav"), os.path.join(GEN, "vo.wav")); shutil.copyfile(os.path.join(BUILD, "timeline.json"), os.path.join(GEN, "timeline.json"))
    else:
        shutil.copyfile(os.path.join(GEN, "vo.wav"), os.path.join(BUILD, "vo", "vo.wav")); shutil.copyfile(os.path.join(GEN, "timeline.json"), os.path.join(BUILD, "timeline.json"))
    print("== page")
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read().replace('url("node_modules/', 'url("../node_modules/')
    open(os.path.join(BUILD, "page.html"), "w", encoding="utf-8").write(tpl.replace("__TIMELINE__", open(os.path.join(BUILD, "timeline.json"), encoding="utf-8").read()))
    print("== render")
    env = {"FPS": str(a.fps)}
    if a.seconds: env["RENDER_SECONDS"] = str(a.seconds)
    print(run(["node", os.path.join(ENGINE, "render.js")], env=env).splitlines()[-1])
    print("== mix"); run([sys.executable, os.path.join(ENGINE, "mix.py")], env={"MUSIC": "playful"})
    out = os.path.join(BUILD, "what_if_grand_canyon" + (f"_first{a.seconds:g}s" if a.seconds else "") + ".mp4")
    print("== mux")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video_silent.mp4", "-i", "mix.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    info = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", out]))
    dur = float(info["format"]["duration"]); v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    expect = a.seconds or json.load(open(os.path.join(BUILD, "timeline.json")))["duration"]
    ok = (v["width"], v["height"]) == (1080, 1920) and abs(dur - expect) < 0.3 and any(s["codec_type"] == "audio" for s in info["streams"])
    if ok and not a.seconds:
        shutil.copyfile(out, os.path.join(HERE, "what_if_grand_canyon.mp4"))
    print(f"== verify: {'OK' if ok else 'FAILED'} {v['width']}x{v['height']} {dur:.2f}s (expected {expect:.2f}s) in {time.time()-t0:.0f}s -> {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
