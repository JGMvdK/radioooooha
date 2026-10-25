/*
 * radiooooo-card: now-playing card for the Radiooooo integration.
 * Buttons act directly; clicking anywhere else on the card opens a settings modal.
 *
 *   type: custom:radiooooo-card
 *   entity: media_player.radiooooo
 */

const FIELDS = [
  ["mode", "Mode"],
  ["mood", "Mood"],
  ["country", "Country"],
  ["decade", "Decade"],
  ["island", "Island"],
];

const CARD_STYLE = `
  :host { display: block; }
  ha-card { cursor: pointer; overflow: hidden; }
  .root { display: flex; gap: 16px; padding: 16px; align-items: stretch; }
  .cover { flex: 0 0 96px; width: 96px; height: 96px; border-radius: var(--ha-card-border-radius, 12px);
    background: var(--secondary-background-color) center / cover no-repeat; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: space-between; gap: 8px; }
  .title { font-size: 1.1em; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .artist, .meta { color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .meta { font-size: 0.85em; }
  .progress { display: flex; align-items: center; gap: 8px; font-size: 0.8em; color: var(--secondary-text-color); }
  .bar { flex: 1; height: 4px; border-radius: 2px; background: var(--divider-color); overflow: hidden; }
  .fill { height: 100%; width: 0; background: var(--primary-color); }
  .controls { display: flex; gap: 4px; align-items: center; }
  .spacer { flex: 1; }
  button { all: unset; box-sizing: border-box; cursor: pointer; width: 40px; height: 40px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center; color: var(--primary-text-color); }
  button:hover { background: var(--secondary-background-color); }
  button:focus-visible { outline: 2px solid var(--primary-color); }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
`;

