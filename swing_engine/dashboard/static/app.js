/* Swing Engine dashboard (vanilla JS, no build step).
 *
 * Safety rules this file follows:
 *  - Untrusted text (alert titles, news, theses, journal) is only ever set with textContent, or passed through
 *    renderMarkdown(), which escapes all HTML first. No other innerHTML with data.
 *  - The page is read-only toward the broker. The only POSTs are alert ratings and tripping the kill switch.
 *  - Every API call goes through api(), which never throws: it returns {ok, data} or {ok:false, unavailable}.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------------------------------------
  // Constants
  // ------------------------------------------------------------------------------------------------
  const FAST_REFRESH_MS = 30 * 1000;      // summary, positions, alerts
  const SLOW_REFRESH_MS = 5 * 60 * 1000;  // charts, regime, orders
  const FETCH_TIMEOUT_MS = 12 * 1000;
  const SLOW_FETCH_TIMEOUT_MS = 25 * 1000;
  const FEED_STALE_OPEN_MIN = 15;         // a feed silent this long while the market is open is stale
  const FEED_STALE_CLOSED_MIN = 24 * 60;  // ... and this long while it is closed
  const SHADOW_MIN_N = 20;                // fewer graded signals than this = dimmed "too few to judge"
  const EVENT_DRIVEN_FEED = /account/i;   // trade-update feeds are silent until something fills: never "stale"
  const ET = "America/New_York";
  const TABS = ["overview", "charts", "signals", "shadow", "drift", "alerts", "journal", "replay", "settings"];
  const THEME_KEY = "swing.theme";

  const REGIMES = {
    healthy_uptrend: { name: "Healthy uptrend", tone: "ok", desc: "SPY is trending up with broad participation. Breakouts and pullbacks are allowed at full size." },
    narrow_uptrend: { name: "Narrow uptrend", tone: "warn", desc: "SPY is up, but few stocks are participating. Leaders-only pullbacks at reduced size; no breakouts." },
    choppy: { name: "Choppy", tone: "warn", desc: "SPY is above its 200-day average without a clean trend. Mean reversion only." },
    correction: { name: "Correction", tone: "bad", desc: "SPY is below its 200-day average or in a downtrend. No new long entries." },
    high_vol_selloff: { name: "High-volatility selloff", tone: "bad", desc: "Volatility is high and SPY is below its 50-day average. Small RSI-2 positions only." },
  };
  const STRATEGY_NAMES = {
    breakout_52w: "52-week breakout",
    sr_breakout: "S/R breakout",
    momentum_burst: "Momentum burst",
    pullback_trend: "Trend pullback",
    sr_bounce: "S/R bounce",
    rsi2_meanrev: "RSI-2 mean reversion",
    insider_cluster: "Insider cluster",
    pullback_holy_grail: "Holy Grail pullback",
    base_breakout: "Base breakout",
    power_gap: "Power gap",
    qullamaggie_flag: "Qullamaggie flag",
    episodic_pivot: "Episodic pivot",
  };
  const DECISIONS = {
    approve_for_risk_check: { label: "Approved", tone: "ok" },
    approve: { label: "Approved", tone: "ok" },
    reject: { label: "Rejected", tone: "bad" },
    needs_more_info: { label: "Needs more info", tone: "warn" },
  };
  const RATINGS = [
    { key: "useful", label: "Useful" },
    { key: "noise", label: "Noise" },
    { key: "traded", label: "Traded" },
  ];

  // ------------------------------------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------------------------------------
  const state = {
    tab: "overview",
    loaded: {},                 // tab -> true once rendered at least once
    summary: null,
    positions: null,            // last successful positions array
    equityPeriod: "3M",
    equityMode: "rebased",
    equityData: null,
    chartSymbol: null,
    chartDays: 180,
    orderStatus: "open",
    signals: null,
    signalFilters: { strategy: "", taken: "all" },
    signalOpen: new Set(),
    alerts: null,
    alertHours: 48,
    alertPrio: "all",
    journalDates: [],
    journalDate: null,
    charts: {},                 // name -> {chart, series...}
    lastFast: 0,
    lastSlow: 0,
    timers: { fast: null, slow: null, tick: null },
    inflight: {},               // key -> AbortController (to drop superseded requests)
    health: null,
  };

  // ------------------------------------------------------------------------------------------------
  // DOM helpers (no innerHTML with data anywhere)
  // ------------------------------------------------------------------------------------------------
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /** el("td", {class: "r", title: "x"}, "text" | Node | [children]) */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "dataset") Object.assign(node.dataset, v);
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else if (v === true) node.setAttribute(k, "");
        else node.setAttribute(k, String(v));
      }
    }
    append(node, children);
    return node;
  }
  function append(node, children) {
    if (children === null || children === undefined || children === false) return node;
    if (Array.isArray(children)) { children.forEach((c) => append(node, c)); return node; }
    node.appendChild(children instanceof Node ? children : document.createTextNode(String(children)));
    return node;
  }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); return node; }
  function replace(node, children) { clear(node); append(node, children); return node; }
  const SVG_NS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, String(v));
    return n;
  }
  function icon(path) {
    const s = svg("svg", { viewBox: "0 0 24 24", width: 16, height: 16, "aria-hidden": "true", class: "state__icon" });
    s.appendChild(svg("path", { d: path, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    return s;
  }
  const ICON_INFO = "M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z";
  const ICON_WARN = "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z";
  function chevron() {
    const s = svg("svg", { viewBox: "0 0 24 24", width: 14, height: 14, "aria-hidden": "true" });
    s.appendChild(svg("path", { d: "M9 6l6 6-6 6", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    return s;
  }

  // ------------------------------------------------------------------------------------------------
  // Panel states: skeleton, unavailable, empty
  // ------------------------------------------------------------------------------------------------
  function skeletonLines(n) {
    const widths = ["w-100", "w-80", "w-60", "w-100", "w-40", "w-80"];
    const box = el("div", { class: "skel-block", "aria-busy": "true", "aria-label": "Loading" });
    for (let i = 0; i < (n || 4); i++) box.appendChild(el("div", { class: "skel skel-line " + widths[i % widths.length] }));
    return box;
  }
  function showSkeleton(node, lines) {
    if (!node) return;
    replace(node, skeletonLines(lines));
  }
  /** Friendly "not available yet" box. reason comes from the API and is shown as plain text. */
  function unavailableBox(reason, opts) {
    const o = opts || {};
    return el("div", { class: "state" + (o.error ? " state--error" : ""), role: "status" }, [
      icon(o.error ? ICON_WARN : ICON_INFO),
      el("div", null, [el("strong", { text: o.title || "Not available yet" }), el("span", { text: ": " + (reason || "no data") })]),
    ]);
  }
  function showUnavailable(node, res, title) {
    if (!node) return;
    replace(node, unavailableBox(res && res.unavailable, { error: res && res.network, title: title }));
  }
  function emptyBox(text) { return el("div", { class: "empty", text: text }); }
  const NOTE_LABELS = {
    spy: "SPY", account: "Account", levels: "Levels", current_stop: "Current stop", ledger: "Order ledger",
    broker: "Broker", breadth_history: "Breadth history", state: "Regime", allowed: "Router", reviews: "Reviews",
    intents: "Intents", autopilot: "Autopilot audit", nightly: "Nightly report", cycle: "Cycle report", regime: "Regime file",
  };
  /** The small line under a panel: a cached copy served while the store was locked by a writer, where the rows came
   *  from when it is a fallback, and the parts that could not be read. res = an api() result (or null to hide). */
  function setNote(id, res, extra, skip) {
    const node = document.getElementById(id);
    if (!node) return;
    const items = [];
    const st = res && res.ok ? res.stale : null;
    if (st && typeof st === "object") {
      const age = toNum(st.age_s);
      const ageText = age === null ? "" : " (" + (age < 90 ? Math.round(age) + " s" : fmtDuration(age * 1000)) + " old)";
      items.push(el("span", { class: "is-warn", text: "Cached copy from " + (st.cached_at ? fmtTime(st.cached_at) : "earlier") + ageText + ": " + reasonText(st.reason || "the store is busy") }));
    }
    (extra || []).filter(Boolean).forEach((t) => items.push(el("span", { text: String(t) })));
    const partial = res && res.ok ? res.partial : null;
    if (partial && typeof partial === "object") {
      Object.entries(partial).forEach(([k, v]) => {
        if (v && !(skip || []).includes(k)) items.push(el("span", { text: (NOTE_LABELS[k] || humanize(k)) + ": " + String(v) }));
      });
    }
    replace(node, items);
    node.hidden = !items.length;
  }
  /** "alpaca paper" / "demo" are the normal sources; anything else is a fallback worth naming. */
  function fallbackSource(src) { return src && !/^(alpaca|demo)\b/i.test(String(src)) ? String(src) : null; }
  /** Re-render node via fn() keeping keyboard focus on the "same" element (matched by a data-key path). */
  function preservingFocus(node, fn) {
    const active = document.activeElement;
    let key = null;
    if (active && node.contains(active)) {
      const holder = active.closest("[data-key]");
      key = holder ? { k: holder.getAttribute("data-key"), sub: active.getAttribute("data-rating"), self: holder === active } : null;
    }
    fn();
    if (!key) return;
    const holder = $$("[data-key]", node).find((n) => n.getAttribute("data-key") === key.k);
    if (!holder) return;
    const target = key.self ? holder : key.sub ? $('[data-rating="' + key.sub + '"]', holder) : null;
    if (target) target.focus();
  }
  /** True when payload is identical to the last one rendered under name (skips needless re-renders). */
  const lastPayload = {};
  function unchanged(name, data) {
    let j;
    try { j = JSON.stringify(data); } catch (e) { return false; }
    if (lastPayload[name] === j) return true;
    lastPayload[name] = j;
    return false;
  }

  // ------------------------------------------------------------------------------------------------
  // API client: never throws, always resolves to {ok:true, data, stale?, partial?, source?} |
  // {ok:false, unavailable, network?}. stale = served from cache while the store was locked by a writer;
  // partial = {section: reason} for parts that could not be read; source = where the rows came from.
  // ------------------------------------------------------------------------------------------------
  async function api(path, opts) {
    const o = opts || {};
    const key = o.key || null;
    if (key && state.inflight[key]) { try { state.inflight[key].abort(); } catch (e) { /* ignore */ } }
    const ctl = new AbortController();
    if (key) state.inflight[key] = ctl;
    let timedOut = false;
    setBusy(1);
    const timer = setTimeout(() => { timedOut = true; ctl.abort(); }, o.timeout || FETCH_TIMEOUT_MS);
    try {
      // X-Swing-Dashboard: the server refuses /api/* without it when the browser sends no Sec-Fetch-Site (a
      // cross-origin page cannot add a custom header without a preflight, and preflights are refused).
      const init = { method: o.method || "GET", headers: { Accept: "application/json", "X-Swing-Dashboard": "1" }, signal: ctl.signal, cache: "no-store", credentials: "same-origin" };
      if (o.body !== undefined) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(o.body);
      }
      const resp = await fetch(path, init);
      let payload = null;
      try { payload = await resp.json(); } catch (e) { payload = null; }
      if (payload && typeof payload === "object" && "ok" in payload) {
        if (payload.ok) return { ok: true, data: payload.data, stale: payload.stale || null, partial: payload.partial || null, source: payload.source || null };
        return { ok: false, unavailable: String(payload.unavailable || payload.error || "no data yet") };
      }
      return { ok: false, unavailable: "the server answered HTTP " + resp.status + " without the expected JSON", network: !resp.ok };
    } catch (err) {
      if (ctl.signal.aborted && !timedOut) return { ok: false, aborted: true, unavailable: "superseded" };
      return {
        ok: false,
        network: true,
        unavailable: timedOut
          ? "the dashboard server did not answer within " + Math.round((o.timeout || FETCH_TIMEOUT_MS) / 1000) + " s"
          : "cannot reach the dashboard server (is it still running?)",
      };
    } finally {
      clearTimeout(timer);
      setBusy(-1);
      if (key && state.inflight[key] === ctl) delete state.inflight[key];
    }
  }
  let busyCount = 0;
  function setBusy(delta) {
    busyCount = Math.max(0, busyCount + delta);
    const n = document.getElementById("updated");
    if (n) n.classList.toggle("is-busy", busyCount > 0);
  }

  // ------------------------------------------------------------------------------------------------
  // Formatting
  // ------------------------------------------------------------------------------------------------
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const toNum = (v) => {
    if (isNum(v)) return v;
    if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
    return null;
  };
  const DASH = "\u2014";
  const MINUS = "\u2212";
  const nfCache = {};
  function nf(min, max) {
    const k = min + ":" + max;
    if (!nfCache[k]) nfCache[k] = new Intl.NumberFormat("en-US", { minimumFractionDigits: min, maximumFractionDigits: max });
    return nfCache[k];
  }
  function fmtNum(v, dec) {
    const n = toNum(v);
    if (n === null) return DASH;
    const d = dec === undefined ? 2 : dec;
    const s = nf(d, d).format(Math.abs(n));
    return (n < 0 && Number(s.replace(/,/g, "")) !== 0 ? MINUS : "") + s;
  }
  function fmtMoney(v, dec) {
    const n = toNum(v);
    if (n === null) return DASH;
    const s = "$" + nf(dec === undefined ? 2 : dec, dec === undefined ? 2 : dec).format(Math.abs(n));
    return (n < 0 ? MINUS : "") + s;
  }
  function fmtSignedMoney(v, dec) {
    const n = toNum(v);
    if (n === null) return DASH;
    const s = "$" + nf(dec === undefined ? 2 : dec, dec === undefined ? 2 : dec).format(Math.abs(n));
    if (Math.abs(n) < 0.005) return s;
    return (n > 0 ? "+" : MINUS) + s;
  }
  /** v is already in percent units (2.5 = 2.5%). */
  function fmtPct(v, dec, signed) {
    const n = toNum(v);
    if (n === null) return DASH;
    const d = dec === undefined ? 2 : dec;
    const s = nf(d, d).format(Math.abs(n)) + "%";
    if (Number(nf(d, d).format(Math.abs(n)).replace(/,/g, "")) === 0) return s;
    if (n < 0) return MINUS + s;
    return (signed ? "+" : "") + s;
  }
  function fmtSigned(v, dec, suffix) {
    const n = toNum(v);
    if (n === null) return DASH;
    const d = dec === undefined ? 2 : dec;
    const s = nf(d, d).format(Math.abs(n)) + (suffix || "");
    if (Number(nf(d, d).format(Math.abs(n)).replace(/,/g, "")) === 0) return s;
    return (n > 0 ? "+" : MINUS) + s;
  }
  function fmtInt(v) { const n = toNum(v); return n === null ? DASH : (n < 0 ? MINUS : "") + nf(0, 0).format(Math.abs(n)); }
  function fmtQty(v) { const n = toNum(v); if (n === null) return DASH; return Number.isInteger(n) ? fmtInt(n) : fmtNum(n, 4).replace(/0+$/, "").replace(/\.$/, ""); }
  /** Win rates and other ratios arrive as fractions (0.55). Treat values > 1 as already-percent. */
  function fmtRatioPct(v, dec) { const n = toNum(v); if (n === null) return DASH; return fmtPct(Math.abs(n) <= 1 ? n * 100 : n, dec === undefined ? 1 : dec); }
  function signClass(v) { const n = toNum(v); if (n === null || Math.abs(n) < 1e-9) return "flat"; return n > 0 ? "pos" : "neg"; }
  function arrow(v) { const n = toNum(v); if (n === null || Math.abs(n) < 1e-9) return ""; return n > 0 ? "\u25b2 " : "\u25bc "; }
  function humanize(s) {
    if (s === null || s === undefined || s === "") return DASH;
    const t = String(s).replace(/[_-]+/g, " ").trim();
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  /** Machine tokens ("daily_cap") are humanized; sentences are shown as written (they may quote config keys). */
  function reasonText(r) {
    if (r === null || r === undefined || r === "") return DASH;
    const t = String(r).trim();
    if (/^[a-z][a-z0-9]*[_.=]/.test(t) && /\s/.test(t)) return t; // starts with a config key: keep it verbatim
    return /\s/.test(t) ? t.charAt(0).toUpperCase() + t.slice(1) : humanize(t);
  }
  function strategyName(code) { return code ? (STRATEGY_NAMES[code] || humanize(code)) : DASH; }

  // Dates -------------------------------------------------------------------------------------------
  function parseTime(v) {
    if (v === null || v === undefined || v === "") return null;
    if (isNum(v)) return new Date(v > 1e12 ? v : v * 1000);
    const s = String(v);
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(s + "T12:00:00Z");
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const dtfCache = {};
  function dtf(opts, tz) {
    const k = JSON.stringify(opts) + (tz || "");
    if (!dtfCache[k]) dtfCache[k] = new Intl.DateTimeFormat("en-US", Object.assign({}, opts, tz ? { timeZone: tz } : {}));
    return dtfCache[k];
  }
  const LOCAL_TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { return ""; } })();
  const LOCAL_IS_ET = (() => {
    try {
      const now = new Date();
      return dtf({ hour: "2-digit", minute: "2-digit", day: "2-digit", hour12: false }, ET).format(now) ===
        dtf({ hour: "2-digit", minute: "2-digit", day: "2-digit", hour12: false }).format(now);
    } catch (e) { return false; }
  })();
  function fmtTime(v, tz) { const d = parseTime(v); return d ? dtf({ hour: "numeric", minute: "2-digit" }, tz).format(d) : DASH; }
  function fmtDateTime(v, tz) { const d = parseTime(v); return d ? dtf({ month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }, tz).format(d) : DASH; }
  function fmtDay(v) {
    if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v)) {
      const d = new Date(v.slice(0, 10) + "T12:00:00Z");
      return dtf({ weekday: "short", month: "short", day: "numeric", year: "numeric" }, "UTC").format(d);
    }
    const d = parseTime(v);
    return d ? dtf({ weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(d) : DASH;
  }
  function fmtShortDay(v) {
    if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v)) {
      return dtf({ month: "short", day: "numeric" }, "UTC").format(new Date(v.slice(0, 10) + "T12:00:00Z"));
    }
    const d = parseTime(v);
    return d ? dtf({ month: "short", day: "numeric" }).format(d) : DASH;
  }
  /** "1:05 PM ET (10:05 AM local)" or just "1:05 PM ET" when the viewer is in ET. */
  function fmtEtLocal(v, withDay) {
    const d = parseTime(v);
    if (!d) return DASH;
    const opts = withDay ? { weekday: "short", hour: "numeric", minute: "2-digit" } : { hour: "numeric", minute: "2-digit" };
    const et = dtf(opts, ET).format(d) + " ET";
    if (LOCAL_IS_ET) return et;
    return et + " (" + dtf(opts).format(d) + " local)";
  }
  /** "Now" for ages and countdowns. Demo data is frozen at its generated_at, so measure from the server clock. */
  let clockOffsetMs = 0;
  function nowMs() { return Date.now() + clockOffsetMs; }
  function ageMinutes(v) { const d = parseTime(v); return d ? (nowMs() - d.getTime()) / 60000 : null; }
  function fmtAgo(v) {
    const m = ageMinutes(v);
    if (m === null) return "never";
    if (m < 0) return "just now";
    if (m < 1) return "just now";
    if (m < 60) return Math.round(m) + " min ago";
    const h = m / 60;
    if (h < 24) return (h < 10 ? h.toFixed(1).replace(/\.0$/, "") : Math.round(h)) + " h ago";
    const days = Math.round(h / 24);
    return days + (days === 1 ? " day ago" : " days ago");
  }
  function fmtDuration(ms) {
    if (!isNum(ms)) return DASH;
    const m = Math.max(0, Math.round(ms / 60000));
    if (m < 60) return m + " min";
    const h = Math.floor(m / 60);
    if (h < 48) return h + " h " + (m % 60) + " min";
    return Math.round(h / 24) + " days";
  }
  function fmtSecs(v) { const n = toNum(v); if (n === null) return DASH; return n < 60 ? n.toFixed(n < 10 ? 1 : 0) + " s" : Math.floor(n / 60) + " m " + Math.round(n % 60) + " s"; }
  /** Normalize any bar/equity timestamp to a "YYYY-MM-DD" session date (daily charts). */
  function toDay(t) {
    if (t === null || t === undefined) return null;
    if (isNum(t)) {
      const d = new Date(t > 1e12 ? t : t * 1000);
      const p = dtf({ year: "numeric", month: "2-digit", day: "2-digit" }, ET).formatToParts(d);
      const g = (type) => (p.find((x) => x.type === type) || {}).value;
      return g("year") + "-" + g("month") + "-" + g("day");
    }
    const s = String(t);
    return /^\d{4}-\d{2}-\d{2}/.test(s) ? s.slice(0, 10) : null;
  }
  function todayET() { return toDay(Date.now()); }

  // Theme -------------------------------------------------------------------------------------------
  function storageGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function storageSet(k, v) { try { if (v === null) window.localStorage.removeItem(k); else window.localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function effectiveTheme() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t === "light" || t === "dark") return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function applyTheme(choice) {
    if (choice === "light" || choice === "dark") document.documentElement.setAttribute("data-theme", choice);
    else document.documentElement.removeAttribute("data-theme");
    storageSet(THEME_KEY, choice === "light" || choice === "dark" ? choice : null);
    $$("#theme-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === (choice || "system"))));
    restyleCharts();
  }
  function initTheme() {
    const saved = storageGet(THEME_KEY);
    $$("#theme-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === (saved === "light" || saved === "dark" ? saved : "system"))));
    $("#theme-btn").addEventListener("click", () => applyTheme(effectiveTheme() === "dark" ? "light" : "dark"));
    $$("#theme-seg button").forEach((b) => b.addEventListener("click", () => applyTheme(b.dataset.themeChoice)));
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => { if (!document.documentElement.getAttribute("data-theme")) restyleCharts(); };
      if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
    }
  }

  // ------------------------------------------------------------------------------------------------
  // Charts (TradingView Lightweight Charts v4). All chart code is guarded: the library may fail to load.
  // ------------------------------------------------------------------------------------------------
  function lwcReady() { return !window.__lwcFailed && typeof window.LightweightCharts !== "undefined"; }
  function chartMessage(container, text) {
    if (!container) return;
    let msg = $(".chart-msg", container.parentNode);
    if (!text) { if (msg) msg.remove(); return; }
    if (!msg) { msg = el("div", { class: "chart-msg" }); container.parentNode.appendChild(msg); }
    msg.textContent = text;
  }
  function chartBaseOptions() {
    const LWC = window.LightweightCharts;
    return {
      autoSize: true,
      layout: {
        background: { type: "solid", color: cssVar("--surface") || "#fff" },
        textColor: cssVar("--muted") || "#666",
        fontFamily: cssVar("--font") || "system-ui",
        fontSize: 11,
      },
      grid: { vertLines: { color: cssVar("--c-grid") }, horzLines: { color: cssVar("--c-grid") } },
      rightPriceScale: { borderColor: cssVar("--border") },
      timeScale: { borderColor: cssVar("--border"), rightOffset: 3, fixLeftEdge: true },
      crosshair: { mode: LWC.CrosshairMode.Normal, vertLine: { color: cssVar("--border-strong"), labelBackgroundColor: cssVar("--text-2") }, horzLine: { color: cssVar("--border-strong"), labelBackgroundColor: cssVar("--text-2") } },
      localization: { locale: "en-US" },
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    };
  }
  /** Create (or reuse) a chart in container; returns null when the library is unavailable. */
  function getChart(name, container) {
    if (!lwcReady()) {
      chartMessage(container, "Chart unavailable: the chart library could not be loaded from unpkg.com.");
      return null;
    }
    const existing = state.charts[name];
    if (existing && existing.container === container) return existing;
    const chart = window.LightweightCharts.createChart(container, chartBaseOptions());
    const entry = { chart: chart, container: container, series: {}, priceLines: [], lastWidth: 0 };
    state.charts[name] = entry;
    // autoSize sizes the canvas asynchronously; re-fit whenever the container width changes (first layout,
    // a hidden tab becoming visible, window resize) so the series always spans the full width.
    if (typeof ResizeObserver !== "undefined") {
      entry.observer = new ResizeObserver(() => {
        const w = container.clientWidth;
        if (w > 0 && Math.abs(w - entry.lastWidth) > 1) { entry.lastWidth = w; fitSoon(entry); }
      });
      entry.observer.observe(container);
    }
    return entry;
  }
  function fitSoon(entry) {
    requestAnimationFrame(() => requestAnimationFrame(() => { try { entry.chart.timeScale().fitContent(); } catch (e) { /* ignore */ } }));
  }
  function resetSeries(entry) {
    for (const s of Object.values(entry.series)) { try { entry.chart.removeSeries(s); } catch (e) { /* ignore */ } }
    entry.series = {};
    entry.priceLines = [];
  }
  function restyleCharts() {
    if (!lwcReady()) return;
    // Wait a frame so the new CSS variables have applied.
    requestAnimationFrame(() => {
      for (const entry of Object.values(state.charts)) {
        try { entry.chart.applyOptions(chartBaseOptions()); } catch (e) { /* ignore */ }
        if (entry.restyle) { try { entry.restyle(); } catch (e) { /* ignore */ } }
      }
    });
  }
  /** Sort ascending and keep one point per day (last wins): the library rejects unsorted/duplicate times. */
  function dailySeries(rows, timeKey, valueFn) {
    const map = new Map();
    for (const r of rows || []) {
      if (!r) continue;
      const day = toDay(r[timeKey]);
      if (!day) continue;
      const v = valueFn(r);
      if (v === null || v === undefined) continue;
      map.set(day, v);
    }
    return Array.from(map.entries()).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([time, v]) => (typeof v === "object" ? Object.assign({ time: time }, v) : { time: time, value: v }));
  }
  function priceFmt() { return { type: "price", precision: 2, minMove: 0.01 }; }
  /** Crosshair times come back as "YYYY-MM-DD", a BusinessDay {year, month, day} or a UTC timestamp. */
  function lwcDay(t) {
    if (t === null || t === undefined) return null;
    if (typeof t === "string") return t.slice(0, 10);
    if (typeof t === "object" && "year" in t) return t.year + "-" + String(t.month).padStart(2, "0") + "-" + String(t.day).padStart(2, "0");
    if (isNum(t)) return new Date(t * 1000).toISOString().slice(0, 10);
    return null;
  }

  // ------------------------------------------------------------------------------------------------
  // Top bar: mode, account, clock, nightly, monitor, kill switch
  // ------------------------------------------------------------------------------------------------
  async function loadSummary() {
    const res = await api("/api/summary", { key: "summary" });
    if (res.aborted) return;
    const conn = $("#conn-banner");
    if (!res.ok) {
      if (res.network) {
        conn.hidden = false;
        conn.textContent = "Connection problem: " + res.unavailable + ". Showing the last data received; retrying every 30 s.";
        markStale(true);
      } else {
        conn.hidden = true;
        renderSummaryUnavailable(res.unavailable);
      }
      return;
    }
    conn.hidden = true;
    markStale(false);
    state.summary = res.data || {};
    const gen = parseTime(state.summary.generated_at);
    clockOffsetMs = String(state.summary.mode || "").toUpperCase() === "DEMO" && gen ? gen.getTime() - Date.now() : 0;
    renderSummary(state.summary);
  }
  function markStale(stale) {
    $$(".topbar__metrics, .topbar__status .status-item").forEach((n) => n.classList.toggle("is-stale", !!stale));
  }
  function renderSummaryUnavailable(reason) {
    setModeBadge(null);
    ["#m-equity", "#m-daypl", "#m-cash", "#m-bp"].forEach((id) => { const n = $(id); n.classList.remove("skel-text"); n.textContent = DASH; n.title = "Not available yet: " + reason; });
    const c = $("#clock"); c.classList.remove("skel-text"); c.textContent = DASH;
    const nt = $("#nightly-text"); nt.classList.remove("skel-text"); nt.textContent = "not available";
    const mt = $("#monitor-text"); mt.classList.remove("skel-text"); mt.textContent = "not available";
    const conn = $("#conn-banner");
    conn.hidden = false;
    conn.textContent = "Account summary not available yet: " + reason;
  }
  function setModeBadge(mode) {
    const b = $("#mode-badge");
    const m = String(mode || "").toUpperCase();
    b.className = "mode-badge";
    if (m === "PAPER") { b.classList.add("mode-badge--paper"); b.textContent = "PAPER"; b.title = "Paper trading account: simulated money"; }
    else if (m === "LIVE") { b.classList.add("mode-badge--live"); b.textContent = "LIVE"; b.title = "LIVE account: real money"; }
    else if (m === "DEMO") { b.classList.add("mode-badge--demo"); b.textContent = "DEMO"; b.title = "Demo data: not a real account"; }
    else { b.classList.add("mode-badge--unknown"); b.textContent = "MODE ?"; b.title = "Account mode unknown"; }
    document.body.classList.toggle("is-demo", m === "DEMO");
    $("#demo-banner").hidden = !(m === "DEMO" || (state.health && state.health.demo));
    document.body.classList.toggle("is-live", m === "LIVE");
  }
  function setMetric(id, text, cls, title) {
    const n = $(id);
    n.classList.remove("skel-text", "pos", "neg", "flat");
    if (cls) n.classList.add(cls);
    if (typeof text === "string") n.textContent = text; else replace(n, text);
    n.title = title || "";
  }
  function renderSummary(s) {
    setModeBadge(s.mode);
    const a = s.account || null;
    if (a && a.unavailable && toNum(a.equity) === null) {
      ["#m-equity", "#m-daypl", "#m-cash", "#m-bp"].forEach((id) => setMetric(id, DASH, null, "Account not available: " + a.unavailable));
    } else if (a) {
      const fb = fallbackSource(a.source);
      setMetric("#m-equity", fb ? [fmtMoney(a.equity), el("small", { class: "muted", text: a.as_of ? "as of " + fmtShortDay(a.as_of) : "snapshot" })] : fmtMoney(a.equity),
        null, fb ? "From " + fb : "");
      const pl = toNum(a.day_pl);
      let pct = toNum(a.day_pl_pct);
      if (pct === null && pl !== null && toNum(a.last_equity)) pct = (pl / toNum(a.last_equity)) * 100;
      const cls = signClass(pl !== null ? pl : pct);
      setMetric("#m-daypl", pl === null && pct === null ? DASH : [arrow(pl !== null ? pl : pct) + fmtSignedMoney(pl), el("small", { text: fmtPct(pct, 2, true) })], cls,
        toNum(a.last_equity) ? "Change since the previous close (last equity " + fmtMoney(a.last_equity) + ")" : "No previous close yet (new account)");
      setMetric("#m-cash", fmtMoney(a.cash));
      setMetric("#m-bp", fmtMoney(a.buying_power));
    } else {
      ["#m-equity", "#m-daypl", "#m-cash", "#m-bp"].forEach((id) => setMetric(id, DASH, null, "Account not available"));
    }
    renderKillSwitch(s.kill_switch);
    renderClock(s.clock);
    renderNightly(s.nightly);
    renderMonitor(s.monitor, s.clock);
    const n24 = s.monitor && toNum(s.monitor.alerts_24h);
    const cnt = $("#alerts-count");
    if (n24 !== null && n24 > 0) { cnt.hidden = false; cnt.textContent = fmtInt(n24); cnt.title = n24 + " alerts in the last 24 hours"; }
    else cnt.hidden = true;
    const upd = $("#updated");
    upd.textContent = "Updated " + dtf({ hour: "numeric", minute: "2-digit", second: "2-digit" }).format(new Date());
    upd.title = s.generated_at ? "Server time " + fmtDateTime(s.generated_at) : "";
  }

  function renderKillSwitch(ks) {
    const tripped = !!(ks && ks.tripped);
    const path = (ks && ks.path) || "state/KILL";
    $("#kill-banner").hidden = !tripped;
    $("#kill-chip").hidden = !tripped;
    const isFile = !/\s|:\/\//.test(path);
    $("#kill-banner-path").textContent = isFile ? "rm " + path : path;
    const why = ks && ks.reason ? String(ks.reason) : "";
    $("#kill-banner-reason").hidden = !why;
    $("#kill-banner-reason").textContent = why ? "Reason: " + why : "";
    document.body.classList.toggle("kill-on", tripped);
    $("#ks-path").textContent = path;
    const chip = $("#ks-state");
    chip.className = "chip " + (tripped ? "chip--solid-bad" : "chip--ok");
    chip.textContent = tripped ? "TRIPPED" : "Not tripped";
    const btn = $("#ks-trip");
    btn.disabled = tripped;
    btn.textContent = tripped ? "Kill switch is tripped" : "Trip kill switch\u2026";
  }

  function renderClock(c) {
    const node = $("#clock");
    node.classList.remove("skel-text");
    if (!c || c.is_open === null || c.is_open === undefined) { node.textContent = DASH; node.title = (c && c.unavailable) || "Market clock not available"; return; }
    const open = !!c.is_open;
    const target = open ? c.next_close : c.next_open;
    const d = parseTime(target);
    const until = d ? fmtDuration(d.getTime() - nowMs()) : null;
    replace(node, [
      el("span", { class: "dot " + (open ? "dot--ok" : "dot--off"), "aria-hidden": "true" }),
      " ",
      el("strong", { text: open ? "Open" : "Closed" }),
      d ? " \u00b7 " + (open ? "closes " : "opens ") + fmtEtLocal(target, !open) : "",
      until ? el("span", { class: "muted", text: " \u00b7 in " + until }) : "",
    ]);
    node.title = (open ? "Next close: " : "Next open: ") + (d ? d.toString() : "unknown");
  }

  function stepTone(status) {
    const s = String(status || "").toLowerCase();
    if (["ok", "success", "succeeded", "done", "passed", "pass"].includes(s)) return "ok";
    if (["fail", "failed", "error", "crashed"].includes(s)) return "bad";
    if (["warn", "warning", "degraded", "partial", "held"].includes(s)) return "warn";
    if (["running", "started", "in_progress"].includes(s)) return "info";
    return "";
  }
  function statusChip(status, label) {
    const tone = stepTone(status);
    const text = label || (String(status || "").toLowerCase() === "ok" ? "OK" : humanize(status || "unknown"));
    return el("span", { class: "chip" + (tone ? " chip--" + tone : ""), text: text });
  }
  function renderNightly(n) {
    const text = $("#nightly-text");
    text.classList.remove("skel-text");
    const pop = $("#nightly-pop");
    if (!n || (n.unavailable && !n.as_of)) {
      replace(text, [el("span", { class: "dot dot--off", "aria-hidden": "true" }), " no run recorded"]);
      replace(pop, emptyBox(n && n.unavailable ? "No nightly report: " + n.unavailable : "No nightly run report found yet."));
      $("#nightly-btn").title = "";
      return;
    }
    const steps = Array.isArray(n.steps) ? n.steps : [];
    const failed = steps.filter((s) => stepTone(s.status) === "bad");
    const ok = n.ok === true && failed.length === 0;
    const running = n.ok === null || n.ok === undefined ? !n.finished_at : false;
    const tone = running ? "info" : ok ? "ok" : "bad";
    const label = running ? "running" : ok ? "OK" : failed.length ? failed.length + " step" + (failed.length > 1 ? "s" : "") + " failed" : "failed";
    replace(text, [
      el("span", { class: "dot dot--" + (tone === "ok" ? "ok" : tone === "bad" ? "bad" : "warn"), "aria-hidden": "true" }),
      " " + (n.as_of ? fmtShortDay(n.as_of) : "") + (n.finished_at ? " \u00b7 " + fmtTime(n.finished_at) : ""),
      " ",
      el("span", { class: "chip chip--" + tone, text: label }),
    ]);
    $("#nightly-btn").title = "Nightly for " + (n.as_of || "?") + ", finished " + (n.finished_at ? fmtDateTime(n.finished_at) + " (" + fmtAgo(n.finished_at) + ")" : "not yet");
    const rows = steps.map((s) => el("tr", null, [
      el("td", { class: "nowrap", text: humanize(s.name) }),
      el("td", null, statusChip(s.status)),
      el("td", { class: "r", text: fmtSecs(s.elapsed_s) }),
      el("td", { class: "muted detail", text: s.detail === null || s.detail === undefined ? "" : typeof s.detail === "string" ? s.detail : JSON.stringify(s.detail) }),
    ]));
    replace(pop, [
      el("h3", { text: "Nightly run " + (n.as_of || "") }),
      el("p", { class: "muted", text: "Finished " + (n.finished_at ? fmtDateTime(n.finished_at) + " (" + fmtAgo(n.finished_at) + ")" : "not yet") }),
      steps.length
        ? el("table", { class: "data compact" }, [
          el("thead", null, el("tr", null, [el("th", { text: "Step" }), el("th", { text: "Status" }), el("th", { class: "r", text: "Time" }), el("th", { text: "Detail" })])),
          el("tbody", null, rows),
        ])
        : emptyBox("No steps recorded."),
    ]);
  }

  function feedStaleMinutes(clock) { return clock && clock.is_open ? FEED_STALE_OPEN_MIN : FEED_STALE_CLOSED_MIN; }
  function renderMonitor(m, clock) {
    const text = $("#monitor-text");
    text.classList.remove("skel-text");
    const pop = $("#monitor-pop");
    if (!m || m.unavailable) {
      replace(text, [el("span", { class: "dot dot--off", "aria-hidden": "true" }), " not running"]);
      replace(pop, emptyBox(m && m.unavailable ? "No monitor data: " + m.unavailable : "No monitor heartbeat found."));
      $("#monitor-btn").title = "";
      return;
    }
    const limit = feedStaleMinutes(clock);
    const feeds = Object.entries(m.feeds || {}).map(([name, seen]) => ({ name: name, seen: seen, age: ageMinutes(seen) }));
    feeds.sort((a, b) => a.name.localeCompare(b.name));
    const isStale = (f) => !EVENT_DRIVEN_FEED.test(f.name) && (f.age === null || f.age > limit);
    const stale = feeds.filter(isStale);
    const lastAge = ageMinutes(m.last_event_at);
    const dead = lastAge === null || lastAge > limit;
    const tone = dead ? "bad" : stale.length ? "warn" : "ok";
    replace(text, [
      el("span", { class: "dot dot--" + tone, "aria-hidden": "true" }),
      " " + (m.last_event_at ? fmtAgo(m.last_event_at) : "no events"),
      stale.length ? el("span", { class: "chip chip--warn", text: stale.length + " stale" }) : "",
    ]);
    $("#monitor-btn").title = "Last event " + (m.last_event_at ? fmtDateTime(m.last_event_at) : "never") + "; " + fmtInt(m.alerts_24h) + " alerts in 24 h";
    const rows = feeds.map((f) => {
      const quiet = EVENT_DRIVEN_FEED.test(f.name);
      return el("tr", null, [
        el("td", { class: "mono", text: f.name }),
        el("td", { class: "r", text: f.seen ? fmtDateTime(f.seen) : DASH }),
        el("td", { class: "r", text: fmtAgo(f.seen) }),
        el("td", null, isStale(f) ? el("span", { class: "chip chip--warn", text: "stale" })
          : quiet ? el("span", { class: "chip", title: "Event-driven: only speaks when an order fills", text: "event-driven" })
            : el("span", { class: "chip chip--ok", text: "live" })),
      ]);
    });
    replace(pop, [
      el("h3", { text: "Monitor feeds" }),
      el("p", { class: "muted", text: "Last event " + fmtAgo(m.last_event_at) + " \u00b7 " + fmtInt(m.alerts_24h) + " alerts in 24 h \u00b7 a feed is stale after " + (limit >= 60 ? limit / 60 + " h" : limit + " min") + " of silence while the market is " + (clock && clock.is_open ? "open" : "closed") + "." }),
      feeds.length
        ? el("table", { class: "data compact" }, [
          el("thead", null, el("tr", null, [el("th", { text: "Feed" }), el("th", { class: "r", text: "Last seen" }), el("th", { class: "r", text: "Age" }), el("th", { text: "State" })])),
          el("tbody", null, rows),
        ])
        : emptyBox("No feeds have reported yet."),
    ]);
  }

  function initPopovers() {
    const pairs = [["#nightly-btn", "#nightly-pop"], ["#monitor-btn", "#monitor-pop"]];
    const closeAll = (except) => pairs.forEach(([b, p]) => { if (b !== except) { $(p).hidden = true; $(b).setAttribute("aria-expanded", "false"); } });
    pairs.forEach(([b, p]) => {
      $(b).addEventListener("click", (ev) => {
        ev.stopPropagation();
        const open = $(p).hidden;
        closeAll(b);
        $(p).hidden = !open;
        $(b).setAttribute("aria-expanded", String(open));
      });
      $(p).addEventListener("click", (ev) => ev.stopPropagation());
    });
    document.addEventListener("click", () => closeAll(null));
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        const openBtn = pairs.find(([, p]) => !$(p).hidden);
        closeAll(null);
        if (openBtn) $(openBtn[0]).focus();
      }
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Overview: equity vs SPY
  // ------------------------------------------------------------------------------------------------
  async function loadEquity(opts) {
    const quiet = opts && opts.quiet;
    const box = $("#eq-chart");
    if (!quiet) { replace($("#eq-stats"), skeletonLines(1)); chartMessage(box, "Loading equity\u2026"); }
    const res = await api("/api/equity?period=" + encodeURIComponent(state.equityPeriod), { key: "equity", timeout: SLOW_FETCH_TIMEOUT_MS });
    if (res.aborted) return;
    if (!res.ok) {
      if (quiet && state.equityData) return; // keep the last good chart on a failed background refresh
      state.equityData = null;
      setNote("eq-note", null);
      replace($("#eq-stats"), unavailableBox(res.unavailable, { error: res.network }));
      clear($("#eq-legend"));
      const entry = state.charts.equity;
      if (entry) resetSeries(entry);
      chartMessage(box, "No equity curve to show.");
      return;
    }
    state.equityData = res.data || {};
    const d = state.equityData;
    const acctPts = Array.isArray(d.account) ? d.account.length : 0;
    const fb = fallbackSource(d.account_source);
    setNote("eq-note", res, [
      fb ? "Account from " + fb : null,
      acctPts === 1 ? "Only one account data point so far: the curve fills in as trading days pass." : null,
    ]);
    renderEquity();
  }
  function renderEquity() {
    const d = state.equityData || {};
    renderEquityStats(d);
    const box = $("#eq-chart");
    const norm = Array.isArray(d.normalized) ? d.normalized : [];
    const acct = Array.isArray(d.account) ? d.account : [];
    if (!norm.length && !acct.length) { chartMessage(box, "No equity history for this period yet. It fills in after the first nightly runs."); clear($("#eq-legend")); return; }
    const entry = getChart("equity", box);
    if (!entry) return;
    chartMessage(box, null);
    resetSeries(entry);
    const chart = entry.chart;
    let accountData;
    let spyData = [];
    const rebased = state.equityMode === "rebased" && norm.length;
    if (rebased) {
      accountData = dailySeries(norm, "t", (r) => toNum(r.account));
      spyData = dailySeries(norm, "t", (r) => toNum(r.spy));
    } else {
      accountData = dailySeries(acct, "t", (r) => toNum(r.equity));
      // SPY in dollars: "what the same starting equity would be worth in SPY".
      if (norm.length && accountData.length) {
        const eqByDay = new Map(accountData.map((p) => [p.time, p.value]));
        const first = norm.map((r) => ({ day: toDay(r.t), r: r })).find((x) => eqByDay.has(x.day) && toNum(x.r.account));
        if (first) {
          const base = eqByDay.get(first.day) / (toNum(first.r.account) / 100);
          spyData = dailySeries(norm, "t", (r) => (toNum(r.spy) === null ? null : (toNum(r.spy) / 100) * base));
        }
      }
    }
    const fmt = rebased ? { type: "price", precision: 1, minMove: 0.1 } : { type: "price", precision: 0, minMove: 1 };
    const spy = chart.addLineSeries({ color: cssVar("--c-spy"), lineWidth: 2, lineStyle: 0, priceLineVisible: false, lastValueVisible: true, priceFormat: fmt, title: "SPY", crosshairMarkerRadius: 3 });
    const account = chart.addLineSeries({ color: cssVar("--c-account"), lineWidth: 2, priceLineVisible: false, lastValueVisible: true, priceFormat: fmt, title: "Account", crosshairMarkerRadius: 3 });
    spy.setData(spyData);
    account.setData(accountData);
    entry.series = { spy: spy, account: account };
    if (rebased) {
      entry.priceLines.push(account.createPriceLine({ price: 100, color: cssVar("--border-strong"), lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "" }));
    }
    entry.restyle = () => {
      account.applyOptions({ color: cssVar("--c-account") });
      spy.applyOptions({ color: cssVar("--c-spy") });
      updateEquityLegend(null);
    };
    fitSoon(entry);
    const lastOf = (arr) => (arr.length ? arr[arr.length - 1].value : null);
    const updateEquityLegend = (param) => {
      let a = lastOf(accountData);
      let s = lastOf(spyData);
      let when = accountData.length ? accountData[accountData.length - 1].time : null;
      if (param && param.time && param.seriesData) {
        const av = param.seriesData.get(account);
        const sv = param.seriesData.get(spy);
        a = av ? av.value : null;
        s = sv ? sv.value : null;
        when = param.time;
      }
      const f = (v) => (v === null || v === undefined ? DASH : rebased ? fmtNum(v, 1) : fmtMoney(v, 0));
      replace($("#eq-legend"), [
        el("span", { text: when ? fmtDay(lwcDay(when)) : "" }),
        el("span", null, [el("i", { class: "sw", style: "background:var(--c-account)" }), "Account ", el("b", { text: f(a) })]),
        el("span", null, [el("i", { class: "sw", style: "background:var(--c-spy)" }), rebased ? "SPY " : "Same $ in SPY ", el("b", { text: f(s) })]),
      ]);
    };
    if (entry.legendHandler) chart.unsubscribeCrosshairMove(entry.legendHandler);
    entry.legendHandler = updateEquityLegend;
    chart.subscribeCrosshairMove(updateEquityLegend);
    updateEquityLegend(null);
  }
  function renderEquityStats(d) {
    const st = d.stats || {};
    const ret = toNum(st.return_pct);
    const spy = toNum(st.spy_return_pct);
    const diff = ret !== null && spy !== null ? ret - spy : null;
    const dd = toNum(st.max_drawdown_pct);
    const stat = (label, value, cls, title) => el("div", { class: "stat", title: title || "" }, [
      el("span", { class: "stat__label", text: label }),
      el("span", { class: "stat__value " + (cls || ""), text: value }),
    ]);
    replace($("#eq-stats"), [
      stat("Account", arrow(ret) + fmtPct(ret, 2, true), signClass(ret), "Account return over the period"),
      stat("SPY", arrow(spy) + fmtPct(spy, 2, true), signClass(spy), "SPY return over the same dates"),
      stat("vs SPY", diff === null ? DASH : fmtSigned(diff, 2, " pts"), signClass(diff), "Account return minus SPY return, in percentage points"),
      stat("Max drawdown", dd === null ? DASH : fmtPct(-Math.abs(dd), 2), dd ? "neg" : "flat", "Largest peak-to-trough fall of the account in the period"),
    ]);
  }
  function initEquityControls() {
    $$("#eq-period button").forEach((b) => b.addEventListener("click", () => {
      state.equityPeriod = b.dataset.period;
      $$("#eq-period button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      loadEquity();
    }));
    $$("#eq-mode button").forEach((b) => b.addEventListener("click", () => {
      state.equityMode = b.dataset.mode;
      $$("#eq-mode button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      if (state.equityData) renderEquity();
    }));
  }

  // ------------------------------------------------------------------------------------------------
  // Overview: regime
  // ------------------------------------------------------------------------------------------------
  async function loadRegime(opts) {
    const body = $("#regime-body");
    if (!(opts && opts.quiet)) showSkeleton(body, 6);
    const res = await api("/api/regime", { key: "regime" });
    if (res.aborted) return;
    if (!res.ok) { if (!(opts && opts.quiet)) { showUnavailable(body, res); setNote("rg-note", null); $("#rg-asof").textContent = ""; } return; }
    setNote("rg-note", res, null, ["allowed"]);
    renderRegime(res.data || {});
  }
  function volLabel(v) {
    const n = toNum(v);
    if (n !== null) return ["Low", "Normal", "High"][Math.max(0, Math.min(2, Math.round(n)))] || String(v);
    return humanize(v);
  }
  function trendLabel(v) {
    const n = toNum(v);
    if (n !== null) return n > 0 ? "Uptrend" : n < 0 ? "Downtrend" : "Flat";
    const w = String(v || "").toLowerCase();
    if (w === "up" || w === "uptrend") return "Uptrend";
    if (w === "down" || w === "downtrend") return "Downtrend";
    if (w === "flat" || w === "sideways" || w === "neutral") return "Sideways";
    return humanize(v);
  }
  function renderRegime(d) {
    const body = $("#regime-body");
    const st = d.state || {};
    const info = REGIMES[st.regime] || { name: humanize(st.regime || "unknown"), tone: "", desc: "" };
    $("#rg-asof").textContent = st.as_of ? "as of " + fmtDay(st.as_of) : "";
    const hist = Array.isArray(d.breadth_history) ? d.breadth_history.slice() : [];
    hist.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const latest = hist.length ? hist[hist.length - 1] : {};
    const br = st.breadth && typeof st.breadth === "object" ? st.breadth : st.breadth_values && typeof st.breadth_values === "object" ? st.breadth_values : {};
    const p50 = toNum(br.pct_above_50) !== null ? toNum(br.pct_above_50) : toNum(latest.pct_above_50);
    const p200 = toNum(br.pct_above_200) !== null ? toNum(br.pct_above_200) : toNum(latest.pct_above_200);
    const ratio = toNum(br.ratio_10d) !== null ? toNum(br.ratio_10d) : toNum(latest.ratio_10d);
    const breadthWord = typeof st.breadth === "string" ? humanize(st.breadth) : br.state || br.label ? humanize(br.state || br.label) : null;

    const facts = el("dl", { class: "regime-facts" }, [
      el("dt", { text: "SPY trend" }), el("dd", { text: trendLabel(st.spy_trend) }),
      el("dt", { text: "Volatility" }), el("dd", { text: volLabel(st.vol_regime) }),
      el("dt", { text: "Breadth" }), el("dd", null, [
        breadthWord ? breadthWord + " \u00b7 " : "",
        el("span", { title: "Share of stocks above their 50-day average", text: fmtPct(p50, 0) + " > 50d" }),
        " \u00b7 ",
        el("span", { title: "Share of stocks above their 200-day average", text: fmtPct(p200, 0) + " > 200d" }),
      ]),
      el("dt", { text: "10-day 4% ratio" }), el("dd", { title: "Stockbee: 10-day count of 4% up days / 4% down days. >= 2 favours longs, <= 0.5 bearish", text: ratio === null ? DASH : fmtNum(ratio, 2) }),
    ]);

    const children = [
      el("div", { class: "regime-name" }, [el("span", { class: "dot dot--" + (info.tone === "ok" ? "ok" : info.tone === "bad" ? "bad" : "warn"), "aria-hidden": "true" }), info.name]),
      info.desc ? el("p", { class: "regime-desc", text: info.desc }) : null,
      facts,
    ];
    if (hist.length > 1) {
      children.push(breadthSpark(hist));
      children.push(el("div", { class: "spark-legend" }, [
        el("span", null, [el("i", { style: "background:var(--c-account)" }), "> 50-day"]),
        el("span", null, [el("i", { style: "background:var(--c-sma50)" }), "> 200-day"]),
        el("span", { title: "60/40 hysteresis band: above 60% is strong breadth, below 40% weak", text: "40\u201360% band" }),
        el("span", { text: fmtShortDay(hist[0].date) + " \u2013 " + fmtShortDay(hist[hist.length - 1].date) }),
      ]));
    }
    const notes = Array.isArray(st.notes) ? st.notes.filter(Boolean) : st.notes ? [st.notes] : [];
    if (notes.length) {
      children.push(el("div", { class: "notes" }, notes.length === 1 ? el("span", { text: String(notes[0]) }) : el("ul", null, notes.map((n) => el("li", { text: String(n) })))));
    }
    children.push(el("h3", { class: "subhead", text: "Allowed strategies & risk multiplier" }));
    const allowed = Object.entries(d.allowed || {}).map(([k, v]) => [k, toNum(v)]).filter(([, v]) => v !== null && v > 0);
    allowed.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    if (d.allowed === null || d.allowed === undefined) {
      const why = d.partial && d.partial.allowed ? String(d.partial.allowed) : "no allowed-strategy table was saved for this date";
      children.push(el("div", { class: "allowed__none", text: "Router not applied: " + why + "." }));
    } else if (!allowed.length) {
      children.push(el("div", { class: "allowed__none", text: "No new entries allowed in this regime." }));
    } else {
      children.push(el("div", { class: "allowed" }, allowed.map(([k, v]) => el("div", { class: "allowed__row" }, [
        el("span", { class: "allowed__name", title: k, text: strategyName(k) }),
        el("div", { class: "mbar", role: "img", "aria-label": strategyName(k) + ": " + Math.round(v * 100) + "% of normal risk" }, [
          el("div", { class: "mbar__track" }, el("div", { class: "mbar__fill", style: "width:" + Math.max(2, Math.min(100, v * 100)) + "%" })),
          el("span", { class: "mbar__val", text: "\u00d7" + fmtNum(v, 2) }),
        ]),
      ]))));
    }
    const blocked = d.blocked && typeof d.blocked === "object" ? Object.entries(d.blocked) : [];
    if (blocked.length) {
      children.push(el("p", { class: "blocked" }, [
        el("span", { class: "muted", text: "Not allowed now: " }),
        ...blocked.map(([k, why], i) => el("span", { title: why ? String(why) : "", text: strategyName(k) + (i < blocked.length - 1 ? ", " : "") })),
      ]));
    }
    replace(body, children);
  }
  /** Tiny inline SVG sparkline of % above 50/200-day, with the 40-60 hysteresis band. */
  function breadthSpark(hist) {
    const W = 320, H = 54, P = 3;
    const s = svg("svg", { class: "spark", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none", role: "img", "aria-label": "Breadth history: percent of stocks above their 50 and 200 day averages" });
    const y = (v) => P + (1 - v / 100) * (H - 2 * P);
    const x = (i) => P + (i / Math.max(1, hist.length - 1)) * (W - 2 * P);
    s.appendChild(svg("rect", { x: 0, y: y(60), width: W, height: y(40) - y(60), style: "fill:var(--surface-3)" }));
    s.appendChild(svg("line", { x1: 0, x2: W, y1: y(50), y2: y(50), style: "stroke:var(--border-strong)", "stroke-width": 1, "stroke-dasharray": "3 3", "vector-effect": "non-scaling-stroke" }));
    const line = (key, color) => {
      let dstr = "";
      let pen = false;
      hist.forEach((r, i) => {
        const v = toNum(r[key]);
        if (v === null) { pen = false; return; }
        dstr += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(Math.max(0, Math.min(100, v))).toFixed(1) + " ";
        pen = true;
      });
      if (dstr) s.appendChild(svg("path", { d: dstr, fill: "none", style: "stroke:var(" + color + ")", "stroke-width": 1.6, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" }));
    };
    line("pct_above_200", "--c-sma50");
    line("pct_above_50", "--c-account");
    return s;
  }

  // ------------------------------------------------------------------------------------------------
  // Overview: positions
  // ------------------------------------------------------------------------------------------------
  async function loadPositions(opts) {
    const body = $("#positions-body");
    if (!(opts && opts.quiet) && !state.positions) showSkeleton(body, 4);
    const res = await api("/api/positions", { key: "positions" });
    if (res.aborted) return;
    if (!res.ok) {
      if (opts && opts.quiet && state.positions) return;
      state.positions = null;
      showUnavailable(body, res);
      setNote("pos-note", null);
      clear($("#pos-summary"));
      $("#pos-meta").textContent = "";
      renderSymbolChips();
      return;
    }
    state.positions = Array.isArray(res.data) ? res.data : [];
    const pfb = fallbackSource(res.source);
    setNote("pos-note", res, [pfb ? "From " + pfb : null]);
    if (unchanged("positions", state.positions) && $("#positions-body table, #positions-body .empty")) return;
    preservingFocus($("#positions-body"), renderPositions);
    renderSymbolChips();
    if (state.loaded.charts && !state.chartSymbol && state.positions.length) loadChart(); // deep link arrived first
    else if (state.tab === "charts") renderChartSide();
  }
  function positionPct(p) {
    const pl = toNum(p.unrealized_pl), entry = toNum(p.avg_entry), qty = toNum(p.qty);
    if (pl !== null && entry && qty) return (pl / (Math.abs(entry * qty))) * 100;
    const pc = toNum(p.unrealized_plpc);
    return pc === null ? null : pc * 100;
  }
  function isShort(p) { return String(p.side || "").toLowerCase() === "short" || toNum(p.qty) < 0; }
  function liveStop(p) { const c = toNum(p.current_stop); return c !== null ? c : toNum(p.stop); }
  function riskToStop(p) {
    const cur = toNum(p.current), stop = liveStop(p), qty = Math.abs(toNum(p.qty) || 0);
    if (cur === null || stop === null || !qty) return null;
    return (isShort(p) ? stop - cur : cur - stop) * qty; // positive = money at risk if stopped from here
  }
  function stopCell(p) {
    const live = liveStop(p), init = toNum(p.stop);
    if (live === null) return el("td", { class: "r neg", text: "none" });
    const trailed = init !== null && Math.abs(live - init) > 0.004;
    return el("td", { class: "r", title: trailed ? "Trailed from the initial stop " + fmtMoney(init) : "" }, [
      fmtMoney(live), trailed ? el("span", { class: "muted", text: " trail" }) : null,
    ]);
  }
  function renderPositions() {
    const list = (state.positions || []).slice().sort((a, b) => String(a.symbol).localeCompare(String(b.symbol)));
    const body = $("#positions-body");
    $("#pos-meta").textContent = list.length ? list.length + " open" : "";
    if (!list.length) {
      clear($("#pos-summary"));
      replace(body, emptyBox("No open positions."));
      return;
    }
    let mv = 0, upl = 0, risk = 0, noStop = 0;
    list.forEach((p) => {
      mv += toNum(p.market_value) || 0;
      upl += toNum(p.unrealized_pl) || 0;
      const r = riskToStop(p);
      if (r === null) noStop += 1; else risk += Math.max(0, r);
    });
    replace($("#pos-summary"), [
      el("span", { class: "stat-inline" }, ["Market value ", el("b", { text: fmtMoney(mv, 0) })]),
      el("span", { class: "stat-inline" }, ["Unrealized ", el("b", { class: signClass(upl), text: arrow(upl) + fmtSignedMoney(upl, 0) })]),
      el("span", { class: "stat-inline", title: "What the open positions would give back from here if every stop were hit" }, ["At risk to stops ", el("b", { text: fmtMoney(risk, 0) })]),
      noStop ? el("span", { class: "chip chip--bad", text: noStop + " without a stop" }) : null,
    ]);
    const head = el("thead", null, el("tr", null, [
      el("th", { text: "Symbol" }), el("th", { text: "Strategy" }), el("th", { class: "r", text: "Qty" }),
      el("th", { class: "r", text: "Entry" }), el("th", { class: "r", text: "Current" }),
      el("th", { class: "r", text: "P&L $" }), el("th", { class: "r", text: "P&L %" }), el("th", { class: "r", text: "R" }),
      el("th", { class: "r", text: "Stop" }), el("th", { class: "r", text: "Target" }), el("th", { class: "r", text: "Days held" }),
    ]));
    const rows = list.map((p) => {
      const pct = positionPct(p);
      const pl = toNum(p.unrealized_pl);
      const r = toNum(p.r_multiple);
      const held = toNum(p.days_held), maxH = toNum(p.max_hold_days);
      const frac = held !== null && maxH ? Math.min(1, held / maxH) : null;
      const tr = el("tr", { class: "is-click", tabindex: "0", "data-key": String(p.symbol || ""), title: "Open the " + p.symbol + " chart", "aria-label": p.symbol + ": open chart" }, [
        el("td", null, [el("span", { class: "sym", text: p.symbol || DASH }), isShort(p) ? el("span", { class: "chip chip--warn", style: "margin-left:6px", text: "SHORT" }) : null]),
        el("td", { class: "strat", title: p.strategy || "", text: strategyName(p.strategy) }),
        el("td", { class: "r", text: fmtQty(p.qty) }),
        el("td", { class: "r", text: fmtMoney(p.avg_entry) }),
        el("td", { class: "r", text: fmtMoney(p.current) }),
        el("td", { class: "r " + signClass(pl), text: arrow(pl) + fmtSignedMoney(pl) }),
        el("td", { class: "r " + signClass(pct), text: fmtPct(pct, 2, true) }),
        el("td", { class: "r " + signClass(r), text: r === null ? DASH : fmtSigned(r, 2, "R") }),
        stopCell(p),
        el("td", { class: "r", text: fmtMoney(p.target) }),
        el("td", { class: "r" }, el("span", { class: "hold", title: frac !== null ? Math.round(frac * 100) + "% of the max hold" : "" }, [
          (held === null ? DASH : fmtInt(held)) + (maxH ? " / " + fmtInt(maxH) : ""),
          frac !== null ? el("span", { class: "hold__track", "aria-hidden": "true" }, el("span", { class: "hold__fill" + (frac >= 0.8 ? " is-late" : ""), style: "display:block;width:" + Math.round(frac * 100) + "%" })) : null,
        ])),
      ]);
      const open = () => openChart(p.symbol);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } });
      return tr;
    });
    replace(body, el("table", { class: "data" }, [head, el("tbody", null, rows)]));
  }

  // ------------------------------------------------------------------------------------------------
  // Positions & charts: candlesticks + volume + SMAs + levels + markers
  // ------------------------------------------------------------------------------------------------
  const SYMBOL_RE = /^[A-Z][A-Z.\-]{0,9}$/; // the server accepts ^[A-Z.-]{1,10}$
  function cleanSymbol(s) { const t = String(s || "").trim().toUpperCase(); return SYMBOL_RE.test(t) ? t : null; }
  function openChart(symbol) {
    const sym = cleanSymbol(symbol);
    if (!sym) return;
    const target = "#charts/" + sym;
    if (location.hash === target) { selectTab("charts", { focus: false }); loadChart(); }
    else location.hash = target;
  }
  function positionFor(sym) { return (state.positions || []).find((p) => String(p.symbol).toUpperCase() === sym) || null; }
  function renderSymbolChips() {
    const box = $("#ch-symbols");
    const syms = (state.positions || []).map((p) => String(p.symbol || "").toUpperCase()).filter(Boolean).sort();
    replace(box, syms.map((s) => el("button", { type: "button", "aria-pressed": String(s === state.chartSymbol), onclick: () => openChart(s), text: s })));
    const dl = $("#ch-datalist");
    const extra = new Set(syms);
    ((state.signals && state.signals.signals) || []).forEach((g) => g && g.symbol && extra.add(String(g.symbol).toUpperCase()));
    replace(dl, Array.from(extra).sort().map((s) => el("option", { value: s })));
  }
  function initChartControls() {
    $("#ch-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const input = $("#ch-input");
      const sym = cleanSymbol(input.value);
      if (!sym) { input.setCustomValidity("Enter a ticker like AAPL"); input.reportValidity(); return; }
      input.setCustomValidity("");
      input.value = "";
      openChart(sym);
    });
    $("#ch-input").addEventListener("input", (ev) => ev.target.setCustomValidity(""));
    $$("#ch-days button").forEach((b) => b.addEventListener("click", () => {
      state.chartDays = Number(b.dataset.days) || 180;
      $$("#ch-days button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      loadChart();
    }));
    $$("#ord-status button").forEach((b) => b.addEventListener("click", () => {
      state.orderStatus = b.dataset.status;
      $$("#ord-status button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      loadOrders();
    }));
  }
  async function loadChart(opts) {
    const quiet = opts && opts.quiet;
    const box = $("#ch-chart");
    if (!state.chartSymbol) {
      const first = (state.positions || []).map((p) => String(p.symbol || "").toUpperCase()).filter(Boolean).sort()[0];
      if (first) state.chartSymbol = first;
    }
    renderSymbolChips();
    const sym = state.chartSymbol;
    $("#ch-symbol").textContent = sym || "Chart";
    if (!sym) {
      $("#ch-sub").textContent = "";
      setNote("ch-note", null);
      chartMessage(box, state.positions === null ? "Positions are not available yet. Type a symbol above to chart it." : "No open positions. Type a symbol above to chart it.");
      clear($("#ch-legend"));
      renderChartSide(null);
      return;
    }
    if (!quiet) { chartMessage(box, "Loading " + sym + "\u2026"); $("#ch-sub").textContent = ""; }
    const res = await api("/api/chart/" + encodeURIComponent(sym) + "?days=" + state.chartDays, { key: "chart", timeout: SLOW_FETCH_TIMEOUT_MS });
    if (res.aborted) return;
    if (sym !== state.chartSymbol) return;
    if (!res.ok) {
      if (quiet && state.chartData && state.chartData.symbol === sym) return;
      state.chartData = null;
      const entry = state.charts.price;
      if (entry) resetSeries(entry);
      clear($("#ch-legend"));
      chartMessage(box, "Chart for " + sym + " not available yet: " + res.unavailable);
      setNote("ch-note", null);
      renderChartSide(null);
      return;
    }
    setNote("ch-note", res);
    state.chartData = Object.assign({ symbol: sym }, res.data || {});
    renderPriceChart(state.chartData);
    renderChartSide(state.chartData);
  }
  function markerStyle(kind) {
    const k = String(kind || "").toLowerCase();
    if (k === "entry") return { position: "belowBar", shape: "arrowUp", color: cssVar("--c-account") };
    if (k === "exit") return { position: "aboveBar", shape: "arrowDown", color: cssVar("--orange") };
    return { position: "belowBar", shape: "circle", color: cssVar("--c-sma50") };
  }
  function renderPriceChart(d) {
    const box = $("#ch-chart");
    const bars = dailySeries(d.bars, "t", (b) => {
      const o = toNum(b.o), h = toNum(b.h), l = toNum(b.l), c = toNum(b.c);
      return o === null || h === null || l === null || c === null ? null : { open: o, high: h, low: l, close: c, volume: toNum(b.v) || 0 };
    });
    if (!bars.length) {
      chartMessage(box, "No price bars for " + d.symbol + " yet.");
      clear($("#ch-legend"));
      return;
    }
    const entry = getChart("price", box);
    if (!entry) return;
    chartMessage(box, null);
    resetSeries(entry);
    const chart = entry.chart;
    const firstClose = bars[0].close;
    $("#ch-sub").textContent = bars.length + " sessions \u00b7 " + fmtShortDay(bars[0].time) + " \u2013 " + fmtShortDay(bars[bars.length - 1].time);

    // Keep entry/stop/target inside the visible price range even when price has moved far from them.
    const lvIn = d.levels || {};
    const levelPrices = [lvIn.entry, lvIn.stop, lvIn.target, lvIn.current_stop].map(toNum).filter((v) => v !== null && v > 0);
    const candles = chart.addCandlestickSeries({
      upColor: cssVar("--c-up"), downColor: cssVar("--c-down"), borderVisible: false,
      wickUpColor: cssVar("--c-up"), wickDownColor: cssVar("--c-down"), priceFormat: priceFmt(), priceLineVisible: false,
      autoscaleInfoProvider: (original) => {
        const r = original();
        if (!r || !r.priceRange || !levelPrices.length) return r;
        return Object.assign({}, r, { priceRange: {
          minValue: Math.min(r.priceRange.minValue, ...levelPrices),
          maxValue: Math.max(r.priceRange.maxValue, ...levelPrices),
        } });
      },
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.12, bottom: 0.24 } });
    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false });
    const sma20 = chart.addLineSeries({ color: cssVar("--c-sma20"), lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceFormat: priceFmt() });
    const sma50 = chart.addLineSeries({ color: cssVar("--c-sma50"), lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceFormat: priceFmt() });

    const paintVolume = () => volume.setData(bars.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? cssVar("--c-vol-up") : cssVar("--c-vol-down") })));
    candles.setData(bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));
    paintVolume();
    const barDays = new Set(bars.map((b) => b.time));
    const clip = (arr) => dailySeries(arr, "t", (r) => toNum(r.v)).filter((p) => barDays.has(p.time));
    sma20.setData(clip(d.sma20));
    sma50.setData(clip(d.sma50));
    entry.series = { candles: candles, volume: volume, sma20: sma20, sma50: sma50 };

    // Levels: entry (neutral), stop (red), current trailing stop (orange dashed), target (green).
    const lv = d.levels || {};
    const LS = window.LightweightCharts.LineStyle;
    const addLevel = (price, colorVar, title, style, width) => {
      const p = toNum(price);
      if (p === null) return;
      entry.priceLines.push({ line: candles.createPriceLine({ price: p, color: cssVar(colorVar), lineWidth: width || 1, lineStyle: style, axisLabelVisible: true, title: title }), colorVar: colorVar });
    };
    addLevel(lv.entry, "--c-entry", "Entry", LS.Solid, 1);
    addLevel(lv.stop, "--c-stop", "Stop", LS.Solid, 2);
    if (toNum(lv.current_stop) !== null && Math.abs(toNum(lv.current_stop) - (toNum(lv.stop) || -1)) > 0.004) addLevel(lv.current_stop, "--c-trail", "Trail", LS.Dashed, 2);
    addLevel(lv.target, "--c-target", "Target", LS.Solid, 2);

    // Markers must sit on a bar time and be sorted: snap each to the last bar on or before its date.
    const days = bars.map((b) => b.time);
    const snap = (t) => {
      const day = toDay(t);
      if (!day) return null;
      let lo = 0, hi = days.length - 1, ans = null;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if (days[mid] <= day) { ans = days[mid]; lo = mid + 1; } else hi = mid - 1; }
      return ans;
    };
    const paintMarkers = () => {
      const ms = (Array.isArray(d.markers) ? d.markers : []).map((m) => {
        const time = snap(m.t);
        if (!time) return null;
        const st = markerStyle(m.kind);
        const label = String(m.kind || "").toLowerCase() === "entry" ? "Buy" : String(m.kind || "").toLowerCase() === "exit" ? "Sell" : "Signal";
        const px = toNum(m.price);
        return { time: time, position: st.position, shape: st.shape, color: st.color, text: label === "Sell" && px !== null ? label + " " + fmtNum(px, 2) : label };
      }).filter(Boolean).sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
      candles.setMarkers(ms);
    };
    paintMarkers();

    entry.restyle = () => {
      candles.applyOptions({ upColor: cssVar("--c-up"), downColor: cssVar("--c-down"), wickUpColor: cssVar("--c-up"), wickDownColor: cssVar("--c-down") });
      sma20.applyOptions({ color: cssVar("--c-sma20") });
      sma50.applyOptions({ color: cssVar("--c-sma50") });
      entry.priceLines.forEach((pl) => pl.line.applyOptions({ color: cssVar(pl.colorVar) }));
      paintVolume();
      paintMarkers();
    };

    // Legend: OHLC + change + volume + SMAs under the crosshair (last bar by default).
    const byDay = new Map(bars.map((b, i) => [b.time, i]));
    const smaAt = (arr) => { const m = new Map(clip(arr).map((p) => [p.time, p.value])); return (t) => m.get(t); };
    const s20 = smaAt(d.sma20), s50 = smaAt(d.sma50);
    const legend = (param) => {
      let i = bars.length - 1;
      if (param && param.time) { const t = lwcDay(param.time); if (byDay.has(t)) i = byDay.get(t); }
      const b = bars[i];
      const prev = i > 0 ? bars[i - 1].close : firstClose;
      const chg = prev ? ((b.close - prev) / prev) * 100 : null;
      replace($("#ch-legend"), [
        el("b", { text: d.symbol }),
        el("span", { text: fmtDay(b.time) }),
        el("span", { text: "O " + fmtNum(b.open) + "  H " + fmtNum(b.high) + "  L " + fmtNum(b.low) + "  C " + fmtNum(b.close) }),
        el("span", { class: signClass(chg), text: arrow(chg) + fmtPct(chg, 2, true) }),
        el("span", { text: "Vol " + compactNum(b.volume) }),
        el("span", null, [el("i", { class: "sw", style: "background:var(--c-sma20)" }), "20 " + fmtNum(s20(b.time))]),
        el("span", null, [el("i", { class: "sw", style: "background:var(--c-sma50)" }), "50 " + fmtNum(s50(b.time))]),
      ]);
    };
    if (entry.legendHandler) chart.unsubscribeCrosshairMove(entry.legendHandler);
    entry.legendHandler = legend;
    chart.subscribeCrosshairMove(legend);
    legend(null);
    fitSoon(entry);
  }
  function compactNum(v) {
    const n = toNum(v);
    if (n === null) return DASH;
    const a = Math.abs(n);
    if (a >= 1e9) return fmtNum(n / 1e9, 2) + "B";
    if (a >= 1e6) return fmtNum(n / 1e6, 2) + "M";
    if (a >= 1e3) return fmtNum(n / 1e3, 1) + "K";
    return fmtInt(n);
  }
  function renderChartSide(chartData) {
    const side = $("#ch-side");
    const sym = state.chartSymbol;
    if (!sym) { replace(side, emptyBox("Pick a symbol.")); return; }
    const d = chartData === undefined ? state.chartData : chartData;
    const lv = (d && d.symbol === sym && d.levels) || {};
    const p = positionFor(sym);
    const cur = p ? toNum(p.current) : (d && Array.isArray(d.bars) && d.bars.length ? toNum(d.bars[d.bars.length - 1].c) : null);
    const entryPx = toNum(lv.entry) !== null ? toNum(lv.entry) : p ? toNum(p.avg_entry) : null;
    const stopPx = toNum(lv.stop) !== null ? toNum(lv.stop) : p ? toNum(p.stop) : null;
    const risk = entryPx !== null && stopPx !== null ? Math.abs(entryPx - stopPx) : null;
    const dist = (px) => {
      const v = toNum(px);
      if (v === null || cur === null || !cur) return "";
      const pct = ((v - cur) / cur) * 100;
      return fmtPct(pct, 1, true);
    };
    const rOf = (px) => {
      const v = toNum(px);
      if (v === null || entryPx === null || !risk) return "";
      const short = p ? isShort(p) : false;
      return fmtSigned(((short ? entryPx - v : v - entryPx) / risk), 1, "R");
    };
    const lvlRow = (cls, label, px) => [
      el("dt", null, [el("span", { class: "lvl lvl--" + cls, "aria-hidden": "true" }), label]),
      el("dd", null, [fmtMoney(px), toNum(px) !== null ? el("span", { class: "lvl-dist", text: [dist(px), rOf(px)].filter(Boolean).join(" \u00b7 ") }) : null]),
    ];
    const blocks = [];
    if (p) {
      const pl = toNum(p.unrealized_pl), pct = positionPct(p), r = toNum(p.r_multiple);
      blocks.push(el("h3", { text: "Position" }));
      blocks.push(el("dl", null, [
        el("dt", { text: "Strategy" }), el("dd", { title: p.strategy || "", text: strategyName(p.strategy) }),
        el("dt", { text: "Quantity" }), el("dd", { text: fmtQty(p.qty) + (isShort(p) ? " short" : "") }),
        el("dt", { text: "Current" }), el("dd", { text: fmtMoney(p.current) }),
        el("dt", { text: "Market value" }), el("dd", { text: fmtMoney(p.market_value) }),
        el("dt", { text: "Unrealized" }), el("dd", { class: signClass(pl), text: arrow(pl) + fmtSignedMoney(pl) + " (" + fmtPct(pct, 2, true) + ")" }),
        el("dt", { text: "R multiple" }), el("dd", { class: signClass(r), text: r === null ? DASH : fmtSigned(r, 2, "R") }),
        el("dt", { text: "Risk / share" }), el("dd", { text: fmtMoney(p.risk_per_share) }),
        el("dt", { text: "Days held" }), el("dd", { text: fmtInt(p.days_held) + (toNum(p.max_hold_days) ? " of " + fmtInt(p.max_hold_days) : "") }),
        el("dt", { text: "Opened" }), el("dd", { text: p.opened_at ? fmtDay(p.opened_at) : DASH }),
      ]));
    } else {
      blocks.push(el("p", { class: "muted", text: "Not an open position. Levels show when the chart data includes them." }));
    }
    blocks.push(el("h3", { text: "Levels" + (cur !== null ? " (vs " + fmtMoney(cur) + ")" : "") }));
    blocks.push(el("dl", null, [
      ...lvlRow("entry", "Entry", entryPx),
      ...lvlRow("stop", "Initial stop", stopPx),
      ...lvlRow("trail", "Current stop", toNum(lv.current_stop) !== null ? lv.current_stop : p ? toNum(p.current_stop) : null),
      ...lvlRow("target", "Target", toNum(lv.target) !== null ? lv.target : p ? p.target : null),
    ]));
    if (p && liveStop(p) === null && toNum(lv.current_stop) === null) blocks.push(el("div", { class: "allowed__none", text: "No stop on this position." }));
    replace(side, blocks);
  }

  // Orders ------------------------------------------------------------------------------------------
  function orderTone(status) {
    const s = String(status || "").toLowerCase();
    if (s === "filled") return "ok";
    if (s === "partially_filled") return "warn";
    if (["rejected", "suspended", "stopped"].includes(s)) return "bad";
    if (["new", "accepted", "pending_new", "accepted_for_bidding", "held", "pending_replace", "replaced", "calculated"].includes(s)) return "info";
    return "";
  }
  function legLabel(o) {
    const t = String(o.type || "").toLowerCase();
    if (t === "limit") return "Target leg";
    if (t === "stop" || t === "stop_limit" || t === "trailing_stop") return "Stop leg";
    return "Leg";
  }
  async function loadOrders(opts) {
    const body = $("#orders-body");
    if (!(opts && opts.quiet)) showSkeleton(body, 4);
    const res = await api("/api/orders?status=" + encodeURIComponent(state.orderStatus) + "&limit=50", { key: "orders" });
    if (res.aborted) return;
    if (!res.ok) { if (!(opts && opts.quiet)) { showUnavailable(body, res); setNote("ord-note", null); } return; }
    const ofb = fallbackSource(res.source);
    setNote("ord-note", res, [ofb ? "From the " + ofb : null]);
    renderOrders(Array.isArray(res.data) ? res.data : []);
  }
  function orderRow(o, isLeg) {
    const qty = toNum(o.qty), filled = toNum(o.filled_qty);
    const side = String(o.side || "").toLowerCase();
    const tr = el("tr", { class: isLeg ? "leg" : "" }, [
      el("td", { class: "nowrap" }, isLeg ? ["\u21b3 ", legLabel(o)] : fmtDateTime(o.submitted_at)),
      el("td", null, isLeg ? "" : el("span", { class: "sym", text: o.symbol || DASH })),
      el("td", { class: side === "buy" ? "pos" : side === "sell" ? "neg" : "", text: side ? side.toUpperCase() : DASH }),
      el("td", { text: humanize(o.type) }),
      el("td", { class: "r", text: (filled ? fmtQty(filled) + " / " : "") + fmtQty(qty) }),
      el("td", { class: "r", text: fmtMoney(o.limit_price) }),
      el("td", { class: "r", text: fmtMoney(o.stop_price) }),
      el("td", null, el("span", { class: "chip" + (orderTone(o.status) ? " chip--" + orderTone(o.status) : ""), text: humanize(o.status) })),
      el("td", { class: "r", text: o.filled_at ? fmtMoney(o.filled_avg_price) : DASH, title: o.filled_at ? "Filled " + fmtDateTime(o.filled_at) : "" }),
      el("td", { class: "strat", title: o.strategy || "", text: isLeg ? "" : strategyName(o.strategy) }),
      el("td", { class: "mono muted", title: o.client_order_id || o.id || "", text: isLeg ? "" : shortId(o.client_order_id || o.id) }),
    ]);
    return tr;
  }
  function shortId(s) { const t = String(s || ""); return t.length > 34 ? t.slice(0, 31) + "\u2026" : t || DASH; }
  function renderOrders(list) {
    const body = $("#orders-body");
    if (!list.length) { replace(body, emptyBox(state.orderStatus === "open" ? "No open orders." : "No recent closed orders.")); return; }
    const sorted = list.slice().sort((a, b) => String(b.submitted_at || "").localeCompare(String(a.submitted_at || "")));
    const rows = [];
    sorted.forEach((o) => {
      rows.push(orderRow(o, false));
      (Array.isArray(o.legs) ? o.legs : []).forEach((leg) => rows.push(orderRow(leg, true)));
    });
    replace(body, el("table", { class: "data" }, [
      el("thead", null, el("tr", null, [
        el("th", { text: "Submitted" }), el("th", { text: "Symbol" }), el("th", { text: "Side" }), el("th", { text: "Type" }),
        el("th", { class: "r", text: "Qty" }), el("th", { class: "r", text: "Limit" }), el("th", { class: "r", text: "Stop" }),
        el("th", { text: "Status" }), el("th", { class: "r", text: "Fill price" }), el("th", { text: "Strategy" }), el("th", { text: "Client order id" }),
      ])),
      el("tbody", null, rows),
    ]));
  }

  // ------------------------------------------------------------------------------------------------
  // Signals
  // ------------------------------------------------------------------------------------------------
  async function loadSignals(date) {
    const body = $("#signals-body");
    showSkeleton(body, 6);
    clear($("#sg-summary"));
    const q = date ? "?date=" + encodeURIComponent(date) : "";
    const res = await api("/api/signals" + q, { key: "signals", timeout: SLOW_FETCH_TIMEOUT_MS });
    if (res.aborted) return;
    if (!res.ok) {
      state.signals = null;
      showUnavailable(body, res);
      setNote("sg-note", null);
      $("#sg-date-label").textContent = date ? fmtDay(date) : "";
      return;
    }
    state.signals = res.data || { signals: [] };
    const rs = state.signals.review_status;
    const rsText = rs && rs.status && rs.status !== "ok"
      ? "Claude review step " + (rs.status === "running" ? "did not finish" : rs.status === "skip" ? "was skipped" : "failed") +
        (rs.detail ? " (" + rs.detail + ")" : "") + (rs.at ? " at " + fmtDateTime(rs.at) : "") +
        ((state.signals.signals || []).some((x) => x && x.review) ? ". The reviews shown are from an earlier run and were not applied." : ".")
      : null;
    setNote("sg-note", res, [rsText]);
    state.signalOpen = new Set();
    if (state.signals.date) $("#sg-date").value = toDay(state.signals.date) || "";
    $("#sg-date-label").textContent = state.signals.date ? fmtDay(state.signals.date) : "";
    populateStrategyFilter();
    renderSignals();
    renderSymbolChips();
  }
  function populateStrategyFilter() {
    const sel = $("#sg-strategy");
    const keep = state.signalFilters.strategy;
    const strategies = Array.from(new Set(((state.signals && state.signals.signals) || []).map((s) => s && s.strategy).filter(Boolean))).sort();
    replace(sel, [el("option", { value: "", text: "All strategies" }), ...strategies.map((s) => el("option", { value: s, text: strategyName(s) }))]);
    sel.value = strategies.includes(keep) ? keep : "";
    state.signalFilters.strategy = sel.value;
  }
  function isTaken(s) { return s && (s.taken === true || s.taken === "true" || s.taken === 1); }
  /** A review the latest review step did not produce (it was skipped / failed): shown, but not counted or toned. */
  function reviewApplied(review) { return !!review && review.current !== false; }
  function decisionChip(review) {
    if (!review) return el("span", { class: "muted", text: "not reviewed" });
    const d = DECISIONS[String(review.decision || "").toLowerCase()] || { label: humanize(review.decision), tone: "" };
    if (!reviewApplied(review)) return el("span", { class: "chip", title: "From an earlier run: the latest review step did not run, so this decision was not applied", text: d.label + " (earlier run)" });
    return el("span", { class: "chip" + (d.tone ? " chip--" + d.tone : ""), text: d.label });
  }
  function signalKey(s, i) { return [s.strategy, s.symbol, s.side, i].join("|"); }
  function renderSignals() {
    const body = $("#signals-body");
    const all = ((state.signals && state.signals.signals) || []).filter(Boolean);
    const f = state.signalFilters;
    const list = all
      .map((s, i) => ({ s: s, key: signalKey(s, i) }))
      .filter(({ s }) => (!f.strategy || s.strategy === f.strategy) && (f.taken === "all" || (f.taken === "taken") === isTaken(s)))
      .sort((a, b) => (Number(isTaken(b.s)) - Number(isTaken(a.s))) || ((toNum(b.s.score) || -Infinity) - (toNum(a.s.score) || -Infinity)));
    const taken = all.filter(isTaken).length;
    const reviewed = all.filter((s) => reviewApplied(s.review)).length;
    const vetoed = all.filter((s) => reviewApplied(s.review) && ["reject", "needs_more_info"].includes(String(s.review.decision || "").toLowerCase())).length;
    replace($("#sg-summary"), [
      el("span", { class: "stat-inline" }, [el("b", { text: fmtInt(all.length) }), " signals"]),
      el("span", { class: "stat-inline" }, [el("b", { text: fmtInt(taken) }), " taken"]),
      el("span", { class: "stat-inline" }, [el("b", { text: fmtInt(all.length - taken) }), " skipped"]),
      el("span", { class: "stat-inline" }, [el("b", { text: fmtInt(reviewed) }), " reviewed by Claude"]),
      vetoed ? el("span", { class: "stat-inline" }, [el("b", { text: fmtInt(vetoed) }), " vetoed"]) : null,
      list.length !== all.length ? el("span", { class: "muted", text: "showing " + list.length }) : null,
    ]);
    if (!all.length) { replace(body, emptyBox("The strategies produced no signals for this date.")); return; }
    if (!list.length) { replace(body, emptyBox("No signals match these filters.")); return; }
    const rows = [];
    list.forEach(({ s, key }, idx) => {
      const open = state.signalOpen.has(key);
      const detailId = "sg-detail-" + idx;
      const btn = el("button", { type: "button", class: "expander", "aria-expanded": String(open), "aria-controls": detailId, "aria-label": "Details for " + (s.symbol || "") + " " + strategyName(s.strategy) }, chevron());
      const tr = el("tr", null, [
        el("td", { class: "c" }, btn),
        el("td", null, el("span", { class: "sym", text: s.symbol || DASH })),
        el("td", { class: "strat", title: s.strategy || "", text: strategyName(s.strategy) }),
        el("td", { text: String(s.side || "long").toLowerCase() === "short" ? "Short" : "Long" }),
        el("td", { class: "r", text: fmtMoney(s.entry) }),
        el("td", { class: "r", text: fmtMoney(s.stop) }),
        el("td", { class: "r", text: fmtMoney(s.target) }),
        el("td", { class: "r", text: toNum(s.reward_risk) === null ? DASH : fmtNum(s.reward_risk, 2) + " : 1" }),
        el("td", { class: "r", text: fmtNum(s.score, 2) }),
        el("td", null, isTaken(s) ? el("span", { class: "chip chip--ok", text: "\u2713 Taken" }) : el("span", { class: "chip", text: "Skipped" })),
        el("td", { class: "muted", text: isTaken(s) ? "" : s.skip_reason ? reasonText(s.skip_reason) : DASH }),
        el("td", null, decisionChip(s.review)),
      ]);
      const detail = el("tr", { class: "detail", id: detailId, hidden: !open }, el("td", { colspan: "12" }, signalDetail(s)));
      btn.addEventListener("click", () => {
        const now = btn.getAttribute("aria-expanded") !== "true";
        btn.setAttribute("aria-expanded", String(now));
        detail.hidden = !now;
        if (now) state.signalOpen.add(key); else state.signalOpen.delete(key);
      });
      rows.push(tr, detail);
    });
    replace(body, el("table", { class: "data" }, [
      el("thead", null, el("tr", null, [
        el("th", null, el("span", { class: "sr-only", text: "Expand" })), el("th", { text: "Symbol" }), el("th", { text: "Strategy" }), el("th", { text: "Side" }),
        el("th", { class: "r", text: "Entry" }), el("th", { class: "r", text: "Stop" }), el("th", { class: "r", text: "Target" }),
        el("th", { class: "r", text: "Reward : risk" }), el("th", { class: "r", text: "Score" }), el("th", { text: "Status" }),
        el("th", { text: "Skip reason" }), el("th", { text: "Claude review" }),
      ])),
      el("tbody", null, rows),
    ]));
  }
  function signalDetail(s) {
    const entry = toNum(s.entry), stop = toNum(s.stop), target = toNum(s.target);
    const risk = entry !== null && stop !== null ? Math.abs(entry - stop) : null;
    const rv = s.review;
    const left = [];
    if (rv) {
      left.push(el("h4", null, ["Claude's review ", decisionChip(rv)]));
      if (!reviewApplied(rv)) left.push(el("p", { class: "muted", text: "This review is from an earlier run. The latest review step did not run, so the decision was not applied to this signal." }));
      left.push(el("p", { class: "review__thesis", text: rv.thesis ? String(rv.thesis) : "No thesis given." }));
      const flags = Array.isArray(rv.event_risk_flags) ? rv.event_risk_flags.filter(Boolean) : [];
      left.push(el("h4", { text: "Event risk flags" }));
      left.push(flags.length ? el("div", null, flags.map((fl) => el("span", { class: "tag tag--flag", text: humanize(fl) }))) : el("p", { class: "muted", text: "None flagged." }));
    } else {
      left.push(el("h4", { text: "Claude's review" }));
      left.push(el("p", { class: "muted", text: isTaken(s) ? "Not reviewed (no API key, or the review step was skipped for this run)." : "Not reviewed: skipped signals are usually not sent for review." }));
    }
    if (!isTaken(s) && s.skip_reason) {
      left.push(el("h4", { text: "Why it was not taken" }));
      left.push(el("p", { text: reasonText(s.skip_reason) }));
    }
    const right = el("div", null, [
      el("h4", { text: "Geometry" }),
      el("dl", null, [
        el("dt", { text: "Risk / share" }), el("dd", { text: fmtMoney(risk) }),
        el("dt", { text: "Stop distance" }), el("dd", { text: risk !== null && entry ? fmtPct((risk / entry) * 100, 2) : DASH }),
        el("dt", { text: "Target distance" }), el("dd", { text: target !== null && entry ? fmtPct(((target - entry) / entry) * 100, 2, true) : DASH }),
        el("dt", { text: "Reward : risk" }), el("dd", { text: toNum(s.reward_risk) === null ? DASH : fmtNum(s.reward_risk, 2) + " : 1" }),
      ]),
      el("p", { style: "margin-top:10px" }, el("button", { type: "button", class: "linkish", onclick: () => openChart(s.symbol), text: "Open " + (s.symbol || "") + " chart \u2192" })),
    ]);
    return el("div", { class: "review" }, [el("div", null, left), right]);
  }
  function initSignalControls() {
    $("#sg-date").addEventListener("change", (ev) => {
      const v = ev.target.value;
      if (v) setHash("signals", v); else setHash("signals");
    });
    $("#sg-strategy").addEventListener("change", (ev) => { state.signalFilters.strategy = ev.target.value; renderSignals(); });
    $$("#sg-taken button").forEach((b) => b.addEventListener("click", () => {
      state.signalFilters.taken = b.dataset.taken;
      $$("#sg-taken button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      renderSignals();
    }));
    $("#sg-date").max = todayET();
  }

  // ------------------------------------------------------------------------------------------------
  // Shadow ledger
  // ------------------------------------------------------------------------------------------------
  async function loadShadow() {
    const targets = [["strategy", $("#shadow-strategy")], ["regime", $("#shadow-regime")]];
    targets.forEach(([, node]) => showSkeleton(node, 5));
    const results = await Promise.all(targets.map(([by]) => api("/api/shadow?by=" + by, { key: "shadow-" + by, timeout: SLOW_FETCH_TIMEOUT_MS })));
    let updated = null;
    setNote("sh-note", results.find((r) => r.ok && r.stale) || null);
    results.forEach((res, i) => {
      const [by, node] = targets[i];
      if (res.aborted) return;
      if (!res.ok) { showUnavailable(node, res); return; }
      const d = res.data || {};
      if (d.updated_at) updated = d.updated_at;
      renderShadowTable(node, Array.isArray(d.rows) ? d.rows : [], by);
    });
    $("#sh-updated").textContent = updated ? "graded " + fmtDateTime(updated) + " (" + fmtAgo(updated) + ")" : "";
  }
  function fmtPF(v, infinite) {
    if (infinite === true || v === "inf" || v === "Infinity" || v === Infinity) return "\u221e";
    const n = toNum(v);
    return n === null ? DASH : fmtNum(n, 2);
  }
  function groupName(g, by) {
    if (by === "regime") return (REGIMES[g] && REGIMES[g].name) || humanize(g);
    return strategyName(g);
  }
  function renderShadowTable(node, rows, by) {
    if (!rows.length) { replace(node, emptyBox("No graded signals yet. Signals are graded once the bars after them arrive.")); return; }
    const sorted = rows.slice().sort((a, b) => (toNum(b.expectancy_r) ?? -Infinity) - (toNum(a.expectancy_r) ?? -Infinity));
    const maxAbs = Math.max(0.5, ...sorted.map((r) => Math.abs(toNum(r.expectancy_r) || 0)));
    const body = sorted.map((r) => {
      const n = toNum(r.n) || 0;
      const exp = toNum(r.expectancy_r);
      const width = exp === null ? 0 : (Math.abs(exp) / maxAbs) * 50;
      return el("tr", { class: n < SHADOW_MIN_N ? "is-dim" : "", title: n < SHADOW_MIN_N ? "Only " + n + " graded signals: too few to judge" : "" }, [
        el("td", { class: "strat", title: String(r.group || ""), text: groupName(r.group, by) }),
        el("td", { class: "r", text: fmtInt(r.n) }),
        el("td", { class: "r", text: fmtRatioPct(r.win_rate, 1) }),
        el("td", { class: "r " + signClass(r.avg_r), text: fmtSigned(r.avg_r, 2, "R") }),
        el("td", { class: "r " + signClass(exp), text: fmtSigned(exp, 2, "R") }),
        el("td", null, el("div", { class: "dbar", role: "img", "aria-label": "Expectancy " + fmtSigned(exp, 2, "R") }, [
          el("span", { class: "dbar__axis" }),
          exp === null ? null : el("span", { class: "dbar__fill " + (exp >= 0 ? "is-pos" : "is-neg"), style: "width:" + width.toFixed(1) + "%" }),
        ])),
        el("td", { class: "r", title: r.profit_factor_infinite ? "No losing signals yet" : "", text: fmtPF(r.profit_factor, r.profit_factor_infinite) }),
        el("td", { class: "r muted", text: fmtInt(r.pending) }),
        el("td", { class: "r muted", title: "Signals sized into an order intent that survived the review, of all signals recorded", text: toNum(r.n_signals) === null ? DASH : fmtInt(r.n_taken) + " / " + fmtInt(r.n_signals) }),
      ]);
    });
    replace(node, el("table", { class: "data" }, [
      el("thead", null, el("tr", null, [
        el("th", { text: by === "regime" ? "Regime" : "Strategy" }), el("th", { class: "r", text: "n" }), el("th", { class: "r", text: "Win rate" }),
        el("th", { class: "r", text: "Avg R" }), el("th", { class: "r", text: "Expectancy" }), el("th", { text: "\u2212 0 +", class: "c", title: "Expectancy, scaled to the largest row" }),
        el("th", { class: "r", text: "Profit factor" }), el("th", { class: "r", text: "Pending" }),
        el("th", { class: "r", text: "Taken / signals" }),
      ])),
      el("tbody", null, body),
    ]));
  }

  // ------------------------------------------------------------------------------------------------
  // Drift (live shadow ledger vs replay, research.drift)
  // ------------------------------------------------------------------------------------------------
  const DRIFT_HORIZONS = [5, 10, 20];
  async function loadDrift() {
    const node = $("#drift-body");
    showSkeleton(node, 5);
    const res = await api("/api/drift", { key: "drift", timeout: SLOW_FETCH_TIMEOUT_MS });
    if (res.aborted) return;
    setNote("dr-note", res.ok && res.stale ? res : null);
    if (!res.ok) { showUnavailable(node, res); return; }
    const d = res.data || {};
    $("#dr-updated").textContent = d.as_of ? "live window: " + d.window_days + " days to " + d.as_of + (d.replay_rows ? "" : " (no replay ledger in this store)") : "";
    renderDrift(node, Array.isArray(d.rows) ? d.rows : []);
  }
  function driftChip(flag) {
    if (flag === "below") return el("span", { class: "chip chip--bad", text: "below" });
    if (flag === "above") return el("span", { class: "chip chip--ok", text: "above" });
    return null;
  }
  function renderDrift(node, rows) {
    if (!rows.length) { replace(node, emptyBox("No live shadow signals in the window yet.")); return; }
    const rank = { below: 0, above: 1, "": 2 };
    const sorted = rows.slice().sort((a, b) => (rank[a.flag || ""] - rank[b.flag || ""]) || ((toNum(a.diff_10d) ?? Infinity) - (toNum(b.diff_10d) ?? Infinity)));
    const head = [el("th", { text: "Strategy" }), el("th", { text: "Flag" })];
    DRIFT_HORIZONS.forEach((h) => {
      ["n", "Win", "Live", "Replay", "Diff"].forEach((t) => head.push(el("th", { class: "r", text: t + " " + h + "d" })));
    });
    const body = sorted.map((r) => {
      const cells = [el("td", { class: "strat", title: String(r.strategy || ""), text: strategyName(r.strategy) }), el("td", null, driftChip(r.flag))];
      DRIFT_HORIZONS.forEach((h) => {
        const n = toNum(r["n_" + h + "d"]) || 0;
        const flag = r["flag_" + h + "d"];
        cells.push(
          el("td", { class: "r" + (n < SHADOW_MIN_N ? " muted" : ""), text: fmtInt(n) }),
          el("td", { class: "r", text: fmtRatioPct(r["win_" + h + "d"], 0) }),
          el("td", { class: "r " + signClass(r["live_r_" + h + "d"]), text: fmtSigned(r["live_r_" + h + "d"], 2, "R") }),
          el("td", { class: "r muted", title: "replay trades: " + fmtInt(r["replay_n_" + h + "d"]), text: fmtSigned(r["replay_r_" + h + "d"], 2, "R") }),
          el("td", { class: "r " + (flag ? (flag === "below" ? "neg" : "pos") : "muted"), title: "standard error " + fmtSigned(r["se_" + h + "d"], 2, "R"), text: fmtSigned(r["diff_" + h + "d"], 2, "R") }),
        );
      });
      return el("tr", { class: (toNum(r.n_10d) || 0) < SHADOW_MIN_N ? "is-dim" : "" }, cells);
    });
    replace(node, el("table", { class: "data" }, [el("thead", null, el("tr", null, head)), el("tbody", null, body)]));
  }

  // ------------------------------------------------------------------------------------------------
  // Alerts (titles come from the internet: textContent only; links only http/https)
  // ------------------------------------------------------------------------------------------------
  function safeUrl(u) {
    if (typeof u !== "string") return null;
    const t = u.trim();
    if (!/^https?:\/\//i.test(t)) return null;
    try { const parsed = new URL(t); return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null; } catch (e) { return null; }
  }
  function prioClass(p) { const s = String(p || "").toUpperCase(); return ["P0", "P1", "P2", "P3"].includes(s) ? "chip--" + s.toLowerCase() : "chip--p1"; }
  async function loadAlerts(opts) {
    const body = $("#alerts-body");
    const quiet = opts && opts.quiet;
    if (quiet && state.ratingPending > 0) return; // do not re-render under a pending rating
    if (!quiet || !state.alerts) showSkeleton(body, 6);
    const res = await api("/api/alerts?hours=" + encodeURIComponent(state.alertHours), { key: "alerts" });
    if (res.aborted) return;
    if (!res.ok) { if (!(quiet && state.alerts)) { state.alerts = null; showUnavailable(body, res); } return; }
    if (quiet && state.ratingPending > 0) return;
    const data = Array.isArray(res.data) ? res.data : [];
    if (quiet && unchanged("alerts", data) && state.alerts) return;
    lastPayload.alerts = JSON.stringify(data);
    state.alerts = data;
    preservingFocus($("#alerts-body"), renderAlerts);
  }
  function renderAlerts() {
    const body = $("#alerts-body");
    const all = (state.alerts || []).filter(Boolean);
    const list = all
      .filter((a) => state.alertPrio === "all" || String(a.priority || "").toUpperCase() === state.alertPrio)
      .sort((a, b) => (parseTime(b.ts) || 0) - (parseTime(a.ts) || 0));
    if (!all.length) { replace(body, emptyBox("No alerts in this window.")); return; }
    if (!list.length) { replace(body, emptyBox("No " + state.alertPrio + " alerts in this window.")); return; }
    replace(body, el("ul", { class: "alert-list" }, list.map(alertItem)));
  }
  function alertItem(a) {
    const url = safeUrl(a.url);
    const title = String(a.title || "(no title)");
    const titleNode = url
      ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer", referrerpolicy: "no-referrer" }, [title, el("span", { class: "ext", "aria-hidden": "true", text: "\u2197" }), el("span", { class: "sr-only", text: " (opens the source in a new tab)" })])
      : title;
    const symbols = Array.isArray(a.symbols) ? a.symbols.filter(Boolean) : [];
    const rules = Array.isArray(a.rule_hits) ? a.rule_hits.filter(Boolean) : [];
    const msg = el("span", { class: "rate-msg", role: "status" });
    const group = el("div", { class: "rate-group", role: "group", "aria-label": "Rate this alert" });
    RATINGS.forEach((r) => {
      const b = el("button", { type: "button", "data-rating": r.key, "aria-pressed": String(a.rating === r.key), text: r.label });
      b.addEventListener("click", () => rateAlert(a, r.key, group, msg));
      group.appendChild(b);
    });
    if (a.rating) msg.textContent = "Rated " + humanize(a.rating).toLowerCase();
    return el("li", { class: "alert", "data-key": String(a.event_id || "") }, [
      el("div", { class: "alert__prio" }, el("span", { class: "chip " + prioClass(a.priority), text: String(a.priority || "P?").toUpperCase() })),
      el("div", null, [
        el("div", { class: "alert__title" }, titleNode),
        el("div", { class: "alert__meta" }, [
          el("span", { class: "nowrap", title: a.ts ? fmtDateTime(a.ts) + " local / " + fmtDateTime(a.ts, ET) + " ET" : "", text: fmtDateTime(a.ts) + " \u00b7 " + fmtAgo(a.ts) }),
          a.source ? el("span", { class: "mono", text: String(a.source) }) : null,
          a.kind ? el("span", { text: humanize(a.kind) }) : null,
          symbols.length ? el("span", null, symbols.slice(0, 12).map((s) => el("button", { type: "button", class: "tag tag--sym linkish", title: "Open " + s + " chart", onclick: () => openChart(s), text: String(s) }))) : null,
          rules.length ? el("span", null, rules.map((r) => el("span", { class: "tag", text: String(r) }))) : null,
        ]),
      ]),
      el("div", { class: "alert__rate" }, [group, msg]),
    ]);
  }
  async function rateAlert(alert, rating, group, msg) {
    if (!alert.event_id) { msg.textContent = "This alert has no id to rate."; msg.classList.add("is-error"); return; }
    const buttons = $$("button", group);
    buttons.forEach((b) => { b.disabled = true; });
    msg.classList.remove("is-error");
    msg.textContent = "Saving\u2026";
    state.ratingPending = (state.ratingPending || 0) + 1;
    const res = await api("/api/alerts/" + encodeURIComponent(alert.event_id) + "/rate", { method: "POST", body: { rating: rating } });
    state.ratingPending -= 1;
    buttons.forEach((b) => { b.disabled = false; });
    if (!res.ok) {
      msg.classList.add("is-error");
      msg.textContent = "Not saved: " + res.unavailable;
      return;
    }
    const saved = (res.data && res.data.rating) || rating;
    alert.rating = saved;
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.rating === saved)));
    msg.textContent = "Rated " + humanize(saved).toLowerCase();
  }
  function initAlertControls() {
    $$("#al-prio button").forEach((b) => b.addEventListener("click", () => {
      state.alertPrio = b.dataset.prio;
      $$("#al-prio button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      renderAlerts();
    }));
    $("#al-hours").addEventListener("change", (ev) => { state.alertHours = Number(ev.target.value) || 48; loadAlerts(); });
  }

  // ------------------------------------------------------------------------------------------------
  // Markdown: a tiny, safe renderer. ALL HTML is escaped first; only our own tags are produced.
  // Supports headings, paragraphs, lists (nested by indent), bold/italic, inline + fenced code,
  // blockquotes, rules, pipe tables and http(s) links (rel="noopener noreferrer").
  // ------------------------------------------------------------------------------------------------
  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function mdInline(escaped) {
    const stash = [];
    const put = (html) => "\u0000" + (stash.push(html) - 1) + "\u0000";
    let s = escaped;
    s = s.replace(/`([^`]+)`/g, (m, code) => put("<code>" + code + "</code>"));
    s = s.replace(/\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/g, (m, text, url) => {
      if (!/^https?:\/\/[^\s]+$/i.test(url)) return text;
      return put('<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + mdEmphasis(text) + "</a>");
    });
    s = s.replace(/(^|[\s(])(https?:\/\/(?:(?!&quot;|&#39;|&lt;|&gt;)[^\s<)])+)/g, (m, lead, url) => {
      const trail = (url.match(/[.,;:!?]+$/) || [""])[0];
      const u = trail ? url.slice(0, -trail.length) : url;
      return lead + put('<a href="' + u + '" target="_blank" rel="noopener noreferrer">' + u + "</a>") + trail;
    });
    s = mdEmphasis(s);
    return s.replace(/\u0000(\d+)\u0000/g, (m, i) => stash[Number(i)]);
  }
  function mdEmphasis(s) {
    return s
      .replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+?)__/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, "$1<em>$2</em>")
      .replace(/(^|[^_\w])_(?!\s)([^_]+?)_(?!\w)/g, "$1<em>$2</em>");
  }
  function mdSplitRow(line) {
    let t = line.trim();
    if (t.startsWith("|")) t = t.slice(1);
    if (t.endsWith("|") && !t.endsWith("\\|")) t = t.slice(0, -1);
    return t.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
  }
  const MD_NUMERIC = /^[-+\u2212]?\$?[\d,]*\.?\d+(%|R|x)?$/;
  function renderMarkdown(src) {
    const lines = String(src || "").replace(/\u0000/g, "").replace(/\r\n?/g, "\n").split("\n").map(escapeHtml);
    const out = [];
    let para = [];
    let list = null; // stack of {type, indent}
    const flushPara = () => { if (para.length) { out.push("<p>" + mdInline(para.join(" ")) + "</p>"); para = []; } };
    const closeLists = (toIndent) => {
      while (list && list.length && (toIndent === undefined || list[list.length - 1].indent > toIndent)) {
        out.push("</li></" + list.pop().type + ">");
      }
      if (list && !list.length) list = null;
    };
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      // fenced code
      if (/^\s*```/.test(line)) {
        flushPara(); closeLists();
        const code = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) { code.push(lines[i]); i++; }
        out.push("<pre><code>" + code.join("\n") + "</code></pre>");
        continue;
      }
      if (!line.trim()) { flushPara(); closeLists(); continue; }
      const h = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
      if (h) { flushPara(); closeLists(); const n = h[1].length; out.push("<h" + n + ">" + mdInline(h[2]) + "</h" + n + ">"); continue; }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flushPara(); closeLists(); out.push("<hr>"); continue; }
      // table: header row followed by a separator row
      if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
        flushPara(); closeLists();
        const head = mdSplitRow(line);
        const rows = [];
        i += 2;
        while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(mdSplitRow(lines[i])); i++; }
        i--;
        const numericCol = head.map((_, c) => rows.length > 0 && rows.every((r) => !r[c] || MD_NUMERIC.test(r[c].replace(/\s/g, ""))));
        const th = head.map((c, k) => "<th" + (numericCol[k] ? ' class="r"' : "") + ">" + mdInline(c) + "</th>").join("");
        const tb = rows.map((r) => "<tr>" + head.map((_, k) => "<td" + (numericCol[k] ? ' class="r"' : "") + ">" + mdInline(r[k] || "") + "</td>").join("") + "</tr>").join("");
        out.push('<div class="md-table"><table><thead><tr>' + th + "</tr></thead><tbody>" + tb + "</tbody></table></div>");
        continue;
      }
      const bq = /^\s*&gt;\s?(.*)$/.exec(line);
      if (bq) { flushPara(); closeLists(); out.push("<blockquote><p>" + mdInline(bq[1]) + "</p></blockquote>"); continue; }
      const li = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
      if (li) {
        flushPara();
        const indent = li[1].replace(/\t/g, "  ").length;
        const type = /\d/.test(li[2]) ? "ol" : "ul";
        if (!list) list = [];
        const top = list[list.length - 1];
        if (!top || indent > top.indent) {
          out.push("<" + type + "><li>");
          list.push({ type: type, indent: indent });
        } else {
          closeLists(indent);
          const cur = list && list[list.length - 1];
          if (cur && cur.type === type) out.push("</li><li>");
          else { if (cur) out.push("</li></" + list.pop().type + ">"); if (!list) list = []; out.push("<" + type + "><li>"); list.push({ type: type, indent: indent }); }
        }
        out.push(mdInline(li[3]));
        continue;
      }
      if (list && /^\s{2,}\S/.test(line)) { out.push(" " + mdInline(line.trim())); continue; } // lazy continuation
      closeLists();
      para.push(line.trim());
    }
    flushPara();
    closeLists();
    return out.join("\n");
  }

  // ------------------------------------------------------------------------------------------------
  // Journal
  // ------------------------------------------------------------------------------------------------
  async function loadJournal(date) {
    const body = $("#journal-body");
    showSkeleton(body, 8);
    const res = await api("/api/journal" + (date ? "?date=" + encodeURIComponent(date) : ""), { key: "journal" });
    if (res.aborted) return;
    if (!res.ok) { showUnavailable(body, res); updateJournalNav(); return; }
    const d = res.data || {};
    state.journalDate = d.date ? toDay(d.date) : date || null;
    const dates = Array.isArray(d.available_dates) ? d.available_dates.map(toDay).filter(Boolean) : [];
    state.journalDates = Array.from(new Set(dates.concat(state.journalDate ? [state.journalDate] : []))).sort().reverse();
    const sel = $("#jr-date");
    replace(sel, state.journalDates.map((x) => el("option", { value: x, text: fmtDay(x) })));
    if (state.journalDate) sel.value = state.journalDate;
    updateJournalNav();
    if (!d.markdown || !String(d.markdown).trim()) { replace(body, emptyBox("No journal entry for this date.")); return; }
    body.innerHTML = renderMarkdown(d.markdown); // safe: renderMarkdown escapes all HTML first
  }
  function updateJournalNav() {
    const i = state.journalDates.indexOf(state.journalDate);
    $("#jr-prev").disabled = i < 0 || i >= state.journalDates.length - 1;
    $("#jr-next").disabled = i <= 0;
  }
  function initJournalControls() {
    $("#jr-date").addEventListener("change", (ev) => setHash("journal", ev.target.value));
    $("#jr-prev").addEventListener("click", () => { const i = state.journalDates.indexOf(state.journalDate); if (i >= 0 && i < state.journalDates.length - 1) setHash("journal", state.journalDates[i + 1]); });
    $("#jr-next").addEventListener("click", () => { const i = state.journalDates.indexOf(state.journalDate); if (i > 0) setHash("journal", state.journalDates[i - 1]); });
  }

  // ------------------------------------------------------------------------------------------------
  // Replay (playbook backtest over recent history)
  // ------------------------------------------------------------------------------------------------
  const FRACTION_KEYS = new Set(["win_rate", "cagr", "max_dd", "total_return", "cost_drag", "exposure", "avg_exposure", "hit_rate"]);
  const SUMMARY_ORDER = [
    ["total_return", "Total return"], ["cagr", "CAGR"], ["max_dd", "Max drawdown"], ["sharpe", "Sharpe"],
    ["sortino", "Sortino"], ["deflated_sharpe", "Deflated Sharpe"], ["trades", "Trades"], ["win_rate", "Win rate"],
    ["avg_r", "Avg R"], ["avg_win_r", "Avg win"], ["avg_loss_r", "Avg loss"], ["expectancy_r", "Expectancy"],
    ["expectancy", "Expectancy $ / trade"], ["profit_factor", "Profit factor"], ["avg_hold_bars", "Avg hold (days)"],
    ["avg_exposure", "Avg exposure"], ["turnover", "Turnover / yr"], ["cost_drag", "Cost drag / yr"], ["total_costs", "Total costs"],
    ["sessions", "Sessions"], ["years", "Years"], ["n_signals", "Signals"], ["n_orders", "Orders"],
    ["n_entries_skipped", "Entries skipped"], ["start", "Start"], ["end", "End"], ["use_router", "Regime router"],
  ];
  // Summary keys that are bookkeeping, not results (shown elsewhere or not useful on the page).
  const SUMMARY_HIDDEN = new Set(["strategy", "n_obs", "skew", "kurt", "breadth_error", "shadow_recorded", "shadow_resolved", "router_available", "breadth_available"]);
  // research.metrics reports returns, CAGR, drawdown and win rate as fractions (cagr 0.128); the server says so in
  // latest.units. Older files without it: guess from the size of the numbers.
  let replayPctUnits = false;
  function detectPctUnits(latest) {
    if (latest && latest.units) return String(latest.units).toLowerCase() === "pct";
    const summary = (latest && latest.summary) || {};
    return ["cagr", "max_dd", "total_return"].some((k) => Math.abs(toNum(summary[k]) || 0) > 1.5);
  }
  function fmtMetric(key, v) {
    const k = String(key).toLowerCase();
    if (v === null || v === undefined || v === "") return DASH;
    if (typeof v === "boolean") return v ? "On" : "Off";
    if (typeof v === "string" && !isNum(toNum(v))) return /^\d{4}-\d{2}-\d{2}/.test(v) ? fmtShortDay(v) + " " + v.slice(0, 4) : v;
    const n = toNum(v);
    if (n === null) return DASH;
    if (k === "max_dd" || k === "max_drawdown") return fmtPct(-Math.abs(replayPctUnits ? n : n * 100), 2);
    if (k === "win_rate" || k === "hit_rate") return fmtRatioPct(n, 1);
    if (FRACTION_KEYS.has(k)) return fmtPct(replayPctUnits ? n : n * 100, 2, !["cost_drag", "exposure", "avg_exposure"].includes(k));
    if (k.endsWith("_pct")) return fmtPct(n, 2, true);
    if (k === "avg_r" || k.endsWith("_r")) return fmtSigned(n, 2, "R");
    if (k === "profit_factor") return fmtPF(n);
    if (k === "turnover") return fmtNum(n, 1) + "\u00d7";
    if (k === "total_costs") return fmtMoney(n, 0);
    if (k === "expectancy") return fmtSignedMoney(n, 2);
    if (k === "avg_hold_bars" || k === "years") return fmtNum(n, 1);
    if (k.includes("pnl") || k.includes("equity") || k.includes("cash")) return fmtSignedMoney(n, 0);
    if (["trades", "sessions", "n_orders", "n", "pending"].includes(k) || k.startsWith("n_")) return fmtInt(n);
    return Number.isInteger(n) ? fmtInt(n) : fmtNum(n, 2);
  }
  function metricClass(key, v) {
    const k = String(key).toLowerCase();
    const n = toNum(v);
    if (n === null) return "";
    if (k === "max_dd") return n ? "neg" : "";
    if (["total_return", "cagr", "avg_r", "expectancy_r", "expectancy", "total_pnl", "total_r"].includes(k) || k.endsWith("_pct")) return signClass(n);
    return "";
  }
  async function loadReplay() {
    ["#rp-summary", "#rp-runs", "#rp-strategy", "#rp-regime"].forEach((id) => showSkeleton($(id), 4));
    const res = await api("/api/replay", { key: "replay", timeout: SLOW_FETCH_TIMEOUT_MS });
    if (res.aborted) return;
    if (!res.ok) {
      ["#rp-summary", "#rp-runs", "#rp-strategy", "#rp-regime"].forEach((id) => showUnavailable($(id), res));
      chartMessage($("#rp-chart"), "No replay yet. Run `swing replay` on the computer to create one.");
      return;
    }
    const d = res.data || {};
    renderReplayRuns(Array.isArray(d.runs) ? d.runs : []);
    const latest = d.latest || null;
    if (!latest) {
      replace($("#rp-summary"), emptyBox("No replay has been run yet."));
      [$("#rp-strategy"), $("#rp-regime")].forEach((n) => replace(n, emptyBox("Nothing to show yet.")));
      chartMessage($("#rp-chart"), "No replay equity curve yet.");
      return;
    }
    replayPctUnits = detectPctUnits(latest);
    renderReplaySummary(latest.summary || {}, latest.id);
    renderGroupTable($("#rp-strategy"), latest.by_strategy, "strategy");
    renderGroupTable($("#rp-regime"), latest.by_regime, "regime");
    renderReplayChart(Array.isArray(latest.equity_curve) ? latest.equity_curve : []);
  }
  function renderReplaySummary(s, runId) {
    const meta = [];
    if (runId) meta.push(String(runId));
    if (s.start || s.end) meta.push((s.start ? String(s.start).slice(0, 10) : "?") + " \u2192 " + (s.end ? String(s.end).slice(0, 10) : "?"));
    if (Array.isArray(s.strategies)) meta.push(s.strategies.length + " strategies");
    $("#rp-meta").textContent = meta.join(" \u00b7 ");
    const items = [];
    const used = new Set();
    SUMMARY_ORDER.forEach(([k, label]) => {
      if (!(k in s) || k === "start" || k === "end") return;
      used.add(k);
      items.push(el("div", { class: "kv" }, [el("span", { class: "kv__k", text: label }), el("span", { class: "kv__v " + metricClass(k, s[k]), text: fmtMetric(k, s[k]) })]));
    });
    Object.entries(s).forEach(([k, v]) => {
      if (used.has(k) || SUMMARY_HIDDEN.has(k) || k === "start" || k === "end" || v === null || typeof v === "object") return;
      if (typeof v === "string" && v.length > 40) return;
      items.push(el("div", { class: "kv" }, [el("span", { class: "kv__k", text: humanize(k) }), el("span", { class: "kv__v " + metricClass(k, v), text: fmtMetric(k, v) })]));
    });
    const extras = [];
    const dictTags = (obj, nameFn, unit) => Object.entries(obj).map(([k, v]) => el("span", { class: "tag", text: nameFn(k) + " " + fmtInt(v) + (unit || "") }));
    if (s.regime_days && typeof s.regime_days === "object" && Object.keys(s.regime_days).length) {
      extras.push(el("div", { class: "kv", style: "grid-column:1/-1" }, [el("span", { class: "kv__k", text: "Days per regime" }), el("div", null, dictTags(s.regime_days, (k) => (REGIMES[k] && REGIMES[k].name) || humanize(k), " d"))]));
    }
    if (s.skip_reasons && typeof s.skip_reasons === "object" && Object.keys(s.skip_reasons).length) {
      extras.push(el("div", { class: "kv", style: "grid-column:1/-1" }, [el("span", { class: "kv__k", text: "Why entries were skipped" }), el("div", null, dictTags(s.skip_reasons, humanize))]));
    }
    replace($("#rp-summary"), items.length || extras.length ? items.concat(extras) : emptyBox("The replay summary is empty."));
  }
  function renderGroupTable(node, rows, kind) {
    const list = Array.isArray(rows) ? rows.filter((r) => r && typeof r === "object") : [];
    if (!list.length) { replace(node, emptyBox("No trades in this replay.")); return; }
    const keys = Object.keys(list[0]);
    const nameKey = ["group", kind, "name", "strategy", "regime"].find((k) => keys.includes(k)) || keys[0];
    const ORDER = ["trades", "n", "win_rate", "avg_r", "expectancy_r", "profit_factor", "total_r", "total_pnl", "avg_hold_bars", "pending", "n_signals", "n_taken"];
    const rank = (k) => (ORDER.indexOf(k) === -1 ? ORDER.length : ORDER.indexOf(k));
    const cols = keys.filter((k) => k !== nameKey && list.some((r) => r[k] === null || typeof r[k] !== "object")).sort((a, b) => rank(a) - rank(b));
    const label = (k) => ({ trades: "Trades", win_rate: "Win rate", avg_r: "Avg R", expectancy_r: "Expectancy", profit_factor: "PF", total_pnl: "P&L", total_r: "Total R", avg_hold_bars: "Avg hold (d)", n: "n", n_signals: "Signals", n_taken: "Taken", pending: "Pending" })[k] || humanize(k);
    const nameOf = (v) => (kind === "regime" ? (REGIMES[v] && REGIMES[v].name) || humanize(v) : strategyName(v));
    replace(node, el("table", { class: "data" }, [
      el("thead", null, el("tr", null, [el("th", { text: kind === "regime" ? "Regime" : "Strategy" }), ...cols.map((k) => el("th", { class: "r", text: label(k) }))])),
      el("tbody", null, list.map((r) => el("tr", null, [
        el("td", { class: "strat", title: String(r[nameKey] || ""), text: nameOf(r[nameKey]) }),
        ...cols.map((k) => el("td", { class: "r " + metricClass(k, r[k]), text: k === "avg_hold_bars" ? fmtNum(r[k], 1) : fmtMetric(k, r[k]) })),
      ]))),
    ]));
  }
  function renderReplayChart(curve) {
    const box = $("#rp-chart");
    const data = dailySeries(curve, "t", (r) => toNum(r.equity));
    if (!data.length) { chartMessage(box, "No equity curve in this replay."); return; }
    const entry = getChart("replay", box);
    if (!entry) return;
    chartMessage(box, null);
    resetSeries(entry);
    const area = entry.chart.addAreaSeries({
      lineColor: cssVar("--c-account"), topColor: cssVar("--accent-soft"), bottomColor: "rgba(0,0,0,0)", lineWidth: 2,
      priceLineVisible: false, priceFormat: { type: "price", precision: 0, minMove: 1 },
    });
    area.setData(data);
    entry.series = { area: area };
    entry.restyle = () => area.applyOptions({ lineColor: cssVar("--c-account"), topColor: cssVar("--accent-soft") });
    fitSoon(entry);
  }
  function renderReplayRuns(runs) {
    const node = $("#rp-runs");
    if (!runs.length) { replace(node, emptyBox("No replay runs recorded.")); return; }
    const sorted = runs.slice().sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
    replace(node, el("table", { class: "data compact" }, [
      el("thead", null, el("tr", null, [el("th", { text: "Run" }), el("th", { text: "Period" }), el("th", { class: "r", text: "Created" })])),
      el("tbody", null, sorted.map((r, i) => el("tr", null, [
        el("td", null, [el("span", { class: "mono", title: String(r.id || ""), text: shortId(r.id) }), i === 0 ? el("span", { class: "chip chip--info", style: "margin-left:6px", text: "latest" }) : null]),
        el("td", { class: "nowrap", text: (r.start ? String(r.start).slice(0, 10) : "?") + " \u2192 " + (r.end ? String(r.end).slice(0, 10) : "?") }),
        el("td", { class: "r", text: fmtDateTime(r.created_at) }),
      ]))),
    ]));
  }

  // ------------------------------------------------------------------------------------------------
  // Safety & settings: system info and the kill switch (trip only; clearing is a manual action)
  // ------------------------------------------------------------------------------------------------
  async function loadHealth() {
    const node = $("#sys-body");
    const res = await api("/api/health", { key: "health" });
    if (res.aborted) return;
    if (!res.ok) { showUnavailable(node, res); return; }
    const h = res.data || {};
    state.health = h;
    $("#demo-banner").hidden = !h.demo;
    const row = (k, v, mono) => el("div", { class: "kv" }, [el("span", { class: "kv__k", text: k }), el("span", { class: "kv__v" + (mono ? " mono" : ""), text: v === null || v === undefined || v === "" ? DASH : String(v) })]);
    replace(node, [
      row("Version", h.version, true),
      row("Settings file", h.settings_path, true),
      row("Data store", h.store_path, true),
      row("Demo data", h.demo ? "Yes: sample data, not your account" : "No"),
      row("Your time zone", (LOCAL_TZ || "unknown") + (LOCAL_IS_ET ? " (same as market time)" : "")),
    ]);
  }
  function initKillSwitch() {
    const dialog = $("#ks-dialog");
    const input = $("#ks-input");
    const confirmBtn = $("#ks-confirm");
    const dmsg = $("#ks-dialog-msg");
    const open = () => {
      input.value = "";
      confirmBtn.disabled = true;
      dmsg.textContent = "";
      dmsg.className = "form-msg";
      if (typeof dialog.showModal === "function") dialog.showModal(); else dialog.setAttribute("open", "");
      input.focus();
    };
    const close = () => { if (typeof dialog.close === "function") dialog.close(); else dialog.removeAttribute("open"); $("#ks-trip").focus(); };
    $("#ks-trip").addEventListener("click", open);
    $("#ks-cancel").addEventListener("click", close);
    input.addEventListener("input", () => { confirmBtn.disabled = input.value.trim() !== "TRIP"; });
    $("#ks-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (input.value.trim() !== "TRIP") { confirmBtn.disabled = true; return; }
      confirmBtn.disabled = true;
      dmsg.className = "form-msg";
      dmsg.textContent = "Tripping\u2026";
      const res = await api("/api/killswitch/trip", { method: "POST", body: { confirm: "TRIP" } });
      if (!res.ok) {
        dmsg.className = "form-msg is-error";
        dmsg.textContent = "Not tripped: " + res.unavailable + ". On the computer you can run: touch state/KILL";
        confirmBtn.disabled = false;
        return;
      }
      const path = (res.data && res.data.path) || "state/KILL";
      close();
      const msg = $("#ks-msg");
      msg.className = "form-msg is-ok";
      msg.textContent = "Kill switch tripped: " + path + ". Clear it on the computer once the cause is understood and journaled.";
      renderKillSwitch({ tripped: true, path: path });
      loadSummary();
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Tabs + deep links (#tab or #tab/arg)
  // ------------------------------------------------------------------------------------------------
  function parseHash() {
    const raw = decodeURIComponent((location.hash || "").replace(/^#\/?/, ""));
    const [tab, ...rest] = raw.split("/");
    return { tab: TABS.includes(tab) ? tab : "overview", arg: rest.join("/") || null };
  }
  function setHash(tab, arg) {
    const target = "#" + tab + (arg ? "/" + arg : "");
    if (location.hash === target) route(); else location.hash = target;
  }
  function selectTab(name, opts) {
    state.tab = name;
    $$('[role="tab"]').forEach((t) => {
      const on = t.dataset.tab === name;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      if (on && opts && opts.focus) t.focus();
    });
    $$('[role="tabpanel"]').forEach((p) => { p.hidden = p.id !== "panel-" + name; });
    const label = $("#tab-" + name);
    document.title = (name === "overview" ? "" : label.textContent.replace(/\s*\d+$/, "").trim() + " \u00b7 ") + "Swing Engine";
  }
  function route() {
    const { tab, arg } = parseHash();
    selectTab(tab);
    const first = !state.loaded[tab];
    state.loaded[tab] = true;
    switch (tab) {
      case "overview":
        if (first) { loadEquity(); loadRegime(); }
        break;
      case "charts": {
        const sym = cleanSymbol(arg);
        if (sym && sym !== state.chartSymbol) { state.chartSymbol = sym; loadChart(); }
        else if (first) loadChart();
        if (first) loadOrders();
        break;
      }
      case "signals": {
        const date = arg && /^\d{4}-\d{2}-\d{2}$/.test(arg) ? arg : null;
        const cur = state.signals && state.signals.date ? toDay(state.signals.date) : null;
        if (first || (date && date !== cur) || (!date && state.signalsRequested)) { state.signalsRequested = !!date; loadSignals(date); }
        break;
      }
      case "shadow": if (first) loadShadow(); break;
      case "drift": if (first) loadDrift(); break;
      case "alerts": if (first) loadAlerts(); break;
      case "journal": {
        const date = arg && /^\d{4}-\d{2}-\d{2}$/.test(arg) ? arg : null;
        if (first || (date && date !== state.journalDate)) loadJournal(date);
        break;
      }
      case "replay": if (first) loadReplay(); break;
      case "settings": if (first || !state.health) loadHealth(); break;
      default: break;
    }
  }
  function initTabs() {
    const tabs = $$('[role="tab"]');
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => {
        const name = t.dataset.tab;
        if (name === "charts" && state.chartSymbol) setHash("charts", state.chartSymbol);
        else if (name === "signals" && state.signalsRequested && state.signals && state.signals.date) setHash("signals", toDay(state.signals.date));
        else if (name === "journal" && state.journalDate) setHash("journal", state.journalDate);
        else setHash(name);
      });
      t.addEventListener("keydown", (ev) => {
        let j = null;
        if (ev.key === "ArrowRight") j = (i + 1) % tabs.length;
        else if (ev.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
        else if (ev.key === "Home") j = 0;
        else if (ev.key === "End") j = tabs.length - 1;
        if (j === null) return;
        ev.preventDefault();
        tabs[j].focus();
        tabs[j].click();
      });
    });
    window.addEventListener("hashchange", route);
  }

  // ------------------------------------------------------------------------------------------------
  // Refresh loop: fast (30 s) and slow (5 min), paused while the page is hidden
  // ------------------------------------------------------------------------------------------------
  function refreshFast() {
    state.lastFast = Date.now();
    loadSummary();
    loadPositions({ quiet: true });
    if (state.alerts !== null || state.tab === "alerts") loadAlerts({ quiet: true });
  }
  function refreshSlow() {
    state.lastSlow = Date.now();
    if (state.loaded.overview) { loadEquity({ quiet: true }); loadRegime({ quiet: true }); }
    if (state.loaded.charts) { loadChart({ quiet: true }); loadOrders({ quiet: true }); }
  }
  async function refreshAll() {
    const btn = $("#refresh-btn");
    btn.classList.add("spinning");
    btn.disabled = true;
    refreshFast();
    refreshSlow();
    if (state.loaded.signals && state.tab === "signals") loadSignals(state.signals && state.signals.date ? toDay(state.signals.date) : null);
    if (state.loaded.shadow && state.tab === "shadow") loadShadow();
    if (state.loaded.drift && state.tab === "drift") loadDrift();
    if (state.loaded.journal && state.tab === "journal") loadJournal(state.journalDate);
    if (state.loaded.replay && state.tab === "replay") loadReplay();
    if (state.tab === "settings") loadHealth();
    setTimeout(() => { btn.classList.remove("spinning"); btn.disabled = false; }, 700);
  }
  function startTimers() {
    stopTimers();
    state.timers.fast = setInterval(() => { if (!document.hidden) refreshFast(); }, FAST_REFRESH_MS);
    state.timers.slow = setInterval(() => { if (!document.hidden) refreshSlow(); }, SLOW_REFRESH_MS);
  }
  function stopTimers() {
    Object.keys(state.timers).forEach((k) => { if (state.timers[k]) clearInterval(state.timers[k]); state.timers[k] = null; });
  }
  function initVisibility() {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { stopTimers(); return; }
      const now = Date.now();
      if (now - state.lastFast > FAST_REFRESH_MS) refreshFast();
      if (now - state.lastSlow > SLOW_REFRESH_MS) refreshSlow();
      startTimers();
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------------------------------------
  function init() {
    if (!lwcReady()) $("#lib-banner").hidden = false;
    initTheme();
    initPopovers();
    initEquityControls();
    initChartControls();
    initSignalControls();
    initAlertControls();
    initJournalControls();
    initKillSwitch();
    initTabs();
    initVisibility();
    $("#refresh-btn").addEventListener("click", refreshAll);
    loadHealth();
    refreshFast();
    state.lastSlow = Date.now();
    route();
    startTimers();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  // Exposed for debugging in the browser console only (read-only helpers).
  window.__swingDashboard = { state: state, renderMarkdown: renderMarkdown };
})();
