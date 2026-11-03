#!/usr/bin/env python3
"""Render the Ashoka explainer end to end.

Stages: preflight -> voice -> map -> [retrieve] -> manifest -> page -> render -> mix -> mux -> verify

  python3 run_pipeline.py                      full render; missing images stay placeholders
  python3 run_pipeline.py --retrieve           also try Openverse / Internet Archive / LOC first
  python3 run_pipeline.py --preview-unverified include selected-but-unverified images, watermarked
  python3 run_pipeline.py --seconds 10         quick partial render (not copied to the deliverable)

Committed inputs in generated/ (vo.wav, timeline.json, map.json) are reused, so the
voice model is only needed with --regen-voice. Scratch files go to build/.
"""
import argparse, json, os, shutil, subprocess, sys, tarfile, time, urllib.request

VIDEO = os.path.dirname(os.path.abspath(__file__))
SRC, GEN, BUILD = (os.path.join(VIDEO, d) for d in ("src", "generated", "build"))
VOICE_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-libritts-high.tar.gz"
VOICE_DIR = os.path.join(VIDEO, ".cache", "voices", "en-us-libritts-high")
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_DIR = os.path.join(VIDEO, ".cache", "voices", "kokoro")
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
REPORT = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "stages": [], "errors": [], "warnings": []}


class StageError(Exception):
    pass


def run(cmd, cwd=BUILD, env=None):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise StageError(f"{' '.join(cmd)} exited {r.returncode}:\n{out[-3000:]}")
    return out


def stage(name):
    def deco(fn):
        def wrapped(*a, **k):
            t = time.time()
            print(f"== {name}", flush=True)
            try:
                detail = fn(*a, **k) or ""
                REPORT["stages"].append({"stage": name, "status": "ok", "seconds": round(time.time() - t, 1), "detail": detail})
                if detail:
                    print("   " + str(detail).replace("\n", "\n   "))
            except StageError as e:
                REPORT["stages"].append({"stage": name, "status": "failed", "seconds": round(time.time() - t, 1), "detail": str(e)})
                REPORT["errors"].append(f"{name}: {e}")
                raise
        return wrapped
    return deco


