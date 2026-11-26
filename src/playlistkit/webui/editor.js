// PlaylistKit video editor: media library, preview, timeline, export.
// Uses api(), $(), esc(), startJob(), P and refresh() from index.html.
(() => {
const css = `
#editor { position: fixed; inset: 0; z-index: 25; background: var(--bg); display: grid;
  grid-template-rows: 52px minmax(0, 1fr) 320px; }
#editor[hidden] { display: none; }
.ed-top { display: flex; align-items: center; gap: 10px; padding: 0 18px; border-bottom: 1px solid var(--border); }
.ed-main { display: grid; grid-template-columns: 270px minmax(0, 1fr) 290px; min-height: 0; }
.ed-media { border-right: 1px solid var(--border); padding: 14px; overflow: auto; }
.ed-media .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.mcard { border-radius: 10px; overflow: hidden; background: var(--surface); border: 1px solid var(--border); cursor: grab; position: relative; }
.mcard:hover { border-color: var(--border-2); }
.mcard .mt { aspect-ratio: 16/10; background: #1d1824 center/cover no-repeat; display: grid; place-items: center; position: relative; }
.mcard .mt canvas { width: 100%; height: 100%; }
.mcard .dur { position: absolute; left: 6px; bottom: 5px; font-size: 11px; background: rgba(0,0,0,.65); padding: 1px 6px; border-radius: 6px; }
.mcard .nm { font-size: 11.5px; padding: 6px 7px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mcard .del { position: absolute; right: 4px; top: 4px; display: none; }
.mcard:hover .del { display: inline-flex; }
.ed-center { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 14px 18px; min-width: 0; min-height: 0; }
.stage { position: relative; width: 100%; max-height: 100%; aspect-ratio: 16/9; background: #000; overflow: hidden; border-radius: 6px; container-type: size; }
.stage .layer { position: absolute; inset: 0; }
.stage img, .stage video { position: absolute; inset: 0; width: 100%; height: 100%; }
.stage .bg { object-fit: cover; filter: blur(18px) brightness(.85); transform: scale(1.08); }
.stage .ov { position: absolute; color: #fff; font-family: "Segoe UI", sans-serif; font-weight: 700; white-space: pre; line-height: 1.15; }
.stage .ov.box { background: rgba(0,0,0,.45); }
.stage .ov.shadow { text-shadow: 2px 2px 2px rgba(0,0,0,.7); }
.stage canvas.wave { position: absolute; left: 5%; width: 90%; }
.stage .pbar { position: absolute; left: 0; height: 6px; }
.ed-controls { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.ed-controls .time { font: 600 14px Consolas, monospace; min-width: 160px; text-align: center; }
.ed-props { border-left: 1px solid var(--border); padding: 14px; overflow: auto; }
.ed-props .field { margin-bottom: 10px; }
.ed-props .input { width: 100%; }
.ed-tl { border-top: 1px solid var(--border); display: grid; grid-template-rows: 40px minmax(0, 1fr); min-height: 0; }
.tl-bar { display: flex; align-items: center; gap: 8px; padding: 0 14px; border-bottom: 1px solid var(--border); }
.tl-scroll { overflow: auto; position: relative; }
.tl-inner { position: relative; min-height: 100%; }
.ruler { position: sticky; top: 0; height: 24px; z-index: 3; background: var(--bg); border-bottom: 1px solid var(--border); cursor: pointer; }
.ruler span { position: absolute; top: 5px; font-size: 11px; color: var(--faint); transform: translateX(-50%); }
.ruler i { position: absolute; bottom: 0; width: 1px; height: 6px; background: var(--border-2); }
.track { position: relative; height: 56px; border-bottom: 1px solid var(--border); }
.track.ov { height: 40px; } .track.au { height: 64px; }
.track .lbl { position: sticky; left: 0; z-index: 2; display: inline-block; font-size: 11px; color: var(--faint); padding: 3px 8px;
  background: rgba(13,11,16,.8); border-radius: 0 0 8px 0; pointer-events: none; }
.track.drop { background: rgba(224, 83, 61, .08); }
.clip { position: absolute; top: 6px; bottom: 6px; border-radius: 8px; overflow: hidden; cursor: grab; border: 2px solid transparent;
  background: #2b2433 center/auto 100% repeat-x; box-sizing: border-box; user-select: none; }
.clip.sel { border-color: #fff; }
.clip.au { background: #3b2f8f; } .clip.ov { background: #6b3a2a; } .clip.ov .cn { top: 4px; left: 110px; }
.clip .cn { position: absolute; left: 8px; top: 18px; font-size: 11.5px; text-shadow: 0 1px 2px #000; white-space: nowrap; pointer-events: none; }
.clip canvas { position: absolute; left: 0; top: 0; height: 100%; pointer-events: none; }
.clip .h { position: absolute; top: 0; bottom: 0; width: 8px; cursor: ew-resize; z-index: 2; }
.clip .h.l { left: 0; } .clip .h.r { right: 0; }
.clip .h:hover { background: rgba(255,255,255,.35); }
.playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: #fff; z-index: 5; pointer-events: none; }
.playhead::before { content: ""; position: absolute; left: -6px; top: 0; width: 14px; height: 14px; border-radius: 50%; background: #fff; }
#dropzone { position: fixed; inset: 0; z-index: 60; background: rgba(224, 83, 61, .18); border: 3px dashed var(--accent);
  display: grid; place-items: center; font-size: 22px; font-weight: 700; pointer-events: none; }
`;
const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

const html = `
<div class="ed-top">
  <button class="btn ghost" onclick="closeEditor()">← Back</button>
  <b id="edName"></b><span class="muted small" id="edSaved"></span>
  <div class="spacer"></div>
  <button class="btn small ghost" onclick="edUndo()" title="Undo (Ctrl+Z)">↶</button>
  <button class="btn small ghost" onclick="edRedo()" title="Redo (Ctrl+Y)">↷</button>
  <button class="btn small" onclick="edReset()" title="Thumbnail + mix + now playing">Reset layout</button>
  <button class="btn small" onclick="edFrame()">Check frame</button>
  <select class="input sm" id="edRes"><option>480p</option><option selected>720p</option><option>1080p</option></select>
  <button class="btn primary" onclick="edExport()">⬆ Export</button>
</div>
<div class="ed-main">
  <aside class="ed-media">
    <div class="row"><b style="flex:1">Media</b><button class="btn small primary" onclick="edImport()">Import</button></div>
    <div class="faint small" style="margin-top:6px">Drag files here from Explorer, then drag them onto the timeline.</div>
    <div class="grid" id="edMedia"></div>
  </aside>
  <div class="ed-center">
    <div class="stage" id="edStage"></div>
    <div class="ed-controls">
      <button class="btn small ghost" onclick="edSeek(0)" title="Start">⏮</button>
      <button class="btn small ghost" onclick="edSeek(ED.t - 5)">−5s</button>
      <button class="btn primary" id="edPlay" onclick="edToggle()" style="width:48px">▶</button>
      <button class="btn small ghost" onclick="edSeek(ED.t + 5)">+5s</button>
      <span class="time" id="edTime">0:00:00 / 0:00:00</span>
    </div>
  </div>
  <aside class="ed-props" id="edProps"></aside>
</div>
<div class="ed-tl">
  <div class="tl-bar">
    <button class="btn small" onclick="edSplit()" title="Split at the playhead (S)">✂ Split</button>
    <button class="btn small" onclick="edDelete()" title="Delete (Del)">🗑 Delete</button>
    <span class="faint">|</span>
    <button class="btn small" onclick="edAddOverlay('text')">+ Text</button>
    <button class="btn small" onclick="edAddOverlay('nowplaying')">+ Now playing</button>
    <button class="btn small" onclick="edAddOverlay('wave')">+ Sound wave</button>
    <button class="btn small" onclick="edAddOverlay('progress')">+ Progress bar</button>
    <div class="spacer"></div>
    <span class="faint small">Zoom</span><input type="range" id="edZoom" min="0" max="100" value="30" style="width:140px">
  </div>
  <div class="tl-scroll" id="edScroll"><div class="tl-inner" id="edInner">
    <div class="ruler" id="edRuler"></div>
    <div class="track vi" data-track="video"><span class="lbl">Video &amp; images</span></div>
    <div class="track ov" data-track="overlay"><span class="lbl">Text &amp; effects</span></div>
    <div class="track au" data-track="audio"><span class="lbl">Audio</span></div>
    <div class="playhead" id="edHead"></div>
  </div></div>
</div>`;

const ED = window.ED = {edit: null, media: [], byRef: {}, titles: [], mix: [], t: 0, playing: false, pps: 4, sel: null,
  hist: [], fut: [], peaks: {}, els: {}, startedAt: 0, t0: 0, saveTimer: null, dirty: false};
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{2B00}-\u{2BFF}]/gu;
const noEmoji = s => String(s || '').replace(EMOJI, '').replace(/\s+/g, ' ').trim();
const fmtT = s => { s = Math.max(0, s || 0); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = Math.floor(s % 60);
  return `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}`; };
const fmtS = s => { s = Math.max(0, s || 0); const m = Math.floor(s / 60), x = (s % 60).toFixed(1); return `${m}:${x.padStart(4, '0')}`; };
const parseS = v => { const p = String(v).trim().split(':').map(Number); return p.reduce((a, b) => a * 60 + b, 0) || 0; };
const uid = () => Math.random().toString(16).slice(2, 10);
const dur = () => Math.max(0, ...['video', 'overlay', 'audio'].flatMap(k => ED.edit[k].map(c => c.start + c.dur)));
const fileUrl = ref => { const [area, ...rest] = ref.split('/'); return `/files/${P.id}/${area}/${encodeURIComponent(rest.join('/'))}`; };
const clipKind = c => c.kind ? 'overlay' : (ED.byRef[c.media] || {}).kind;
const trackOf = c => ED.edit.video.includes(c) ? 'video' : ED.edit.audio.includes(c) ? 'audio' : 'overlay';

// ---------------------------------------------------------------- open / close
window.openEditor = async () => {
  let box = $('editor');
  if (!box) { box = document.createElement('section'); box.id = 'editor'; box.innerHTML = html; document.body.appendChild(box); wire(); }
  box.hidden = false; $('edName').textContent = P.name;
  const r = await api('/api/edit?id=' + encodeURIComponent(P.id));
  Object.assign(ED, {edit: r.edit, titles: r.titles, mix: r.mix, sel: null, hist: [], fut: [], t: 0, snap: JSON.stringify(r.edit)});
  setMedia(r.media); $('edRes').value = ED.edit.res;
  fitZoom(); renderAll();
};
window.closeEditor = async () => { pause(); await saveNow(); $('editor').hidden = true; Object.values(ED.els).forEach(e => e.pause && e.pause()); refresh(); };
window.edOnJobDone = async () => { if ($('editor') && !$('editor').hidden) { setMedia(await api('/api/media?id=' + encodeURIComponent(P.id))); renderMedia(); } };

function setMedia(list) { ED.media = list; ED.byRef = Object.fromEntries(list.map(m => [m.ref, m])); }

// ---------------------------------------------------------------- history + save
function commit() {
  ED.hist.push(ED.snap); ED.fut = []; if (ED.hist.length > 80) ED.hist.shift();
  ED.snap = JSON.stringify(ED.edit); scheduleSave(); renderAll();
}
function begin() { ED.snap = ED.snap || JSON.stringify(ED.edit); }
window.edUndo = () => { if (!ED.hist.length) return; ED.fut.push(JSON.stringify(ED.edit)); ED.edit = JSON.parse(ED.hist.pop()); ED.snap = JSON.stringify(ED.edit); ED.sel = null; scheduleSave(); renderAll(); };
window.edRedo = () => { if (!ED.fut.length) return; ED.hist.push(JSON.stringify(ED.edit)); ED.edit = JSON.parse(ED.fut.pop()); ED.snap = JSON.stringify(ED.edit); scheduleSave(); renderAll(); };
function scheduleSave() { ED.dirty = true; $('edSaved').textContent = ' · saving…'; clearTimeout(ED.saveTimer); ED.saveTimer = setTimeout(saveNow, 700); }
async function saveNow() {
  clearTimeout(ED.saveTimer); if (!ED.dirty || !ED.edit) return; ED.dirty = false;
  try { const r = await api('/api/edit/save', {id: P.id, edit: ED.edit}); $('edSaved').textContent = ' · saved'; ED.titles = (await api('/api/edit?id=' + encodeURIComponent(P.id))).titles; }
  catch (e) { $('edSaved').textContent = ' · not saved'; }
}
window.edReset = async () => { if (!confirm('Replace the timeline with: thumbnail + the mix + now playing?')) return;
  begin(); const r = await api('/api/edit/reset', {id: P.id}); ED.edit = r.edit; commit(); };

// ---------------------------------------------------------------- media panel
function renderMedia() {
  $('edMedia').innerHTML = ED.media.map(m => `<div class="mcard" draggable="true" data-ref="${esc(m.ref)}" title="${esc(m.name)}">
    <div class="mt" style="${m.kind === 'image' ? `background-image:url('${fileUrl(m.ref)}')` : m.kind === 'video' ? `background-image:url('/api/media/vthumb?id=${encodeURIComponent(P.id)}&ref=${encodeURIComponent(m.ref)}')` : ''}">
      ${m.kind === 'audio' ? `<canvas data-peaks="${esc(m.ref)}" width="220" height="120"></canvas>` : ''}
      ${m.dur && m.kind !== 'image' ? `<span class="dur">${fmtT(m.dur).replace(/^0:/, '')}</span>` : ''}</div>
    <div class="nm">${m.kind === 'audio' ? '♪ ' : m.kind === 'video' ? '▶ ' : ''}${esc(m.name)}</div>
    ${m.area === 'media' ? `<button class="btn small del" onclick="edDeleteMedia(event,'${esc(m.ref)}')">✕</button>` : ''}</div>`).join('')
    || '<p class="faint small">No media yet.</p>';
  document.querySelectorAll('#edMedia .mcard').forEach(el => el.addEventListener('dragstart', e => {
    e.dataTransfer.setData('text/x-ref', el.dataset.ref); e.dataTransfer.effectAllowed = 'copy'; }));
  document.querySelectorAll('#edMedia canvas[data-peaks]').forEach(async cv => {
    const pk = await getPeaks(cv.dataset.peaks); drawPeaks(cv, pk, 0, pk.length, '#8e84ff'); });
}
window.edDeleteMedia = async (e, ref) => { e.stopPropagation(); if (!confirm('Move this file to the Recycle Bin?')) return;
  await api('/api/media/delete', {id: P.id, ref}); begin();
  for (const k of ['video', 'audio']) ED.edit[k] = ED.edit[k].filter(c => c.media !== ref);
  commit(); setMedia(await api('/api/media?id=' + encodeURIComponent(P.id))); renderMedia(); };
window.edImport = async () => { const r = await api('/api/media/import', {id: P.id}); if (r.refs.length) { setMedia(await api('/api/media?id=' + encodeURIComponent(P.id))); renderMedia(); } };
async function getPeaks(ref) {
  if (!ED.peaks[ref]) ED.peaks[ref] = api(`/api/media/peaks?id=${encodeURIComponent(P.id)}&ref=${encodeURIComponent(ref)}`);
  return ED.peaks[ref];
}
function drawPeaks(cv, pk, i0, i1, color) {
  const g = cv.getContext('2d'), W = cv.width, H = cv.height, n = Math.max(1, i1 - i0);
  g.clearRect(0, 0, W, H); g.fillStyle = color;
  for (let x = 0; x < W; x++) {
    const a = i0 + Math.floor(x * n / W), b = Math.max(a + 1, i0 + Math.floor((x + 1) * n / W));
    let v = 0; for (let i = a; i < b && i < pk.length; i++) v = Math.max(v, pk[i]);
    const h = Math.max(1, v * H * .9); g.fillRect(x, (H - h) / 2, 1, h);
  }
}

// ---------------------------------------------------------------- uploads from Explorer
let dragDepth = 0;
function hasFiles(e) { return [...(e.dataTransfer?.types || [])].includes('Files'); }
document.addEventListener('dragenter', e => { if (!hasFiles(e) || $('editor')?.hidden !== false) return; e.preventDefault(); dragDepth++; showDrop(true); });
document.addEventListener('dragleave', e => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) showDrop(false); });
document.addEventListener('dragover', e => { if (hasFiles(e) && $('editor')?.hidden === false) e.preventDefault(); });
document.addEventListener('drop', async e => {
  if (!hasFiles(e) || $('editor')?.hidden !== false) return; e.preventDefault(); dragDepth = 0; showDrop(false);
  for (const f of e.dataTransfer.files) await upload(f);
  setMedia(await api('/api/media?id=' + encodeURIComponent(P.id))); renderMedia();
});
function showDrop(on) { let z = $('dropzone'); if (!z) { z = document.createElement('div'); z.id = 'dropzone'; z.textContent = 'Drop to add to this playlist'; document.body.appendChild(z); } z.hidden = !on; }
function upload(file) {
  return new Promise(res => {
    const x = new XMLHttpRequest();
    x.open('POST', `/api/media/upload?id=${encodeURIComponent(P.id)}&name=${encodeURIComponent(file.name)}`);
    x.setRequestHeader('X-PlaylistKit', '1');
    x.upload.onprogress = ev => { if (ev.lengthComputable) $('edSaved').textContent = ` · adding ${file.name} ${Math.round(ev.loaded * 100 / ev.total)}%`; };
    x.onload = () => { const r = JSON.parse(x.responseText || '{}'); $('edSaved').textContent = r.error ? ' · ' + r.error : ` · added ${file.name}`; res(r); };
    x.onerror = () => { $('edSaved').textContent = ' · upload failed'; res({}); };
    x.send(file);
  });
}

