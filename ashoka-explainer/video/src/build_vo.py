import json, os, re, sys, numpy as np, soundfile as sf
from piper import PiperVoice, SynthesisConfig
# Voice model: set PIPER_MODEL, or run `run_pipeline.py --fetch-voice` (saves to video/.cache/voices/).
MODEL=os.environ.get("PIPER_MODEL", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "voices", "en-us-libritts-high", "en-us-libritts-high.onnx"))
if not os.path.exists(MODEL): sys.exit(f"voice model not found: {MODEL}")
SPK=int(sys.argv[1]) if len(sys.argv)>1 else 92
v=PiperVoice.load(MODEL, config_path=MODEL+".json"); SR=v.config.sample_rate
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
 ("close",[("So was it conscience or strategy?",None),("Historians still argue.",None),
           ("Either way, it's a rare moment where a ruler lets us read his emotions.",None),("And they're still on the rock.",None)]),
]
def synth(t):
    a=np.concatenate([c.audio_float_array for c in v.synthesize(t, syn_config=SynthesisConfig(speaker_id=SPK, length_scale=1.1, noise_scale=0.6, noise_w_scale=0.7))])
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
        gap=0.38 if si<len(sents)-1 else (0.85 if bi<len(BEATS)-1 else 0.0)
        if disp in ("In public.",): gap=0.3
        audio.append(np.zeros(int(gap*SR))); t+=gap
    b["end"]=round(t,3); TL.append(b)
tail=2.2; audio.append(np.zeros(int(tail*SR))); t+=tail
y=np.concatenate(audio); y=y/np.abs(y).max()*0.89
os.makedirs("vo", exist_ok=True); sf.write("vo/vo.wav", y, SR, subtype="PCM_16")
json.dump({"duration":round(t,3),"beats":TL}, open("timeline.json","w"), indent=1)
for b in TL: print(b["name"], round(b["start"],2), round(b["end"],2))
print("total", round(t,2))
