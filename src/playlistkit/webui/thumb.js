// Thumbnail maker: draws the playlist's YouTube thumbnail (1280 x 720) and saves it as thumb.jpg.
// A background made for the genre (or a picture from the playlist), the playlist name and the genre.
// Without a thumbnail, PlaylistKit makes one by itself once the playlist has a name, and keeps it in step with the
// name until you edit it here or choose your own picture.
(() => {
const W = 1280, H = 720, V = 2;  // V: design version; older made-by-itself thumbnails are redrawn with the new defaults
const LOOKS = {city: 'City night', neon: 'Synthwave', night: 'Night sky', sunset: 'Sunset', vinyl: 'Vinyl record',
  aurora: 'Aurora', ocean: 'Ocean', rain: 'Rainy window', forest: 'Forest', bokeh: 'Bokeh', festive: 'Festive', paper: 'Paper (light)'};
const GENRE_LOOK = {indie: 'night', ballad: 'rain', rnb: 'vinyl', sleep: 'aurora', meditation: 'aurora', trinh: 'paper',
  bolero: 'paper', acoustic: 'paper', piano: 'paper', classical: 'paper', jazz: 'vinyl', bossa: 'vinyl', country: 'forest',
  thieunhi: 'paper', indiefolk: 'forest', chill: 'ocean', deephouse: 'ocean', thai: 'ocean', lofi: 'rain', study: 'rain',
  slowed: 'rain', vpop: 'sunset', tiktok: 'sunset', usuk: 'sunset', latin: 'sunset', kpop: 'bokeh', cpop: 'bokeh', jpop: 'bokeh',
  anime: 'bokeh', douyin: 'bokeh', rock: 'neon', hiphop: 'city', rap: 'city', phonk: 'city', remix: 'neon', vinahouse: 'neon',
  edm: 'neon', synthwave: 'neon', gaming: 'neon', nightcore: 'neon', christmas: 'festive', tet: 'festive'};
// per background: the font it starts with, the title effect "Auto" means, the glow colour and the title gradient
const LOOK_FX = {
  night: {font: 'clean', effect: 'glow', glow: 'rgba(186,160,255,.85)', grad: ['#ffffff', '#d8ccff']},
  sunset: {font: 'clean', effect: 'gradient', glow: 'rgba(255,110,120,.65)', grad: ['#fff7dc', '#ffbf86']},
  neon: {font: 'heavy', effect: 'gradient', glow: 'rgba(255,60,170,.9)', grad: ['#ffe76a', '#ff4fa3']},
  city: {font: 'heavy', effect: 'gradient', glow: 'rgba(255,70,190,.9)', grad: ['#ffffff', '#8fe9ff']},
  vinyl: {font: 'narrow', effect: 'gradient', glow: 'rgba(255,140,80,.6)', grad: ['#ffffff', '#ffd29a']},
  aurora: {font: 'clean', effect: 'glow', glow: 'rgba(110,255,200,.75)', grad: ['#ffffff', '#c8fff0']},
  ocean: {font: 'clean', effect: 'shadow', glow: 'rgba(120,220,255,.7)', grad: ['#ffffff', '#bff0ff']},
  rain: {font: 'serif', effect: 'glow', glow: 'rgba(255,190,120,.7)', grad: ['#ffffff', '#ffe0b8']},
  forest: {font: 'clean', effect: 'shadow', glow: 'rgba(255,240,200,.6)', grad: ['#ffffff', '#e6f2d8']},
  bokeh: {font: 'clean', effect: 'glow', glow: 'rgba(255,150,210,.85)', grad: ['#ffffff', '#ffd6ec']},
  festive: {font: 'serif', effect: 'gradient', glow: 'rgba(255,190,90,.7)', grad: ['#fff6d8', '#ffc95e']},
  paper: {font: 'serif', effect: 'shadow', glow: 'rgba(0,0,0,0)', grad: ['#2b2520', '#6b4a3a']}};
const FONTS = {clean: ['Clean', s => `700 ${s}px "Segoe UI", "Segoe UI Emoji", sans-serif`],
  heavy: ['Heavy capitals', s => `900 ${s}px "Segoe UI Black", "Segoe UI", "Segoe UI Emoji", sans-serif`],
  serif: ['Serif italic', s => `italic 600 ${s}px Georgia, "Palatino Linotype", "Segoe UI Emoji", serif`],
  narrow: ['Narrow', s => `700 ${s}px Bahnschrift, "Segoe UI", "Segoe UI Emoji", sans-serif`],
  hand: ['Handwritten', s => `${s}px "Segoe Script", "Ink Free", "Segoe UI Emoji", cursive`]};
const EFFECTS = {auto: 'Auto (made for the background)', gradient: 'Gradient + glow', glow: 'Glow', outline: 'Outline', shadow: 'Shadow'};
const COLORS = {auto: 'Auto', '#ffffff': 'White', '#fff3df': 'Warm white', '#ffd27a': 'Gold', '#ffb3c7': 'Pink', '#9fe8ff': 'Cyan', '#2b2520': 'Dark'};
const LAYOUTS = {center: 'Center', left: 'Left', bottom: 'Bottom left'};
const UNDER = {none: 'Nothing', artists: 'Artists in this playlist', length: 'Length (e.g. 1 giờ 45 phút)', custom: 'Your own text'};

const genreOf = () => (G.genres || []).find(g => g.id === P.genre) || {name: P.genre_name || '', emoji: P.emoji || ''};
const nameNow = () => P.title_name || '';
function artists() {  // the first artist of each song, a few of them: "Juky San · RHYDER · Dangrangto"
  const seen = new Set(), out = [];
  for (const t of P.tracks || []) {
    const a = String(t.name || '').split(' - ')[0].split(/\s*(?:,|&|\s[xX×]\s|\sft\.?\s|\sfeat\.?\s)\s*/)[0].replace(/["“”]/g, '').trim();
    if (a && !seen.has(a.toLowerCase())) { seen.add(a.toLowerCase()); out.push(a.length > 24 ? a.slice(0, 23) + '…' : a); }
    if (out.length === 3) break;
  }
  return out.join(' · ');
}
const underText = d => ({artists: artists(), length: P.length_text || '', custom: d.sub || ''})[d.under] || '';
const autoKey = d => [nameNow(), P.genre, d.under, underText(d)].join('|');
function fresh() {
  const g = genreOf(), look = GENRE_LOOK[P.genre] || 'night';
  return {v: V, look, seed: 1 + Math.floor(Math.random() * 1e6), picture: '', dim: 0.45, blur: 6,
    title: nameNow() || P.name || '', under: 'none', sub: '', top: g.name ? `playlist · ${g.name}` : 'playlist',
    emoji: true, font: LOOK_FX[look].font, effect: 'auto', layout: 'center', color: 'auto'};
}
function upgrade(d) {  // a design saved by 0.2.5: its line under the title was free text (the length by default)
  if (!d || d.v === V) return d;
  return {...d, v: V, effect: 'auto', under: d.sub && !P.thumb_auto ? 'custom' : 'none'};
}

// ------------------------------------------------------------ drawing helpers
function rng(seed) { let a = seed >>> 0;
  return () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function vgrad(g, stops) { const gr = g.createLinearGradient(0, 0, 0, H); stops.forEach((c, i) => gr.addColorStop(i / (stops.length - 1), c)); g.fillStyle = gr; g.fillRect(0, 0, W, H); }
function glow(g, x, y, r, color) { const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, color); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(x - r, y - r, 2 * r, 2 * r); }
function dot(g, x, y, r) { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); }
function stars(g, r, n, maxY) { g.fillStyle = '#fff';
  for (let i = 0; i < n; i++) { g.globalAlpha = .25 + r() * .75; dot(g, r() * W, r() * maxY, r() < .06 ? 2.4 : .5 + r() * 1.3); } g.globalAlpha = 1; }
function blobs(g, r, n, colors, minR, maxR, blur, alpha, maxY = H) { g.save(); g.filter = `blur(${blur}px)`;
  for (let i = 0; i < n; i++) { g.globalAlpha = alpha * (.45 + r() * .55); g.fillStyle = colors[Math.floor(r() * colors.length)]; dot(g, r() * W, r() * maxY, minR + r() * (maxR - minR)); }
  g.restore(); }
function ridge(g, r, base, amp, color) { const p = [r() * 6, r() * 6, r() * 6]; g.beginPath(); g.moveTo(0, H);
  for (let x = 0; x <= W; x += 8) g.lineTo(x, base - amp * (.5 * Math.sin(x / 260 + p[0]) + .3 * Math.sin(x / 117 + p[1]) + .2 * Math.sin(x / 53 + p[2])));
  g.lineTo(W, H); g.closePath(); g.fillStyle = color; g.fill(); }
function pines(g, r, base, size, color, n) { g.fillStyle = color;
  for (let i = 0; i < n; i++) { const x = r() * (W + 80) - 40, h = size * (.6 + r() * .7), y = base + r() * size * .25;
    g.beginPath(); g.moveTo(x, y - h); g.lineTo(x - h * .28, y); g.lineTo(x + h * .28, y); g.closePath(); g.fill(); g.fillRect(x - 3, y, 6, h * .12); } }
function moon(g, x, y, rad) { glow(g, x, y, rad * 3.4, 'rgba(255,236,200,.20)');
  const c = document.createElement('canvas'); c.width = c.height = rad * 2 + 4; const m = c.getContext('2d');
  m.fillStyle = '#fff4dc'; dot(m, rad + 2, rad + 2, rad); m.globalCompositeOperation = 'destination-out'; dot(m, rad + 2 + rad * .48, rad + 2 - rad * .28, rad * .94);
  g.drawImage(c, x - rad - 2, y - rad - 2); }
function retroSun(g, x, y, rad, top, bottom, stripes) { glow(g, x, y, rad * 2.4, 'rgba(255,170,120,.28)');
  const c = document.createElement('canvas'); c.width = c.height = rad * 2; const m = c.getContext('2d');
  const gr = m.createLinearGradient(0, 0, 0, rad * 2); gr.addColorStop(0, top); gr.addColorStop(1, bottom); m.fillStyle = gr; dot(m, rad, rad, rad);
  if (stripes) { m.globalCompositeOperation = 'destination-out'; for (let i = 0; i < 7; i++) { const yy = rad * (1.05 + i * .14); m.fillRect(0, yy, rad * 2, 3 + i * 2.2); } }
  g.drawImage(c, x - rad, y - rad); }
function skyline(g, r, base, minH, maxH, color, lit) {  // one row of buildings with lit windows
  for (let x = -20; x < W + 20;) {
    const w = 46 + r() * 96, h = minH + r() * (maxH - minH), top = base - h;
    g.fillStyle = color; g.fillRect(x, top, w, H - top);
    if (r() < .18) g.fillRect(x + w * .45, top - 26 - r() * 30, 3, 40);  // antenna
    if (lit) for (let wy = top + 12; wy < H - 10; wy += 16) for (let wx = x + 8; wx < x + w - 10; wx += 13)
      if (r() < .3) { g.globalAlpha = lit * (.4 + r() * .6); g.fillStyle = ['#ffd98a', '#9fe8ff', '#ff9bd2'][Math.floor(r() * 3)]; g.fillRect(wx, wy, 6, 8); }
    g.globalAlpha = 1; x += w + 2 + r() * 10;
  }
}
function vinyl(g, x, y, R, r) {
  g.save(); g.beginPath(); g.arc(x, y, R, 0, Math.PI * 2); g.clip();
  const base = g.createRadialGradient(x, y, R * .3, x, y, R); base.addColorStop(0, '#18161b'); base.addColorStop(1, '#070608');
  g.fillStyle = base; g.fillRect(x - R, y - R, 2 * R, 2 * R);
  for (let rr = R * .34; rr < R - 4; rr += 3) { g.strokeStyle = `rgba(255,255,255,${.025 + r() * .045})`; g.lineWidth = 1; g.beginPath(); g.arc(x, y, rr, 0, Math.PI * 2); g.stroke(); }
  const sheen = g.createConicGradient(-0.6, x, y);
  [[0, 0], [.06, .22], [.14, 0], [.5, 0], [.56, .16], [.64, 0], [1, 0]].forEach(([s, a]) => sheen.addColorStop(s, `rgba(255,255,255,${a})`));
  g.fillStyle = sheen; g.fillRect(x - R, y - R, 2 * R, 2 * R); g.restore();
  g.strokeStyle = 'rgba(255,255,255,.14)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, R, 0, Math.PI * 2); g.stroke();
  const lab = g.createLinearGradient(x, y - R * .3, x, y + R * .3); lab.addColorStop(0, '#ffb05e'); lab.addColorStop(1, '#ff5f6d');
  g.fillStyle = lab; dot(g, x, y, R * .3); g.fillStyle = 'rgba(0,0,0,.25)'; dot(g, x, y, R * .3 * .55); g.fillStyle = '#0b0a0d'; dot(g, x, y, R * .025 + 4);
}
function vignette(g, strength) { const gr = g.createRadialGradient(W / 2, H / 2, H * .35, W / 2, H / 2, W * .72);
  gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, `rgba(0,0,0,${strength})`); g.fillStyle = gr; g.fillRect(0, 0, W, H); }
function grain(g, r, light) { g.fillStyle = light ? '#000' : '#fff';
  for (let i = 0; i < 9000; i++) { g.globalAlpha = .025 + r() * .035; g.fillRect(r() * W, r() * H, 1.4, 1.4); } g.globalAlpha = 1; }

// focal: where the moon / sun / record sits, away from the text
function art(g, look, r, focal) {
  const fx = focal === 'center' ? W * .5 : W * .76;
  if (look === 'night') {
    vgrad(g, ['#060a1d', '#161846', '#352a5e', '#6b3f6e']); stars(g, r, 320, H * .78);
    if (focal === 'center') moon(g, W * .92, H * .15, 50); else moon(g, W * .78, H * .26, 66);
    ridge(g, r, H * .80, 46, '#1d1538'); ridge(g, r, H * .9, 30, '#0c0a1c');
  } else if (look === 'sunset') {
    vgrad(g, ['#2a0f55', '#74287a', '#d24d6e', '#f7a35c']);
    retroSun(g, fx, H * .66, 200, '#ffe29a', '#ff6f91', true);
    ridge(g, r, H * .78, 40, '#46155a'); ridge(g, r, H * .9, 26, '#200a30');
  } else if (look === 'neon') {
    vgrad(g, ['#040010', '#160434', '#3a0a5c']); stars(g, r, 140, H * .5);
    const hz = H * .63; retroSun(g, fx, hz - 40, 175, '#ffd319', '#ff2975', true);
    ridge(g, r, hz + 2, 34, '#1a0530');
    const fl = g.createLinearGradient(0, hz, 0, H); fl.addColorStop(0, '#1d0038'); fl.addColorStop(1, '#05000c'); g.fillStyle = fl; g.fillRect(0, hz, W, H - hz);
    g.strokeStyle = 'rgba(255,60,200,.75)'; g.lineWidth = 2; g.shadowColor = '#ff3cc8'; g.shadowBlur = 12;
    for (let k = 1; k <= 12; k++) { const y = hz + (H - hz) * (k / 12) ** 2; g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
    for (let k = -14; k <= 14; k++) { g.beginPath(); g.moveTo(fx + k * 26, hz); g.lineTo(fx + k * 190, H); g.stroke(); }
    g.shadowBlur = 0; g.fillStyle = 'rgba(120,240,255,.9)'; g.fillRect(0, hz - 1, W, 2); glow(g, fx, hz, 520, 'rgba(120,220,255,.12)');
  } else if (look === 'city') {
    vgrad(g, ['#05071a', '#15103a', '#3a1a5a', '#8a2d6a']); stars(g, r, 130, H * .45);
    glow(g, fx, H * .56, 460, 'rgba(255,80,170,.32)');
    retroSun(g, fx, H * .5, 150, '#ffd6ec', '#ff5e9c', false);
    skyline(g, r, H * .8, 50, 170, '#2b1848', .18); skyline(g, r, H * .9, 50, 190, '#170c2c', .4); skyline(g, r, H * 1.01, 30, 130, '#07040e', .7);
    const fog = g.createLinearGradient(0, H * .7, 0, H); fog.addColorStop(0, 'rgba(255,80,170,0)'); fog.addColorStop(1, 'rgba(255,80,170,.18)');
    g.fillStyle = fog; g.fillRect(0, H * .7, W, H * .3);
  } else if (look === 'vinyl') {
    vgrad(g, ['#120c18', '#2a1530', '#5a2a3a']); blobs(g, r, 14, ['#ff9d6c', '#ffcf7a', '#ff6f91'], 30, 90, 30, .35);
    if (focal === 'center') { glow(g, W / 2, H * 1.05, 620, 'rgba(255,140,90,.25)'); vinyl(g, W / 2, H * 1.08, 440, r); }
    else { glow(g, W * .8, H * .5, 420, 'rgba(255,140,90,.25)'); vinyl(g, W * .8, H * .5, 300, r); }
  } else if (look === 'aurora') {
    vgrad(g, ['#020814', '#06203a', '#0b3a4a', '#123d3a']); stars(g, r, 260, H * .6);
    const bands = [['rgba(80,255,180,.55)', 90], ['rgba(60,200,255,.45)', 70], ['rgba(180,110,255,.4)', 60]];
    for (const [pass, blur] of [[0, 30], [1, 8]]) {
      g.save(); g.filter = `blur(${blur}px)`; g.globalCompositeOperation = 'lighter';
      bands.forEach(([c, lw], i) => { const p = rng(i + 11)() * 6; g.strokeStyle = c; g.lineWidth = pass ? 5 : lw; g.beginPath();
        for (let x = -40; x <= W + 40; x += 10) g.lineTo(x, H * (.22 + i * .09) + 70 * Math.sin(x / 230 + p) + 25 * Math.sin(x / 90 + p * 2)); g.stroke(); });
      g.restore(); }
    ridge(g, r, H * .8, 60, '#0a1a22'); ridge(g, r, H * .9, 34, '#03080c');
  } else if (look === 'ocean') {
    vgrad(g, ['#0a2540', '#13507a', '#2d8fb0', '#9ad7d9']); glow(g, fx, H * .3, 320, 'rgba(255,255,225,.33)');
    const cols = ['rgba(150,215,225,.35)', 'rgba(90,175,200,.45)', 'rgba(40,125,165,.6)', 'rgba(20,85,125,.75)', 'rgba(10,55,90,.9)'];
    cols.forEach((c, i) => { const base = H * (.56 + i * .09), p = r() * 6; g.beginPath(); g.moveTo(0, H);
      for (let x = 0; x <= W; x += 6) g.lineTo(x, base + 14 * Math.sin(x / (90 + i * 30) + p) + 7 * Math.sin(x / 37 + p * 2)); g.lineTo(W, H); g.closePath(); g.fillStyle = c; g.fill(); });
    g.fillStyle = '#fff'; for (let i = 0; i < 90; i++) { g.globalAlpha = .15 + r() * .5; dot(g, fx - 260 + r() * 520, H * (.56 + r() * .2), .6 + r() * 1.4); } g.globalAlpha = 1;
  } else if (look === 'rain') {
    vgrad(g, ['#121826', '#222e45', '#3a4a63']);
    blobs(g, r, 46, ['#ffb86b', '#6bd5ff', '#ff8fb1', '#ffe08a'], 14, 70, 20, .42);
    g.strokeStyle = '#fff'; g.lineWidth = 1.2;
    for (let i = 0; i < 380; i++) { const x = r() * W, y = r() * H, l = 18 + r() * 46; g.globalAlpha = .06 + r() * .16; g.beginPath(); g.moveTo(x, y); g.lineTo(x - l * .18, y + l); g.stroke(); }
    for (let i = 0; i < 70; i++) { const x = r() * W, y = r() * H, s = 2 + r() * 5; g.globalAlpha = .18; g.fillStyle = '#cfe6ff'; dot(g, x, y, s); g.globalAlpha = .35; g.fillStyle = '#fff'; dot(g, x - s * .3, y - s * .3, s * .35); }
    g.globalAlpha = 1;
  } else if (look === 'paper') {
    g.fillStyle = '#f4ecdd'; g.fillRect(0, 0, W, H);
    blobs(g, r, 7, ['#e8b4a0', '#a8c3a0', '#f2d38a', '#b9c7e4', '#d9b8d6'], 120, 260, 70, .6);
    g.strokeStyle = 'rgba(60,45,35,.18)'; g.lineWidth = 1.5;
    for (let i = 0; i < 3; i++) { const y = H * (.2 + r() * .6), p = r() * 6; g.beginPath(); for (let x = 0; x <= W; x += 10) g.lineTo(x, y + 18 * Math.sin(x / 140 + p)); g.stroke(); }
  } else if (look === 'forest') {
    vgrad(g, ['#0b1a2a', '#1c3440', '#40605a', '#9fb39a']); stars(g, r, 90, H * .35);
    glow(g, fx, H * .34, 260, 'rgba(255,240,210,.25)');
    pines(g, r, H * .72, 150, '#2c4a46', 34); g.fillStyle = 'rgba(200,220,215,.18)'; g.fillRect(0, H * .66, W, 60);
    pines(g, r, H * .86, 200, '#1a2f2e', 26); pines(g, r, H * 1.02, 280, '#0b1716', 18);
  } else if (look === 'festive') {
    vgrad(g, ['#2a0508', '#5c0d14', '#8a1a1f']); blobs(g, r, 40, ['#ffcc66', '#ff9966', '#fff0c2'], 10, 55, 16, .5);
    g.fillStyle = '#fff'; for (let i = 0; i < 260; i++) { g.globalAlpha = .3 + r() * .6; dot(g, r() * W, r() * H, .8 + r() * 2.4); } g.globalAlpha = 1;
  } else { // bokeh
    vgrad(g, ['#1d0b3a', '#5b1a6e', '#c2457a', '#f39c7a']); blobs(g, r, 34, ['#ffd1e8', '#ffe7a8', '#b8a6ff', '#ff9bb3', '#9ee6ff'], 30, 120, 24, .5);
  }
}
function picture(g, img, d) {
  const s = Math.max(W / img.naturalWidth, H / img.naturalHeight) * (d.blur > 0 ? 1.06 : 1);
  const w = img.naturalWidth * s, h = img.naturalHeight * s;
  g.save(); if (d.blur > 0) g.filter = `blur(${d.blur}px)`; g.drawImage(img, (W - w) / 2, (H - h) / 2, w, h); g.restore();
  g.fillStyle = `rgba(0,0,0,${d.dim})`; g.fillRect(0, 0, W, H);
}
function wrap(g, text, maxW) {
  const out = [];
  for (const para of String(text).split('\n')) { let line = '';
    for (const w of para.split(/\s+/).filter(Boolean)) { const t = line ? line + ' ' + w : w;
      if (!line || g.measureText(t).width <= maxW) line = t; else { out.push(line); line = w; } }
    if (line) out.push(line); }
  return out;
}
// the largest size at which the title fits the width, at most maxLines lines and maxH pixels high
function fit(g, text, font, maxW, maxLines, big, small, maxH, lhf) {
  for (let s = big; s >= small; s -= 4) { g.font = font(s); let lines = wrap(g, text, maxW);
    if (lines.length <= maxLines && lines.length * s * lhf <= maxH && lines.every(l => g.measureText(l).width <= maxW)) {
      for (let w = maxW - 20; lines.length > 1 && w > maxW * .5; w -= 20) {  // even out the lines
        const t = wrap(g, text, w); if (t.length !== lines.length) break; lines = t; }
      return {s, lines}; } }
  g.font = font(small); return {s: small, lines: wrap(g, text, maxW).slice(0, maxLines)};
}
function roundRect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function words(g, d, light) {
  const fx = LOOK_FX[d.look] || LOOK_FX.night, color = d.color === 'auto' ? (light ? '#2b2520' : '#ffffff') : d.color, dark = isDark(color);
  const effect = dark ? 'plain' : d.effect === 'auto' ? (d.picture ? 'outline' : fx.effect) : d.effect;
  const [, font] = FONTS[d.font] || FONTS.clean, caps = d.font === 'heavy', lhf = d.font === 'hand' ? 1.3 : 1.08;
  const title = caps ? d.title.toLocaleUpperCase('vi') : d.title;
  const left = d.layout !== 'center', x0 = d.layout === 'left' ? 96 : 80, maxW = d.layout === 'center' ? 1000 : d.layout === 'left' ? 620 : 940;
  const big = {center: 200, left: 170, bottom: 150}[d.layout] || 200, maxH = {center: 400, left: 440, bottom: 330}[d.layout] || 400;
  const t = fit(g, title, font, maxW, 3, big, 52, maxH, lhf), lh = t.s * lhf;
  const sub = underText(d), topText = [d.emoji ? genreOf().emoji : '', (d.top || '').toLocaleUpperCase('vi')].filter(Boolean).join('   ');
  const topH = topText ? 58 : 0, subH = sub ? 96 : 0, total = topH + t.lines.length * lh + subH;
  let y = d.layout === 'bottom' ? H - 64 - total : (H - total) / 2;
  if (d.layout === 'bottom' && !light) { const gr = g.createLinearGradient(0, y - 120, 0, H); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,.6)'); g.fillStyle = gr; g.fillRect(0, y - 120, W, H); }
  g.textAlign = left ? 'left' : 'center'; g.textBaseline = 'alphabetic'; const ax = left ? x0 : W / 2;
  const shadow = (c, blur, dy = 0) => { g.shadowColor = c; g.shadowBlur = blur; g.shadowOffsetY = dy; };
  const soft = () => shadow(dark ? 'rgba(0,0,0,0)' : 'rgba(0,0,0,.55)', dark ? 0 : 24, dark ? 0 : 3);
  if (topText) {
    g.font = '600 26px "Segoe UI", "Segoe UI Emoji", sans-serif'; g.letterSpacing = '6px'; g.fillStyle = color; g.globalAlpha = .88; soft();
    g.fillText(topText, ax + (left ? 0 : 3), y + 30);
    if (!left) {  // a short line each side: — PLAYLIST · RAP VIỆT —
      const w = g.measureText(topText).width / 2 + 22; shadow('rgba(0,0,0,0)', 0); g.fillRect(W / 2 - w - 46, y + 21, 46, 2); g.fillRect(W / 2 + w, y + 21, 46, 2); }
    g.letterSpacing = '0px'; g.globalAlpha = 1; y += topH;
  }
  g.font = font(t.s);
  const fill = (effect === 'gradient' && d.color === 'auto') ? (() => { const gr = g.createLinearGradient(0, y, 0, y + t.lines.length * lh);
    gr.addColorStop(0, fx.grad[0]); gr.addColorStop(1, fx.grad[1]); return gr; })() : color;
  const lines = (draw) => t.lines.forEach((l, i) => draw(l, ax, y + lh * (i + .8)));
  if (effect === 'outline') {
    g.lineJoin = 'round'; g.lineWidth = Math.max(6, t.s * .075); g.strokeStyle = 'rgba(8,5,16,.92)'; shadow('rgba(0,0,0,.6)', 30, 4);
    lines((l, x, yy) => g.strokeText(l, x, yy)); shadow('rgba(0,0,0,0)', 0); g.fillStyle = fill; lines((l, x, yy) => g.fillText(l, x, yy));
  } else if (effect === 'glow' || effect === 'gradient') {
    g.fillStyle = fill; shadow('rgba(0,0,0,.5)', 26, 4); lines((l, x, yy) => g.fillText(l, x, yy));
    shadow(fx.glow, effect === 'glow' ? 46 : 34); lines((l, x, yy) => g.fillText(l, x, yy));
    shadow('rgba(0,0,0,0)', 0); lines((l, x, yy) => g.fillText(l, x, yy));
  } else { g.fillStyle = fill; soft(); lines((l, x, yy) => g.fillText(l, x, yy)); }
  y += t.lines.length * lh;
  if (sub) { g.font = '600 36px "Segoe UI", "Segoe UI Emoji", sans-serif'; const w = Math.min(maxW, g.measureText(sub).width + 56), px = left ? x0 : W / 2 - w / 2;
    shadow('rgba(0,0,0,0)', 0); g.fillStyle = dark ? 'rgba(255,255,255,.55)' : 'rgba(0,0,0,.4)'; roundRect(g, px, y + 26, w, 60, 30); g.fill();
    g.strokeStyle = dark ? 'rgba(0,0,0,.15)' : 'rgba(255,255,255,.35)'; g.lineWidth = 1.5; g.stroke();
    g.fillStyle = color; g.textAlign = 'center'; g.fillText(sub, px + w / 2, y + 68, w - 40); }
  shadow('rgba(0,0,0,0)', 0);
}
function isDark(hex) { const n = parseInt(hex.slice(1), 16); return ((n >> 16) * .299 + (n >> 8 & 255) * .587 + (n & 255) * .114) < 110; }
const loadImg = url => new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = bad; i.src = url; });
const picUrl = ref => { const [area, ...rest] = ref.split('/'); return `/files/${P.id}/${area}/${encodeURIComponent(rest.join('/'))}`; };

async function draw(cv, d) {
  const g = cv.getContext('2d'), r = rng(d.seed); let light = d.look === 'paper' && !d.picture;
  g.save(); g.clearRect(0, 0, W, H);
  if (d.picture) { try { picture(g, await loadImg(picUrl(d.picture)), d); } catch { art(g, d.look, r, d.layout); light = d.look === 'paper'; } }
  else art(g, d.look, r, d.layout);
  if (!light) vignette(g, .45);
  grain(g, rng(d.seed + 7), light);
  g.restore(); words(g, d, light);
}
async function save(d, auto) {
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H; await draw(cv, d);
  const design = {...d, v: V, key: autoKey(d)};
  const r = await api('/api/thumb/save', {id: P.id, data: cv.toDataURL('image/jpeg', .92), design, auto});
  P.thumb = r.thumb; P.thumb_auto = auto; P.thumb_design = design;
}

// ------------------------------------------------------------ made by itself
let AUTO_BUSY = false;
window.thumbCheck = async (force) => {
  if (!P || AUTO_BUSY) return;
  if (!force && !nameNow()) return;  // wait for the playlist name (written after the remix)
  if (P.thumb && !P.thumb_auto) return;  // your own picture or your own design: never replaced
  const old = P.thumb_design || {};
  // an older made-by-itself design starts over with today's defaults (it keeps its stars and hills)
  const d = old.v === V ? {...fresh(), ...old} : {...fresh(), ...(old.seed ? {seed: old.seed} : {})};
  d.title = nameNow() || P.name || ''; delete d.key;
  if (P.thumb && old.v === V && old.key === autoKey(d)) return;
  AUTO_BUSY = true;
  try { await save(d, true); renderMeta(); } catch (e) { console.warn('thumbnail', e); } finally { AUTO_BUSY = false; }
};

// ------------------------------------------------------------ the window
document.body.insertAdjacentHTML('beforeend', `
<div class="modal" id="thDlg" hidden onclick="if(event.target===this)this.hidden=true">
  <div class="card" style="width:min(1180px,100%)">
    <h2>Thumbnail</h2>
    <div style="display:grid;grid-template-columns:1fr 300px;gap:18px;align-items:start">
      <div><canvas id="thCv" width="${W}" height="${H}" style="width:100%;aspect-ratio:16/9;border-radius:10px;border:1px solid var(--border);display:block"></canvas>
        <p class="faint small">1280 × 720, saved as thumb.jpg in the playlist folder. Make MP4 and the video editor use it.</p></div>
      <div class="col" style="gap:10px">
        <label class="field"><span>Background</span><select class="input sm" id="thLook"></select></label>
        <div class="row" id="thArtRow"><button class="btn small" onclick="thShuffle()">🎲 Shuffle</button><span class="faint small">new stars, lights and buildings</span></div>
        <div class="row" id="thPicRow" hidden><label class="field" style="flex:1"><span>Darken</span><input type="range" id="thDim" min="0" max="0.8" step="0.05"></label>
          <label class="field" style="flex:1"><span>Blur</span><input type="range" id="thBlur" min="0" max="30" step="1"></label></div>
        <label class="field"><span>Small line on top</span><input class="input sm" id="thTop"></label>
        <label class="chk small"><input type="checkbox" id="thEmoji"> genre emoji in the top line</label>
        <label class="field"><span>Title</span><textarea class="input" id="thTitle" rows="2" style="resize:vertical;font-family:inherit"></textarea></label>
        <label class="field"><span>Under the title</span><select class="input sm" id="thUnder"></select></label>
        <input class="input sm" id="thSub" placeholder="your text" hidden>
        <div class="row"><label class="field" style="flex:1"><span>Font</span><select class="input sm" id="thFont"></select></label>
          <label class="field" style="flex:1"><span>Text colour</span><select class="input sm" id="thColor"></select></label></div>
        <div class="row"><label class="field" style="flex:1"><span>Title effect</span><select class="input sm" id="thEffect"></select></label>
          <label class="field" style="flex:1"><span>Position</span><select class="input sm" id="thLayout"></select></label></div>
      </div>
    </div>
    <div class="row" style="margin-top:16px"><div class="spacer"></div><button class="btn" onclick="$('thDlg').hidden=true">Cancel</button>
      <button class="btn primary" onclick="thSave()">Save thumbnail</button></div>
  </div>
</div>`);
const opts = o => Object.entries(o).map(([k, v]) => `<option value="${esc(k)}">${esc(Array.isArray(v) ? v[0] : v)}</option>`).join('');
$('thFont').innerHTML = opts(FONTS); $('thColor').innerHTML = opts(COLORS); $('thLayout').innerHTML = opts(LAYOUTS);
$('thEffect').innerHTML = opts(EFFECTS); $('thUnder').innerHTML = opts(UNDER);
let TD = null, PICS = [];
function lookOptions() {
  $('thLook').innerHTML = `<optgroup label="Made by PlaylistKit">${opts(LOOKS)}</optgroup>` +
    (PICS.length ? `<optgroup label="Pictures in this playlist">${PICS.map(m => `<option value="pic:${esc(m.ref)}">${esc(m.name)}</option>`).join('')}</optgroup>` : '') +
    `<option value="choose">Choose a picture…</option>`;
}
function toForm(d) {
  lookOptions(); $('thLook').value = d.picture ? 'pic:' + d.picture : d.look;
  $('thDim').value = d.dim; $('thBlur').value = d.blur; $('thTop').value = d.top; $('thTitle').value = d.title; $('thSub').value = d.sub || '';
  $('thUnder').value = d.under; $('thSub').hidden = d.under !== 'custom'; $('thEffect').value = d.effect;
  $('thEmoji').checked = d.emoji; $('thFont').value = d.font; $('thColor').value = COLORS[d.color] ? d.color : 'auto'; $('thLayout').value = d.layout;
  $('thArtRow').hidden = !!d.picture; $('thPicRow').hidden = !d.picture;
}
let DRAWING = 0;
async function redraw() { const n = ++DRAWING; const cv = document.createElement('canvas'); cv.width = W; cv.height = H; await draw(cv, TD);
  if (n === DRAWING) $('thCv').getContext('2d').drawImage(cv, 0, 0); }
function fromForm() {
  const v = $('thLook').value;
  if (v.startsWith('pic:')) TD.picture = v.slice(4); else if (v !== 'choose') { TD.picture = ''; TD.look = v; }
  Object.assign(TD, {dim: +$('thDim').value, blur: +$('thBlur').value, top: $('thTop').value, title: $('thTitle').value, sub: $('thSub').value,
    under: $('thUnder').value, effect: $('thEffect').value, emoji: $('thEmoji').checked, font: $('thFont').value, color: $('thColor').value,
    layout: $('thLayout').value});
  $('thSub').hidden = TD.under !== 'custom'; $('thArtRow').hidden = !!TD.picture; $('thPicRow').hidden = !TD.picture; redraw();
}
['thDim', 'thBlur', 'thTop', 'thTitle', 'thSub'].forEach(id => $(id).addEventListener('input', fromForm));
['thEmoji', 'thFont', 'thColor', 'thLayout', 'thEffect', 'thUnder'].forEach(id => $(id).addEventListener('change', fromForm));
$('thLook').addEventListener('change', async () => {
  if ($('thLook').value !== 'choose') return fromForm();
  const r = await api('/api/media/import', {id: P.id}), ref = (r.refs || []).find(x => /\.(jpe?g|png|webp|bmp)$/i.test(x));
  if (ref) { await loadPics(); TD.picture = ref; } toForm(TD); redraw();
});
async function loadPics() { try { PICS = (await api('/api/media?id=' + encodeURIComponent(P.id))).filter(m => m.kind === 'image' && m.area !== 'thumb'); } catch { PICS = []; } }
window.openThumb = async () => {
  await loadPics();
  const saved = upgrade(P.thumb_design && P.thumb_design.look ? P.thumb_design : null);
  TD = {...fresh(), ...(saved || {})}; delete TD.key;
  if (P.thumb_auto || !saved || !saved.title) TD.title = nameNow() || P.name || '';
  if (TD.picture && !PICS.some(m => m.ref === TD.picture)) TD.picture = '';
  toForm(TD); $('thDlg').hidden = false; await redraw();
};
window.thShuffle = () => { TD.seed = 1 + Math.floor(Math.random() * 1e6); redraw(); };
window.thSave = async () => { await save(TD, false); $('thDlg').hidden = true; renderMeta(); };
busyWhile('openThumb', 'thSave');
if (P) thumbCheck();
})();
