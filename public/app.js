/* Kiln prototype — frontend.
 * The canvas is the source of truth: frames live here, the panel only reads them,
 * and nothing on the canvas changes until someone presses Insert.
 * Every claim arrives with its evidence; every rule the person sets is echoed back;
 * nothing is remembered unless the person turns memory on. */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "style") n.style.cssText = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : document.createTextNode(c));
    return n;
  };
  const svg = (d, size = 14) => `<svg width="${size}" height="${size}" viewBox="0 0 14 14" fill="none" aria-hidden="true">${d}</svg>`;
  const I = {
    copy: svg('<rect x="4" y="4" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.3"/><path d="M2 9.5V3a1 1 0 0 1 1-1h6.5" stroke="currentColor" stroke-width="1.3"/>', 13),
    insert: svg('<rect x="1.5" y="1.5" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M7 4.5v5M4.5 7h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>', 13),
    regen: svg('<path d="M11.5 5A5 5 0 1 0 12 8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><path d="M12 2v3.2H8.8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>', 13),
    ok: svg('<path d="M2 7l3.5 3.5L12 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'),
    no: svg('<path d="M3.5 3.5l7 7M10.5 3.5l-7 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'),
    err: svg('<circle cx="7" cy="7" r="6" stroke="currentColor"/><path d="M7 4v4M7 10h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'),
    frame: svg('<rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.2"/>', 10),
    clip: svg('<path d="M3 7.5 7.5 3a2.5 2.5 0 0 1 3.5 3.5L5.5 12a1.5 1.5 0 0 1-2-2L8.5 5" stroke="currentColor" stroke-width="1.2"/>', 11),
    speak: svg('<path d="M2 5.5h2L7 3v8L4 8.5H2z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M9.5 5a2.5 2.5 0 0 1 0 4M11 3.5a4.5 4.5 0 0 1 0 7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>', 13),
    check: svg('<circle cx="6" cy="6" r="4.2" stroke="currentColor" stroke-width="1.3"/><path d="M9.2 9.2 12.5 12.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><path d="M4.3 6l1.2 1.2L7.8 4.8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>', 13),
    edit: svg('<path d="M9 2.5 11.5 5 5 11.5H2.5V9z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>', 12),
    lock: svg('<rect x="3" y="6" width="8" height="6" rx="1.2" stroke="currentColor" stroke-width="1.2"/><path d="M5 6V4.5a2 2 0 0 1 4 0V6" stroke="currentColor" stroke-width="1.2"/>', 11),
    rule: svg('<path d="M7 1.5 12 3.5v3.3c0 2.8-2.1 4.9-5 5.7-2.9-.8-5-2.9-5-5.7V3.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M4.8 7l1.5 1.5L9.3 5.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>', 12),
  };
  // functional icons per finding kind: the shape says what kind of problem it is
  const KIND_ICON = {
    contrast: svg('<circle cx="7" cy="7" r="5.2" stroke="currentColor" stroke-width="1.3"/><path d="M7 1.8a5.2 5.2 0 0 1 0 10.4z" fill="currentColor"/>'),
    hierarchy: svg('<rect x="2" y="2.5" width="10" height="3" rx="1" fill="currentColor"/><rect x="2" y="7" width="7" height="2" rx="1" stroke="currentColor"/><rect x="2" y="10.5" width="5" height="1.5" rx=".75" stroke="currentColor"/>'),
    target: svg('<circle cx="7" cy="7" r="5.2" stroke="currentColor" stroke-width="1.2"/><circle cx="7" cy="7" r="2.4" stroke="currentColor" stroke-width="1.2"/><circle cx="7" cy="7" r=".8" fill="currentColor"/>'),
    type: svg('<path d="M3 3.5h8M7 3.5v7.5M5.3 11h3.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'),
    spacing: svg('<path d="M1.5 7h11M1.5 7 3.5 5M1.5 7l2 2M12.5 7l-2-2M12.5 7l-2 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 2.5v2M7 9.5v2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>'),
    empty: svg('<rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 1.6"/>'),
    lead: svg('<path d="M2.5 4h9M2.5 7h9M2.5 10h5.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'),
    care: svg('<circle cx="7" cy="7" r="5.2" stroke="currentColor" stroke-width="1.2"/><path d="M7 6.3v3.6M7 4.3h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>'),
    rule: I.rule,
  };
  const dotsEl = () => el("span", { class: "dots", "aria-hidden": "true" }, el("span"), el("span"), el("span"));
  const frameNum = (f) => f.name.split("·")[0].trim();
  const frameTitle = (f) => f.name.split("·").slice(1).join("·").trim();
  const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  const TONES = {
    concise: "Up to 2 points, one sentence each. No overview.",
    balanced: "Explains the top issues with the reasoning behind them.",
    technical: "Adds measurements and the rule behind every claim, as spec lines.",
    plain: "Short sentences and everyday words. No ratios or jargon.",
  };
  const GLOSSARY = {
    "WCAG": "Web Content Accessibility Guidelines: the international standard for accessible digital content.",
    "AA": "The middle conformance level of WCAG, and the one most laws and policies point to.",
    "contrast": "How different text is from its background in lightness. Measured as a ratio from 1:1 (none) to 21:1 (black on white).",
    "APCA": "A newer contrast method proposed for WCAG 3. Still a draft, so Kiln shows it for comparison only.",
    "hierarchy": "The visual order that tells people what to look at first.",
    "empty state": "What a screen shows when there's no content yet, such as an empty cart.",
    "tap target": "The area you can press with a finger. Bigger is easier to hit.",
    "44pt": "Apple's recommended minimum size for a tappable area (about 7mm).",
  };

  // ------------------------------------------------------------------ memory (consent first, all off by default)
  const MEM_KEYS = { prefs: "kiln.prefs", rules: "kiln.rules", thread: "kiln.thread", dismissed: "kiln.dismissed" };
  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
    del(k) { try { localStorage.removeItem(k); } catch {} },
  };
  const consent = Object.assign({ prefs: false, rules: false, thread: false, dismissed: false, improve: false },
    store.get("kiln.consent") || {});

  // ------------------------------------------------------------------ state
  const S = {
    frames: [],
    selected: null,
    analysis: new Map(),
    inflight: null,
    undo: [],
    showDropped: false,
    tone: "balanced",
    rules: [],             // active constraints, echoed back by the server
    dismissed: {},         // frameId -> [{issue, layer, name}]
    platform: "web",
    spelling: "en-US",
    maskPII: true,
    wellbeing: true,
    thread: [],            // [{frameId, message, text}] only kept if consent.thread
  };
  if (consent.prefs) Object.assign(S, pick(store.get(MEM_KEYS.prefs) || {}, ["tone", "platform", "spelling", "maskPII", "wellbeing"]));
  if (consent.rules) S.rules = store.get(MEM_KEYS.rules) || [];
  if (consent.dismissed) S.dismissed = store.get(MEM_KEYS.dismissed) || {};
  function pick(o, keys) { const r = {}; keys.forEach((k) => k in o && (r[k] = o[k])); return r; }
  function persist() {
    store.set("kiln.consent", consent);
    consent.prefs ? store.set(MEM_KEYS.prefs, pick(S, ["tone", "platform", "spelling", "maskPII", "wellbeing"])) : store.del(MEM_KEYS.prefs);
    consent.rules ? store.set(MEM_KEYS.rules, S.rules) : store.del(MEM_KEYS.rules);
    consent.dismissed ? store.set(MEM_KEYS.dismissed, S.dismissed) : store.del(MEM_KEYS.dismissed);
    consent.thread ? store.set(MEM_KEYS.thread, S.thread.slice(-30)) : store.del(MEM_KEYS.thread);
    const on = ["prefs", "rules", "thread", "dismissed"].filter((k) => consent[k]).length;
    $("#mem-dot").className = on ? "mem-dot on" : "mem-dot";
    $("#btn-settings").setAttribute("aria-label", `Memory and settings. Kiln remembers ${on ? on + " kind" + (on > 1 ? "s" : "") + " of thing" : "nothing"}.`);
  }
  const byId = (id) => S.frames.find((f) => f.id === id);

  // ------------------------------------------------------------------ privacy: mask identifiers before they leave the device
  const PII = [
    ["email", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g],
    ["card", /\b(?:\d[ -]?){13,19}\b/g],
    ["phone", /(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b/g],
  ];
  function maskText(t, counts) {
    for (const [k, re] of PII) t = t.replace(re, (m) => { counts[k] = (counts[k] || 0) + 1; return "•".repeat(m.length); });
    return t;
  }
  function outbound(frame, message) {
    const counts = { frame: {}, message: {} };
    if (!S.maskPII) return { frame, message, counts, n: 0 };
    const f = structuredClone(frame);
    f.layers.forEach((l) => { if (l.text) l.text = maskText(l.text, counts.frame); });
    const m = message == null ? message : maskText(message, counts.message);
    const n = [...Object.values(counts.frame), ...Object.values(counts.message)].reduce((a, b) => a + b, 0);
    return { frame: f, message: m, counts, n };
  }

  // ------------------------------------------------------------------ colour + geometry (client-side fact checking)
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const rgb = (h) => { h = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255); };
  const lum = (h) => { const [r, g, b] = rgb(h).map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const containsCenter = (o, l) => { const cx = l.x + l.w / 2, cy = l.y + l.h / 2; return o.x <= cx && cx <= o.x + o.w && o.y <= cy && cy <= o.y + o.h; };
  function bgOf(f, idx) {
    const me = f.layers[idx];
    for (let j = idx - 1; j >= 0; j--) {
      const o = f.layers[j];
      if (o.fill && ["container", "image", "button_primary", "button_secondary", "input"].includes(o.role) && containsCenter(o, me) && o.w >= me.w && o.h >= me.h) return o.fill;
    }
    return f.bg || "#FFFFFF";
  }
  function gap(a, b) {
    const dx = Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w), 0), dy = Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h), 0);
    if (dx === 0 && dy === 0) return -Math.min(Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
    return dx === 0 || dy === 0 ? Math.max(dx, dy) : Math.hypot(dx, dy);
  }
  /** Re-measure one claim against the canvas as it is *now*. */
  function remeasure(frameId, block) {
    const f = byId(frameId), facts = block.facts || {};
    const idx = f.layers.findIndex((l) => l.id === facts.layer);
    if (idx < 0) return { ok: false, text: "That layer no longer exists on the canvas." };
    const l = f.layers[idx];
    switch (block.issue) {
      case "low_contrast": {
        const bg = l.fill && ["button_primary", "button_secondary", "input"].includes(l.role) ? l.fill : bgOf(f, idx);
        const r = contrast(l.color || "#000000", bg);
        const t = facts.target_value || 4.5;
        return { ok: r < t, text: `Re-measured now: ${l.color} on ${bg} = ${r.toFixed(2)}:1, needs ${t}:1. ${r < t ? "Still fails." : "Now passes."}` };
      }
      case "small_tap_target": {
        const m = Math.min(l.w, l.h);
        return { ok: m < facts.min, text: `Re-measured now: ${l.w}×${l.h}, smallest side ${m} vs ${facts.min} minimum. ${m < facts.min ? "Still too small." : "Now big enough."}` };
      }
      case "small_text": {
        const s = l.size || 14;
        return { ok: s < facts.min, text: `Re-measured now: ${s}px vs ${facts.min}px. ${s < facts.min ? "Still small." : "Now fine."}` };
      }
      case "crowded": {
        const o = f.layers.find((x) => x.id === facts.other_id);
        if (!o) return { ok: false, text: "The other layer no longer exists." };
        const g = gap(l, o);
        return { ok: g < 4, text: `Re-measured now: ${g < 0 ? "overlapping by " + Math.abs(Math.round(g)) + "px" : Math.round(g) + "px gap"} to "${o.name}", minimum 4px. ${g < 4 ? "Still crowded." : "Now spaced."}` };
      }
      default: return null; // judgments can't be re-measured; the critic re-scores them instead
    }
  }

  // ------------------------------------------------------------------ canvas
  const framesEl = $("#frames");
  const scaleObs = new ResizeObserver((entries) => {
    for (const e of entries) {
      const box = e.target, f = byId(box.dataset.frame);
      if (f) box.firstChild.style.transform = `scale(${e.contentRect.width / f.w})`;
    }
  });
  function renderLayer(l) {
    const isText = ["heading", "body", "caption", "link"].includes(l.role);
    const n = el("div", {
      class: `ly r-${l.role}${isText ? " t-text" : ""}`, "data-layer": l.id, title: l.name,
      style: [`left:${l.x}px;top:${l.y}px;width:${l.w}px;height:${Math.max(1, l.h)}px`, l.fill ? `background-color:${l.fill}` : "",
        l.radius ? `border-radius:${l.radius}px` : "", l.color ? `color:${l.color}` : "", `font-size:${l.size || 14}px;font-weight:${l.weight || 400}`].join(";"),
    });
    if (l.text && l.role !== "icon_button") n.append(l.text);
    return n;
  }
  function renderFrame(f) {
    const inner = el("div", { class: "frame-inner", style: `width:${f.w}px;height:${f.h}px;background:${f.bg}` });
    f.layers.forEach((l) => inner.append(renderLayer(l)));
    const box = el("div", { class: "frame-box", "data-frame": f.id, style: `aspect-ratio:${f.w}/${f.h};background:${f.bg}` }, inner);
    const wrap = el("button", { class: "frame-wrap", type: "button", role: "option", "data-frame": f.id,
      "aria-selected": String(S.selected === f.id), "aria-label": `${f.name}, ${f.layers.length} layers`, onclick: () => select(f.id) },
      el("span", { class: "frame-label", text: f.name }), box);
    scaleObs.observe(box);
    return wrap;
  }
  const renderCanvas = () => framesEl.replaceChildren(...S.frames.map(renderFrame));
  function rerenderFrame(id) { const old = framesEl.querySelector(`.frame-wrap[data-frame="${id}"]`); if (old) old.replaceWith(renderFrame(byId(id))); }
  function highlightLayer(frameId, layerId) {
    const wrap = framesEl.querySelector(`.frame-wrap[data-frame="${frameId}"]`);
    const n = wrap && wrap.querySelector(`[data-layer="${CSS.escape(layerId)}"]`);
    if (!n) return;
    closePanelMobile();
    wrap.scrollIntoView({ block: "nearest", inline: "nearest", behavior: reduceMotion() ? "auto" : "smooth" });
    n.classList.remove("cite-hl"); void n.offsetWidth; n.classList.add("cite-hl");
    setTimeout(() => n.classList.remove("cite-hl"), 2400);
  }

  // ------------------------------------------------------------------ selection & context
  async function select(id) {
    S.selected = id;
    framesEl.querySelectorAll(".frame-wrap").forEach((w) => w.setAttribute("aria-selected", String(w.dataset.frame === id)));
    const f = byId(id);
    $("#panel-title").textContent = `Kiln · Frame ${frameNum(f)} · ${frameTitle(f)}`;
    $("#status-dot").className = "dot live";
    $("#input").placeholder = "Ask Kiln about this frame…";
    $("#fab").textContent = `Ask about Frame ${frameNum(f)}`;
    updateSend(); renderAttach(); renderChips(null);
    const a = await analysis(id);
    if (S.selected === id) { renderAttach(); renderChips(a.chips); }
  }
  async function analysis(id) {
    if (S.analysis.has(id)) return S.analysis.get(id);
    const { frame } = outbound(byId(id), null);
    const res = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ frame, dismissed: S.dismissed[id] || [] }) });
    const a = await res.json();
    S.analysis.set(id, a);
    return a;
  }
  function renderAttach() {
    const row = $("#attach-row");
    row.replaceChildren();
    const f = S.selected && byId(S.selected);
    const picker = el("select", { class: "attach attach-pick", "aria-label": "Attach a frame", onchange: (e) => e.target.value && select(e.target.value) },
      el("option", { value: "", text: f ? "Change…" : "Attach frame…" }), ...S.frames.map((fr) => el("option", { value: fr.id, text: fr.name })));
    if (!f) { row.append(picker); return; }
    const a = S.analysis.get(f.id), ctx = a && a.context;
    const count = !ctx ? `${f.layers.length} layers` : ctx.dropped.length ? `${ctx.kept.length} of ${ctx.total} layers` : `${ctx.total} layers`;
    row.append(el("span", { class: "attach", html: I.clip }, ` Frame ${frameNum(f)} (${count})`));
    if (ctx && ctx.dropped.length) {
      row.append(el("button", { type: "button", class: "attach attach-drop", "aria-expanded": String(S.showDropped),
        onclick: () => { S.showDropped = !S.showDropped; renderAttach(); } }, `${ctx.dropped.length} dropped to fit`));
      if (S.showDropped) row.append(el("div", { class: "dropped-list" }, ...ctx.dropped.map((d) => el("s", { text: d.name }))));
    }
    const dis = S.dismissed[f.id] || [];
    if (dis.length) row.append(el("button", { type: "button", class: "attach attach-drop", onclick: openSettings, title: "Findings you marked as not an issue" }, `${dis.length} dismissed by you`));
    row.append(picker);
  }
  function renderChips(chips) {
    $("#chips").replaceChildren(...(chips || []).map((c) => el("button", { type: "button", class: "chip", text: c, onclick: () => send(c) })));
  }

  // ------------------------------------------------------------------ tone
  function setTone(t) {
    S.tone = t;
    document.querySelectorAll("#tone-seg [data-tone]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.tone === t)));
    $("#tone-expect").textContent = TONES[t];
    persist();
  }
  document.querySelectorAll("#tone-seg [data-tone]").forEach((b) => b.addEventListener("click", () => setTone(b.dataset.tone)));
  $("#tone-seg").addEventListener("keydown", (e) => {
    const order = Object.keys(TONES), i = order.indexOf(S.tone);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const t = order[(i + (e.key === "ArrowRight" ? 1 : order.length - 1)) % order.length];
      setTone(t); $(`#tone-seg [data-tone="${t}"]`).focus();
    }
  });

  // ------------------------------------------------------------------ rules (explicit constraint reminders)
  function renderRules(justAdded = []) {
    const row = $("#rules-row");
    row.replaceChildren();
    S.rules.forEach((r) => {
      const pill = el("span", { class: `rule-pill${justAdded.includes(r.id) ? " fresh" : ""}` },
        el("span", { class: "rule-ic", html: I.rule }), el("span", { class: "rule-k", text: "Rule active" }), r.label,
        el("button", { type: "button", class: "rule-x", "aria-label": `Remove rule: ${r.label}`, html: I.no,
          onclick: () => { S.rules = S.rules.filter((x) => x.id !== r.id); persist(); renderRules(); toast(`Rule removed: ${r.label}`); } }));
      row.append(pill);
    });
    if (justAdded.length) {
      const labels = S.rules.filter((r) => justAdded.includes(r.id)).map((r) => r.label).join(", ");
      $("#live").textContent = `Rule active: ${labels}`;
    }
  }

  // ------------------------------------------------------------------ streaming
  async function* streamChat(body, signal) {
    const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line) yield JSON.parse(line);
      }
    }
    if (buf.trim()) yield JSON.parse(buf);
  }

  const BASIS_HELP = {
    standard: "A published standard with broad consensus (WCAG).",
    convention: "A widely used guideline that isn't universal. Other reasonable thresholds exist.",
    judgment: "The critic model's interpretation. It can't be measured, so treat it as an informed opinion.",
    summary: "Kiln's summary of the findings below.",
    authored: "Fixed text written and reviewed by Kiln's authors. Not generated.",
  };

  /** One assistant reply. States: queued → thinking → streaming → complete | error | stopped.
   *  Content arrives as evidence-carrying blocks, rendered with visual anchors. */
  class Reply {
    constructor(container, { frameId, message, compact = false }) {
      this.frameId = frameId; this.message = message; this.compact = compact;
      this.root = el("div", { class: "msg-a", tabindex: "-1" });
      container.append(this.root);
      this.reset();
    }
    reset() {
      clearInterval(this.timer);
      this.root.replaceChildren();
      this.state = "queued";
      this.blocks = new Map(); this.order = []; this.cur = null; this.buffer = "";
      this.findings = []; this.proposal = null; this.alts = null; this.meta = null; this.speech = "";
      this.considered = null; this.compliance = null; this.privacy = null; this.safety = null;
      this.frameSnapshot = JSON.stringify(byId(this.frameId));
      this.stateLine = el("div", { class: "state-line" }, dotsEl());
      this.root.append(this.stateLine);
    }
    setThinking(txt) { this.state = "thinking"; this.stateLine.replaceChildren(el("span", { text: txt }), dotsEl()); }
    ensureBubble() {
      if (this.bubble) return;
      this.state = "streaming";
      this.stateLine.remove();
      this.bubble = el("div", { class: `bubble${this.safety ? " care" : ""}` });
      this.cursor = el("span", { class: "cursor", "aria-hidden": "true" });
      this.root.append(this.bubble);
      this.timer = setInterval(() => this.flush(), 80); // batch, don't blink
    }
    startBlock(ev) {
      this.ensureBubble();
      this.flush();
      const kind = ev.icon || "lead";
      const isFinding = !!ev.issue;
      const b = { ...ev, text: "", n: isFinding ? this.order.filter((x) => this.blocks.get(x).issue).length + 1 : null };
      if (this.order.length) this.bubble.append(el("hr", { class: "blk-div", "aria-hidden": "true" }));
      const body = el("p", { class: "blk-body", "aria-hidden": "true" });
      const node = el("section", { class: `blk k-${kind}${isFinding ? " finding" : ""}`, "data-block": ev.id, "aria-label": ev.title || "Summary" });
      if (ev.title || isFinding) {
        const head = el("div", { class: "blk-head" },
          el("span", { class: "blk-ic", html: KIND_ICON[kind] || KIND_ICON.lead }),
          el("span", { class: "blk-title", text: ev.title || "" }));
        if (ev.basis && ev.basis !== "summary") head.append(el("span", { class: `basis b-${ev.basis}`, title: BASIS_HELP[ev.basis] || "", text: ev.basis_label }));
        if (ev.confidence) head.append(el("span", { class: `conf c-${ev.confidence.band}`, title: ev.confidence.band === "verified" ? "The critic flagged it and Kiln's geometry check confirmed it." : "Critic model probability. Judgments can't be measured.", text: ev.confidence.band === "verified" ? "Verified" : ev.confidence.label.replace(" confidence", "") }));
        node.append(head);
      }
      node.append(body);
      body.append(this.cursor);
      this.bubble.append(node);
      b.node = node; b.body = body;
      this.blocks.set(ev.id, b); this.order.push(ev.id);
      this.cur = b;
    }
    push(blockId, t) {
      if (!this.cur || this.cur.id !== blockId) { this.flush(); this.cur = this.blocks.get(blockId); this.cur && this.cur.body.append(this.cursor); }
      this.buffer += t;
    }
    flush() {
      if (!this.buffer || !this.cur) return;
      const before = scrollState();
      this.cur.body.insertBefore(document.createTextNode(this.buffer), this.cursor);
      this.cur.text += this.buffer;
      this.buffer = "";
      afterGrow(before);
    }
    endBlock(ev) {
      this.flush();
      const b = this.blocks.get(ev.id);
      if (!b) return;
      Object.assign(b, { text: ev.text, speech: ev.speech, nudges: ev.nudges || [] });
      this.decorate(b);
    }
    /** Turn a finished block's plain text into anchored, inspectable content. */
    decorate(b) {
      const body = b.body;
      body.replaceChildren(...richText(b.text, b.nudges));
      if (b.issue && b.cite && b.cite.length) {
        body.append(" ", el("button", { type: "button", class: "cite-sup", "aria-label": `Source ${b.n}: show layer and evidence`, text: `[${b.n}]`,
          onclick: () => { highlightLayer(this.frameId, b.cite[0]); this.openFacts(b.id); } }));
      }
      if (b.editedBy) body.append(el("span", { class: "edited-tag", text: b.editedBy }));
      // screen readers get the speech-shaped version, not the symbol-dense one
      b.node.querySelector(".sr-speech")?.remove();
      b.node.append(el("p", { class: "sr-only sr-speech", text: (b.title ? b.title + ". " : "") + (b.speech || b.text) }));
      if (b.nudges && b.nudges.length && !this.bubble.querySelector(".nudge-note")) {
        this.bubble.append(el("p", { class: "nudge-note framing" }, el("b", { text: "Framing note: " }),
          "wavy-underlined words are persuasive emphasis, there to motivate the change. The measurements are the facts; the framing is Kiln arguing for them."));
      } else if (this.bubble.querySelector(".nudge-note.framing")) this.bubble.append(this.bubble.querySelector(".nudge-note.framing"));
      if (b.spec && !b.node.querySelector(".code-blk")) b.node.append(codeBlock("SPEC", b.spec));
      if (b.perspectives && b.perspectives.length && !b.node.querySelector(".persp")) b.node.append(perspectivesEl(b.perspectives));
      if (!this.compact && !b.node.querySelector(".blk-edit") && b.text) {
        (b.node.querySelector(".blk-head") || b.node).append(el("button", { type: "button", class: "blk-edit", "aria-haspopup": "menu", "aria-label": `Edit this part: ${b.title || "summary"}`,
          html: I.edit, title: "Edit this part", onclick: (e) => openEditMenu(this, b, e.currentTarget) }, " Edit"));
      }
    }
    stopTimer() { clearInterval(this.timer); this.flush(); this.cursor && this.cursor.remove(); }
    finish(ev) {
      this.stopTimer();
      this.state = "complete";
      this.speech = ev.speech || "";
      this.ensureBubble(); this.stopTimer();
      this.renderPatch(); this.renderAlts(); this.renderCompliance(); this.renderConsidered();
      this.renderActions(true);
    }
    stopped() {
      this.stopTimer();
      this.state = "stopped";
      if (!this.bubble) { this.stateLine.replaceChildren(el("span", { class: "stopped-note", text: "Stopped by you before any text arrived." })); this.renderActions(false); return; }
      this.order.forEach((id) => { const b = this.blocks.get(id); if (!b.speech) { b.speech = b.text; this.decorate(b); } });
      const last = this.blocks.get(this.order[this.order.length - 1]);
      last && last.body.append(el("em", { class: "stopped-note", text: " (stopped by you)" }));
      this.renderActions(false);
    }
    error(txt, retry) {
      this.stopTimer();
      this.state = "error";
      if (this.stateLine.isConnected) this.stateLine.remove();
      const line = el("div", { class: "err-line", role: "alert", html: I.err });
      line.append(el("span", { text: txt || "Couldn't reach the model" }), el("button", { class: "retry", type: "button", text: "Retry", onclick: retry }));
      this.root.append(line);
    }
    text() { return this.order.map((id) => this.blocks.get(id).text).filter(Boolean).join("\n\n"); }
    renderPatch() {
      if (!this.proposal || !this.proposal.lines || !this.proposal.lines.length) return;
      this.root.append(patchBlock(this.proposal.lines));
    }
    renderAlts() {
      if (!this.alts) return;
      const grid = el("div", { class: "alts" });
      this.alts.options.forEach((o) => {
        const b = el("button", { type: "button", class: "alt", onclick: () => requestInsert(this.frameId, o.ops, o.lines, b, o.label, true) },
          el("span", { class: "sw", style: `background:${o.swatch}`, text: "Continue" }), el("span", { text: `Insert ${o.label.toLowerCase()}` }));
        grid.append(b);
      });
      this.root.append(grid, el("p", { class: "nudge-note", html: `<b>Order disclosure:</b> ${this.alts.disclosure}` }));
    }
    renderCompliance() {
      if (!this.compliance) return;
      const row = el("div", { class: "compliance", "aria-label": "Rules check" });
      this.compliance.forEach((c) => row.append(el("span", { class: `comp ${c.ok ? "ok" : "bad"}`, html: c.ok ? I.ok : I.no }, c.detail)));
      this.root.append(row);
    }
    renderConsidered() {
      const c = this.considered;
      if (!c || (!c.items.length && !c.unverified.length) || this.compact) return;
      const d = el("details", { class: "considered" }, el("summary", { text: "Also considered, not claimed" }));
      c.items.forEach((i) => d.append(el("p", {}, el("b", { text: i.label }), ` · critic ${Math.round(i.prob * 100)}%, below the 50% bar, so Kiln doesn't claim it.`)));
      c.unverified.forEach((u) => d.append(el("p", {}, el("b", { text: u.issue.replace(/_/g, " ") }), ` · the critic suspected ${u.layers.map((x) => `"${x}"`).join(", ")}, but measurement disagreed, so it's left out.`)));
      this.root.append(d);
    }
    openFacts(focusId) {
      let panel = this.root.querySelector(".facts");
      if (!panel) { panel = el("div", { class: "facts", role: "region", "aria-label": "Fact check" }); this.root.append(panel); }
      checkFacts(this, panel, focusId);
    }
    renderActions(complete) {
      const row = el("div", { class: "actions-row" });
      const act = (label, icon, fn, cls = "act") => { const b = el("button", { type: "button", class: cls, onclick: fn, html: icon }); b.append(label); return b; };
      if (complete && !this.safety) row.append(el("span", { class: "ok", html: I.ok }, this.compact ? "" : "Ready to act on"));
      row.append(act("Copy", I.copy, async (e) => {
        try { await navigator.clipboard.writeText(this.text()); e.currentTarget.lastChild.textContent = "Copied"; } catch { toast("Couldn't copy"); }
      }));
      if (complete && this.proposal && this.proposal.ops.length) {
        const b = act(this.proposal.label, I.insert, () => requestInsert(this.frameId, this.proposal.ops, this.proposal.lines, b, "fix", this.proposal.review), "act primary");
        row.append(b);
      }
      if (this.findings.length && !this.safety) row.append(act("Check facts", I.check, () => this.openFacts()));
      if ("speechSynthesis" in window) row.append(act("Read aloud", I.speak, (e) => readAloud(this, e.currentTarget)));
      if (!this.compact && !this.safety) row.append(act("Regenerate", I.regen, () => run(this, { seed: 1 + Math.floor(Math.random() * 1e6) })));
      if (this.compact) row.append(act("Open in panel", I.frame, () => { closeQuick(); send(this.message); }));
      this.root.append(row);
      if (this.meta && !this.compact && !this.safety) {
        const m = this.meta;
        this.root.append(el("div", { class: "meta-line", text: `${m.tone} · intent ${m.intent} ${Math.round(m.intent_p * 100)}% · focus ${m.focus.replace(/_/g, " ")} ${Math.round(m.focus_p * 100)}% · critic ${m.latency_ms}ms · wording by narrator model` }));
      }
      if (consent.improve && !this.compact) this.root.append(feedbackRow(this));
    }
  }

  // text with glossary terms and persuasive phrases marked up
  function richText(text, nudges = []) {
    const marks = [];
    nudges.forEach((p) => { const i = text.toLowerCase().indexOf(p.toLowerCase()); if (i >= 0) marks.push({ i, len: p.length, type: "nudge" }); });
    Object.keys(GLOSSARY).forEach((term) => {
      const re = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
      const m = re.exec(text);
      if (m && !marks.some((x) => m.index < x.i + x.len && x.i < m.index + term.length)) marks.push({ i: m.index, len: m[0].length, type: "term", term });
    });
    marks.sort((a, b) => a.i - b.i);
    const out = [];
    let at = 0;
    for (const m of marks) {
      if (m.i < at) continue;
      out.push(text.slice(at, m.i));
      const s = text.slice(m.i, m.i + m.len);
      if (m.type === "nudge") out.push(el("span", { class: "nudge", title: "Persuasive framing: emphasis meant to motivate the change" }, s));
      else out.push(el("button", { type: "button", class: "term", "aria-label": `${s}: definition`, title: GLOSSARY[m.term], onclick: (e) => showTerm(e.currentTarget, m.term) }, s));
      at = m.i + m.len;
    }
    out.push(text.slice(at));
    // hex colours get a swatch so the value is visible, not just readable
    return out.flatMap((part) => typeof part !== "string" ? [part] : part.split(/(#[0-9A-Fa-f]{6}\b)/).map((seg) =>
      /^#[0-9A-Fa-f]{6}$/.test(seg) ? el("span", { class: "hex" }, el("i", { style: `background:${seg}`, "aria-hidden": "true" }), seg) : seg));
  }
  function showTerm(btn, term) {
    const pop = $("#edit-pop");
    pop.replaceChildren(el("p", { class: "term-def" }, el("b", { text: term }), " · ", GLOSSARY[term]));
    pop.setAttribute("role", "tooltip");
    placePop(pop, btn);
  }
  function codeBlock(label, text) {
    return el("div", { class: "code-blk" }, el("span", { class: "code-lbl", text: label }), el("code", { text }));
  }
  function patchBlock(lines) {
    const box = el("div", { class: "code-blk patch" }, el("span", { class: "code-lbl", text: "PATCH · proposed, not applied" }));
    const list = el("ul", { class: "patch-list" });
    lines.slice(0, 12).forEach((l) => list.append(el("li", {}, el("span", { class: "p-layer", text: l.layer }), el("span", { class: "p-prop", text: l.prop }),
      l.from != null ? valueEl(l.from) : "", l.from != null ? el("span", { class: "p-arrow", text: "→" }) : el("span", { class: "p-arrow", text: "+" }), valueEl(l.to))));
    if (lines.length > 12) list.append(el("li", { class: "p-more", text: `+ ${lines.length - 12} more changes` }));
    box.append(list);
    return box;
  }
  function valueEl(v) {
    const s = String(v);
    if (/^#[0-9A-Fa-f]{6}$/.test(s)) return el("span", { class: "p-val hex" }, el("i", { style: `background:${s}` }), s);
    return el("span", { class: "p-val", text: s.length > 36 ? s.slice(0, 34) + "…" : s });
  }
  function perspectivesEl(list) {
    const d = el("details", { class: "persp" }, el("summary", { text: `Where people disagree · ${list.length} views` }));
    const ul = el("ul");
    list.forEach((p) => ul.append(el("li", { class: `st-${p.stance}` }, el("span", { class: "p-src", text: p.source }),
      el("span", { class: "p-stance", text: p.stance === "applied" ? "Kiln applies" : p.stance === "compared" ? "For comparison" : "Also valid" }),
      el("span", { class: "p-view", text: p.view }))));
    d.append(ul);
    return d;
  }

  // ------------------------------------------------------------------ fact check
  async function checkFacts(reply, panel, focusId) {
    panel.replaceChildren(el("div", { class: "facts-head" }, el("span", { html: I.check }), el("b", { text: "Fact check" }),
      el("span", { class: "meta-line", text: "Re-measuring against the canvas as it is now" }), dotsEl()));
    const changed = JSON.stringify(byId(reply.frameId)) !== reply.frameSnapshot;
    S.analysis.delete(reply.frameId);
    let fresh;
    try { fresh = await analysis(reply.frameId); } catch { fresh = null; }
    panel.querySelector(".dots")?.remove();
    panel.querySelector(".facts-head .meta-line").textContent = changed ? "The frame changed after this answer. Results reflect the current canvas." : "The frame hasn't changed since this answer.";
    const list = el("ol", { class: "facts-list" });
    reply.order.map((id) => reply.blocks.get(id)).filter((b) => b.issue).forEach((b) => {
      const m = remeasure(reply.frameId, b);
      const now = fresh && fresh.findings.find((f) => f.issue === b.issue && f.layers.some((l) => l.id === b.facts.layer));
      let status, detail;
      if (m) { status = m.ok ? "holds" : "changed"; detail = m.text; }
      else { status = now ? "holds" : "changed"; detail = now ? `Judgment, not measurable. The critic still flags it at ${Math.round(now.prob * 100)}%.` : "Judgment. The critic no longer flags it on the current canvas."; }
      const li = el("li", { class: `fact ${status}${focusId === b.id ? " focus" : ""}` },
        el("span", { class: "fact-n", text: `[${b.n}]` }),
        el("div", {}, el("p", { class: "fact-claim" }, el("b", { text: b.title }), ` on "${b.facts.layer_name}"`),
          el("p", { class: "fact-meta" }, el("span", { class: `basis b-${b.basis}`, text: b.basis_label }), ` ${b.rule}`),
          el("p", { class: "fact-detail" }, el("span", { class: "fact-st", html: status === "holds" ? I.ok : I.no }), detail),
          el("p", { class: "fact-meta", text: "Wording: generated by the narrator model from these measurements. Numbers are filled from geometry, never generated." }),
          el("button", { type: "button", class: "act", onclick: () => highlightLayer(reply.frameId, b.facts.layer), html: I.frame }, " Show layer")));
      list.append(li);
    });
    panel.append(list);
    (panel.querySelector(".fact.focus") || panel).scrollIntoView({ block: "nearest", behavior: reduceMotion() ? "auto" : "smooth" });
  }

  // ------------------------------------------------------------------ edit this part (one-click corrections)
  const pop = $("#edit-pop");
  function placePop(p, anchor) {
    const r = anchor.getBoundingClientRect();
    p.hidden = false;
    const w = p.offsetWidth || 220;
    p.style.left = `${Math.max(8, Math.min(r.left, innerWidth - w - 8))}px`;
    p.style.top = `${Math.min(r.bottom + 6, innerHeight - p.offsetHeight - 8)}px`;
  }
  function closePop() { pop.hidden = true; pop.replaceChildren(); }
  function openEditMenu(reply, b, anchor) {
    pop.setAttribute("role", "menu");
    const item = (label, hint, fn) => el("button", { type: "button", role: "menuitem", class: "pop-item", onclick: () => { closePop(); fn(); } }, el("b", { text: label }), el("span", { text: hint }));
    const items = [];
    if (b.issue) {
      items.push(item("Rephrase", "Same facts, new wording", () => regenBlock(reply, b, {})));
      items.push(item("Shorter", "One sentence", () => regenBlock(reply, b, { tone: "concise" })));
      items.push(item("Plainer", "Everyday words", () => regenBlock(reply, b, { tone: "plain" })));
      items.push(item("More technical", "Add the measurements", () => regenBlock(reply, b, { tone: "technical" })));
      items.push(item("Not an issue", "Kiln stops flagging this layer", () => dismissFinding(reply, b)));
    }
    items.push(item("Edit the text myself", "Your words replace Kiln's", () => editInPlace(reply, b)));
    pop.replaceChildren(el("p", { class: "pop-title", text: `Edit: ${b.title || "summary"}` }), ...items);
    placePop(pop, anchor);
    pop.querySelector("button")?.focus();
  }
  async function regenBlock(reply, b, { tone }) {
    const { frame, message } = outbound(byId(reply.frameId), reply.message);
    b.body.replaceChildren(dotsEl());
    let text = "", got = null;
    try {
      for await (const ev of streamChat({ frame, message, seed: 1 + Math.floor(Math.random() * 1e6), tone: tone || S.tone, constraints: S.rules,
        dismissed: S.dismissed[reply.frameId] || [], platform: S.platform, spelling: S.spelling, only_issue: b.issue }, undefined)) {
        if (ev.type === "block" && ev.issue === b.issue) { got = ev; b.body.replaceChildren(); }
        else if (ev.type === "token" && got && ev.block === got.id) { text += ev.text; b.body.textContent = text; }
        else if (ev.type === "block_end" && got && ev.id === got.id) { Object.assign(b, { text: ev.text, speech: ev.speech, nudges: ev.nudges, spec: got.spec, editedBy: tone ? `Edited: ${tone}` : "Edited: rephrased" }); }
      }
      b.node.querySelector(".code-blk")?.remove();
      reply.decorate(b);
      $("#live").textContent = `Updated: ${b.title}. ${b.speech}`;
    } catch { b.body.textContent = b.text; toast("Couldn't regenerate that part"); }
  }
  function dismissFinding(reply, b) {
    const list = (S.dismissed[reply.frameId] ||= []);
    list.push({ issue: b.issue, layer: b.facts.layer, name: b.facts.layer_name, label: b.title });
    persist();
    b.node.classList.add("dismissed");
    b.body.prepend(el("span", { class: "edited-tag", text: "Dismissed by you" }), " ");
    S.analysis.delete(reply.frameId);
    if (S.selected === reply.frameId) select(reply.frameId);
    toast(`Kiln won't flag ${b.title.toLowerCase()} on "${b.facts.layer_name}" again`, "Undo", () => {
      S.dismissed[reply.frameId] = (S.dismissed[reply.frameId] || []).filter((d) => !(d.issue === b.issue && d.layer === b.facts.layer));
      persist(); b.node.classList.remove("dismissed"); b.body.querySelector(".edited-tag")?.remove();
      S.analysis.delete(reply.frameId); if (S.selected === reply.frameId) select(reply.frameId);
    });
  }
  function editInPlace(reply, b) {
    b.body.removeAttribute("aria-hidden");
    b.body.textContent = b.text;
    b.body.contentEditable = "true";
    b.body.classList.add("editing");
    b.body.focus();
    const bar = el("div", { class: "edit-bar" },
      el("button", { type: "button", class: "act primary", text: "Save", onclick: () => done(true) }),
      el("button", { type: "button", class: "act", text: "Cancel", onclick: () => done(false) }));
    b.node.append(bar);
    function done(save) {
      if (save) { b.text = b.body.innerText.trim(); b.speech = b.text; b.nudges = []; b.editedBy = "Edited by you"; }
      b.body.contentEditable = "false"; b.body.classList.remove("editing"); b.body.setAttribute("aria-hidden", "true");
      bar.remove(); reply.decorate(b);
    }
  }
  // selecting text inside a block offers the same edit menu
  document.addEventListener("mouseup", () => {
    const sel = getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return;
    const node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
    const blk = node && node.closest(".blk");
    const msg = blk && blk.closest(".msg-a");
    if (!blk || !msg || !msg.__reply) return;
    const b = msg.__reply.blocks.get(blk.dataset.block);
    if (!b || !b.text || blk.querySelector(".editing")) return;
    const r = sel.getRangeAt(0).getBoundingClientRect();
    const anchor = { getBoundingClientRect: () => r };
    pop.setAttribute("role", "menu");
    pop.replaceChildren(el("button", { type: "button", class: "pop-item pop-inline", html: I.edit, onclick: () => openEditMenu(msg.__reply, b, anchor) }, el("b", { text: " Edit this part" })));
    placePop(pop, anchor);
  });
  document.addEventListener("mousedown", (e) => { if (!pop.hidden && !pop.contains(e.target)) closePop(); });

  // ------------------------------------------------------------------ read aloud (speech-shaped text)
  let speaking = null;
  function readAloud(reply, btn) {
    if (speaking) { speechSynthesis.cancel(); const was = speaking; speaking = null; was.lastChild.textContent = "Read aloud"; if (was === btn) return; }
    const text = reply.order.map((id) => { const b = reply.blocks.get(id); return (b.title ? b.title + ". " : "") + (b.speech || b.text); }).join(" ");
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1; u.lang = S.spelling;
    u.onend = u.onerror = () => { if (speaking === btn) { btn.lastChild.textContent = "Read aloud"; speaking = null; } };
    speaking = btn; btn.lastChild.textContent = "Stop reading";
    speechSynthesis.speak(u);
  }

  // ------------------------------------------------------------------ run a reply
  async function run(reply, { seed = 0 } = {}) {
    if (S.inflight && S.inflight.reply !== reply) stop();
    reply.reset();
    reply.root.__reply = reply;
    const controller = new AbortController();
    const isPanel = !reply.compact;
    if (isPanel) { S.inflight = { controller, reply }; setBusy(true); pin(); }
    const { frame, message } = outbound(byId(reply.frameId), reply.message);
    const body = { frame, message, seed, pace_ms: $("#opt-slow").checked ? 45 : 0, fail: $("#opt-fail").checked, tone: S.tone,
      constraints: S.rules, dismissed: S.dismissed[reply.frameId] || [], platform: S.platform, spelling: S.spelling };
    try {
      for await (const ev of streamChat(body, controller.signal)) {
        switch (ev.type) {
          case "status": reply.setThinking(ev.text); break;
          case "constraints":
            S.rules = ev.active; persist(); renderRules(ev.added);
            if (ev.cleared) toast("All rules cleared");
            break;
          case "meta": reply.meta = ev; reply.findings = ev.findings; break;
          case "safety": reply.safety = ev; if (ev.level === "crisis" && isPanel) renderChips([]); break;
          case "block": reply.startBlock(ev); break;
          case "token": reply.push(ev.block, ev.text); break;
          case "block_end": reply.endBlock(ev); break;
          case "proposal": reply.proposal = ev; break;
          case "alternates": reply.alts = ev; break;
          case "considered": reply.considered = ev; break;
          case "compliance": reply.compliance = ev.items; break;
          case "chips": if (isPanel && S.selected === reply.frameId) renderChips(ev.chips); break;
          case "error": throw new Error(ev.text);
          case "done":
            reply.finish(ev);
            if (reply.safety && reply.safety.links && reply.safety.links.length) reply.root.insertBefore(careLinks(reply.safety.links), reply.root.querySelector(".actions-row"));
            break;
        }
      }
      if (reply.state !== "complete") throw new Error("Stream ended early");
    } catch (err) {
      if (controller.signal.aborted) reply.stopped();
      else reply.error(err.message && err.message.startsWith("Couldn't") ? err.message : "Couldn't reach the model", () => run(reply, { seed }));
    } finally {
      if (isPanel && S.inflight && S.inflight.reply === reply) {
        S.inflight = null; setBusy(false);
        if (reply.state === "complete") $("#live").textContent = `Kiln: ${reply.order.map((id) => reply.blocks.get(id).speech || "").join(" ")}`;
        else if (reply.state === "error") $("#live").textContent = "Kiln couldn't reach the model.";
        $("#input").focus({ preventScroll: true });
        if (consent.thread && reply.state === "complete") { S.thread.push({ frameId: reply.frameId, message: reply.message, text: reply.text() }); persist(); }
      }
      afterGrow(scrollState());
    }
    return reply.state;
  }
  function careLinks(links) {
    return el("div", { class: "care-links" }, ...links.map((l) => el("a", { href: l.href, target: l.href.startsWith("http") ? "_blank" : null, rel: "noopener", class: "care-link", text: l.label })));
  }

  function send(text) {
    const message = (text || "").trim();
    if (!message || !S.selected) return;
    const f = byId(S.selected);
    $("#empty-thread")?.remove();
    const stream = $("#stream");
    const probe = outbound(f, message);
    const u = el("div", { class: "msg-user" }, message, el("span", { class: "about", text: `re: Frame ${frameNum(f)}` }));
    if (probe.n) {
      const kinds = [...new Set([...Object.keys(probe.counts.frame), ...Object.keys(probe.counts.message)])].join(", ");
      u.append(el("span", { class: "masked", html: I.lock }, ` ${probe.n} identifier${probe.n > 1 ? "s" : ""} (${kinds}) masked on your device before sending`));
    }
    stream.append(u);
    const reply = new Reply(stream, { frameId: f.id, message });
    $("#input").value = ""; autosize(); updateSend();
    pin(true);
    reply.root.focus({ preventScroll: true });
    openPanelMobile();
    run(reply);
  }
  function stop() { if (S.inflight) S.inflight.controller.abort(); }
  function setBusy(b) {
    const btn = $("#send");
    btn.classList.toggle("stop", b);
    btn.setAttribute("aria-label", b ? "Stop generating" : "Send");
    $("#status-dot").className = b ? "dot busy" : S.selected ? "dot live" : "dot";
    updateSend();
  }
  function updateSend() { $("#send").disabled = !S.inflight && (!S.selected || !$("#input").value.trim()); }

  // ------------------------------------------------------------------ scroll lock
  const stream = $("#stream");
  let pinned = true, programmatic = false, unseen = 0;
  const nearBottom = () => stream.scrollHeight - stream.scrollTop - stream.clientHeight < 32;
  function pin() {
    pinned = true; unseen = 0; $("#jump-pill").hidden = true;
    programmatic = true; stream.scrollTop = stream.scrollHeight;
    requestAnimationFrame(() => (programmatic = false));
  }
  const scrollState = () => stream.scrollHeight;
  function afterGrow(prev) {
    if (pinned) { programmatic = true; stream.scrollTop = stream.scrollHeight; requestAnimationFrame(() => (programmatic = false)); return; }
    const grown = stream.scrollHeight - prev;
    if (grown > 0) {
      unseen += grown;
      const lines = Math.max(1, Math.round(unseen / 22));
      $("#jump-count").textContent = `${lines} new line${lines === 1 ? "" : "s"}`;
      $("#jump-pill").hidden = false;
    }
  }
  stream.addEventListener("scroll", () => { if (programmatic) return; if (nearBottom()) { pinned = true; unseen = 0; $("#jump-pill").hidden = true; } else pinned = false; });
  stream.addEventListener("wheel", (e) => { if (e.deltaY < 0) pinned = false; }, { passive: true });
  $("#jump-pill").addEventListener("click", pin);

  // ------------------------------------------------------------------ insert (with friction for larger changes)
  function applyOps(f, ops) {
    const changed = new Set();
    for (const op of ops) {
      if (op.op === "set") { const l = f.layers.find((x) => x.id === op.layer); if (l) { Object.assign(l, op.props); changed.add(l.id); } }
      else if (op.op === "insert") { const i = f.layers.findIndex((x) => x.id === op.after); if (!f.layers.some((x) => x.id === op.layer.id)) { f.layers.splice(i + 1, 0, structuredClone(op.layer)); changed.add(op.layer.id); } }
      else if (op.op === "shift") {
        const a = f.layers.find((x) => x.id === op.within);
        const contains = (c) => a && c.role === "container" && c.x <= a.x && c.y <= a.y && c.x + c.w >= a.x + a.w && c.y + c.h >= a.y + a.h;
        for (const l of f.layers) { if (contains(l)) l.h = Math.min(f.h - l.y, l.h + op.dy); else if (l.y >= op.from_y) l.y += op.dy; }
      }
    }
    return changed;
  }
  /** Small changes insert immediately (with Undo). Larger ones pause for a review
   *  where each change can be unticked: the person decides, line by line. */
  function requestInsert(frameId, ops, lines, btn, label, review) {
    if (!review || !lines) return insert(frameId, ops, btn, label);
    const dlg = $("#review"), body = $("#review-body");
    const f = byId(frameId);
    body.replaceChildren(el("p", { text: `${lines.length} changes to Frame ${frameNum(f)}. Untick anything you don't want. Nothing is applied until you confirm, and you can undo afterwards.` }));
    const list = el("ul", { class: "review-list" });
    lines.forEach((l, i) => list.append(el("li", {}, el("label", {}, el("input", { type: "checkbox", checked: true, "data-i": i }),
      el("span", { class: "p-layer", text: l.layer }), el("span", { class: "p-prop", text: l.prop }),
      l.from != null ? valueEl(l.from) : "", el("span", { class: "p-arrow", text: l.from != null ? "→" : "+" }), valueEl(l.to)))));
    const go = el("button", { type: "button", class: "act primary", text: `Insert ${lines.length} changes` });
    list.addEventListener("change", () => { const n = list.querySelectorAll("input:checked").length; go.textContent = n ? `Insert ${n} change${n > 1 ? "s" : ""}` : "Nothing selected"; go.disabled = !n; });
    go.addEventListener("click", () => {
      const keep = new Set([...list.querySelectorAll("input:checked")].map((c) => +c.dataset.i));
      const out = [];
      ops.forEach((op, k) => {
        const mine = lines.map((l, i) => ({ ...l, i })).filter((l) => l.op === k);
        const kept = mine.filter((l) => keep.has(l.i));
        if (!kept.length) return;
        if (op.op === "set") { const props = {}; kept.forEach((l) => (l.props || [l.prop]).forEach((p) => (props[p] = op.props[p]))); out.push({ ...op, props }); }
        else out.push(op);
      });
      dlg.close();
      insert(frameId, out, btn, label);
    });
    body.append(list, el("div", { class: "review-actions" }, go, el("button", { type: "button", class: "act", text: "Cancel", onclick: () => dlg.close() })));
    dlg.showModal();
  }
  function insert(frameId, ops, btn, label) {
    const f = byId(frameId);
    S.undo.push({ frameId, before: structuredClone(f) });
    const changed = applyOps(f, ops);
    S.analysis.delete(frameId);
    rerenderFrame(frameId);
    const wrap = framesEl.querySelector(`.frame-wrap[data-frame="${frameId}"]`);
    changed.forEach((id) => { const n = wrap.querySelector(`[data-layer="${CSS.escape(id)}"]`); if (n) { n.classList.add("changed"); setTimeout(() => n.classList.remove("changed"), 2600); } });
    if (btn) { btn.disabled = true; const t = btn.lastChild; if (t && t.nodeType === 3) t.textContent = "Inserted"; }
    toast(`Inserted ${label} into Frame ${frameNum(f)}`, "Undo", undo);
    if (S.selected === frameId) select(frameId);
  }
  function undo() {
    const u = S.undo.pop();
    if (!u) return;
    S.frames[S.frames.findIndex((f) => f.id === u.frameId)] = u.before;
    S.analysis.delete(u.frameId);
    rerenderFrame(u.frameId);
    if (S.selected === u.frameId) select(u.frameId);
    toast(`Reverted Frame ${frameNum(u.before)}`);
  }
  let toastTimer;
  function toast(msg, actionLabel, action) {
    const t = $("#toast");
    t.replaceChildren(el("span", { text: msg }));
    if (actionLabel) t.append(el("button", { type: "button", text: actionLabel, onclick: () => { t.hidden = true; action(); } }));
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 6000);
  }

  // ------------------------------------------------------------------ settings: memory, privacy, locale, wellbeing
  function openSettings() {
    const body = $("#settings-body");
    const sw = (label, hint, checked, onchange) => {
      const id = "sw-" + label.replace(/\W+/g, "-").toLowerCase();
      return el("div", { class: "sw-row" },
        el("label", { for: id }, el("b", { text: label }), el("span", { text: hint })),
        el("input", { type: "checkbox", role: "switch", id, class: "sw", checked, onchange: (e) => onchange(e.target.checked) }));
    };
    const remembers = [];
    if (consent.prefs) remembers.push(`Style: ${S.tone}; platform: ${S.platform}; spelling: ${S.spelling}`);
    if (consent.rules) remembers.push(`Rules: ${S.rules.map((r) => r.label).join(", ") || "none yet"}`);
    if (consent.dismissed) remembers.push(`Dismissed findings: ${Object.values(S.dismissed).flat().length}`);
    if (consent.thread) remembers.push(`Thread history: ${S.thread.length} replies`);
    const dismissedAll = Object.entries(S.dismissed).flatMap(([fid, arr]) => arr.map((d) => ({ ...d, fid })));
    body.replaceChildren(...[
      el("section", { class: "set-sec" }, el("h3", { text: "What Kiln remembers" }),
        el("p", { class: "set-note", text: "Everything is off until you turn it on. Anything remembered stays in this browser only, never on a server." }),
        el("div", { class: `mem-now${remembers.length ? "" : " empty"}` }, remembers.length ? el("ul", {}, ...remembers.map((r) => el("li", { text: r }))) : "Right now: nothing. Close this tab and it's all gone."),
        sw("Style and locale", "Response style, platform and spelling", consent.prefs, (v) => { consent.prefs = v; persist(); openSettings(); }),
        sw("Rules you set", "Keep rules like “under 50 words” across visits", consent.rules, (v) => { consent.rules = v; persist(); openSettings(); }),
        sw("Dismissed findings", "Things you marked “not an issue”", consent.dismissed, (v) => { consent.dismissed = v; persist(); openSettings(); }),
        sw("Thread history", "Your questions and Kiln's answers", consent.thread, (v) => { consent.thread = v; if (!v) S.thread = []; persist(); openSettings(); }),
        el("button", { type: "button", class: "act danger", text: "Forget everything now", onclick: () => {
          Object.values(MEM_KEYS).forEach(store.del); store.del("kiln.consent");
          Object.keys(consent).forEach((k) => (consent[k] = false));
          S.thread = []; S.rules = []; S.dismissed = {}; renderRules(); persist(); S.analysis.clear(); if (S.selected) select(S.selected);
          toast("Forgotten. Kiln remembers nothing."); openSettings();
        } })),
      dismissedAll.length ? el("section", { class: "set-sec" }, el("h3", { text: "Dismissed by you" }),
        el("ul", { class: "dis-list" }, ...dismissedAll.map((d) => el("li", {}, `${d.label} on “${d.name}” · Frame ${frameNum(byId(d.fid))}`,
          el("button", { type: "button", class: "act", text: "Restore", onclick: () => { S.dismissed[d.fid] = S.dismissed[d.fid].filter((x) => !(x.issue === d.issue && x.layer === d.layer)); persist(); S.analysis.delete(d.fid); if (S.selected === d.fid) select(d.fid); openSettings(); } }))))) : null,
      el("section", { class: "set-sec" }, el("h3", { text: "Privacy" }),
        sw("Mask identifiers before sending", "Emails, phone and card numbers in frames or messages are replaced with dots on your device. The critic only needs text length.", S.maskPII, (v) => { S.maskPII = v; persist(); }),
        el("p", { class: "set-note", html: "The server keeps nothing: no logs of messages or frames, and responses are sent with <code>Cache-Control: no-store</code>." }),
        sw("Help improve Kiln", "Off by default. Adds a rating to each reply and shows exactly what would be shared.", consent.improve, (v) => { consent.improve = v; persist(); openSettings(); }),
        consent.improve ? el("p", { class: "set-note", text: "This prototype has no collection server, so ratings stay on this page. What would be sent: rating, response style and intent. Never the frame or your words." }) : null),
      el("section", { class: "set-sec" }, el("h3", { text: "Platform and language" }),
        el("p", { class: "set-note", text: "Changes the units Kiln uses and which guideline it cites first. Spelling follows your variety of English." }),
        seg("Platform", [["web", "Web · px"], ["ios", "iOS · pt"], ["android", "Android · dp"]], S.platform, (v) => { S.platform = v; persist(); }),
        seg("Spelling", [["en-US", "US (color)"], ["en-GB", "UK (colour)"]], S.spelling, (v) => { S.spelling = v; persist(); })),
      el("section", { class: "set-sec" }, el("h3", { text: "Wellbeing" }),
        sw("Gentle break reminders", "A quiet note after an hour, or late at night. Nothing is tracked beyond this tab.", S.wellbeing, (v) => { S.wellbeing = v; persist(); }),
        el("button", { type: "button", class: "act", text: "Preview a reminder", onclick: () => { $("#settings").close(); showWellbeing("hour"); } })),
    ].filter(Boolean));
    if (!$("#settings").open) $("#settings").showModal();
  }
  function seg(label, opts, cur, onpick) {
    const g = el("div", { class: "seg-row", role: "radiogroup", "aria-label": label }, el("span", { class: "seg-lbl", text: label }));
    opts.forEach(([v, t]) => g.append(el("button", { type: "button", role: "radio", "aria-checked": String(v === cur), text: t,
      onclick: (e) => { g.querySelectorAll("[role=radio]").forEach((b) => b.setAttribute("aria-checked", "false")); e.currentTarget.setAttribute("aria-checked", "true"); onpick(v); } })));
    return g;
  }
  function feedbackRow(reply) {
    const row = el("div", { class: "fb-row" }, el("span", { text: "Was this useful?" }));
    ["Yes", "No"].forEach((v) => row.append(el("button", { type: "button", class: "act", text: v, onclick: () => {
      row.replaceChildren(el("span", { class: "meta-line", text: `Recorded on this page only: {rating: "${v.toLowerCase()}", style: "${reply.meta?.tone}", intent: "${reply.meta?.intent}"}` }));
    } })));
    return row;
  }
  $("#btn-settings").addEventListener("click", openSettings);
  document.querySelectorAll("dialog [data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));

  // ------------------------------------------------------------------ wellbeing: time-aware, gentle, dismissible
  const T0 = (() => { try { const v = +sessionStorage.getItem("kiln.t0"); if (v) return v; const n = Date.now(); sessionStorage.setItem("kiln.t0", n); return n; } catch { return Date.now(); } })();
  let snoozeUntil = 0, lateShown = false;
  function showWellbeing(kind) {
    const w = $("#wellbeing");
    const msg = kind === "late"
      ? "It's late. Kiln will still be here tomorrow, and design calls made after midnight are worth a second look in the morning."
      : "You've been at this for about an hour. A short break is a good way to see the frame fresh.";
    w.replaceChildren(el("span", { class: "wb-ic", html: KIND_ICON.care }), el("span", { text: msg }),
      el("button", { type: "button", class: "act", text: "Remind me in 30 min", onclick: () => { snoozeUntil = Date.now() + 30 * 60e3; w.hidden = true; } }),
      el("button", { type: "button", class: "act", text: "Turn off", onclick: () => { S.wellbeing = false; persist(); w.hidden = true; } }),
      el("button", { type: "button", class: "icon-btn", "aria-label": "Dismiss", html: I.no, onclick: () => { snoozeUntil = Date.now() + 60 * 60e3; w.hidden = true; } }));
    w.hidden = false;
  }
  setInterval(() => {
    if (!S.wellbeing || Date.now() < snoozeUntil || !$("#wellbeing").hidden) return;
    const h = new Date().getHours();
    if (!lateShown && h >= 0 && h < 5) { lateShown = true; showWellbeing("late"); return; }
    if (Date.now() - T0 > 60 * 60e3) { snoozeUntil = Date.now() + 60 * 60e3; showWellbeing("hour"); }
  }, 60e3);

  // ------------------------------------------------------------------ quick-ask overlay (a guest)
  function openQuick() {
    const q = $("#quick");
    if (!S.selected) select(S.frames[3]?.id || S.frames[0].id);
    const f = byId(S.selected);
    const box = framesEl.querySelector(`.frame-wrap[data-frame="${f.id}"] .frame-box`).getBoundingClientRect();
    const w = Math.min(380, innerWidth - 32);
    q.style.left = `${Math.max(16, Math.min(box.left, innerWidth - w - 16))}px`;
    q.style.top = `${Math.max(16, Math.min(box.top + 40, innerHeight - 260))}px`;
    $("#quick-attach").innerHTML = I.clip;
    $("#quick-attach").append(` Frame ${frameNum(f)}`);
    $("#quick-answer").replaceChildren();
    q.hidden = false;
    $("#quick-input").value = "";
    $("#quick-input").focus();
  }
  function closeQuick() { $("#quick").hidden = true; }
  $("#quick-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const message = $("#quick-input").value.trim();
    if (!message) return;
    const ans = $("#quick-answer");
    ans.replaceChildren();
    run(new Reply(ans, { frameId: S.selected, message, compact: true }));
  });
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#quick").hidden ? openQuick() : closeQuick(); }
    else if (e.key === "Escape") { if (!pop.hidden) closePop(); else if (!$("#quick").hidden) closeQuick(); else if (S.inflight) stop(); }
  });
  document.addEventListener("mousedown", (e) => { const q = $("#quick"); if (!q.hidden && !q.contains(e.target)) closeQuick(); });

  // ------------------------------------------------------------------ composer
  const input = $("#input");
  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; }
  input.addEventListener("input", () => { autosize(); updateSend(); });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!S.inflight) send(input.value); } });
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); S.inflight ? stop() : send(input.value); });

  // ------------------------------------------------------------------ panel resize + mobile
  const resizer = $("#resizer");
  const setW = (w) => document.documentElement.style.setProperty("--panel-w", `${Math.max(340, Math.min(w, innerWidth * 0.6))}px`);
  resizer.addEventListener("pointerdown", (e) => {
    resizer.setPointerCapture(e.pointerId);
    const move = (ev) => setW(innerWidth - ev.clientX);
    const up = () => { resizer.removeEventListener("pointermove", move); resizer.removeEventListener("pointerup", up); };
    resizer.addEventListener("pointermove", move); resizer.addEventListener("pointerup", up);
  });
  resizer.addEventListener("keydown", (e) => { const cur = $("#panel").getBoundingClientRect().width; if (e.key === "ArrowLeft") setW(cur + 24); if (e.key === "ArrowRight") setW(cur - 24); });
  function openPanelMobile() { $("#app").classList.add("panel-open"); }
  function closePanelMobile() { $("#app").classList.remove("panel-open"); }
  $("#fab").addEventListener("click", () => { if (!S.selected && S.frames[0]) select(S.frames[3]?.id || S.frames[0].id); openPanelMobile(); input.focus(); });
  $("#btn-close-panel").addEventListener("click", closePanelMobile);

  // ------------------------------------------------------------------ model card
  $("#btn-model").addEventListener("click", async () => {
    const d = $("#model-dialog");
    d.showModal();
    try {
      const m = await (await fetch("/api/model")).json();
      const c = m.metrics.critic, it = m.metrics.intent, n = m.metrics.narrator, par = it.parity || {};
      const pct = (x) => `${(x * 100).toFixed(1)}%`;
      const rows = Object.entries(c.frame).map(([k, v]) => `<tr><td>${k.replace(/_/g, " ")}</td><td class="n">${pct(v.f1)}</td><td class="n">${pct(c.layer[k].f1)}</td><td class="n">${pct(v.precision)}</td><td class="n">${pct(v.recall)}</td></tr>`).join("");
      const parRow = (k, lbl) => par[k] ? `<tr><td>${lbl}</td><td class="n">${par[k].n}</td><td class="n">${pct(par[k].intent_acc)}</td><td class="n">${pct(par[k].focus_acc)}</td></tr>` : "";
      $("#md-body").innerHTML = `
        <p>Three small models, trained in PyTorch ${m.metrics.torch} and exported to ONNX. The server runs them with onnxruntime in a single Vercel function; PyTorch never ships to production.</p>
        <div class="md-stats">
          <div><span class="k">Critic frame F1</span><span class="v">${pct(c.frame_macro_f1)}</span></div>
          <div><span class="k">Critic layer F1</span><span class="v">${pct(c.layer_macro_f1)}</span></div>
          <div><span class="k">Intent · informal phrasing</span><span class="v">${par.informal ? pct(par.informal.intent_acc) : "–"}</span></div>
        </div>
        <div><h3>1 · Critic (set transformer, ${(c.params / 1000).toFixed(0)}k params)</h3>
        Reads up to ${m.max_layers} layers per frame. Each layer attends to every other layer, then a per-layer head scores six issues; the frame score is a max over layers, so the layer that drives a finding is the one Kiln cites. For measurable issues (contrast, targets, type size, spacing) a citation is kept only if the layer's geometry confirms it; the model proposes, measurement confirms. Trained on ${c.n_train.toLocaleString()} procedurally generated frames labelled by design-review heuristics; scores below are on ${c.n_val.toLocaleString()} held-out frames.</div>
        <table class="md-table"><thead><tr><th>Issue</th><th class="n">Frame F1</th><th class="n">Layer F1</th><th class="n">Precision</th><th class="n">Recall</th></tr></thead><tbody>${rows}</tbody></table>
        <div><h3>2 · Intent (hashed n-gram MLP)</h3>Maps a question to what you want (diagnose, fix, alternates, audit, describe, clarify, or something personal) and which issue it's about. Trained with informal, regional and non-native phrasings as first-class examples, then tested on two hand-written sets it never saw:</div>
        <table class="md-table"><thead><tr><th>Held-out set</th><th class="n">n</th><th class="n">Intent</th><th class="n">Focus</th></tr></thead><tbody>${parRow("standard", "Textbook English")}${parRow("informal", "Informal, regional, non-native")}</tbody></table>
        <p class="meta-line">Small sets (${par.standard ? par.standard.n : "?"} each), so treat differences of one question (≈4.5 points) as noise.</p>
        <div><h3>3 · Narrator (conditional GRU, vocab ${n.vocab})</h3>Writes each sentence token by token in one of ${(m.modes || []).length} registers (${(m.modes || []).join(", ")}). Numbers and layer names are slot tokens filled from measured geometry, and slots a finding can't fill are masked out during decoding, so it can't invent a ratio.</div>
        <div><h3>How claims are labelled</h3><b>Standard</b> means published consensus (WCAG). <b>Convention</b> means a common guideline with credible alternatives, shown under “Where people disagree”. <b>Judgment</b> is the critic's opinion with its probability. Care responses are <b>written by people</b>, never generated.</div>
        <p class="meta-line">Limits: synthetic training data; heuristics are the teacher. Care routing is a keyword safety net plus the intent model. It will miss things and is not a clinical screen.</p>`;
    } catch { $("#md-body").textContent = "Couldn't load the model card."; }
  });
  $("#md-close").addEventListener("click", () => $("#model-dialog").close());

  // ------------------------------------------------------------------ boot
  setTone(S.tone);
  renderRules();
  persist();
  (async function boot() {
    try {
      const { frames } = await (await fetch("/api/frames")).json();
      S.frames = frames;
      renderCanvas();
      renderAttach();
    } catch {
      framesEl.replaceChildren(el("p", { class: "err-line", text: "Couldn't load the canvas. Is the API running?" }));
    }
  })();
})();
