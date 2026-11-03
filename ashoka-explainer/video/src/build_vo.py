import json, os, re, sys, numpy as np, soundfile as sf
# Voice engine (env TTS_ENGINE):
#   kokoro (default): Kokoro-82M via kokoro-onnx; weights Apache-2.0 per the hexgrad/kokoro and kokoro-onnx READMEs.
#                     Files: video/.cache/voices/kokoro/{kokoro-v1.0.onnx,voices-v1.0.bin} (run_pipeline.py --fetch-voice).
#                     KOKORO_VOICE (default af_heart), KOKORO_SPEED (default 0.95).
#   piper:            the original Piper en-us-libritts-high voice (PIPER_MODEL); argv[1] = speaker id.
VOICES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "voices")
ENGINE = os.environ.get("TTS_ENGINE", "kokoro")
if ENGINE == "kokoro":
    from kokoro_onnx import Kokoro
    KDIR = os.environ.get("KOKORO_DIR", os.path.join(VOICES, "kokoro"))
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not os.path.exists(os.path.join(KDIR, f)): sys.exit(f"voice model not found: {os.path.join(KDIR, f)}")
    _k = Kokoro(os.path.join(KDIR, "kokoro-v1.0.onnx"), os.path.join(KDIR, "voices-v1.0.bin"))
    KVOICE = os.environ.get("KOKORO_VOICE", "af_heart"); KSPEED = float(os.environ.get("KOKORO_SPEED", "0.95")); SR = 24000
    def _raw(t):
        a, sr = _k.create(t, voice=KVOICE, speed=KSPEED, lang="en-gb" if KVOICE[0] == "b" else "en-us")
        return np.asarray(a, dtype=np.float32)
    VOICE_DESC = f"kokoro-v1.0 {KVOICE} speed {KSPEED}"
else:
    from piper import PiperVoice, SynthesisConfig
    MODEL=os.environ.get("PIPER_MODEL", os.path.join(VOICES, "en-us-libritts-high", "en-us-libritts-high.onnx"))
    if not os.path.exists(MODEL): sys.exit(f"voice model not found: {MODEL}")
    SPK=int(sys.argv[1]) if len(sys.argv)>1 else 414
    v=PiperVoice.load(MODEL, config_path=MODEL+".json"); SR=v.config.sample_rate
    def _raw(t):
        return np.concatenate([c.audio_float_array for c in v.synthesize(t, syn_config=SynthesisConfig(speaker_id=SPK, length_scale=1.1, noise_scale=0.6, noise_w_scale=0.7))])
    VOICE_DESC = f"piper en-us-libritts-high speaker {SPK}"
# (display text, spoken text or None)
BEATS=[
 ("cold",[("Kings carve victories into stone.",None),("This one carved his regret.",None)]),
 ("setup",[("Ashoka ruled the largest empire India had yet seen.",None),
           ("Around 261 BCE, he invaded Kalinga, an independent kingdom on the east coast.","Around two sixty one B.C.E., he invaded Kalinga, an independent kingdom on the east coast.")]),
 ("numbers",[("By his own count: a hundred thousand killed, a hundred and fifty thousand deported, and many more dead.",None),
             ("Then he does something rulers almost never do.",None),("He says he feels remorse.",None),("In public.",None),("On a rock.",None)]),
 ("turn",[("But here's the thing.",None),("These aren't diary entries.",None),("They're public notices, meant to be read aloud to crowds.",None),
          ("And in Kalinga itself, the confession is left out.",None),
          ("So: was this a king in pain, or a king managing his image?","So, was this a king in pain? Or a king managing his image?")]),
 ("evidence",[("The case for sincerity: he urges people to watch themselves for cruelty, anger, pride and envy.",None),
              ("He funds medicine for people and animals, and wells along the roads.",None),
              ("The case for strategy: he keeps the death penalty, and warns forest tribes that, remorse or not, he can still punish them.",None)]),
 ("thesis",[("Maybe that's the point.",None),("Ashoka didn't just feel something.",None),
            ("He turned a feeling into policy, and carved it across an empire.",None),("Remorse became a way to govern.",None)]),
 ("debate",[("So what do historians actually argue?",None),
             ("Romila Thapar reads his dhamma as a public ethic, built to hold a vast and diverse empire together.","Romila Thapar reads his dhamma as a public ethic, built to hold a vast and diverse empire together."),
             ("Upinder Singh notes that he gave up conquest, but kept the state's power to punish.",None),
             ("Patrick Olivelle reads him as a philosopher-king, working out his ideas in public.",None),
             ("And one twist: the Buddhist legends about Ashoka never mention the Kalinga war.",None),
             ("The remorse comes only from his own inscriptions.",None)]),
 ("close",[("So was it conscience or strategy?",None),("Historians still argue.",None),
           ("Either way, it's a rare moment where a ruler lets us read his emotions.",None),("And they're still on the rock.",None)]),
]
DEF = {"kokoro": ("0.48", "1.2", "3.0"), "piper": ("0.38", "0.85", "2.2")}[ENGINE]  # pacing tuned to a 2:00 cut with kokoro
GAP_S=float(os.environ.get("GAP_SENT", DEF[0])); GAP_B=float(os.environ.get("GAP_BEAT", DEF[1]))
def synth(t):
    a=_raw(t)
    env=np.abs(a)>0.01; idx=np.where(env)[0]
    return a[max(0,idx[0]-200):idx[-1]+800]
def chunks(text, maxw=4):
    parts=re.split(r'(?<=[,:;?.])\s+', text); out=[]
    for p in parts:
        w=p.split()
        while len(w)>maxw:
            n=maxw if len(w)-maxw!=1 else maxw-1
            out.append(' '.join(w[:n])); w=w[n:]
        if w: out.append(' '.join(w))
    return out
audio=[np.zeros(int(0.35*SR))]; t=0.35; TL=[]
for bi,(name,sents) in enumerate(BEATS):
    b={"name":name,"start":t,"sentences":[]}
    for si,(disp,spk) in enumerate(sents):
        a=synth(spk or disp); d=len(a)/SR
        cs=chunks(disp); L=sum(len(c) for c in cs); acc=t; ch=[]
        for c in cs:
            dd=d*len(c)/L; ch.append({"start":round(acc,3),"end":round(acc+dd,3),"text":c}); acc+=dd
        b["sentences"].append({"start":round(t,3),"end":round(t+d,3),"text":disp,"chunks":ch})
        audio.append(a); t+=d
        gap=GAP_S if si<len(sents)-1 else (GAP_B if bi<len(BEATS)-1 else 0.0)
        if disp in ("In public.",): gap=0.3
        audio.append(np.zeros(int(gap*SR))); t+=gap
    b["end"]=round(t,3); TL.append(b)
tail=float(os.environ.get("TAIL", DEF[2])); audio.append(np.zeros(int(tail*SR))); t+=tail
y=np.concatenate(audio); y=y/np.abs(y).max()*0.89
os.makedirs("vo", exist_ok=True); sf.write("vo/vo.wav", y, SR, subtype="PCM_16")
json.dump({"duration":round(t,3),"voice":VOICE_DESC,"beats":TL}, open("timeline.json","w"), indent=1)
for b in TL: print(b["name"], round(b["start"],2), round(b["end"],2))
print("total", round(t,2))