// ---------------------------------------------------------------- timeline
function fitZoom() { const W = $('edScroll').clientWidth - 40; const d = Math.max(30, dur()); ED.pps = Math.max(0.02, W / d);
  $('edZoom').value = Math.round(zoomToSlider(ED.pps)); }
const sliderToZoom = v => 0.01 * Math.pow(10, v / 100 * 4.3);   // 0.01 .. 200 px per second
const zoomToSlider = z => Math.log10(z / 0.01) / 4.3 * 100;
function renderTimeline() {
  const total = Math.max(dur() + 30, ($('edScroll').clientWidth - 20) / ED.pps);
  const W = total * ED.pps; $('edInner').style.width = W + 'px';
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
  const step = steps.find(s => s * ED.pps >= 70) || 3600;
  let r = ''; for (let s = 0; s <= total; s += step) r += `<i style="left:${s * ED.pps}px"></i><span style="left:${s * ED.pps}px">${fmtT(s).replace(/^0:/, '')}</span>`;
  $('edRuler').innerHTML = r;
  for (const tr of document.querySelectorAll('#editor .track')) {
    tr.querySelectorAll('.clip').forEach(c => c.remove());
    const k = tr.dataset.track;
    if (k === 'overlay') {  // overlapping texts and effects get their own lanes
      const lanes = [];
      for (const c of [...ED.edit.overlay].sort((a, b) => a.start - b.start)) {
        let i = lanes.findIndex(end => end <= c.start + 0.01); if (i < 0) { i = lanes.length; lanes.push(0); }
        lanes[i] = c.start + c.dur; const el = clipEl(c, k); el.style.top = (4 + i * 30) + 'px'; el.style.bottom = 'auto'; el.style.height = '26px';
        tr.appendChild(el);
      }
      tr.style.height = Math.max(40, lanes.length * 30 + 8) + 'px';
      continue;
    }
    for (const c of ED.edit[k]) tr.appendChild(clipEl(c, k));
  }
  placeHead();
}
function clipEl(c, k) {
  const el = document.createElement('div'); el.className = `clip ${k === 'audio' ? 'au' : k === 'overlay' ? 'ov' : ''} ${ED.sel === c ? 'sel' : ''}`;
  el.style.left = c.start * ED.pps + 'px'; el.style.width = Math.max(4, c.dur * ED.pps) + 'px';
  const m = ED.byRef[c.media] || {};
  let label = k === 'overlay' ? ({text: 'T  ' + (c.text || 'Text'), nowplaying: '♪ Now playing', wave: '〰 Sound wave', progress: '▬ Progress bar'}[c.kind]) : (m.name || c.media);
  el.innerHTML = `<span class="cn">${esc(label)}</span><div class="h l"></div><div class="h r"></div>`;
  if (k === 'video') el.style.backgroundImage = m.kind === 'image' ? `url('${fileUrl(c.media)}')` : `url('/api/media/vthumb?id=${encodeURIComponent(P.id)}&ref=${encodeURIComponent(c.media)}')`;
  if (k === 'audio') {
    const w = Math.min(8000, Math.max(4, Math.round(c.dur * ED.pps)));
    const cv = document.createElement('canvas'); cv.width = w; cv.height = 50; cv.style.width = Math.max(4, c.dur * ED.pps) + 'px';
    el.prepend(cv);
    getPeaks(c.media).then(pk => drawPeaks(cv, pk, Math.floor(c.in * 10), Math.floor((c.in + c.dur) * 10), 'rgba(255,255,255,.55)'));
  }
  el.addEventListener('pointerdown', e => dragClip(e, c, k, el));
  return el;
}
function snapPoints(except) {
  const pts = [0, ED.t];
  for (const k of ['video', 'overlay', 'audio']) for (const c of ED.edit[k]) if (c !== except) pts.push(c.start, c.start + c.dur);
  return pts;
}
function snap(t, except) { const tol = 8 / ED.pps; let best = t, d = tol;
  for (const p of snapPoints(except)) if (Math.abs(p - t) < d) { d = Math.abs(p - t); best = p; } return best; }
