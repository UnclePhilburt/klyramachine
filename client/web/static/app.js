// Klyra web UI — vanilla JS, no build step.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ----- Data ----------------------------------------------------------------
const DISPLAY_NAMES = {
  af_alloy: "Iris", af_aoede: "Aria", af_bella: "Bella",
  af_heart: "Hazel", af_jessica: "Jessica", af_kore: "Cora",
  af_nicole: "Nicole", af_nova: "Nova", af_river: "River",
  af_sarah: "Sarah", af_sky: "Skye",
  am_adam: "Adam", am_echo: "Ethan", am_eric: "Eric",
  am_fenrir: "Finn", am_liam: "Liam", am_michael: "Michael",
  am_onyx: "Owen", am_puck: "Parker", am_santa: "Nick",
  bf_alice: "Alice", bf_emma: "Emma", bf_isabella: "Isabella", bf_lily: "Lily",
  bm_daniel: "Daniel", bm_fable: "Theo", bm_george: "George", bm_lewis: "Lewis",
};

const CATEGORIES = [
  ["American Female", ["af_alloy","af_aoede","af_bella","af_heart","af_jessica",
                       "af_kore","af_nicole","af_nova","af_river","af_sarah","af_sky"]],
  ["American Male",   ["am_adam","am_echo","am_eric","am_fenrir","am_liam",
                       "am_michael","am_onyx","am_puck","am_santa"]],
  ["British Female",  ["bf_alice","bf_emma","bf_isabella","bf_lily"]],
  ["British Male",    ["bm_daniel","bm_fable","bm_george","bm_lewis"]],
];

const PRESETS = {
  Sassy:    { emoji: "😏", tag: "Witty, sharp, never holds back" },
  Friendly: { emoji: "☺️", tag: "Warm, upbeat, encouraging" },
  Helpful:  { emoji: "💼", tag: "Direct, clear, useful" },
  Chill:    { emoji: "😎", tag: "Laid-back, easygoing, no rush" },
};

const WALLPAPERS = [
  { id: "sunset",   name: "Sunset",   grad: "linear-gradient(135deg, #FF6B47 0%, #FF8E5C 40%, #B45BA8 100%)" },
  { id: "ocean",    name: "Ocean",    grad: "linear-gradient(135deg, #0EA5E9 0%, #06B6D4 50%, #14B8A6 100%)" },
  { id: "aurora",   name: "Aurora",   grad: "linear-gradient(135deg, #10B981 0%, #06B6D4 50%, #8B5CF6 100%)" },
  { id: "lavender", name: "Lavender", grad: "linear-gradient(135deg, #C084FC 0%, #F472B6 100%)" },
  { id: "midnight", name: "Midnight", grad: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #312E81 100%)" },
  { id: "cherry",   name: "Cherry",   grad: "linear-gradient(135deg, #FB7185 0%, #E11D48 100%)" },
  { id: "forest",   name: "Forest",   grad: "linear-gradient(135deg, #166534 0%, #15803D 50%, #166534 100%)" },
  { id: "sand",     name: "Sand",     grad: "linear-gradient(135deg, #FDE68A 0%, #FCD34D 50%, #F59E0B 100%)" },
];
const DEFAULT_WALLPAPER = "sunset";

function applyWallpaper(id) {
  const wp = WALLPAPERS.find(w => w.id === id) || WALLPAPERS[0];
  document.body.style.background = wp.grad;
  document.body.style.backgroundAttachment = "fixed";
}

// Slider <-> config value mappings
const speedFromSlider = (v) => +(0.7 + (v - 70) / 70 * 0.7).toFixed(2);
const speedToSlider   = (s) => Math.round((s - 0.7) / 0.7 * 70 + 70);
const threshFromSlider = (v) => Math.round(2500 - v / 100 * (2500 - 600));
const threshToSlider   = (t) => Math.round((2500 - t) / (2500 - 600) * 100);
const waitFromSlider  = (v) => +(1.0 + v / 100 * 7.0).toFixed(1);
const waitToSlider    = (w) => Math.round((w - 1.0) / 7.0 * 100);

// ----- API helpers ---------------------------------------------------------
const api = {
  config:        () => fetch("/api/config").then(r => r.json()),
  saveConfig:    (patch) => fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(r => r.json()),
  activity:      () => fetch("/api/activity").then(r => r.json()),
  clearMemory:   () => fetch("/api/clear-memory", { method: "POST" }).then(r => r.json()),
  spotifyOpen:   () => fetch("/api/spotify/open",  { method: "POST" }).then(r => r.json()),
  spotifyClose:  () => fetch("/api/spotify/close", { method: "POST" }).then(r => r.json()),
  spotifyStatus: () => fetch("/api/spotify/status").then(r => r.json()),
  browsers:      () => fetch("/api/browsers").then(r => r.json()),
  browserOpen:   () => fetch("/api/browser/open", { method: "POST" }).then(r => r.json()),
};

function attachLongPress(el, callback, delay = 500) {
  let timer = null;
  let triggered = false;
  const start = (e) => {
    if (e.button !== undefined && e.button !== 0) return;
    triggered = false;
    timer = setTimeout(() => {
      triggered = true;
      callback();
    }, delay);
  };
  const cancel = () => { if (timer) { clearTimeout(timer); timer = null; } };
  el.addEventListener("pointerdown", start);
  el.addEventListener("pointerup", cancel);
  el.addEventListener("pointerleave", cancel);
  el.addEventListener("pointercancel", cancel);
  el.addEventListener("click", (e) => {
    if (triggered) { e.stopImmediatePropagation(); e.preventDefault(); triggered = false; }
  }, true);
}

// ----- UI helpers ----------------------------------------------------------
function toast(msg, kind = "info") {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.add("hidden"), 3000);
}

