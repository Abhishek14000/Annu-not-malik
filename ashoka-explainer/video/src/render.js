// Renders page.html (in the current directory) frame by frame into video_silent.mp4.
// Also writes sfx.json (sound cues from the page) and render_stats.json.
// Fails (exit 1) on page errors, missing fonts, undecodable images or ffmpeg errors.
// Env: FPS (default 30), RENDER_SECONDS (render only the first N seconds, for quick tests).
const {chromium} = require('playwright');
const {spawn} = require('child_process');
const fs = require('fs'), path = require('path');

(async () => {
  const FPS = +(process.env.FPS || 30);
  const page_url = 'file://' + path.resolve('page.html');
  const b = await chromium.launch();
  const fail = async (msg) => { console.error('RENDER FAILED: ' + msg); await b.close(); process.exit(1); };
  const p = await b.newPage({viewport: {width: 1080, height: 1920}});
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  p.on('requestfailed', r => errs.push('requestfailed: ' + r.url() + ' ' + (r.failure() || {}).errorText));
  await p.goto(page_url);
  await p.evaluate(() => document.fonts.ready);
  // Fonts: make sure the web fonts actually loaded (no silent fallback).
  const fonts = await p.evaluate(async () => {
    const want = {'Playfair 900': '900 40px Playfair', 'Inter 800': '800 40px Inter', 'Brahmi': '40px Brahmi'};
    const out = {};
    for (const [k, f] of Object.entries(want)) {
      try { await document.fonts.load(f, k === 'Brahmi' ? '\u{11024}' : 'A'); } catch (e) { /* reported below */ }
      out[k] = [...document.fonts].some(ff => ff.status === 'loaded' && f.includes(ff.family.replace(/"/g, '')));
    }
    return out;
  });
  const missing = Object.entries(fonts).filter(([, ok]) => !ok).map(([k]) => k);
  if (missing.length) return fail('fonts not loaded: ' + missing.join(', ') + ' (run npm install in video/)');
  // Images: every <img> must decode.
  const imgs = await p.evaluate(async () => Promise.all([...document.images].map(async im => {
    try { await im.decode(); } catch (e) {}
    return {src: im.getAttribute('src'), ok: im.complete && im.naturalWidth > 0, w: im.naturalWidth, h: im.naturalHeight};
  })));
  const bad = imgs.filter(i => !i.ok);
  if (bad.length) return fail('images failed to load: ' + bad.map(i => i.src).join(', '));
  if (errs.length) return fail(errs.join('\n'));

  const D = await p.evaluate(() => TL.duration);
  const until = process.env.RENDER_SECONDS ? Math.min(D, +process.env.RENDER_SECONDS) : D;
  fs.writeFileSync('sfx.json', JSON.stringify(await p.evaluate(() => window.SFX)));
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', 'video_silent.mp4'], {stdio: ['pipe', 'inherit', 'inherit']});
  let ffCode = null; const ffDone = new Promise(r => ff.on('close', c => { ffCode = c; r(); }));
  ff.stdin.on('error', e => errs.push('ffmpeg stdin: ' + e.message));
  const N = Math.ceil(until * FPS), t0 = Date.now();
  for (let i = 0; i < N; i++) {
    await p.evaluate(t => render(t), i / FPS);
    if (errs.length) { ff.stdin.end(); await ffDone; return fail(`at frame ${i}: ` + errs.join('\n')); }
    const buf = await p.screenshot({type: 'jpeg', quality: 93});
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 300 === 0) console.log('frame', i, '/', N);
  }
  ff.stdin.end(); await ffDone;
  if (ffCode !== 0) return fail('ffmpeg exited with code ' + ffCode);
  const stats = {frames: N, fps: FPS, seconds: N / FPS, timeline_duration: D, partial: until < D, render_seconds_wall: (Date.now() - t0) / 1000, fonts, images: imgs};
  fs.writeFileSync('render_stats.json', JSON.stringify(stats, null, 1));
  await b.close();
  console.log('done', JSON.stringify({frames: N, seconds: N / FPS}));
})().catch(e => { console.error('RENDER FAILED: ' + (e.stack || e)); process.exit(1); });
