/*
 * radiooooo-card: full control card for the Radiooooo integration.
 *
 *   type: custom:radiooooo-card
 *   entity: media_player.radiooooo
 */

// Click the mode button to cycle through these, in order.
const MODES = [
  { id: "random", label: "Random", icon: "mdi:shuffle-variant", tip: "Random: any song, filtered by mood only" },
  { id: "explore", label: "Explore", icon: "mdi:compass-outline", tip: "Explore: songs from the chosen country and decade" },
  { id: "island", label: "Island", icon: "mdi:island", tip: "Island: a curated playlist from the chosen island" },
];

// Which mode actually uses each setting; the others are dimmed (picking one still switches mode).
const SETTINGS = [
  ["mood", "Mood", null],
  ["country", "Country", "explore"],
  ["decade", "Decade", "explore"],
  ["island", "Island", "island"],
];

const STYLE = `
  :host { display: block; }
  .root { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .top { display: flex; gap: 16px; align-items: center; }
  .cover { flex: 0 0 88px; width: 88px; height: 88px; border-radius: 12px;
    background: var(--secondary-background-color) center / cover no-repeat; }
  .info { flex: 1; min-width: 0; }
  .title { font-size: 1.15em; font-weight: 500; }
  .title, .artist, .meta { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .artist, .meta { color: var(--secondary-text-color); }
  .meta { font-size: 0.85em; margin-top: 2px; }

  .progress { display: flex; align-items: center; gap: 8px; font-size: 0.8em; color: var(--secondary-text-color); }
  .progress span { min-width: 2.6em; font-variant-numeric: tabular-nums; }
  .progress span:last-child { text-align: right; }
  input[type="range"] { flex: 1; margin: 0; height: 24px; cursor: pointer; accent-color: var(--primary-color); }
  input[type="range"]:disabled { cursor: default; opacity: 0.5; }

  .controls { display: flex; gap: 4px; align-items: center; }
  .spacer { flex: 1; }
  button { all: unset; box-sizing: border-box; cursor: pointer; width: 44px; height: 44px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center; color: var(--primary-text-color); }
  button:hover { background: var(--secondary-background-color); }
  button:focus-visible { outline: 2px solid var(--primary-color); }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  button.mode { width: auto; padding: 0 14px 0 10px; gap: 6px; border-radius: 22px;
    background: var(--secondary-background-color); }
  button.mode span { font-size: 0.9em; }

  .settings { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
  label { display: block; font-size: 0.8em; color: var(--secondary-text-color); min-width: 0; }
  label.dim { opacity: 0.5; }
  label.wide { grid-column: 1 / -1; }
  select { width: 100%; margin-top: 3px; padding: 9px 8px; font: inherit; color: var(--primary-text-color);
    background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 8px;
    box-sizing: border-box; }
  .output { display: flex; align-items: center; gap: 8px; }
  .output ha-icon { color: var(--secondary-text-color); margin-top: 3px; }
  .output select { flex: 1; }
`;

const fmt = (sec) => {
  sec = Math.max(0, Math.floor(sec || 0));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
};

class RadiooooCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(
      (id) => id.startsWith("media_player.") && hass.states[id].attributes.settings_entities,
    );
    return { entity: entity || "media_player.radiooooo" };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("radiooooo-card: 'entity' is required");
    this._config = config;
    if (!this._built) this._build();
  }

  getCardSize() {
    return 6;
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._tick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  _build() {
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${STYLE}</style>
      <ha-card><div class="root">
        <div class="top">
          <div class="cover"></div>
          <div class="info"><div class="title"></div><div class="artist"></div><div class="meta"></div></div>
        </div>
        <div class="progress">
          <span class="elapsed"></span>
          <input type="range" min="0" max="0" step="1" value="0" disabled />
          <span class="total"></span>
        </div>
        <div class="controls">
          <button class="mode" data-a="mode"><ha-icon></ha-icon><span></span></button>
          <span class="spacer"></span>
          <button data-a="stop" title="Stop"><ha-icon icon="mdi:stop"></ha-icon></button>
          <button data-a="play" class="primary" title="Play / pause"><ha-icon icon="mdi:play"></ha-icon></button>
          <button data-a="next" title="Next track"><ha-icon icon="mdi:skip-next"></ha-icon></button>
        </div>
        <div class="settings"></div>
      </div></ha-card>`;

    const $ = (s) => root.querySelector(s);
    this._root = root;
    this._els = {
      cover: $(".cover"), title: $(".title"), artist: $(".artist"), meta: $(".meta"),
      elapsed: $(".elapsed"), total: $(".total"), slider: $("input[type=range]"),
      play: $('[data-a="play"] ha-icon'), modeBtn: $(".mode"), modeIcon: $(".mode ha-icon"), modeText: $(".mode span"),
    };

    root.addEventListener("click", (e) => {
      const button = e.target.closest("button[data-a]");
      if (button) this._action(button.dataset.a);
    });

    // Dragging only previews; the seek is sent on release so the speaker isn't flooded.
    const { slider } = this._els;
    slider.addEventListener("input", () => {
      this._seeking = true;
      this._els.elapsed.textContent = fmt(slider.value);
    });
    slider.addEventListener("change", () => {
      this._seeking = false;
      this._holdUntil = Date.now() + 2500; // keep the thumb put until the new position arrives
      this._hass.callService("media_player", "media_seek", {
        entity_id: this._config.entity,
        seek_position: Number(slider.value),
      });
    });

    this._selects = {};
    const grid = $(".settings");
    const add = (key, label, parent = grid) => {
      const wrap = document.createElement("label");
      wrap.append(label);
      const sel = document.createElement("select");
      wrap.append(sel);
      parent.append(wrap);
      this._selects[key] = { wrap, sel };
      return wrap;
    };
    for (const [key, label] of SETTINGS) {
      add(key, label);
      this._selects[key].sel.addEventListener("change", (e) => {
        const entity_id = this._state?.attributes.settings_entities?.[key];
        if (entity_id) this._hass.callService("select", "select_option", { entity_id, option: e.target.value });
      });
    }

    // Output player is a media_player source, not a select entity.
    const out = add("source", "Output player");
    out.classList.add("wide");
    const row = document.createElement("div");
    row.className = "output";
    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:cast");
    row.append(icon, this._selects.source.sel);
    out.append(row);
    this._selects.source.sel.addEventListener("change", (e) => {
      this._hass.callService("media_player", "select_source", {
        entity_id: this._config.entity,
        source: e.target.value,
      });
    });
  }

  get _state() {
    return this._hass?.states[this._config.entity];
  }

  _action(name) {
    const entity_id = this._config.entity;
    const call = (service) => this._hass.callService("media_player", service, { entity_id });
    if (name === "mode") return this._cycleMode();
    if (name === "next") return call("media_next_track");
    if (name === "stop") return call("media_stop");
    return call(this._state?.state === "playing" ? "media_pause" : "media_play");
  }

  _cycleMode() {
    const a = this._state?.attributes || {};
    const entity_id = a.settings_entities?.mode;
    if (!entity_id) return;
    const i = MODES.findIndex((m) => m.id === a.mode);
    const next = MODES[(i + 1) % MODES.length];
    this._hass.callService("select", "select_option", { entity_id, option: next.label });
  }

  _setOptions(sel, options, value) {
    const key = options.map((o) => o[0]).join("\u0001");
    if (sel.dataset.opts !== key) {
      sel.dataset.opts = key;
      sel.replaceChildren(...options.map(([val, text]) => new Option(text, val)));
    }
    // Don't change the value under the user while the dropdown is open.
    if (this._root.activeElement !== sel) sel.value = value ?? "";
  }

  _update() {
    const st = this._state;
    if (!st || !this._els) return;
    const a = st.attributes;
    const e = this._els;

    e.title.textContent = a.media_title || (st.state === "unavailable" ? "Unavailable" : "Nothing playing");
    e.artist.textContent = a.media_artist || "";
    e.meta.textContent = [a.country, a.decade, a.mood && String(a.mood).toLowerCase()].filter(Boolean).join(" · ");
    e.cover.style.backgroundImage = a.entity_picture ? `url("${a.entity_picture}")` : "none";
    e.play.setAttribute("icon", st.state === "playing" ? "mdi:pause" : "mdi:play");

    const dur = a.media_duration || 0;
    e.total.textContent = dur ? fmt(dur) : "";
    e.slider.max = dur;
    e.slider.disabled = !dur || st.state === "idle";

    const mode = MODES.find((m) => m.id === a.mode) || MODES[0];
    const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    e.modeIcon.setAttribute("icon", mode.icon);
    e.modeText.textContent = mode.label;
    e.modeBtn.title = `${mode.tip}. Click for ${next.label}.`;

    for (const [key, , usedBy] of SETTINGS) {
      const entity = this._hass.states[a.settings_entities?.[key]];
      const { wrap, sel } = this._selects[key];
      sel.disabled = !entity;
      wrap.classList.toggle("dim", !!usedBy && usedBy !== mode.id);
      this._setOptions(sel, (entity?.attributes.options || []).map((o) => [o, o]), entity?.state);
    }
    const sources = (a.source_list || []).map((s) => [s, this._hass.states[s]?.attributes.friendly_name || s]);
    this._setOptions(
      this._selects.source.sel,
      a.source ? sources : [["", "Choose a player…"], ...sources],
      a.source,
    );

    this._tick();
  }

  _tick() {
    const st = this._state;
    if (!st || !this._els || this._seeking || Date.now() < (this._holdUntil || 0)) return;
    const a = st.attributes;
    let pos = a.media_position;
    if (pos != null && st.state === "playing" && a.media_position_updated_at) {
      pos += (Date.now() - new Date(a.media_position_updated_at).getTime()) / 1000;
    }
    const dur = a.media_duration;
    pos = pos == null ? 0 : Math.min(pos, dur || pos);
    this._els.elapsed.textContent = a.media_title ? fmt(pos) : "";
    this._els.slider.value = pos;
  }
}

// Guarded because the script can be loaded twice (HA's automatic registration plus a manually added Resource).
if (!customElements.get("radiooooo-card")) {
  customElements.define("radiooooo-card", RadiooooCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "radiooooo-card")) {
  window.customCards.push({
    type: "radiooooo-card",
    name: "Radiooooo",
    description: "Now playing, seek bar, mode and settings for the Radiooooo integration",
  });
}