@stage("preflight")
def preflight(a):
    notes = []
    for tool in ("ffmpeg", "ffprobe", "node"):
        if not shutil.which(tool):
            raise StageError(f"{tool} not found on PATH")
    try:
        run(["node", "-e", "require('playwright')"], cwd=VIDEO)
    except StageError:
        raise StageError("Node package 'playwright' not found (install it, or set NODE_PATH)")
    need = ["@fontsource/inter", "@fontsource/playfair-display", "@fontsource/noto-sans-brahmi", "world-atlas", "d3-geo", "topojson-client"]
    if any(not os.path.isdir(os.path.join(VIDEO, "node_modules", n)) for n in need):
        if not a.install:
            raise StageError("node_modules incomplete; rerun with --install (runs npm install in video/)")
        notes.append(run(["npm", "install", "--no-audit", "--no-fund"], cwd=VIDEO).splitlines()[-1])
    for mod in ("numpy", "soundfile", "requests", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            raise StageError(f"Python module {mod} missing (pip install -r requirements.txt)")
    os.makedirs(BUILD, exist_ok=True)
    notes.append("tools and packages present")
    return "; ".join(notes)


@stage("voice")
def voice(a):
    os.makedirs(os.path.join(BUILD, "vo"), exist_ok=True)
    have = all(os.path.exists(os.path.join(GEN, f)) for f in ("vo.wav", "timeline.json"))
    if have and not a.regen_voice:
        shutil.copyfile(os.path.join(GEN, "vo.wav"), os.path.join(BUILD, "vo", "vo.wav"))
        shutil.copyfile(os.path.join(GEN, "timeline.json"), os.path.join(BUILD, "timeline.json"))
        return "reused generated/vo.wav and generated/timeline.json"
    env = {"TTS_ENGINE": a.engine}
    if a.engine == "kokoro":
        if any(not os.path.exists(os.path.join(KOKORO_DIR, f)) for f in KOKORO_FILES):
            if not a.fetch_voice:
                raise StageError(f"Kokoro model files missing in {KOKORO_DIR}; rerun with --fetch-voice")
            fetch_kokoro()
        mod = "kokoro_onnx"; env.update(KOKORO_DIR=KOKORO_DIR, KOKORO_VOICE=a.voice)
    else:
        model = os.environ.get("PIPER_MODEL") or os.path.join(VOICE_DIR, "en-us-libritts-high.onnx")
        if not os.path.exists(model):
            if not a.fetch_voice:
                raise StageError(f"voice model missing ({model}); rerun with --fetch-voice or set PIPER_MODEL")
            fetch_voice()
        mod = "piper"; env["PIPER_MODEL"] = model
    try:
        __import__(mod)
    except ImportError:
        raise StageError(f"{mod} not installed (pip install -r requirements.txt)")
    out = run([sys.executable, os.path.join(SRC, "build_vo.py"), str(a.speaker)], env=env)
    shutil.copyfile(os.path.join(BUILD, "vo", "vo.wav"), os.path.join(GEN, "vo.wav"))
    shutil.copyfile(os.path.join(BUILD, "timeline.json"), os.path.join(GEN, "timeline.json"))
    return "regenerated voiceover:\n" + out


def _download(url, dst):
    for i in range(4):
        try:
            urllib.request.urlretrieve(url, dst)
            return
        except Exception as e:
            if i == 3:
                raise StageError(f"download failed ({url}): {e}")
            time.sleep(2 ** (i + 1))


def fetch_kokoro():
    os.makedirs(KOKORO_DIR, exist_ok=True)
    for f in KOKORO_FILES:
        _download(KOKORO_URL + f, os.path.join(KOKORO_DIR, f))


def fetch_voice():
    os.makedirs(VOICE_DIR, exist_ok=True)
    tgz = VOICE_DIR + ".tar.gz"
    for i in range(4):
        try:
            urllib.request.urlretrieve(VOICE_URL, tgz)
            break
        except Exception as e:
            if i == 3:
                raise StageError(f"voice download failed: {e}")
            time.sleep(2 ** (i + 1))
    with tarfile.open(tgz) as t:
        t.extractall(VOICE_DIR, filter="data")
    card = open(os.path.join(VOICE_DIR, "MODEL_CARD"), encoding="utf-8").read()
    REPORT["warnings"].append("voice MODEL_CARD licence line: " + next((l.strip() for l in card.splitlines() if "License" in l), "not found") + " (as stated by the model card; not independently verified)")


@stage("map")
def map_stage(a):
    dst = os.path.join(BUILD, "map.json")
    if os.path.exists(os.path.join(GEN, "map.json")) and not a.regen_map:
        shutil.copyfile(os.path.join(GEN, "map.json"), dst)
        return "reused generated/map.json"
    run(["node", os.path.join(SRC, "map.mjs"), dst])
    shutil.copyfile(dst, os.path.join(GEN, "map.json"))
    return "regenerated generated/map.json"


@stage("retrieve")
def retrieve(a):
    cmd = [sys.executable, os.path.join(SRC, "retrieve_images.py"), "--report", os.path.join(BUILD, "retrieval_report.json")]
    if a.providers:
        cmd += ["--providers", a.providers]
    try:
        out = run(cmd, cwd=VIDEO)
    except StageError as e:  # retrieval is optional: never block the render
        REPORT["warnings"].append(f"retrieval failed, placeholders kept: {e}")
        return "failed (placeholders kept); see warnings"
    rep = json.load(open(os.path.join(BUILD, "retrieval_report.json"), encoding="utf-8"))
    REPORT["retrieval"] = rep
    lines = [f"{p}: {v['status']}" + (f" ({v.get('reason')})" if v.get("reason") else "") for p, v in rep["providers"].items()]
    lines += [f"slot {k}: {v['download_status']}, {v['downloaded']} downloaded" for k, v in rep["slots"].items()]
    return "\n".join(lines)


@stage("manifest")
def manifest(a):
    return run([sys.executable, os.path.join(SRC, "assets.py"), "report", "--timeline", os.path.join(BUILD, "timeline.json")], cwd=VIDEO)


@stage("page")
def page(a):
    cmd = [sys.executable, os.path.join(SRC, "build_page.py")] + (["--preview-unverified"] if a.preview_unverified else [])
    out = run(cmd)
    REPORT["slots"] = json.load(open(os.path.join(BUILD, "slots_resolved.json"), encoding="utf-8"))
    return out


@stage("render")
def render(a):
    env = {"FPS": str(a.fps)}
    if a.seconds:
        env["RENDER_SECONDS"] = str(a.seconds)
    run(["node", os.path.join(SRC, "render.js")], env=env)
    st = json.load(open(os.path.join(BUILD, "render_stats.json"), encoding="utf-8"))
    return f"{st['frames']} frames in {st['render_seconds_wall']:.0f}s; fonts {st['fonts']}; {len(st['images'])} image(s)"


@stage("mix")
def mix(a):
    return run([sys.executable, os.path.join(SRC, "mix.py")])


@stage("mux")
def mux(a):
    out = os.path.join(BUILD, a.out_name)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video_silent.mp4", "-i", "mix.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    return out


@stage("verify")
def verify(a):
    out = os.path.join(BUILD, a.out_name)
    info = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate", "-of", "json", out]))
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    au = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    expect = a.seconds or json.load(open(os.path.join(BUILD, "timeline.json")))["duration"]
    problems = []
    if not v or (v["width"], v["height"]) != (1080, 1920):
        problems.append(f"video stream wrong or missing: {v}")
    if not au:
        problems.append("no audio stream")
    if abs(dur - expect) > 0.3:
        problems.append(f"duration {dur:.2f}s, expected {expect:.2f}s")
    vol = run(["ffmpeg", "-i", out, "-af", "volumedetect", "-vn", "-f", "null", "-"])
    mean = next((l.split(":")[-1].strip() for l in vol.splitlines() if "mean_volume" in l), "?")
    if mean != "?" and float(mean.split()[0]) < -40:
        problems.append(f"audio nearly silent (mean {mean})")
    if problems:
        raise StageError("; ".join(problems))
    REPORT["output"] = {"file": out, "duration": round(dur, 2), "bytes": int(info["format"]["size"]), "video": f"{v['codec_name']} {v['width']}x{v['height']} @ {v['r_frame_rate']}", "audio": au["codec_name"], "mean_volume": mean}
    if not a.seconds:  # copy full renders next to the scripts
        dst = os.path.join(VIDEO, a.out_name)
        shutil.copyfile(out, dst)
        REPORT["output"]["deliverable"] = dst
    return json.dumps(REPORT["output"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retrieve", action="store_true", help="run the optional image-retrieval stage")
    ap.add_argument("--providers", help="comma list for retrieval: openverse,internet_archive,loc")
    ap.add_argument("--preview-unverified", action="store_true", help="show selected-but-unverified images, watermarked")
    ap.add_argument("--regen-voice", action="store_true"); ap.add_argument("--fetch-voice", action="store_true")
    ap.add_argument("--engine", choices=["kokoro", "piper"], default="kokoro", help="voice engine for --regen-voice")
    ap.add_argument("--voice", default="af_heart", help="Kokoro voice id (e.g. af_heart, am_michael, bm_george)")
    ap.add_argument("--speaker", type=int, default=414, help="Piper speaker id")
    ap.add_argument("--regen-map", action="store_true")
    ap.add_argument("--install", action="store_true", help="npm install if node_modules is incomplete")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, help="render only the first N seconds (test)")
    a = ap.parse_args()
    a.out_name = "ashoka_explainer" + ("_PREVIEW_UNVERIFIED" if a.preview_unverified else "") + (f"_first{a.seconds:g}s" if a.seconds else "") + ".mp4"
    stages = [preflight, voice, map_stage] + ([retrieve] if a.retrieve else []) + [manifest, page, render, mix, mux, verify]
    ok = True
    try:
        for s in stages:
            s(a)
    except StageError:
        ok = False
    REPORT["ok"] = ok
    REPORT["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "pipeline_report.json"), "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=1, ensure_ascii=False)
    print("\nRESULT:", "OK" if ok else "FAILED")
    for e in REPORT["errors"]:
        print("ERROR:", e)
    for w in REPORT["warnings"]:
        print("WARNING:", w)
    for k, v in (REPORT.get("slots") or {}).items():
        print(f"slot {k}: {v.get('status') or 'placeholder'} ({v['reason']})")
    print("report:", os.path.join(BUILD, "pipeline_report.json"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