function dragClip(e, c, k, el) {
  e.preventDefault(); e.stopPropagation(); ED.sel = c; begin();
  const mode = e.target.classList.contains('l') ? 'l' : e.target.classList.contains('r') ? 'r' : 'move';
  const x0 = e.clientX, s0 = c.start, d0 = c.dur, in0 = c.in || 0;
  const mdur = (ED.byRef[c.media] || {}).dur || 0, limited = k !== 'overlay' && clipKind(c) !== 'image' && mdur > 0;
  let moved = false;
  const onMove = ev => {
    const dt = (ev.clientX - x0) / ED.pps; if (Math.abs(ev.clientX - x0) > 2) moved = true;
    if (mode === 'move') { let ns = Math.max(0, s0 + dt); const se = snap(ns + c.dur, c) - c.dur; ns = snap(ns, c); c.start = Math.abs(ns - (s0 + dt)) <= Math.abs(se - (s0 + dt)) ? ns : Math.max(0, se); }
    else if (mode === 'r') { let end = snap(s0 + d0 + dt, c); let nd = Math.max(0.2, end - s0); if (limited) nd = Math.min(nd, mdur - in0); c.dur = nd; }
    else { let ns = snap(s0 + dt, c); ns = Math.max(0, Math.min(ns, s0 + d0 - 0.2)); if (limited) ns = Math.max(ns, s0 - in0);
      const shift = ns - s0; c.start = ns; c.dur = d0 - shift; if (k !== 'overlay') c.in = Math.max(0, in0 + shift); }
    el.style.left = c.start * ED.pps + 'px'; el.style.width = Math.max(4, c.dur * ED.pps) + 'px';
    renderStage(); renderTime();
  };
  const onUp = () => { removeEventListener('pointermove', onMove); removeEventListener('pointerup', onUp);
    if (moved) commit(); else { ED.snap = JSON.stringify(ED.edit); renderAll(); } };
  addEventListener('pointermove', onMove); addEventListener('pointerup', onUp);
  renderProps(); document.querySelectorAll('#editor .clip').forEach(x => x.classList.remove('sel')); el.classList.add('sel');
}
function placeHead() { $('edHead').style.left = ED.t * ED.pps + 'px'; }
function wire() {
  $('edZoom').addEventListener('input', () => { const mid = ED.t; ED.pps = sliderToZoom(+$('edZoom').value); renderTimeline();
    $('edScroll').scrollLeft = Math.max(0, mid * ED.pps - $('edScroll').clientWidth / 2); });
  $('edRes').addEventListener('change', () => { begin(); ED.edit.res = $('edRes').value; commit(); });
  const seekAt = e => { const r = $('edInner').getBoundingClientRect(); edSeek((e.clientX - r.left) / ED.pps); };
  $('edRuler').addEventListener('pointerdown', e => { seekAt(e); const mv = ev => seekAt(ev); addEventListener('pointermove', mv);
    addEventListener('pointerup', () => removeEventListener('pointermove', mv), {once: true}); });
  for (const tr of document.querySelectorAll('#editor .track')) {
    tr.addEventListener('pointerdown', e => { if (e.target === tr) { ED.sel = null; seekAt(e); renderProps(); renderTimeline(); } });
    tr.addEventListener('dragover', e => { if ([...e.dataTransfer.types].includes('text/x-ref')) { e.preventDefault(); tr.classList.add('drop'); } });
    tr.addEventListener('dragleave', () => tr.classList.remove('drop'));
    tr.addEventListener('drop', e => { tr.classList.remove('drop'); const ref = e.dataTransfer.getData('text/x-ref'); if (!ref) return; e.preventDefault();
      const r = $('edInner').getBoundingClientRect(); addMedia(ref, tr.dataset.track, (e.clientX - r.left) / ED.pps); });
  }
  addEventListener('keydown', e => {
    if ($('editor').hidden || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (e.code === 'Space') { e.preventDefault(); edToggle(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') edDelete();
    else if (e.key === 's' || e.key === 'S') edSplit();
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? edRedo() : edUndo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); edRedo(); }
    else if (e.key === 'ArrowLeft') edSeek(ED.t - (e.shiftKey ? 10 : 1));
    else if (e.key === 'ArrowRight') edSeek(ED.t + (e.shiftKey ? 10 : 1));
  });
  addEventListener('resize', () => { if (!$('editor').hidden) renderTimeline(); });
}
function addMedia(ref, track, at) {
  const m = ED.byRef[ref]; if (!m) return;
  if (m.kind === 'audio' && track !== 'audio') track = 'audio';
  if (m.kind === 'image' && track !== 'video') track = 'video';
  if (m.kind === 'video' && track === 'overlay') track = 'video';
  begin(); at = snap(Math.max(0, at));
  const audioEnd = Math.max(0, ...ED.edit.audio.map(c => c.start + c.dur));
  if (track === 'audio') ED.edit.audio.push(ED.sel = {id: uid(), media: ref, start: at, in: 0, dur: m.dur || 10, volume: 1, fade_in: 0, fade_out: 0});
  else ED.edit.video.push(ED.sel = {id: uid(), media: ref, start: at, in: 0,
    dur: m.kind === 'image' ? (audioEnd > at + 1 ? audioEnd - at : 10) : (m.dur || 10), fit: 'blur', zoom: false});
  commit();
}
window.edAddOverlay = kind => {
  begin(); const d = dur() || 10;
  const o = {id: uid(), kind, start: kind === 'text' ? ED.t : 0, dur: kind === 'text' ? 8 : d, text: kind === 'text' ? 'Your title' : '',
    pos: {text: 'top', nowplaying: 'bottom-left', wave: 'bottom', progress: 'bottom'}[kind], size: {text: 7, nowplaying: 3.6, wave: 4, progress: 4}[kind],
    color: '#ffffff', box: kind === 'nowplaying'};
  ED.edit.overlay.push(o); ED.sel = o; commit();
};
window.edDelete = () => { const c = ED.sel; if (!c) return; begin(); const k = trackOf(c); ED.edit[k] = ED.edit[k].filter(x => x !== c); ED.sel = null; commit(); };
window.edSplit = () => {
  const c = ED.sel || [...ED.edit.video, ...ED.edit.audio, ...ED.edit.overlay].find(x => ED.t > x.start + .1 && ED.t < x.start + x.dur - .1);
  if (!c || !(ED.t > c.start + .1 && ED.t < c.start + c.dur - .1)) return;
  begin(); const k = trackOf(c), cut = ED.t - c.start;
  const b = {...c, id: uid(), start: ED.t, dur: c.dur - cut}; if ('in' in c && k !== 'overlay') b.in = (c.in || 0) + cut;
  if (k === 'audio') { b.fade_in = 0; c.fade_out = 0; }
  c.dur = cut; ED.edit[k].splice(ED.edit[k].indexOf(c) + 1, 0, b); ED.sel = b; commit();
};

// ---------------------------------------------------------------- properties
function renderProps() {
  const c = ED.sel, box = $('edProps');
  if (!c) { box.innerHTML = `<h3>Timeline</h3><p class="muted small">Drag media from the left onto a track. Click a clip to edit it.
    Drag a clip to move it, drag its edges to trim. <b>Space</b> play/pause, <b>S</b> split, <b>Del</b> delete, <b>Ctrl+Z</b> undo.</p>
    <p class="muted small">Length: <b>${fmtT(dur())}</b></p>`; return; }
  const k = trackOf(c), m = ED.byRef[c.media] || {};
  const num = (label, key, val, extra = '') => `<label class="field"><span>${label}</span><input class="input sm" data-k="${key}" value="${val}" ${extra}></label>`;
  let h = `<h3>${k === 'overlay' ? {text: 'Text', nowplaying: 'Now playing', wave: 'Sound wave', progress: 'Progress bar'}[c.kind] : esc(m.name || c.media)}</h3>`;
  h += `<div class="grid2" style="gap:8px">${num('Start', 'start', fmtS(c.start))}${num('Length', 'dur', fmtS(c.dur))}</div>`;
  if (k === 'video') {
    h += `<label class="field"><span>Fit</span><select class="input sm" data-k="fit">${['blur', 'fill', 'fit'].map(f => `<option ${c.fit === f ? 'selected' : ''} value="${f}">${{blur: 'Fit on a blurred copy', fill: 'Fill (crop)', fit: 'Fit (black bars)'}[f]}</option>`).join('')}</select></label>`;
    if (m.kind === 'image') h += `<label class="chk small"><input type="checkbox" data-k="zoom" ${c.zoom ? 'checked' : ''}> Slow zoom (exports at 25 fps, slower)</label>`;
  } else if (k === 'audio') {
    h += num('Start inside the file', 'in', fmtS(c.in));
    h += `<label class="field"><span>Volume ${Math.round(c.volume * 100)}%</span><input type="range" min="0" max="200" value="${Math.round(c.volume * 100)}" data-k="volume"></label>`;
    h += `<div class="grid2" style="gap:8px">${num('Fade in (s)', 'fade_in', c.fade_in)}${num('Fade out (s)', 'fade_out', c.fade_out)}</div>`;
  } else {
    if (c.kind === 'text' || c.kind === 'nowplaying') h += `<label class="field"><span>${c.kind === 'text' ? 'Text' : 'Before the song name (optional)'}</span><textarea class="input" rows="2" data-k="text">${esc(c.text)}</textarea></label>
      <p class="faint small" style="margin-top:-4px">Emoji are not drawn in the video.</p>`;
    h += `<label class="field"><span>Position</span><select class="input sm" data-k="pos">${['top-left', 'top', 'top-right', 'center', 'bottom-left', 'bottom', 'bottom-right'].map(p => `<option ${c.pos === p ? 'selected' : ''}>${p}</option>`).join('')}</select></label>`;
    h += `<div class="grid2" style="gap:8px">${num('Size', 'size', c.size, 'type="number" step="0.2" min="1" max="20"')}<label class="field"><span>Colour</span><input type="color" class="input sm" data-k="color" value="${c.color}"></label></div>`;
    if (c.kind === 'text' || c.kind === 'nowplaying') h += `<label class="chk small"><input type="checkbox" data-k="box" ${c.box ? 'checked' : ''}> Dark box behind the text</label>`;
  }
  h += `<div class="row" style="margin-top:14px"><button class="btn small" onclick="edSplit()">✂ Split</button><button class="btn small danger" onclick="edDelete()">Delete</button></div>`;
  box.innerHTML = h;
  box.querySelectorAll('[data-k]').forEach(inp => inp.addEventListener('change', () => {
    begin(); const key = inp.dataset.k;
    if (['start', 'dur', 'in'].includes(key)) c[key] = Math.max(key === 'dur' ? 0.2 : 0, parseS(inp.value));
    else if (key === 'volume') c.volume = +inp.value / 100;
    else if (['fade_in', 'fade_out', 'size'].includes(key)) c[key] = Math.max(0, +inp.value || 0);
    else if (inp.type === 'checkbox') c[key] = inp.checked;
    else c[key] = inp.value;
    commit(); renderProps();
  }));
}

// ---------------------------------------------------------------- preview + playback
function active(list, t) { return list.filter(c => t >= c.start && t < c.start + c.dur); }
function mediaEl(c) {
  const k = clipKind(c), key = c.id;
  if (!ED.els[key] || ED.els[key].dataset.src !== c.media) {
    const el = document.createElement(k === 'audio' ? 'audio' : 'video'); el.preload = 'auto'; el.src = fileUrl(c.media); el.dataset.src = c.media;
    if (k === 'video') el.muted = true;
    ED.els[key] = el;
  }
  return ED.els[key];
}
function renderStage() {
  const t = ED.t, stage = $('edStage');
  const v = active(ED.edit.video, t).pop();
  let h = '';
  if (v) {
    const k = clipKind(v), url = fileUrl(v.media), prog = (t - v.start) / v.dur;
    const z = v.zoom && k === 'image' ? `transform:scale(${1 + 0.12 * prog})` : '';
    if (k === 'image') {
      if (v.fit === 'blur') h += `<img class="bg" src="${url}"><img src="${url}" style="object-fit:contain;${z}">`;
      else h += `<img src="${url}" style="object-fit:${v.fit === 'fill' ? 'cover' : 'contain'};${z}">`;
    } else h += `<div class="layer" id="edVid"></div>`;
  }
  const H = stage.clientHeight, W = stage.clientWidth;
  for (const o of active(ED.edit.overlay, t)) {
    const fs = Math.max(6, H * o.size / 100), m = H * 0.05;
    const [vert, horiz0] = o.pos.includes('-') ? o.pos.split('-') : (['left', 'right'].includes(o.pos) ? ['center', o.pos] : [o.pos, 'center']);
    const horiz = horiz0 || 'center';
    const pos = `${horiz === 'left' ? `left:${m}px;` : horiz === 'right' ? `right:${m}px;` : 'left:50%;transform:translateX(-50%);'}` +
      `${vert === 'top' ? `top:${m}px;` : vert === 'bottom' ? `bottom:${m}px;` : `top:50%;transform:translate(${horiz === 'center' ? '-50%' : '0'},-50%);`}`;
    if (o.kind === 'text' || o.kind === 'nowplaying') {
      let text = o.text;
      if (o.kind === 'nowplaying') { const s = ED.titles.find(([a, b]) => t >= a && t < b); if (!s) continue; text = (o.text ? o.text + ' ' : '') + s[2]; }
      text = noEmoji(text); if (!text) continue;
      h += `<div class="ov ${o.box ? 'box' : 'shadow'}" style="${pos}font-size:${fs}px;color:${o.color};padding:${o.box ? fs / 3 : 0}px">${esc(text)}</div>`;
    } else if (o.kind === 'progress') {
      const bh = Math.max(3, H * o.size / 400), p = (t - o.start) / o.dur;
      h += `<div class="pbar" style="${o.pos.startsWith('top') ? 'top:0' : 'bottom:0'};width:${p * 100}%;height:${bh}px;background:${o.color};opacity:.85"></div>`;
    } else if (o.kind === 'wave') {
      const wh = Math.max(20, H * o.size / 100 * 2.5);
      const y = o.pos.startsWith('top') ? `top:${H * .06}px` : o.pos === 'center' ? `top:${(H - wh) / 2}px` : `bottom:${H * .15}px`;
      h += `<canvas class="wave" data-color="${o.color}" width="${Math.round(W * .9)}" height="${Math.round(wh)}" style="${y};height:${wh}px"></canvas>`;
    }
  }
  stage.innerHTML = h;
  if (v && clipKind(v) === 'video') {
    const el = mediaEl(v); el.style.objectFit = v.fit === 'fill' ? 'cover' : 'contain'; $('edVid').appendChild(el);
    const want = (v.in || 0) + t - v.start; if (Math.abs(el.currentTime - want) > 0.3) el.currentTime = want;
    if (ED.playing && el.paused) el.play().catch(() => {}); if (!ED.playing && !el.paused) el.pause();
  }
  stage.querySelectorAll('canvas.wave').forEach(cv => drawWave(cv, t));
}
function drawWave(cv, t) {
  const a = active(ED.edit.audio, t)[0]; const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height);
  if (!a || !ED.peaks[a.media]) { if (a) getPeaks(a.media); return; }
  ED.peaks[a.media].then(pk => {
    const pos = ((a.in || 0) + t - a.start) * 10, W = cv.width, H = cv.height; g.clearRect(0, 0, W, H);
    g.fillStyle = cv.dataset.color; g.globalAlpha = .85;
    for (let x = 0; x < W; x += 3) { const i = Math.floor(pos - 20 + x * 40 / W); const v = (pk[i] || 0) * (0.6 + 0.4 * Math.abs(Math.sin(x * .7 + t * 9)));
      const h = Math.max(1, v * H * .95); g.fillRect(x, (H - h) / 2, 2, h); }
  });
}
function syncAudio() {
  const t = ED.t;
  for (const c of ED.edit.audio) {
    const el = mediaEl(c), on = ED.playing && t >= c.start && t < c.start + c.dur;
    if (!on) { if (!el.paused) el.pause(); continue; }
    const want = c.in + t - c.start;
    if (el.paused) { el.currentTime = want; el.play().catch(() => {}); }
    else if (Math.abs(el.currentTime - want) > 0.35) el.currentTime = want;
    let f = 1; const into = t - c.start, left = c.start + c.dur - t;
    if (c.fade_in > 0 && into < c.fade_in) f = into / c.fade_in;
    if (c.fade_out > 0 && left < c.fade_out) f = Math.min(f, left / c.fade_out);
    el.volume = Math.max(0, Math.min(1, c.volume * f));
  }
}
function renderTime() { $('edTime').textContent = `${fmtT(ED.t)} / ${fmtT(dur())}`; placeHead(); }
function renderAll() { renderMedia(); renderTimeline(); renderProps(); renderStage(); renderTime(); }
function tick() {
  if (!ED.playing) return;
  ED.t = ED.t0 + (performance.now() - ED.startedAt) / 1000;
  if (ED.t >= dur()) { ED.t = dur(); pause(); }
  syncAudio(); renderStage(); renderTime();
  const sc = $('edScroll'), x = ED.t * ED.pps; if (x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = x - 80;
  requestAnimationFrame(tick);
}
function pause() { ED.playing = false; $('edPlay') && ($('edPlay').textContent = '▶'); syncAudio(); renderStage(); }
window.edToggle = () => { if (ED.playing) return pause(); if (ED.t >= dur() - 0.05) ED.t = 0;
  ED.playing = true; ED.t0 = ED.t; ED.startedAt = performance.now(); $('edPlay').textContent = '❚❚'; requestAnimationFrame(tick); };
window.edSeek = t => { ED.t = Math.max(0, Math.min(dur(), t)); if (ED.playing) { ED.t0 = ED.t; ED.startedAt = performance.now(); Object.values(ED.els).forEach(e => e.pause()); }
  syncAudio(); renderStage(); renderTime(); };

// ---------------------------------------------------------------- export
window.edExport = async () => { await saveNow(); if (!dur()) return toast('The timeline is empty.');
  pause(); startJob('/api/edit/export', {id: P.id, edit: ED.edit}); };
window.edFrame = async () => {
  await saveNow(); const r = await api('/api/edit/frame', {id: P.id, edit: ED.edit, at: ED.t});
  $('notesTitle').textContent = `Exported frame at ${fmtT(ED.t)}`;
  $('notesBody').innerHTML = `<img src="${r.url}" style="width:100%;border-radius:8px">`; $('notes').hidden = false;
};
})();
