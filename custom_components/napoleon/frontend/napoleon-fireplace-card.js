/*
 * Napoleon Fireplace card for Home Assistant.
 *
 * Shipped with (and auto-registered by) the hass-napoleon integration, so no
 * Lovelace resource needs to be added by hand:
 *
 *   type: custom:napoleon-fireplace-card
 *   entity: switch.living_room_fireplace   # any entity of the fireplace device
 *
 * The rest of the fireplace's entities are discovered from the device via
 * their translation keys. The flames are a WebGL fragment shader driven by
 * the fireplace's real settings (flame height, orange/yellow intensity, ember
 * bed colour/brightness, top light, colour cycling).
 */
(() => {
  const CARD_TAG = "napoleon-fireplace-card";
  if (customElements.get(CARD_TAG)) return;

  const ROLES = {
    climate: "fireplace",
    power: "fireplace_power",
    ember: "ember_bed",
    top: "top_light",
    flame_speed: "flame_speed",
    orange: "orange_flame",
    yellow: "yellow_flame",
    favourite: "favourite",
    eco: "eco_mode",
    boost: "boost_mode",
    ember_cycle: "ember_bed_cycling",
    top_cycle: "top_light_cycling",
  };

  const PRESETS = [
    { option: "partytime", name: "Party Time", icon: "mdi:party-popper" },
    { option: "campfirewarmth", name: "Campfire", icon: "mdi:campfire" },
    { option: "summerday", name: "Summer Day", icon: "mdi:weather-sunny" },
    { option: "glowingsunset", name: "Sunset", icon: "mdi:weather-sunset" },
  ];
  const SWATCHES = ["#ff5a1e", "#ff2a00", "#ffb020", "#ffffff", "#3a7bff", "#00c8ff", "#b040ff", "#30e070"];
  const EMBER_MAX = 5; // ember bed brightness steps on the device
  const PENDING_MS = 12000; // how long an optimistic value wins over HA state
  const MAX_FPS = 40;

  // ───────────────────────────── shader ─────────────────────────────
  const VERT = `attribute vec2 aPos; void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

  const FRAG = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2  uRes;
uniform float uTime;      // flame time (scaled by flame speed)
uniform float uClock;     // wall-clock seconds (light cycling, twinkle)
uniform float uOn;        // 0..1 power fade
uniform float uHeight;    // flame height, fraction of firebox
uniform float uOrange;    // 0..1
uniform float uYellow;    // 0..1
uniform vec3  uEmber;     // ember bed colour 0..1
uniform float uEmberBri;  // 0..1
uniform float uEmberCycle;
uniform vec3  uTop;
uniform float uTopCycle;
uniform float uMedia;     // 0 logs, 1 crystals

// small-magnitude hash: stays stable when GPUs fuse/reorder math on large lattice coords
float h21(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), u.x),
             mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p){
  float s = 0.0, a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 5; i++){ s += a * vnoise(p); p = m * p; a *= 0.5; }
  return s;
}
vec3 hsv2rgb(vec3 c){
  vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0);
  return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}
float sdCap(vec2 p, vec2 a, vec2 b, float r, out float h){
  vec2 pa = p - a, ba = b - a;
  h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}

float sdTaper(vec2 p, vec2 a, vec2 b, float ra, float rb, out float h){
  vec2 pa = p - a, ba = b - a;
  h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - mix(ra, rb, h);
}
// One lattice of flame tongues: each cell holds a tongue that tapers to a tip.
float tongues(float x, float y, float t, float H, float seed){
  float xc = x * 4.2 + seed;
  float c0 = floor(xc);
  float best = -10.0;
  // tongues are jittered and can be wider than a cell, so check neighbours too
  for (int j = -1; j <= 1; j++){
    float ci = c0 + float(j);
    float u = xc - ci - 0.5 - (h21(vec2(ci, seed)) - 0.5) * 0.45;
    float wd = 0.65 + 0.7 * h21(vec2(ci + 3.1, seed));
    float hc = H * (0.3 + 0.7 * vnoise(vec2(ci * 1.7 + seed, t * 0.7)));
    float ny = y / hc;
    best = max(best, (1.0 - ny) - abs(u) * 2.0 / wd * (0.2 + 1.1 * ny));
  }
  return best;
}

// Turbulent flame density at p (x in aspect units, y = height above the burner).
float fireField(vec2 p, float t, float H, float seed){
  float y = p.y;
  if (y < -0.04 || H < 0.01) return 0.0;
  // tongues lean and sway as they rise
  float rise = y / max(H, 0.05);
  float sway = (vnoise(vec2(y * 2.5 - t * 1.1, p.x * 1.3 + seed)) - 0.5) * 0.22 * rise;
  float x = p.x + sway;
  // upward-scrolling, domain-warped turbulence
  vec2 q = vec2(x * 3.0, y * 2.0 - t * 1.4);
  vec2 w = vec2(fbm(q + vec2(seed, 0.0)), fbm(q + vec2(5.2 + seed, 1.3)));
  float n = fbm(vec2(x * 6.0, y * 4.2 - t * 2.8) + (w - 0.5) * 2.4);
  float xs = x + (w.x - 0.5) * 0.12;
  float shape = max(tongues(xs, y, t, H, seed), tongues(xs, y, t * 1.13, H * 0.85, seed + 0.5));
  float f = shape * 1.2 + (n - 0.5) * (0.45 + 1.35 * rise);
  f *= smoothstep(-0.04, 0.04, y);
  return clamp(f, -1.0, 1.6);
}
vec3 flameColor(float T, float yr){
  vec3 deep = vec3(0.45, 0.04, 0.0);
  vec3 org  = vec3(1.0, 0.33, 0.03);
  vec3 yel  = vec3(1.0, 0.70, 0.16);
  vec3 core = vec3(1.0, 0.92, 0.70);
  vec3 c = mix(deep, mix(org, yel, yr), smoothstep(0.05, 0.5, T));
  return mix(c, core, smoothstep(0.8, 1.25, T) * (0.5 + 0.5 * yr));
}

void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  float A = uRes.x / uRes.y;
  vec2 p = vec2(uv.x * A, uv.y);
  float on = uOn;

  float o = uOrange, yv = uYellow;
  float fl = max(o, yv);
  float bright = fl > 0.001 ? (0.45 + 0.55 * fl) : 0.0;
  float yr = yv / max(o + yv, 0.001);
  float H = uHeight * on * (bright > 0.0 ? 1.0 : 0.0);
  float t = uTime;
  float flick = 0.82 + 0.18 * vnoise(vec2(uClock * 3.1, 0.0));
  float fireLight = bright * on * (0.4 + uHeight) * flick;
  vec3 fireTint = mix(vec3(1.0, 0.38, 0.08), vec3(1.0, 0.62, 0.22), yr);

  vec3 ember = mix(uEmber, hsv2rgb(vec3(fract(uClock * 0.045), 0.95, 1.0)), uEmberCycle);
  vec3 top   = mix(uTop,   hsv2rgb(vec3(fract(uClock * 0.045 + 0.5), 0.95, 1.0)), uTopCycle);
  float emberB = uEmberBri * on;

  // back wall: dark reflective panel lit by fire, embers and top light
  vec3 col = vec3(0.022, 0.019, 0.018) * (0.7 + 0.3 * fbm(p * vec2(6.0, 18.0)));
  float baseY = uMedia < 0.5 ? 0.13 : 0.15;
  float wallGlow = exp(-max(p.y - baseY, 0.0) * 2.4) * exp(-pow((uv.x - 0.5) * 1.6, 2.0));
  col += fireTint * fireLight * 0.22 * wallGlow;
  col += ember * emberB * 0.12 * exp(-max(p.y - baseY, 0.0) * 6.0);
  float topFall = exp(-(1.0 - uv.y) * 7.5);
  col += top * on * (topFall * 0.38 + 0.015) * (0.6 + 0.4 * sin(uv.x * 3.14159));
  col += top * on * smoothstep(0.975, 1.0, uv.y) * 0.9;

  // back flames
  vec2 fp = vec2(p.x, p.y - baseY);
  float edge = smoothstep(0.0, 0.07 * A, uv.x * A) * smoothstep(0.0, 0.07 * A, (1.0 - uv.x) * A);
  float Tr = fireField(fp, t, H, 0.0) * edge;
  float T = max(Tr, 0.0);
  float rise1 = clamp(fp.y / max(H, 0.05), 0.0, 1.2);
  col += flameColor(T * (1.15 - 0.4 * rise1), yr) * smoothstep(0.03, 0.4, T) * (1.0 - 0.35 * rise1) * bright * 1.35;

  // media: crossed log stack, painted back to front
  if (uMedia < 0.5){
    float px = 1.5 / uRes.y;
    for (int k = 0; k < 5; k++){
      vec2 la, lb; float ra, rb;
if (k == 0)      { la = vec2(0.20 * A, 0.190); lb = vec2(0.80 * A, 0.215); ra = 0.060; rb = 0.054; } // back log
      else if (k == 1) { la = vec2(0.82 * A, 0.080); lb = vec2(0.50 * A, 0.355); ra = 0.060; rb = 0.036; } // right lean
      else if (k == 2) { la = vec2(0.17 * A, 0.080); lb = vec2(0.52 * A, 0.365); ra = 0.064; rb = 0.038; } // left lean
      else if (k == 3) { la = vec2(0.40 * A, 0.065); lb = vec2(0.76 * A, 0.115); ra = 0.052; rb = 0.044; } // front cross log
      else             { la = vec2(0.29 * A, 0.060); lb = vec2(0.38 * A, 0.135); ra = 0.058; rb = 0.050; } // stub pointing at viewer
      float hh;
      float d = sdTaper(p, la, lb, ra, rb, hh);
      float lr = mix(ra, rb, hh);
      // contact shadow onto whatever is behind
      col *= 1.0 - 0.55 * smoothstep(0.035, 0.0, d) * on * step(0.0, d) - 0.25 * smoothstep(0.035, 0.0, d) * step(0.0, d);
      float mask = 1.0 - smoothstep(-px, px, d);
      if (mask <= 0.0) continue;
      float sd = float(k) * 7.31;
      vec2 axis = normalize(lb - la);
      vec2 nrm = vec2(-axis.y, axis.x);
      if (nrm.y < 0.0) nrm = -nrm;
      vec2 c = la + (lb - la) * hh;
      float v = clamp(dot(p - c, nrm) / lr, -1.0, 1.0);      // -1 bottom .. 1 top
      float along = dot(p - la, axis);
      float bark = fbm(vec2(along * 9.0 + sd, v * 6.0 + hh * 4.0)) * 0.6 + 0.4 * fbm(vec2(along * 40.0, v * 2.0 + sd));
      float tone = 0.8 + 0.4 * h21(vec2(sd, 1.0));
      vec3 wood = mix(vec3(0.05, 0.028, 0.015), vec3(0.17, 0.095, 0.05), bark) * tone;
      wood *= 0.45 + 0.55 * (v * 0.5 + 0.5);
      wood += fireTint * fireLight * 0.22 * smoothstep(-0.2, 1.0, v) * (0.6 + 0.6 * bark);
      wood += ember * emberB * 0.25 * smoothstep(0.3, -1.0, v);
      float rn = fbm(vec2(along * 11.0 + sd, v * 1.8 + 3.0));
      float crack = pow(1.0 - abs(2.0 * rn - 1.0), 22.0) * smoothstep(0.45, 0.65, vnoise(vec2(along * 4.0 + sd, 7.0)));
      float glowAmt = on * (0.35 * bright + 0.65 * max(bright, emberB)) * (0.65 + 0.35 * vnoise(vec2(along * 6.0 + sd, uClock * 1.3)));
      wood += mix(vec3(1.0, 0.28, 0.04), ember, 0.35) * crack * glowAmt * 1.2 * smoothstep(-0.6, 0.6, v);
      // cut ends: lighter end grain with rings, charred glowing rim
      float tr = dot(p - la, lb - la) / dot(lb - la, lb - la);
      float cap = max(smoothstep(0.0, -0.02, tr), smoothstep(1.0, 1.02, tr));
      vec2 ec = tr < 0.5 ? la : lb;
      float rr = length(p - ec) / lr;
      vec3 grain = mix(vec3(0.20, 0.12, 0.06), vec3(0.30, 0.19, 0.10), 0.5 + 0.5 * sin(rr * 26.0 + fbm(p * 30.0) * 3.0)) * tone;
      grain += fireTint * fireLight * 0.12;
      grain = mix(grain, vec3(1.0, 0.33, 0.05) * glowAmt * 0.7, smoothstep(0.65, 0.95, rr) * 0.8);
      wood = mix(wood, grain, cap * 0.85);
      col = mix(col, wood, mask);
    }
  }

  // ember / crystal bed
  float bedTop = baseY - 0.01 + 0.012 * vnoise(vec2(p.x * 9.0, 0.0));
  if (p.y < bedTop + 0.01){
    float bm = 1.0 - smoothstep(bedTop - 0.004, bedTop + 0.004, p.y);
    vec2 g = p * vec2(34.0, 40.0) * (uMedia < 0.5 ? 1.0 : 0.6);
    vec2 gi = floor(g), gf = fract(g);
    float md = 8.0, md2 = 8.0; float id = 0.0;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++){
      vec2 nb = vec2(float(i), float(j));
      vec2 pt = nb + vec2(h21(gi + nb), h21(gi + nb + 17.0)) - gf;
      float dd = dot(pt, pt);
      if (dd < md){ md2 = md; md = dd; id = h21(gi + nb + 3.7); }
      else if (dd < md2){ md2 = dd; }
    }
    float cellEdge = sqrt(md2) - sqrt(md);
    float tw = 0.6 + 0.4 * sin(uClock * (1.0 + 2.0 * id) + id * 40.0);
    vec3 bed;
    if (uMedia < 0.5){
      float coal = smoothstep(0.0, 0.5, cellEdge) * (1.0 - smoothstep(0.25, 0.7, md));
      float hot = smoothstep(0.55, 1.0, id);
      bed = vec3(0.028, 0.022, 0.02) * (0.4 + id) * coal;
      bed += ember * emberB * ((1.0 - coal) * 0.55 + hot * coal * 0.9) * tw;
      bed += fireTint * fireLight * 0.12 * coal * id;
    } else {
      float facet = smoothstep(0.0, 0.25, cellEdge);
      bed = vec3(0.05) * id;
      bed += ember * emberB * (0.5 + 0.9 * id) * mix(1.4, 0.6, facet) * tw;
      bed += fireTint * fireLight * 0.12 * (0.4 + id);
      bed += vec3(1.0) * pow(id, 16.0) * (emberB + fireLight) * 0.6 * tw;
    }
    bed *= 0.55 + 0.45 * smoothstep(0.0, bedTop, p.y);
    col = mix(col, bed, bm);
  }

  // front flames, lower and softer, lick over the media
  vec2 fp2 = vec2(p.x + 0.37, p.y - baseY + 0.035);
  float T2 = max(fireField(fp2, t * 1.08, H * 0.42, 11.7), 0.0) * edge;
  col += flameColor(T2 * 0.85, yr) * smoothstep(0.25, 0.9, T2) * bright * 0.6;

  // sparks
  if (H > 0.02){
    for (int i = 0; i < 14; i++){
      float fi = float(i);
      float r1 = h21(vec2(fi, 1.3));
      float life = fract(uTime * (0.16 + 0.12 * r1) + r1 * 7.0);
      vec2 sp = vec2((0.12 + 0.76 * h21(vec2(fi, 7.7))) * A + sin(life * 6.0 + fi) * 0.025,
                     baseY + 0.05 + life * H * 1.35);
      float dd = length(p - sp);
      float s = (1.0 - life) * smoothstep(0.0045, 0.0, dd) * step(0.55, h21(vec2(fi, floor(uTime * 0.2 + r1 * 5.0))));
      col += vec3(1.0, 0.55, 0.18) * s * bright * 1.5;
    }
  }

  // glass vignette
  col *= 0.72 + 0.28 * smoothstep(0.0, 0.12, uv.y) * smoothstep(0.0, 0.08, uv.x) * smoothstep(0.0, 0.08, 1.0 - uv.x);

  col = 1.0 - exp(-col * 1.7);
  gl_FragColor = vec4(col, 1.0);
}`;

  // ───────────────────────────── helpers ─────────────────────────────
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const hexToRgb = (hex) => {
    const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
    return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [255, 90, 30];
  };
  const rgbToHex = (a) =>
    Array.isArray(a) && a.length === 3
      ? "#" + a.map((x) => clamp(Math.round(+x), 0, 255).toString(16).padStart(2, "0")).join("")
      : "#ff5a1e";
  const sameVal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const isLive = (s) => s && s.state !== "unavailable" && s.state !== "unknown";

  const STYLE = `
    :host { display: block; }
    ha-card { display: block; overflow: hidden; }
    :host([fill]) { height: 100%; display: flex; flex-direction: column; }
    :host([fill]) ha-card { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; box-sizing: border-box; }
    :host([fill]) .box { aspect-ratio: auto; flex: 1 1 auto; min-height: 200px; }
    :host([fill]) .head, :host([fill]) .panel, :host([fill]) .presets, :host([fill]) .pad { flex: none; }
    .head { display: flex; align-items: center; gap: 12px; padding: 12px 14px 10px; }
    .head .ic { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
      background: rgba(127,127,127,.15); color: var(--secondary-text-color); transition: all .3s; }
    .head .ic.on { background: rgba(255,122,24,.18); color: #ff8a2a; box-shadow: 0 0 14px rgba(255,122,24,.35); }
    .head .tx { flex: 1; min-width: 0; }
    .head .nm { font-size: 1.05rem; font-weight: 600; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .head .st { font-size: .8rem; color: var(--secondary-text-color); margin-top: 2px; }
    .head .st b { color: #ffc24a; font-weight: 600; }
    .pwr { width: 44px; height: 44px; border-radius: 50%; border: 1px solid rgba(127,127,127,.4); background: rgba(127,127,127,.12);
      color: var(--secondary-text-color); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s; }
    .pwr.on { color: #ffd34a; border-color: #ffd34a; background: rgba(255,200,40,.12); box-shadow: 0 0 12px rgba(255,200,40,.25); }
    .pwr:disabled { opacity: .4; cursor: not-allowed; }

    .box { position: relative; margin: 0 12px; border-radius: 10px; overflow: hidden; background: #0b0a09;
      aspect-ratio: var(--fp-aspect, 2.1); border: 2px solid #2a2622;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.04), 0 6px 18px rgba(0,0,0,.35); }
    canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
    .glass { position: absolute; inset: 0; pointer-events: none; border-radius: 8px;
      box-shadow: inset 0 0 40px rgba(0,0,0,.75), inset 0 10px 18px rgba(0,0,0,.5); }
    .offmsg { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 8px;
      color: rgba(255,255,255,.45); font-size: .85rem; pointer-events: none; transition: opacity .6s; }
    .box.on .offmsg { opacity: 0; }
    .nogl { position: absolute; left: 8px; bottom: 6px; font-size: .7rem; color: rgba(255,255,255,.35); }

    .puck { position: absolute; z-index: 3; width: 42px; height: 42px; margin: -21px 0 0 -21px; border-radius: 50%;
      background: rgba(18,18,18,.72); border: 1px solid rgba(255,255,255,.4); color: #fff; cursor: pointer; padding: 0;
      display: flex; align-items: center; justify-content: center; backdrop-filter: blur(3px);
      box-shadow: 0 2px 8px rgba(0,0,0,.55), 0 0 0 3px rgba(255,215,0,.1); transition: transform .12s, border-color .15s, opacity .4s; }
    .puck:hover { transform: scale(1.08); border-color: #ffd34a; }
    .puck.sel { border-color: #ffd34a; background: rgba(70,55,18,.85); transform: scale(1.08); }
    .puck .lb { position: absolute; top: 46px; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: .62rem;
      color: #ddd; background: rgba(0,0,0,.7); padding: 2px 6px; border-radius: 4px; opacity: 0; transition: opacity .15s; pointer-events: none; }
    .puck:hover .lb { opacity: 1; }
    .box:not(.on) .puck { opacity: 0; pointer-events: none; }
    .puck ha-icon { --mdc-icon-size: 21px; }

    .panel { margin: 10px 12px 0; padding: 4px 14px 8px; border-radius: 10px; background: rgba(127,127,127,.08);
      border: 1px solid rgba(127,127,127,.2); display: none; }
    .panel.open { display: block; }
    .panel h4 { margin: 8px 0 4px; font-size: .72rem; text-transform: uppercase; letter-spacing: .7px; color: #e6b53a;
      display: flex; align-items: center; gap: 6px; }
    .panel h4 ha-icon { --mdc-icon-size: 16px; }
    .row { display: flex; align-items: center; gap: 10px; margin: 9px 0; min-height: 30px; }
    .row .rl { font-size: .82rem; color: var(--primary-text-color); width: 86px; flex-shrink: 0; }
    .row .rv { font-size: .8rem; color: #e6b53a; font-weight: 700; min-width: 34px; text-align: right; }
    .row .sp { flex: 1; }
    input[type=range] { flex: 1; -webkit-appearance: none; appearance: none; height: 8px; border-radius: 4px; outline: none;
      background: rgba(127,127,127,.35); cursor: pointer; margin: 0; }
    input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; border-radius: 50%;
      background: #ffb020; border: 2px solid rgba(0,0,0,.4); }
    input[type=range]::-moz-range-thumb { width: 20px; height: 20px; border-radius: 50%; background: #ffb020; border: 2px solid rgba(0,0,0,.4); }
    .seg { display: flex; flex: 1; border-radius: 8px; overflow: hidden; border: 1px solid rgba(127,127,127,.4); }
    .seg button { flex: 1; background: transparent; color: var(--primary-text-color); border: none; padding: 7px 4px;
      font-size: .8rem; font-weight: 600; cursor: pointer; border-right: 1px solid rgba(127,127,127,.4); }
    .seg button:last-child { border-right: none; }
    .seg button.act { background: #b5562a; color: #fff; }
    .step { display: flex; align-items: center; gap: 8px; }
    .step button { width: 32px; height: 32px; border-radius: 8px; border: 1px solid rgba(127,127,127,.4); background: transparent;
      color: var(--primary-text-color); font-size: 1.1rem; cursor: pointer; }
    .step .tv { font-size: 1.15rem; font-weight: 700; color: #e6b53a; min-width: 64px; text-align: center; }
    .tog { position: relative; width: 44px; height: 24px; flex-shrink: 0; }
    .tog input { opacity: 0; width: 0; height: 0; }
    .tog span { position: absolute; inset: 0; cursor: pointer; background: rgba(127,127,127,.45); border-radius: 12px; transition: background .2s; }
    .tog span::after { content: ""; position: absolute; width: 18px; height: 18px; left: 3px; top: 3px; border-radius: 50%;
      background: #fff; transition: transform .2s; }
    .tog input:checked + span { background: #d48a2a; }
    .tog input:checked + span::after { transform: translateX(20px); }
    .sw { display: flex; gap: 6px; flex-wrap: wrap; flex: 1; align-items: center; }
    .sw button { width: 24px; height: 24px; border-radius: 50%; border: 2px solid rgba(255,255,255,.25); cursor: pointer; padding: 0; }
    .sw button.act { border-color: #fff; box-shadow: 0 0 0 2px #e6b53a; }
    .sw input[type=color] { width: 28px; height: 26px; border: none; background: none; padding: 0; cursor: pointer; }

    .presets { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 10px 12px 12px; }
    .presets button { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 9px 4px 7px; border-radius: 10px;
      background: rgba(127,127,127,.1); border: 1px solid rgba(127,127,127,.25); color: var(--primary-text-color);
      font-size: .74rem; font-weight: 600; cursor: pointer; transition: background .15s, border-color .15s; }
    .presets button ha-icon { color: #ff9a3c; --mdc-icon-size: 22px; }
    .presets button:hover { background: rgba(255,154,60,.12); }
    .presets button.act { border-color: #e6b53a; background: rgba(181,86,42,.3); }
    .presets.hidden { display: none; }
    .presets.hidden + .pad { height: 12px; }
    .warn { padding: 16px; color: var(--error-color, #f44336); }
  `;

  // ───────────────────────────── card ─────────────────────────────
  class NapoleonFireplaceCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._pending = {};
      this._timers = {};
      this._panel = null;
      this._dragging = false;
      this._gl = null;
      this._raf = null;
      this._visible = true;
      this._u = null;
      this._cur = null; // smoothed shader params
    }

    static getStubConfig(hass) {
      const ents = Object.values((hass && hass.entities) || {});
      const pw = ents.find((e) => e.platform === "napoleon" && e.translation_key === ROLES.power);
      return { entity: pw ? pw.entity_id : "" };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "entity", required: true, selector: { entity: { filter: { integration: "napoleon" } } } },
          { name: "name", selector: { text: {} } },
          {
            type: "grid",
            name: "",
            schema: [
              {
                name: "media",
                selector: {
                  select: {
                    mode: "dropdown",
                    options: [
                      { value: "logs", label: "Logs" },
                      { value: "crystals", label: "Crystals" },
                    ],
                  },
                },
              },
              { name: "aspect_ratio", selector: { number: { min: 1, max: 4, step: 0.1, mode: "box" } } },
            ],
          },
          { name: "show_presets", selector: { boolean: {} } },
          { name: "fill", selector: { boolean: {} } },
        ],
        computeLabel: (s) =>
          ({
            entity: "Fireplace (any of its entities)",
            name: "Name",
            media: "Fire media",
            aspect_ratio: "Firebox aspect ratio",
            show_presets: "Show presets",
            fill: "Fill container height (ignores aspect ratio)",
          })[s.name],
      };
    }

    setConfig(config) {
      if (!config || (!config.entity && !config.device_id)) {
        throw new Error("Set 'entity' to any entity of a Napoleon fireplace");
      }
      this._config = { media: "logs", show_presets: true, aspect_ratio: 2.1, ...config };
      this.toggleAttribute("fill", this._config.fill === true);
      this._built = false;
      this._ids = null;
      this._stopLoop();
      this._gl = null;
      if (this._hass) this._render();
    }

    set hass(hass) {
      this._hass = hass;
      if (!this._ids) this._resolve();
      this._render();
    }

    getCardSize() {
      return 7;
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6, rows: "auto" };
    }

    connectedCallback() {
      if (this._built) this._kick();
    }

    disconnectedCallback() {
      this._stopLoop();
    }

    // ── entity discovery ──
    _resolve() {
      const reg = this._hass.entities || {};
      let deviceId = this._config.device_id;
      if (!deviceId && reg[this._config.entity]) deviceId = reg[this._config.entity].device_id;
      const ids = {};
      if (deviceId) {
        for (const e of Object.values(reg)) {
          if (e.device_id !== deviceId || e.platform !== "napoleon") continue;
          for (const [role, tk] of Object.entries(ROLES)) if (e.translation_key === tk) ids[role] = e.entity_id;
        }
      }
      Object.assign(ids, this._config.entities || {});
      this._ids = ids;
      this._deviceId = deviceId;
    }

    _st(role) {
      const id = this._ids && this._ids[role];
      return id ? this._hass.states[id] : undefined;
    }

    _model() {
      const s = (r) => this._st(r);
      const on = (r) => !!s(r) && s(r).state === "on";
      const num = (r, d) => {
        const v = parseFloat(s(r) && s(r).state);
        return Number.isFinite(v) ? v : d;
      };
      const pw = s("power");
      const cl = s("climate");
      const em = s("ember");
      const tp = s("top");
      let heater = 0;
      if (cl && cl.state === "heat") heater = cl.attributes.preset_mode === "high" ? 2 : 1;
      const m = {
        available: isLive(pw),
        power: on("power"),
        heater,
        setpoint: cl ? cl.attributes.temperature : null,
        minT: (cl && cl.attributes.min_temp) || 18,
        maxT: (cl && cl.attributes.max_temp) || 23,
        stepT: (cl && cl.attributes.target_temp_step) || 1,
        flame_speed: num("flame_speed", 3),
        orange: num("orange", 2),
        yellow: num("yellow", 2),
        ember_on: on("ember"),
        ember_bri: on("ember") ? Math.max(1, Math.round(((em.attributes.brightness || 0) * EMBER_MAX) / 255)) : 0,
        ember_rgb: (em && em.attributes.rgb_color) || null,
        top_on: on("top"),
        top_rgb: (tp && tp.attributes.rgb_color) || null,
        favourite: isLive(s("favourite")) ? s("favourite").state : null,
        eco: on("eco"),
        boost: on("boost"),
        ember_cycle: on("ember_cycle"),
        top_cycle: on("top_cycle"),
      };
      const now = Date.now();
      for (const [k, p] of Object.entries(this._pending)) {
        if (now > p.until || sameVal(m[k], p.value)) delete this._pending[k];
        else m[k] = p.value;
      }
      if (!m.power) m.heater = 0;
      return m;
    }

    _name() {
      if (this._config.name) return this._config.name;
      const dev = this._deviceId && this._hass.devices && this._hass.devices[this._deviceId];
      if (dev) return dev.name_by_user || dev.name;
      const pw = this._st("power");
      return (pw && pw.attributes.friendly_name) || "Fireplace";
    }

    // ── service calls ──
    _call(domain, service, data, role) {
      const entity_id = this._ids[role];
      if (!entity_id) return Promise.resolve();
      return Promise.resolve(this._hass.callService(domain, service, { entity_id, ...data })).catch((err) => {
        this._pending = {};
        this._render();
        this.dispatchEvent(
          new CustomEvent("hass-notification", {
            detail: { message: `Fireplace: ${err && err.message ? err.message : err}` },
            bubbles: true,
            composed: true,
          }),
        );
      });
    }

    _optimistic(key, value) {
      this._pending[key] = { value, until: Date.now() + PENDING_MS };
    }

    _debounced(key, fn, ms = 400) {
      clearTimeout(this._timers[key]);
      this._timers[key] = setTimeout(fn, ms);
    }

    _act(action, value) {
      const m = this._model();
      switch (action) {
        case "power":
          this._optimistic("power", !m.power);
          if (m.power) this._panel = null;
          this._call("switch", m.power ? "turn_off" : "turn_on", {}, "power");
          break;
        case "heater":
          this._optimistic("heater", value);
          if (value === 0) this._call("climate", "set_hvac_mode", { hvac_mode: "off" }, "climate");
          else this._call("climate", "set_preset_mode", { preset_mode: value === 2 ? "high" : "low" }, "climate");
          break;
        case "temp": {
          const base = m.setpoint == null ? m.minT : m.setpoint;
          const next = clamp(base + value * m.stepT, m.minT, m.maxT);
          this._optimistic("setpoint", next);
          this._debounced("temp", () => this._call("climate", "set_temperature", { temperature: next }, "climate"), 700);
          break;
        }
        case "flame_speed":
        case "orange":
        case "yellow":
          this._optimistic(action, value);
          this._debounced(action, () => this._call("number", "set_value", { value }, action));
          break;
        case "ember_bri":
          this._optimistic("ember_bri", value);
          this._optimistic("ember_on", value > 0);
          this._debounced("ember", () =>
            value > 0
              ? this._call("light", "turn_on", { brightness: Math.round((value * 255) / EMBER_MAX) }, "ember")
              : this._call("light", "turn_off", {}, "ember"),
          );
          break;
        case "ember_rgb":
          this._optimistic("ember_rgb", value);
          this._debounced("ember_rgb", () => this._call("light", "turn_on", { rgb_color: value }, "ember"));
          break;
        case "top_on":
          this._optimistic("top_on", value);
          this._call("light", value ? "turn_on" : "turn_off", {}, "top");
          break;
        case "top_rgb":
          this._optimistic("top_rgb", value);
          this._optimistic("top_on", true);
          this._debounced("top_rgb", () => this._call("light", "turn_on", { rgb_color: value }, "top"));
          break;
        case "eco":
        case "boost":
        case "ember_cycle":
        case "top_cycle":
          this._optimistic(action, value);
          this._call("switch", value ? "turn_on" : "turn_off", {}, action);
          break;
        case "favourite":
          // select.select_option powers the fireplace on first if needed
          this._optimistic("favourite", value);
          if (!m.power) this._optimistic("power", true);
          this._call("select", "select_option", { option: value }, "favourite");
          break;
      }
      this._render();
    }

    // ── DOM ──
    _build() {
      const root = this.shadowRoot;
      const c = this._config;
      root.innerHTML = `
        <style>${STYLE}</style>
        <ha-card>
          <div class="head">
            <div class="ic"><ha-icon icon="mdi:fireplace"></ha-icon></div>
            <div class="tx"><div class="nm"></div><div class="st"></div></div>
            <button class="pwr" title="Power"><ha-icon icon="mdi:power"></ha-icon></button>
          </div>
          <div class="box" style="--fp-aspect:${+c.aspect_ratio || 2.1}">
            <canvas></canvas>
            <div class="glass"></div>
            <div class="offmsg"><ha-icon icon="mdi:fireplace-off"></ha-icon><span></span></div>
            <button class="puck" data-p="heat" style="left:9%;top:18%"><ha-icon icon="mdi:thermometer"></ha-icon><span class="lb">Heat</span></button>
            <button class="puck" data-p="top" style="left:50%;top:16%"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><span class="lb">Top light</span></button>
            <button class="puck" data-p="flame" style="left:91%;top:18%"><ha-icon icon="mdi:fire"></ha-icon><span class="lb">Flame</span></button>
            <button class="puck" data-p="ember" style="left:91%;top:82%"><ha-icon icon="mdi:dots-hexagon"></ha-icon><span class="lb">Ember bed</span></button>
          </div>
          <div class="panel" data-panel="heat">
            <h4><ha-icon icon="mdi:thermometer"></ha-icon>Heat</h4>
            <div class="row"><span class="rl">Heater</span><div class="seg">
              <button data-heater="0">Off</button><button data-heater="1">Low</button><button data-heater="2">High</button></div></div>
            <div class="row"><span class="rl">Target</span><div class="step">
              <button data-temp="-1">−</button><span class="tv"></span><button data-temp="1">+</button></div></div>
            <div class="row"><span class="rl">Eco</span><span class="sp"></span><label class="tog"><input type="checkbox" data-flag="eco"><span></span></label></div>
            <div class="row"><span class="rl">Boost</span><span class="sp"></span><label class="tog"><input type="checkbox" data-flag="boost"><span></span></label></div>
          </div>
          <div class="panel" data-panel="flame">
            <h4><ha-icon icon="mdi:fire"></ha-icon>Flame</h4>
            <div class="row"><span class="rl">Height</span><input type="range" min="1" max="5" step="1" data-set="flame_speed"><span class="rv"></span></div>
            <div class="row"><span class="rl">Orange</span><input type="range" min="0" max="4" step="1" data-set="orange"><span class="rv"></span></div>
            <div class="row"><span class="rl">Yellow</span><input type="range" min="0" max="4" step="1" data-set="yellow"><span class="rv"></span></div>
          </div>
          <div class="panel" data-panel="ember">
            <h4><ha-icon icon="mdi:dots-hexagon"></ha-icon>Ember bed</h4>
            <div class="row"><span class="rl">Brightness</span><input type="range" min="0" max="${EMBER_MAX}" step="1" data-set="ember_bri"><span class="rv"></span></div>
            <div class="row"><span class="rl">Colour</span><div class="sw" data-sw="ember_rgb"></div></div>
            <div class="row"><span class="rl">Colour cycle</span><span class="sp"></span><label class="tog"><input type="checkbox" data-flag="ember_cycle"><span></span></label></div>
          </div>
          <div class="panel" data-panel="top">
            <h4><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon>Top light</h4>
            <div class="row"><span class="rl">On</span><span class="sp"></span><label class="tog"><input type="checkbox" data-flag="top_on"><span></span></label></div>
            <div class="row"><span class="rl">Colour</span><div class="sw" data-sw="top_rgb"></div></div>
            <div class="row"><span class="rl">Colour cycle</span><span class="sp"></span><label class="tog"><input type="checkbox" data-flag="top_cycle"><span></span></label></div>
          </div>
          <div class="presets ${c.show_presets === false ? "hidden" : ""}">
            ${PRESETS.map((p) => `<button data-fav="${p.option}"><ha-icon icon="${p.icon}"></ha-icon>${p.name}</button>`).join("")}
          </div>
          <div class="pad"></div>
        </ha-card>`;

      const $ = (q) => root.querySelector(q);
      const $$ = (q) => root.querySelectorAll(q);
      this._el = {
        name: $(".nm"),
        status: $(".st"),
        icon: $(".head .ic"),
        pwr: $(".pwr"),
        box: $(".box"),
        canvas: $("canvas"),
        offmsg: $(".offmsg span"),
        tv: $(".tv"),
      };

      this._el.pwr.addEventListener("click", () => this._act("power"));
      $$(".puck").forEach((b) =>
        b.addEventListener("click", () => {
          this._panel = this._panel === b.dataset.p ? null : b.dataset.p;
          this._render();
        }),
      );
      $$("[data-heater]").forEach((b) => b.addEventListener("click", () => this._act("heater", +b.dataset.heater)));
      $$("[data-temp]").forEach((b) => b.addEventListener("click", () => this._act("temp", +b.dataset.temp)));
      $$("[data-flag]").forEach((i) => i.addEventListener("change", () => this._act(i.dataset.flag, i.checked)));
      $$("[data-set]").forEach((i) => {
        i.addEventListener("pointerdown", () => (this._dragging = true));
        const end = () => (this._dragging = false);
        i.addEventListener("pointerup", end);
        i.addEventListener("pointercancel", end);
        i.addEventListener("change", end);
        i.addEventListener("input", () => this._act(i.dataset.set, +i.value));
      });
      $$("[data-sw]").forEach((wrap) => {
        const key = wrap.dataset.sw;
        wrap.innerHTML =
          SWATCHES.map((h) => `<button data-hex="${h}" style="background:${h}" title="${h}"></button>`).join("") +
          `<input type="color" title="Custom colour">`;
        wrap.querySelectorAll("button").forEach((b) =>
          b.addEventListener("click", () => this._act(key, hexToRgb(b.dataset.hex))),
        );
        wrap.querySelector("input").addEventListener("input", (e) => this._act(key, hexToRgb(e.target.value)));
      });
      $$("[data-fav]").forEach((b) => b.addEventListener("click", () => this._act("favourite", b.dataset.fav)));

      this._initGL();
      this._built = true;
    }

    _render() {
      if (!this._config || !this._hass) return;
      if (!this._ids || !this._ids.power) {
        this._resolve();
        if (!this._ids.power) {
          this._built = false;
          const what = String(this._config.entity || this._config.device_id).replace(/[<>&"]/g, "");
          this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="warn">Napoleon fireplace not found for <code>${what}</code></div></ha-card>`;
          return;
        }
      }
      if (!this._built) this._build();
      const m = this._model();
      this._m = m;
      const el = this._el;
      const root = this.shadowRoot;
      const unit = (this._hass.config && this._hass.config.unit_system && this._hass.config.unit_system.temperature) || "°C";

      el.name.textContent = this._name();
      let status;
      if (!m.available) status = "Unavailable";
      else if (!m.power) status = "Off";
      else {
        const heat = m.heater ? `Heat <b>${m.heater === 2 ? "High" : "Low"}</b> · ${m.setpoint ?? "–"}${unit}` : "Heater off";
        status = `<b>On</b> · Flame ${m.flame_speed}/5 · ${heat}`;
      }
      el.status.innerHTML = status;
      el.icon.classList.toggle("on", m.power);
      el.pwr.classList.toggle("on", m.power);
      el.pwr.disabled = !m.available;
      el.box.classList.toggle("on", m.power);
      el.offmsg.textContent = m.available ? "Off — tap power or a preset" : "Unavailable";
      if (!m.power) this._panel = null;

      root.querySelectorAll(".puck").forEach((b) => b.classList.toggle("sel", b.dataset.p === this._panel));
      root.querySelectorAll(".panel").forEach((p) => p.classList.toggle("open", p.dataset.panel === this._panel));
      root.querySelectorAll("[data-heater]").forEach((b) => b.classList.toggle("act", +b.dataset.heater === m.heater));
      el.tv.textContent = m.setpoint == null ? "–" : `${m.setpoint}${unit}`;
      root.querySelectorAll("[data-flag]").forEach((i) => (i.checked = !!m[i.dataset.flag]));
      root.querySelectorAll("[data-set]").forEach((i) => {
        if (!this._dragging) i.value = m[i.dataset.set];
        i.nextElementSibling.textContent = `${i.value}/${i.max}`;
      });
      root.querySelectorAll("[data-sw]").forEach((w) => {
        const hex = m[w.dataset.sw] ? rgbToHex(m[w.dataset.sw]) : null;
        w.querySelectorAll("button").forEach((b) => b.classList.toggle("act", hex === b.dataset.hex));
        const ci = w.querySelector("input");
        if (hex && root.activeElement !== ci) ci.value = hex;
      });
      root.querySelectorAll("[data-fav]").forEach((b) => {
        b.classList.toggle("act", m.power && m.favourite === b.dataset.fav);
        b.disabled = !m.available;
      });
      this._kick();
    }

    // ── WebGL ──
    _initGL() {
      const cv = this._el.canvas;
      let gl = null;
      try {
        gl = cv.getContext("webgl", { antialias: false, alpha: false, powerPreference: "low-power" });
      } catch (e) {
        gl = null;
      }
      if (!gl) {
        this._el.box.insertAdjacentHTML("beforeend", `<div class="nogl">WebGL unavailable</div>`);
        return;
      }
      const sh = (type, src) => {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
        return s;
      };
      try {
        const prog = gl.createProgram();
        gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
        gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
        gl.useProgram(prog);
        gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
        const loc = gl.getAttribLocation(prog, "aPos");
        gl.enableVertexAttribArray(loc);
        gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
        this._u = {};
        for (const n of ["uRes", "uTime", "uClock", "uOn", "uHeight", "uOrange", "uYellow", "uEmber", "uEmberBri",
          "uEmberCycle", "uTop", "uTopCycle", "uMedia"]) this._u[n] = gl.getUniformLocation(prog, n);
        this._gl = gl;
      } catch (e) {
        console.error("napoleon-fireplace-card shader error", e);
        this._el.box.insertAdjacentHTML("beforeend", `<div class="nogl">Flame renderer failed</div>`);
        return;
      }
      cv.addEventListener("webglcontextlost", (e) => {
        e.preventDefault();
        this._stopLoop();
        this._gl = null;
      });
      cv.addEventListener("webglcontextrestored", () => {
        this._initGL();
        this._kick();
      });

      if ("IntersectionObserver" in window && !this._io) {
        this._io = new IntersectionObserver((ents) => {
          this._visible = ents.some((x) => x.isIntersecting);
          this._kick();
        });
      }
      if (this._io) {
        this._io.disconnect();
        this._io.observe(cv);
      }
      if (!this._onVis) {
        this._onVis = () => this._kick();
        document.addEventListener("visibilitychange", this._onVis);
      }
    }

    _targets() {
      const m = this._m || {};
      const lin = (rgb) => (rgb ? rgb.map((x) => x / 255) : [0, 0, 0]);
      const fs = clamp(m.flame_speed || 3, 1, 5) - 1;
      return {
        on: m.power ? 1 : 0,
        height: 0.42 + 0.1 * fs,
        speed: 0.65 + 0.14 * fs,
        orange: clamp(m.orange || 0, 0, 4) / 4,
        yellow: clamp(m.yellow || 0, 0, 4) / 4,
        ember: lin(m.ember_rgb || [255, 90, 30]),
        emberBri: m.ember_on ? clamp(m.ember_bri || 0, 0, EMBER_MAX) / EMBER_MAX : 0,
        emberCycle: m.ember_cycle && m.ember_on ? 1 : 0,
        top: m.top_on ? lin(m.top_rgb || [255, 255, 255]) : [0, 0, 0],
        topCycle: m.top_cycle && m.top_on ? 1 : 0,
      };
    }

    _kick() {
      if (!this._gl || this._raf || !this.isConnected || !this._visible || document.hidden) return;
      this._last = performance.now() - 1000 / MAX_FPS;
      this._raf = requestAnimationFrame((t) => this._frame(t));
    }

    _stopLoop() {
      if (this._raf) cancelAnimationFrame(this._raf);
      this._raf = null;
    }

    _frame(now) {
      this._raf = null;
      const gl = this._gl;
      if (!gl || !this.isConnected || !this._visible || document.hidden) return;
      const elapsed = (now - this._last) / 1000;
      if (elapsed < 1 / MAX_FPS - 0.002) {
        this._raf = requestAnimationFrame((t) => this._frame(t));
        return;
      }
      const dt = Math.min(0.1, elapsed);
      this._last = now;

      const T = this._targets();
      if (!this._cur) this._cur = { ...T, ember: [...T.ember], top: [...T.top], time: Math.random() * 100, clock: 0 };
      const c = this._cur;
      const k = 1 - Math.exp(-dt * 2.2);
      const kOn = 1 - Math.exp(-dt * (T.on > c.on ? 1.1 : 2.0));
      for (const key of ["height", "speed", "orange", "yellow", "emberBri", "emberCycle", "topCycle"]) c[key] += (T[key] - c[key]) * k;
      for (let i = 0; i < 3; i++) {
        c.ember[i] += (T.ember[i] - c.ember[i]) * k;
        c.top[i] += (T.top[i] - c.top[i]) * k;
      }
      c.on += (T.on - c.on) * kOn;
      if (Math.abs(T.on - c.on) < 0.002) c.on = T.on;
      c.time = (c.time + dt * c.speed) % 3600;
      c.clock = (c.clock + dt) % 3600;

      const cv = this._el.canvas;
      const scale = Math.min(window.devicePixelRatio || 1, 1.5) * 0.8;
      const w = Math.max(32, Math.min(1400, Math.round(cv.clientWidth * scale)));
      const h = Math.max(16, Math.round(cv.clientHeight * scale));
      if (cv.width !== w || cv.height !== h) {
        cv.width = w;
        cv.height = h;
      }
      gl.viewport(0, 0, w, h);
      const u = this._u;
      gl.uniform2f(u.uRes, w, h);
      gl.uniform1f(u.uTime, c.time);
      gl.uniform1f(u.uClock, c.clock);
      gl.uniform1f(u.uOn, c.on);
      gl.uniform1f(u.uHeight, c.height);
      gl.uniform1f(u.uOrange, c.orange);
      gl.uniform1f(u.uYellow, c.yellow);
      gl.uniform3fv(u.uEmber, c.ember);
      gl.uniform1f(u.uEmberBri, c.emberBri);
      gl.uniform1f(u.uEmberCycle, c.emberCycle);
      gl.uniform3fv(u.uTop, c.top);
      gl.uniform1f(u.uTopCycle, c.topCycle);
      gl.uniform1f(u.uMedia, this._config.media === "crystals" ? 1 : 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

      // Fully off and settled: one static frame is enough, stop animating.
      if (T.on === 0 && c.on === 0) return;
      this._raf = requestAnimationFrame((t) => this._frame(t));
    }
  }

  customElements.define(CARD_TAG, NapoleonFireplaceCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TAG,
    name: "Napoleon Fireplace",
    description: "Animated fireplace with flame, ember bed, top light, heat and preset controls.",
    preview: true,
    documentationURL: "https://github.com/sslivins/hass-napoleon#dashboard-card",
  });
})();