const DIALOG_STYLE = `
  .overlay { position: fixed; inset: 0; z-index: 9999; background: rgba(0, 0, 0, 0.5);
    display: flex; align-items: center; justify-content: center; padding: 16px; box-sizing: border-box; }
  .dialog { background: var(--card-background-color, #fff); color: var(--primary-text-color);
    border-radius: var(--ha-card-border-radius, 12px); width: min(420px, 100%); max-height: 90vh; overflow: auto;
    padding: 16px 20px 20px; box-sizing: border-box; font-family: var(--paper-font-body1_-_font-family, inherit); }
  .head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  h2 { margin: 0; font-size: 1.2em; font-weight: 500; }
  button.x { all: unset; cursor: pointer; width: 36px; height: 36px; border-radius: 50%; text-align: center;
    line-height: 36px; font-size: 1.4em; color: var(--secondary-text-color); }
  button.x:hover { background: var(--secondary-background-color); }
  label { display: block; margin-top: 12px; font-size: 0.85em; color: var(--secondary-text-color); }
  select { width: 100%; margin-top: 4px; padding: 10px 8px; font: inherit; color: var(--primary-text-color);
    background: var(--secondary-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
  .hint { margin-top: 16px; font-size: 0.8em; color: var(--secondary-text-color); line-height: 1.4; }
  .list button.opt { all: unset; box-sizing: border-box; display: block; width: 100%; padding: 12px; cursor: pointer;
    border-radius: 8px; }
  .list button.opt:hover { background: var(--secondary-background-color); }
  .list button.opt.on { color: var(--primary-color); font-weight: 500; }
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
    return 3;
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
    this._modal?.refresh();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._tick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._closeModal();
  }

  _build() {
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${CARD_STYLE}</style>
      <ha-card>
        <div class="root">
          <div class="cover"></div>
          <div class="main">
            <div>
              <div class="title"></div>
              <div class="artist"></div>
              <div class="meta"></div>
            </div>
            <div class="progress"><span class="elapsed"></span><div class="bar"><div class="fill"></div></div><span class="total"></span></div>
            <div class="controls">
              <button data-a="cast" title="Output player"><ha-icon icon="mdi:cast"></ha-icon></button>
              <span class="spacer"></span>
              <button data-a="stop" title="Stop"><ha-icon icon="mdi:stop"></ha-icon></button>
              <button data-a="play" class="primary" title="Play / pause"><ha-icon icon="mdi:play"></ha-icon></button>
              <button data-a="next" title="Next track"><ha-icon icon="mdi:skip-next"></ha-icon></button>
            </div>
          </div>
        </div>
      </ha-card>`;
    const $ = (s) => root.querySelector(s);
    this._els = {
      cover: $(".cover"), title: $(".title"), artist: $(".artist"), meta: $(".meta"),
      elapsed: $(".elapsed"), total: $(".total"), fill: $(".fill"), play: $('[data-a="play"] ha-icon'),
    };
    root.addEventListener("click", (e) => {
      const button = e.target.closest("button[data-a]");
      if (button) {
        e.stopPropagation();
        this._action(button.dataset.a);
      } else {
        this._openSettings();
      }
    });
  }

  get _state() {
    return this._hass?.states[this._config.entity];
  }

  _action(name) {
    const entity_id = this._config.entity;
    const call = (service) => this._hass.callService("media_player", service, { entity_id });
    if (name === "cast") return this._openSources();
    if (name === "next") return call("media_next_track");
    if (name === "stop") return call("media_stop");
    return call(this._state?.state === "playing" ? "media_pause" : "media_play");
  }

  _update() {
    const st = this._state;
    if (!st || !this._els) return;
    const a = st.attributes;
    const e = this._els;
    const idle = !a.media_title;
    e.title.textContent = idle ? (st.state === "unavailable" ? "Unavailable" : "Nothing playing") : a.media_title;
    e.artist.textContent = a.media_artist || "";
    e.meta.textContent = [a.country, a.decade, a.mood && String(a.mood).toLowerCase()].filter(Boolean).join(" · ");
    e.cover.style.backgroundImage = a.entity_picture ? `url("${a.entity_picture}")` : "none";
    e.play.setAttribute("icon", st.state === "playing" ? "mdi:pause" : "mdi:play");
    e.total.textContent = a.media_duration ? fmt(a.media_duration) : "";
    this._tick();
  }

  _tick() {
    const st = this._state;
    if (!st || !this._els) return;
    const a = st.attributes;
    let pos = a.media_position;
    if (pos != null && st.state === "playing" && a.media_position_updated_at) {
      pos += (Date.now() - new Date(a.media_position_updated_at).getTime()) / 1000;
    }
    const dur = a.media_duration;
    pos = pos == null ? 0 : Math.min(pos, dur || pos);
    this._els.elapsed.textContent = a.media_title ? fmt(pos) : "";
    this._els.fill.style.width = dur ? `${Math.min(100, (pos / dur) * 100)}%` : "0";
  }

  // ---- dialogs (attached to <body> so no ancestor transform can break position: fixed) ----

  _dialog(title) {
    this._closeModal();
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${DIALOG_STYLE}</style>
      <div class="overlay"><div class="dialog">
        <div class="head"><h2></h2><button class="x" title="Close">×</button></div>
        <div class="body"></div>
      </div></div>`;
    root.querySelector("h2").textContent = title;
    root.querySelector(".x").addEventListener("click", () => this._closeModal());
    root.querySelector(".overlay").addEventListener("click", (e) => {
      if (e.target.classList.contains("overlay")) this._closeModal();
    });
    this._onKey = (e) => e.key === "Escape" && this._closeModal();
    document.addEventListener("keydown", this._onKey);
    document.body.appendChild(host);
    this._modal = { host, root, body: root.querySelector(".body"), refresh: () => {} };
    return this._modal;
  }

  _closeModal() {
    if (!this._modal) return;
    document.removeEventListener("keydown", this._onKey);
    this._modal.host.remove();
    this._modal = null;
  }

  _openSources() {
    const m = this._dialog("Output player");
    m.body.className = "body list";
    m.refresh = () => {
      const a = this._state?.attributes || {};
      m.body.replaceChildren(
        ...(a.source_list || []).map((src) => {
          const b = document.createElement("button");
          b.className = `opt${src === a.source ? " on" : ""}`;
          b.textContent = this._hass.states[src]?.attributes.friendly_name || src;
          b.addEventListener("click", () => {
            this._hass.callService("media_player", "select_source", { entity_id: this._config.entity, source: src });
            this._closeModal();
          });
          return b;
        }),
      );
    };
    m.refresh();
  }

  _openSettings() {
    const m = this._dialog("Radiooooo settings");
    const selects = {};
    const addField = (key, label, onChange) => {
      const wrap = document.createElement("label");
      wrap.textContent = label;
      const sel = document.createElement("select");
      sel.addEventListener("change", () => onChange(sel.value));
      wrap.appendChild(sel);
      m.body.appendChild(wrap);
      selects[key] = sel;
    };

    for (const [key, label] of FIELDS) {
      addField(key, label, (option) => {
        const entity_id = this._state?.attributes.settings_entities?.[key];
        if (entity_id) this._hass.callService("select", "select_option", { entity_id, option });
      });
    }
    addField("source", "Output player", (source) =>
      this._hass.callService("media_player", "select_source", { entity_id: this._config.entity, source }),
    );

    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent =
      "Random uses only the mood. Explore uses country and decade. Island uses the chosen island. " +
      "Picking a country, decade or island switches the mode for you. Changes play a new track right away.";
    m.body.appendChild(hint);

    const setOptions = (sel, options, value) => {
      const key = options.join("\u0001");
      if (sel.dataset.opts !== key) {
        sel.dataset.opts = key;
        sel.replaceChildren(...options.map(([val, text]) => new Option(text, val)));
      }
      // Don't yank the value from under the user while the dropdown is open.
      if (m.root.activeElement !== sel) sel.value = value ?? "";
    };

    m.refresh = () => {
      const a = this._state?.attributes || {};
      for (const [key] of FIELDS) {
        const st = this._hass.states[a.settings_entities?.[key]];
        const sel = selects[key];
        sel.disabled = !st;
        setOptions(sel, (st?.attributes.options || []).map((o) => [o, o]), st?.state);
      }
      const sources = (a.source_list || []).map((s) => [s, this._hass.states[s]?.attributes.friendly_name || s]);
      setOptions(selects.source, a.source ? sources : [["", "Choose a player…"], ...sources], a.source);
    };
    m.refresh();
  }
}

customElements.define("radiooooo-card", RadiooooCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "radiooooo-card",
  name: "Radiooooo",
  description: "Now playing, output player and settings for the Radiooooo integration",
});