function displayName(vid) { return DISPLAY_NAMES[vid] || vid; }
function categoryFor(vid) {
  for (const [cat, voices] of CATEGORIES) if (voices.includes(vid)) return cat;
  return "";
}

function relTime(ts) {
  if (!ts) return "Never";
  const delta = Math.max(0, Date.now() / 1000 - ts);
  if (delta < 60) return "just now";
  if (delta < 3600) return Math.floor(delta / 60) + "m ago";
  if (delta < 86400) return Math.floor(delta / 3600) + "h ago";
  return Math.floor(delta / 86400) + "d ago";
}

// ----- Routing -------------------------------------------------------------
const ROUTES = {
  "#/home":        { tpl: "tpl-home",        title: "Klyra",       hydrate: hydrateHome },
  "#/voice":       { tpl: "tpl-voice",       title: "Voice",       hydrate: hydrateVoice },
  "#/music":       { tpl: "tpl-music",       title: "Music",       hydrate: hydrateMusic },
  "#/personality": { tpl: "tpl-personality", title: "Personality", hydrate: hydratePersonality },
  "#/privacy":     { tpl: "tpl-privacy",     title: "Privacy",     hydrate: hydratePrivacy },
  "#/listening":   { tpl: "tpl-listening",   title: "Listening",   hydrate: hydrateListening },
  "#/wallpaper":   { tpl: "tpl-wallpaper",   title: "Wallpaper",   hydrate: hydrateWallpaper },
  "#/browser":     { tpl: "tpl-browser",     title: "Browser",     hydrate: hydrateBrowser },
  "#/about":       { tpl: "tpl-about",       title: "About",       hydrate: () => {} },
};

