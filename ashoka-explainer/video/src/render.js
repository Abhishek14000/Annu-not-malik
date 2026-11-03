const {chromium}=require('playwright');const {spawn}=require('child_process');const fs=require('fs');
(async()=>{const FPS=30;const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
await p.goto('file://'+__dirname+'/page.html');await p.evaluate(()=>document.fonts.ready);
const D=await p.evaluate(()=>TL.duration);fs.writeFileSync('sfx.json',JSON.stringify(await p.evaluate(()=>window.SFX)));
const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','video_silent.mp4'],{stdio:['pipe','inherit','inherit']});
const N=Math.ceil(D*FPS);for(let i=0;i<N;i++){await p.evaluate(t=>render(t),i/FPS);const buf=await p.screenshot({type:'jpeg',quality:93});
 if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r)); if(i%300==0)console.log('frame',i,'/',N)}
ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();console.log('done')})();
