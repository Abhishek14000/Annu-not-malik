import json, os, subprocess, numpy as np, soundfile as sf
SR=48000; rng=np.random.default_rng(7)
if not os.path.exists('vo/vo48.wav') or os.path.getmtime('vo/vo48.wav')<os.path.getmtime('vo/vo.wav'):
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i','vo/vo.wav','-ar','48000','-ac','1','vo/vo48.wav'],check=True)
vo,_=sf.read('vo/vo48.wav'); N=len(vo); t=np.arange(N)/SR
def env(n,a,d): x=np.arange(n)/SR; return np.minimum(x/a,1)*np.exp(-x/d)
def bp(x,lo,hi):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X[(f<lo)|(f>hi)]=0; return np.fft.irfft(X,len(x))
def chisel():
    n=int(.35*SR); x=np.arange(n)/SR
    s=bp(rng.standard_normal(n),2500,9000)*env(n,.001,.025)*0.9
    s+=0.35*np.sin(2*np.pi*2900*x)*np.exp(-x/.06)+0.25*np.sin(2*np.pi*4100*x)*np.exp(-x/.04)
    s+=0.4*bp(rng.standard_normal(n),100,600)*env(n,.001,.03)
    return s
def whoosh():
    n=int(.7*SR); x=np.arange(n)/SR; w=np.sin(np.pi*x/x[-1])**2
    return bp(rng.standard_normal(n),300,3000)*w*0.35
def thud():
    n=int(.6*SR); x=np.arange(n)/SR; f=70*np.exp(-x/.25)+45
    return 0.9*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-x/.18)+0.3*bp(rng.standard_normal(n),60,400)*env(n,.001,.03)
def stamp(): s=thud(); n=len(s); s[:]+=0.5*bp(rng.standard_normal(n),800,5000)*env(n,.001,.02); return s
def tick():
    n=int(.12*SR); x=np.arange(n)/SR; return 0.5*np.sin(2*np.pi*1400*x)*np.exp(-x/.015)+0.2*bp(rng.standard_normal(n),2000,8000)*env(n,.001,.008)
def pop():
    n=int(.15*SR); x=np.arange(n)/SR; f=900*np.exp(-x/.03)+300
    return 0.8*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-x/.04)
def splash():
    n=int(.9*SR); x=np.arange(n)/SR
    return bp(rng.standard_normal(n),200,6000)*np.minimum(x/.01,1)*np.exp(-x/.18)*0.6
def ding():
    n=int(1.2*SR); x=np.arange(n)/SR
    return sum(a*np.sin(2*np.pi*f*x)*np.exp(-x/d) for f,a,d in [(1568,.5,.5),(2352,.25,.3),(3136,.12,.2)])
def boing():
    n=int(.6*SR); x=np.arange(n)/SR; f=220*(1+0.35*np.sin(2*np.pi*14*x)*np.exp(-x/.2))
    return 0.7*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-x/.22)
def drip():
    n=int(.18*SR); x=np.arange(n)/SR; f=500+2500*x/x[-1]
    return 0.6*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-x/.05)
FX={'chisel':(chisel,.55),'whoosh':(whoosh,.5),'thud':(thud,.6),'stamp':(stamp,.6),'tick':(tick,.35),
    'pop':(pop,.35),'splash':(splash,.45),'ding':(ding,.3),'boing':(boing,.4),'drip':(drip,.3)}
sfx=np.zeros(N)
for e in json.load(open('sfx.json')):
    f,g=FX[e['type']]; s=f()*g; i=int(e['t']*SR); j=min(N,i+len(s)); sfx[i:j]+=s[:j-i]
fade=np.minimum(1,t/2.5)*np.minimum(1,(t[-1]-t)/2.0)
if os.environ.get("MUSIC","drone")=="playful":
    # bouncy plucked progression C-G-Am-F at 104 bpm (additive pluck synthesis)
    pad=np.zeros(N); beat=60/104
    chords=[(261.6,329.6,392.0),(196.0,246.9,293.7),(220.0,261.6,329.6),(174.6,220.0,261.6)]
    def pluck(f,dur=.45):
        n=int(dur*SR); x=np.arange(n)/SR
        return sum((0.6/k)*np.sin(2*np.pi*f*k*x)*np.exp(-x*(3+4*k)) for k in range(1,6))
    k=0; tt=0.0
    while tt<t[-1]:
        ch=chords[(k//8)%4]; step=k%8
        notes=[ch[0]/2] if step in (0,4) else ([ch[1],ch[2]] if step in (2,6) else ([ch[2]*2] if step in (3,7) else []))
        for f in notes:
            s_=pluck(f)*(1.0 if f<200 else .55); i=int(tt*SR); j=min(N,i+len(s_)); pad[i:j]+=s_[:j-i]
        k+=1; tt+=beat/2
    pad*=fade*0.10
else:
    # drone bed: low pad with slow movement
    lfo=0.5+0.5*np.sin(2*np.pi*t/9)
    pad=sum(a*np.sin(2*np.pi*fr*t+ph) for fr,a,ph in [(55,.5,0),(82.41,.35,1),(110,.25,2),(164.8,.12,3),(220,.06,.5)])
    pad*= (0.7+0.3*lfo)
    pad*=fade*0.06
# duck pad slightly under voice
venv=np.convolve(np.abs(vo),np.ones(4800)/4800,'same'); duck=1-0.4*np.clip(venv/0.05,0,1)
mix=vo*0.92+sfx*0.8+pad*duck
mix=mix/np.max(np.abs(mix))*0.95
sf.write('mix.wav',np.stack([mix,mix],1),SR)
print('ok',N/SR)