function routeKey() {
  const hash = location.hash || "#/home";
  return hash.replace(/^#\//, "") || "home";
}

async function render() {
  const route = ROUTES[location.hash] || ROUTES["#/home"];
  const tpl = $("#" + route.tpl).content.cloneNode(true);
  const host = $("#view-host");
  host.innerHTML = "";
  host.appendChild(tpl);
  $("#topbar-title").textContent = route.title;
  $("#back-btn").classList.toggle("hidden", route === ROUTES["#/home"]);
  document.body.dataset.route = routeKey();
  $$(".dock-tile").forEach(t => t.classList.toggle("active", t.dataset.route === (location.hash || "#/home")));
  // Hand off to per-route hydration
  await route.hydrate();
}

// ----- Per-route hydrators -------------------------------------------------

async function hydrateHome() {
  const [cfg, browsers] = await Promise.all([api.config(), api.browsers().catch(() => null)]);
  const name = (cfg.user_name || "").trim();
  $("#home-greeting").textContent = name ? `Hi, ${name}` : "Hi there";

  $$(".tile").forEach(t => {
    if (t.dataset.action === "spotify") {
      t.onclick = async () => {
        const r = await api.spotifyOpen();
        if (!r.ok) toast(r.error || "Failed to open Spotify");
        else toast("Opening Spotify…");
      };
    } else if (t.dataset.action === "browser") {
      const def = browsers && browsers.default;
      const meta = browsers && browsers.browsers.find(b => b.id === def);
      const label = meta ? meta.name : "Browser";
      t.querySelector(".tile-label").textContent = label;
      t.onclick = async () => {
        const r = await api.browserOpen();
        if (!r.ok) toast(r.error || "Failed to open browser");
        else toast(`Opening ${r.name}…`);
      };
      attachLongPress(t, () => { location.hash = "#/browser"; });
    } else {
      t.onclick = () => location.hash = t.dataset.route;
    }
  });
}

async function hydrateVoice() {
  const cfg = await api.config();
  const currentVoice = cfg.kokoro_voice || "bm_lewis";

  // Hero
  const updateHero = (vid) => {
    $("#hero-avatar").textContent = displayName(vid)[0].toUpperCase();
    $("#hero-name").textContent = displayName(vid);
    $("#hero-cat").textContent = categoryFor(vid);
  };
  updateHero(currentVoice);

  // Sliders
  const speedSlider = $("#speed-slider");
  speedSlider.value = speedToSlider(cfg.voice_speed ?? 1.0);
  $("#speed-value").textContent = speedFromSlider(+speedSlider.value).toFixed(2) + "×";
  speedSlider.oninput = () => {
    $("#speed-value").textContent = speedFromSlider(+speedSlider.value).toFixed(2) + "×";
  };

  const volSlider = $("#volume-slider");
  volSlider.value = Math.round((cfg.volume ?? 1.0) * 100);
  $("#volume-value").textContent = volSlider.value + "%";
  volSlider.oninput = () => $("#volume-value").textContent = volSlider.value + "%";

  // Voice grid
  const host = $("#voice-categories");
  host.innerHTML = "";
  let selected = currentVoice;
  for (const [cat, voices] of CATEGORIES) {
    const label = document.createElement("div");
    label.className = "cat-label";
    label.textContent = cat;
    host.appendChild(label);

    const grid = document.createElement("div");
    grid.className = "voice-grid";
    for (const vid of voices) {
      const card = document.createElement("div");
      card.className = "voice-card";
      card.dataset.cat = cat;
      card.dataset.voice = vid;
      const initial = displayName(vid)[0].toUpperCase();
      card.innerHTML = `
        <div class="avatar-tile">${initial}</div>
        <div class="voice-name">${displayName(vid)}</div>
      `;
      if (vid === selected) card.classList.add("selected");
      card.onclick = () => {
        $$(".voice-card", host).forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        selected = vid;
        updateHero(vid);
        // Auto-save on selection
        api.saveConfig({ kokoro_voice: vid }).then(() => toast(`Saved ${displayName(vid)}`));
      };
      grid.appendChild(card);
    }
    host.appendChild(grid);
  }

  // Save speed/volume on slider release
  speedSlider.onchange = () => {
    api.saveConfig({ voice_speed: speedFromSlider(+speedSlider.value) }).then(() => toast("Speed saved"));
  };
  volSlider.onchange = () => {
    api.saveConfig({ volume: +(volSlider.value / 100).toFixed(2) }).then(() => toast("Volume saved"));
  };

  $("#preview-btn").onclick = () => toast("Preview not yet wired (needs Kokoro endpoint)");
}

async function hydrateMusic() {
  const refreshButtons = (running) => {
    $("#spotify-open-btn").classList.toggle("hidden", running);
    $("#spotify-close-btn").classList.toggle("hidden", !running);
    if (running) {
      $("#spotify-status").textContent = "Spotify is open";
      $("#spotify-hint").textContent = "Audio plays through this device.";
    } else {
      $("#spotify-status").textContent = "Tap below to open Spotify";
      $("#spotify-hint").textContent = "Audio plays through this device.";
    }
  };

  const status = await api.spotifyStatus();
  if (!status.installed) {
    $("#spotify-status").textContent = "Spotify not installed";
    $("#spotify-hint").textContent = "Run: sudo snap install spotify";
    $("#spotify-open-btn").disabled = true;
    return;
  }
  refreshButtons(status.running);

  $("#spotify-open-btn").onclick = async () => {
    const r = await api.spotifyOpen();
    if (r.ok) refreshButtons(true);
    else toast(r.error || "Failed to open Spotify");
  };
  $("#spotify-close-btn").onclick = async () => {
    await api.spotifyClose();
    refreshButtons(false);
  };
}

async function hydratePersonality() {
  const cfg = await api.config();
  const currentPreset = cfg.personality_preset || "Sassy";

  const grid = $("#preset-grid");
  grid.innerHTML = "";
  let selected = currentPreset;
  for (const [name, data] of Object.entries(PRESETS)) {
    const card = document.createElement("div");
    card.className = "preset-card";
    if (name === currentPreset) card.classList.add("selected");
    card.innerHTML = `
      <div class="preset-emoji">${data.emoji}</div>
      <div class="preset-text">
        <div class="preset-name">${name}</div>
        <div class="preset-tag">${data.tag}</div>
      </div>
    `;
    card.onclick = () => {
      $$(".preset-card", grid).forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      selected = name;
    };
    grid.appendChild(card);
  }

  $("#user-name").value = cfg.user_name || "";

  $("#save-personality").onclick = async () => {
    await api.saveConfig({
      personality_preset: selected,
      user_name: $("#user-name").value.trim(),
    });
    toast("Saved · restart Klyra to apply");
  };
}

async function hydratePrivacy() {
  const cfg = await api.config();
  $("#camera-toggle").checked = !!cfg.enable_camera;

  $("#save-privacy").onclick = async () => {
    const enabled = $("#camera-toggle").checked;
    const patch = { enable_camera: enabled };
    if (!enabled) patch.vision_engine = "off";
    else if (cfg.vision_engine === "off") patch.vision_engine = "local";
    await api.saveConfig(patch);
    toast("Saved · restart Klyra to apply");
  };

  $("#clear-memory").onclick = async () => {
    if (!confirm("Delete all of Klyra's conversation history? This can't be undone.")) return;
    const r = await api.clearMemory();
    toast(`Cleared ${r.deleted} conversation file(s)`);
  };
}

async function hydrateBrowser() {
  const [cfg, list] = await Promise.all([api.config(), api.browsers()]);
  const current = cfg.browser || list.default;
  const grid = $("#browser-grid");
  const emojiFor = { chrome: "🌐", firefox: "🦊", brave: "🦁" };
  grid.innerHTML = "";
  for (const b of list.browsers) {
    const card = document.createElement("div");
    card.className = "preset-card";
    if (b.id === current) card.classList.add("selected");
    if (!b.installed) card.style.opacity = "0.45";
    card.innerHTML = `
      <div class="preset-emoji">${emojiFor[b.id] || "🌐"}</div>
      <div class="preset-text">
        <div class="preset-name">${b.name}</div>
        <div class="preset-tag">${b.installed ? "Installed" : "Not installed"}</div>
      </div>
    `;
    card.onclick = async () => {
      if (!b.installed) { toast(`${b.name} is not installed`); return; }
      $$(".preset-card", grid).forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      await api.saveConfig({ browser: b.id });
      toast(`Default browser: ${b.name}`);
    };
    grid.appendChild(card);
  }
}

async function hydrateWallpaper() {
  const cfg = await api.config();
  const current = cfg.wallpaper || DEFAULT_WALLPAPER;
  const grid = $("#wallpaper-grid");
  grid.innerHTML = "";
  for (const wp of WALLPAPERS) {
    const card = document.createElement("div");
    card.className = "wallpaper-card";
    card.dataset.id = wp.id;
    card.style.background = wp.grad;
    if (wp.id === current) card.classList.add("selected");
    card.innerHTML = `<div class="wp-check">✓</div><div class="wp-name">${wp.name}</div>`;
    card.onclick = async () => {
      $$(".wallpaper-card", grid).forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      applyWallpaper(wp.id);
      await api.saveConfig({ wallpaper: wp.id });
      toast(`${wp.name} wallpaper`);
    };
    grid.appendChild(card);
  }
}

async function hydrateListening() {
  const cfg = await api.config();
  $("#wake-word").value = cfg.wake_word || "hey buddy";
  $("#conversation-toggle").checked = cfg.conversation_mode !== false;

  const sens = $("#sensitivity-slider");
  sens.value = threshToSlider(cfg.silence_threshold || 1500);

  const wait = $("#wait-slider");
  wait.value = waitToSlider(cfg.pre_speech_timeout || 4.0);
  $("#wait-value").textContent = waitFromSlider(+wait.value).toFixed(1) + "s";
  wait.oninput = () => $("#wait-value").textContent = waitFromSlider(+wait.value).toFixed(1) + "s";

  $("#save-listening").onclick = async () => {
    await api.saveConfig({
      wake_word: $("#wake-word").value.trim() || "hey buddy",
      conversation_mode: $("#conversation-toggle").checked,
      silence_threshold: threshFromSlider(+sens.value),
      pre_speech_timeout: waitFromSlider(+wait.value),
    });
    toast("Saved · restart Klyra to apply");
  };
}

// ----- Clock + back button -------------------------------------------------
function tickClock() {
  const d = new Date();
  $("#clock").textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
$("#back-btn").onclick = (e) => {
  e.preventDefault();
  location.hash = e.target.dataset.route || "#/home";
};

$$(".dock-tile").forEach(t => {
  t.onclick = () => location.hash = t.dataset.route;
});

// ----- Boot ---------------------------------------------------------------
async function boot() {
  try {
    const cfg = await api.config();
    applyWallpaper(cfg.wallpaper || DEFAULT_WALLPAPER);
  } catch {
    applyWallpaper(DEFAULT_WALLPAPER);
  }
  if (!location.hash) location.hash = "#/home";
  render();
}

window.addEventListener("hashchange", render);
boot();
tickClock();
setInterval(tickClock, 30 * 1000);
