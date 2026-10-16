/* The command-centre dashboard's one script (plan 2026-10-17-plan-1, T01). Plain ES2017, no framework.
   Views never carry JavaScript: they declare data-* attributes (components.py) and this file gives them
   behaviour — theme, hash routing, the per-view refresh, posts and their dialogs, filters, the repo
   picker, tabs, the clamp toggle, the menu button, loading timers and freshness stamps.
   Every word shown comes from the catalogue the shell embeds as #qd-strings. */
(function () {
  "use strict";

  var S = {};
  try { S = JSON.parse(document.getElementById("qd-strings").textContent); } catch (e) { S = {}; }
  function t(key, fields) {
    var s = Object.prototype.hasOwnProperty.call(S, key) ? S[key] : key;
    return s.replace(/\{(\w+)\}/g, function (m, k) {
      return fields && Object.prototype.hasOwnProperty.call(fields, k) ? String(fields[k]) : m;
    });
  }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, value) {
    try { if (value === null) { localStorage.removeItem(key); } else { localStorage.setItem(key, value); } } catch (e) {}
  }
  function loadJSON(key) { try { return JSON.parse(load(key) || "null"); } catch (e) { return null; } }
  function each(root, sel, fn) { Array.prototype.forEach.call(root.querySelectorAll(sel), fn); }

  var main = document.getElementById("view");
  var live = document.getElementById("live");
  function announce(msg) { if (live) { live.textContent = msg; } }

  // ---------------------------------------------------------------- theme: system -> light -> dark
  var THEMES = ["system", "light", "dark"];
  function theme() { var v = load("qd-theme"); return v === "light" || v === "dark" ? v : "system"; }
  function applyTheme(v) {
    if (v === "system") { document.documentElement.removeAttribute("data-theme"); save("qd-theme", null); }
    else { document.documentElement.setAttribute("data-theme", v); save("qd-theme", v); }
    each(document, "[data-theme-toggle]", function (b) { b.textContent = t("shell.theme." + v); });
  }

  // ---------------------------------------------------------------- routing
  var CADENCE = { overview: 20, work: 20, accounts: 20 };
  var known = {};
  each(document, "[data-nav]", function (a) { known[a.getAttribute("data-nav")] = true; });
  var current = { view: main ? main.getAttribute("data-view") || "overview" : "overview", arg: "" };

  function parseHash() {
    var h = (location.hash || "").replace(/^#\/?/, "");
    var parts = h.split("/");
    var view = parts[0] ? decodeURIComponent(parts[0]) : "";
    if (!view) { view = (main && main.getAttribute("data-view")) || "overview"; }
    if (!known[view]) { return null; }
    return { view: view, arg: parts.length > 1 ? decodeURIComponent(parts.slice(1).join("/")) : "" };
  }
  function markNav(view) {
    each(document, "[data-nav]", function (a) {
      if (a.getAttribute("data-nav") === view) {
        a.setAttribute("aria-current", "page");
        document.title = a.textContent + " — " + t("app.title");
      } else { a.removeAttribute("aria-current"); }
    });
  }

  // ---------------------------------------------------------------- view fetch, loading timers, swap
  var seq = 0;
  var navigatingSeq = -1;
  var timers = [];
  var controller = null;
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function template(id) {
    var tpl = document.getElementById(id);
    return tpl ? tpl.content.cloneNode(true) : document.createTextNode("");
  }
  function showState(id) { main.innerHTML = ""; main.appendChild(template(id)); }

  function fetchView(opts) {
    if (!main) { return; }
    var my = ++seq;
    var navigating = opts.navigate === true;
    navigatingSeq = navigating ? my : -1;
    clearTimers();
    if (controller) { try { controller.abort(); } catch (e) {} }
    controller = typeof AbortController === "function" ? new AbortController() : null;
    var ctl = controller;
    if (navigating) {
      timers.push(setTimeout(function () { if (my === seq) { showState("qd-state-loading"); } }, 300));
      timers.push(setTimeout(function () {
        if (my !== seq) { return; }
        var box = main.querySelector('[data-state="loading"]');
        if (box && !box.querySelector("[data-still]")) {
          var p = document.createElement("p"); p.setAttribute("data-still", ""); p.textContent = t("state.still_loading");
          box.appendChild(p);
        }
      }, 3000));
      timers.push(setTimeout(function () {
        if (my !== seq) { return; }
        var box = main.querySelector('[data-state="loading"]');
        if (box && !box.querySelector("[data-retry]")) {
          var b = document.createElement("button");
          b.type = "button"; b.className = "btn"; b.setAttribute("data-kind", "secondary");
          b.setAttribute("data-retry", ""); b.textContent = t("state.retry");
          box.appendChild(b);
        }
      }, 10000));
      timers.push(setTimeout(function () {
        if (my !== seq) { return; }
        if (ctl) { try { ctl.abort(); } catch (e) {} }
        seq++; navigatingSeq = -1; showState("qd-state-error");
      }, 30000));
    }
    var init = { cache: "no-store", headers: { "X-Quota-Dash": "1" } };
    if (ctl) { init.signal = ctl.signal; }
    fetch("/v/" + encodeURIComponent(current.view), init)
      .then(function (r) { return r.ok ? r.text() : Promise.reject(new Error(String(r.status))); })
      .then(function (text) {
        if (my !== seq) { return; }
        clearTimers(); navigatingSeq = -1;
        swap(text, opts.force === true || navigating);
      })
      .catch(function () {
        if (my !== seq) { return; }
        clearTimers(); navigatingSeq = -1;
        if (navigating || !main.firstElementChild) { showState("qd-state-failed"); }
      });
  }

  var restoreFocus = null; // the control the operator acted on, re-focused after the refresh it causes
  function stampOf(root) { var s = root.querySelector("[data-stamp]"); return s ? s.getAttribute("data-stamp") : null; }
  function focusKey(el) {
    if (!el || !main.contains(el)) { return null; }
    if (el.id) { return "#" + el.id; }
    if (el.hasAttribute("data-post")) { return "post:" + el.getAttribute("data-post") + "|" + (el.getAttribute("data-body") || ""); }
    return null;
  }
  function findKey(key) {
    if (!key) { return null; }
    if (key.charAt(0) === "#") { return document.getElementById(key.slice(1)); }
    var hit = null;
    each(main, "[data-post]", function (el) {
      if (!hit && "post:" + el.getAttribute("data-post") + "|" + (el.getAttribute("data-body") || "") === key) { hit = el; }
    });
    return hit;
  }
  function detailsKey(d) { if (d.id) { return "#" + d.id; } var s = d.querySelector("summary"); return "s:" + (s ? s.textContent : ""); }

  function swap(text, force) {
    var tpl = document.createElement("template");
    tpl.innerHTML = text;
    var fresh = tpl.content;
    var ns = stampOf(fresh), cs = stampOf(main);
    if (!force && ns !== null && cs !== null && ns === cs) { return; }
    // carry across: typed text by name, open disclosures, scroll, focus
    var kept = {};
    each(main, "input[name], textarea[name], select[name]", function (f) {
      if (f.type !== "hidden" && f.value !== f.defaultValue) { kept[f.name] = f.value; }
    });
    var open = {};
    each(main, "details[open]", function (d) { open[detailsKey(d)] = true; });
    var regions = {};
    each(main, '[role="region"][aria-labelledby]', function (r) {
      regions[r.getAttribute("aria-labelledby")] = [r.scrollLeft, r.scrollTop];
    });
    var ae = document.activeElement;
    var fk = focusKey(ae) || (!ae || ae === document.body ? restoreFocus : null);
    var y = window.scrollY;
    restoreFocus = null;
    main.innerHTML = "";
    main.appendChild(fresh);
    each(main, "input[name], textarea[name], select[name]", function (f) {
      if (Object.prototype.hasOwnProperty.call(kept, f.name)) { f.value = kept[f.name]; }
    });
    each(main, "details", function (d) { if (open[detailsKey(d)]) { d.open = true; } });
    each(main, '[role="region"][aria-labelledby]', function (r) {
      var s = regions[r.getAttribute("aria-labelledby")]; if (s) { r.scrollLeft = s[0]; r.scrollTop = s[1]; }
    });
    initView();
    window.scrollTo(0, y);
    var back = findKey(fk); if (back) { try { back.focus({ preventScroll: true }); } catch (e) {} }
  }

  // ---------------------------------------------------------------- refresh: the INV-5 skips
  function skipTick() {
    if (document.hidden) { return true; }
    var a = document.activeElement;
    if (a && main.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) { return true; }
    if (document.querySelector("dialog[open]")) { return true; }
    var sel = window.getSelection ? String(window.getSelection()) : "";
    return sel !== "";
  }
  function refresh(force) {
    if (navigatingSeq === seq && navigatingSeq !== -1) { return; } // a view load is in flight
    if (force !== true && skipTick()) { return; }
    fetchView({ force: force === true });
  }
  var tickTimer = null;
  function schedule() {
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
    var root = main && main.querySelector("[data-refresh-s]");
    var s = root ? Number(root.getAttribute("data-refresh-s")) : CADENCE[current.view];
    if (s > 0) { tickTimer = setInterval(function () { refresh(false); }, s * 1000); }
  }
  function route(first) {
    var r = parseHash();
    if (!r) { return; }
    // the first route fetches unless the server already rendered this view into <main>
    var rendered = main.firstElementChild && main.getAttribute("data-view") === r.view;
    var needFetch = first === true ? !rendered : r.view !== current.view || !main.firstElementChild;
    current = r;
    markNav(r.view);
    main.setAttribute("data-view", r.view);
    if (needFetch) { fetchView({ navigate: true }); } else { initView(); }
    schedule();
  }
  window.qdRefresh = refresh;

  // ---------------------------------------------------------------- posts, dialogs, refusals
  function inlineError(anchor, msg) {
    var box = anchor.parentNode && anchor.parentNode.querySelector("[data-inline-error]");
    if (!box) {
      box = document.createElement("p");
      box.className = "inline-error"; box.setAttribute("data-inline-error", ""); box.setAttribute("role", "alert");
      anchor.insertAdjacentElement("afterend", box);
    }
    box.textContent = msg; box.hidden = false;
  }
  function clearInline(anchor) {
    var box = anchor.parentNode && anchor.parentNode.querySelector("[data-inline-error]");
    if (box) { box.textContent = ""; box.hidden = true; }
  }
  function readNumber(spec) {
    // "<key>:<int|float>:<min>:<max>:<nullable|required>:<input id>"
    var p = spec.split(":");
    var key = p[0], kind = p[1], min = p[2] === "" ? -Infinity : Number(p[2]), max = p[3] === "" ? Infinity : Number(p[3]);
    var nullable = p[4] === "nullable", el = document.getElementById(p.slice(5).join(":"));
    var raw = el ? el.value.trim() : "";
    var fields = { min: p[2], max: p[3] };
    var word = kind === "int" ? (nullable ? "act.refuse.whole_or_empty" : "act.refuse.whole")
      : (nullable ? "act.refuse.range_or_empty" : "act.refuse.range");
    if (raw === "") { return nullable ? { key: key, value: null } : { error: t(word, fields) }; }
    var n = Number(raw);
    if (!isFinite(n) || (kind === "int" && !Number.isInteger(n)) || n < min || n > max) { return { error: t(word, fields) }; }
    return { key: key, value: n };
  }
  function collect(btn) {
    var body = {};
    try { body = JSON.parse(btn.getAttribute("data-body") || "{}"); } catch (e) { body = {}; }
    var from = btn.getAttribute("data-text-from");
    if (from) {
      var f = document.getElementById(from), v = f ? f.value.trim() : "";
      if (!v) { return { error: t("act.refuse.text") }; }
      body.text = v;
    }
    var spec = btn.getAttribute("data-input");
    if (spec) {
      var n = readNumber(spec);
      if (n.error) { return n; }
      body[n.key] = n.value;
    }
    return { body: body };
  }
  function post(btn, body) {
    var path = btn.getAttribute("data-post");
    restoreFocus = focusKey(btn);
    btn.disabled = true;
    clearInline(btn);
    return fetch(path, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Quota-Dash": "1" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.text().then(function (txt) {
        var j = null; try { j = JSON.parse(txt); } catch (e) { j = null; }
        if (r.status >= 200 && r.status < 300) {
          var from = btn.getAttribute("data-text-from"), f = from && document.getElementById(from);
          if (f) { f.value = ""; f.defaultValue = ""; }
          announce(t("act.done"));
          btn.disabled = false;
          refresh(true);
          return;
        }
        btn.disabled = false;
        if (r.status !== 409) { restoreFocus = null; btn.focus(); }
        if (r.status === 409) { announce(t("act.changed")); refresh(true); return; }
        var err = (j && (j.error || j.message)) || String(r.status);
        inlineError(btn, t("act.failed", { error: err }));
        announce(t("act.failed", { error: err }));
      });
    }).catch(function () {
      btn.disabled = false; restoreFocus = null; btn.focus();
      inlineError(btn, t("act.unreachable"));
      announce(t("act.unreachable"));
    });
  }
  function openDialog(btn, dlg, body) {
    each(dlg, "[data-value-of]", function (s) {
      var f = document.getElementById(s.getAttribute("data-value-of"));
      var v = f ? f.value.trim() : "";
      s.textContent = v || t("act.clear");
    });
    var err = dlg.querySelector("[data-dialog-error]"); if (err) { err.textContent = ""; err.hidden = true; }
    var note = dlg.querySelector("[data-dialog-note]"); if (note) { note.value = ""; }
    dlg._qd = { invoker: btn, body: body };
    dlg._qdInvoker = btn;
    if (typeof dlg.showModal === "function") { dlg.showModal(); } else { dlg.setAttribute("open", ""); }
  }
  function returnFocus(dlg) {
    var inv = dlg._qdInvoker;
    if (inv && document.contains(inv) && !inv.disabled) { inv.focus(); }
  }
  // focus goes back to the invoker synchronously: the close event is queued, and a late focus()
  // from it would steal a field the operator has already moved to
  function closeDialog(dlg) { if (dlg.open) { dlg.close(); returnFocus(dlg); } }
  function confirmDialog(dlg) {
    var st = dlg._qd; if (!st) { closeDialog(dlg); return; }
    var btn = st.invoker, body = st.body, mode = btn.getAttribute("data-note");
    if (mode === "optional" || mode === "required") {
      var note = dlg.querySelector("[data-dialog-note]"), v = note ? note.value.trim() : "";
      if (mode === "required" && !v) {
        var err = dlg.querySelector("[data-dialog-error]");
        if (err) { err.textContent = t("act.refuse.note"); err.hidden = false; }
        if (note) { note.focus(); }
        return;
      }
      if (v) {
        body.text = v;
        if (/\/agent-pause$/.test(btn.getAttribute("data-post") || "")) { body.why = v; }
      }
    }
    dlg._qd = null;
    closeDialog(dlg);
    post(btn, body);
  }
  function act(btn) {
    var c = collect(btn);
    if (c.error) { inlineError(btn, c.error); announce(c.error); return; }
    clearInline(btn);
    var dlgId = btn.getAttribute("data-confirm");
    if (dlgId) {
      var dlg = document.getElementById(dlgId);
      if (dlg) { openDialog(btn, dlg, c.body); return; }
    }
    post(btn, c.body);
  }

  // ---------------------------------------------------------------- filters
  function filterControls(g) {
    var out = [];
    each(g, "[data-filter]", function (el) { if (el.closest("[data-filter-group]") === g) { out.push(el); } });
    return out;
  }
  function applyFilters(g) {
    var state = g._qdFilter || {};
    var names = {};
    filterControls(g).forEach(function (el) { names[el.getAttribute("data-filter").split(":")[0]] = true; });
    var targets = [];
    Object.keys(names).forEach(function (n) {
      if (!/^[a-z0-9-]+$/.test(n)) { return; } // the component's own data-key alphabet
      each(g, "[data-f-" + n + "]", function (el) { if (targets.indexOf(el) < 0) { targets.push(el); } });
    });
    targets.forEach(function (el) {
      var show = true;
      Object.keys(state).forEach(function (n) {
        var f = state[n]; if (!f || f.v === "" || !el.hasAttribute("data-f-" + n)) { return; }
        var have = el.getAttribute("data-f-" + n) || "";
        var ok = f.mode === "token" ? (" " + have + " ").indexOf(" " + f.v + " ") >= 0
          : have.toLowerCase().indexOf(f.v.toLowerCase()) >= 0;
        if (!ok) { show = false; }
      });
      el.hidden = !show;
    });
    filterControls(g).forEach(function (el) {
      var spec = el.getAttribute("data-filter"), i = spec.indexOf(":");
      if (i >= 0) {
        var f = state[spec.slice(0, i)];
        el.setAttribute("aria-pressed", f && f.chip && f.v === spec.slice(i + 1) ? "true" : "false");
      }
    });
  }
  function initFilters() {
    each(main, "[data-filter-group]", function (g) {
      var name = g.getAttribute("data-filter-group");
      var state = loadJSON("qd-filter:" + name) || {};
      var controls = filterControls(g);
      Object.keys(state).forEach(function (n) {
        var f = state[n]; if (!f || !f.chip) { return; }
        var there = controls.some(function (el) { return el.getAttribute("data-filter") === n + ":" + f.v; });
        if (!there) { delete state[n]; }
      });
      g._qdFilter = state;
      controls.forEach(function (el) {
        var spec = el.getAttribute("data-filter");
        if (spec.indexOf(":") < 0 && /^(INPUT|TEXTAREA)$/.test(el.tagName)) {
          var f = state[spec]; el.value = f && !f.chip ? f.v : "";
        }
      });
      applyFilters(g);
    });
  }
  function filterInput(el) {
    var g = el.closest("[data-filter-group]"); if (!g) { return; }
    var n = el.getAttribute("data-filter");
    var state = g._qdFilter || (g._qdFilter = {});
    state[n] = { v: el.value.trim(), mode: el.getAttribute("data-filter-mode") === "token" ? "token" : "substr", chip: false };
    save("qd-filter:" + g.getAttribute("data-filter-group"), JSON.stringify(state));
    applyFilters(g);
  }
  function filterChip(el) {
    var g = el.closest("[data-filter-group]"); if (!g) { return; }
    var spec = el.getAttribute("data-filter"), i = spec.indexOf(":"), n = spec.slice(0, i), v = spec.slice(i + 1);
    var state = g._qdFilter || (g._qdFilter = {});
    var on = state[n] && state[n].chip && state[n].v === v;
    if (on) { delete state[n]; } else { state[n] = { v: v, mode: "token", chip: true }; }
    filterControls(g).forEach(function (f) { if (f.getAttribute("data-filter") === n && "value" in f) { f.value = ""; } });
    save("qd-filter:" + g.getAttribute("data-filter-group"), JSON.stringify(state));
    applyFilters(g);
  }

  // ---------------------------------------------------------------- pick group (/#<view>/<pane>)
  function initPick() {
    each(main, "[data-pick-group]", function (g) {
      var name = g.getAttribute("data-pick-group");
      var panes = [];
      each(g, "[data-pick]", function (p) { if (p.closest("[data-pick-group]") === g) { panes.push(p); } });
      if (!panes.length) { return; }
      var has = function (v) { return panes.some(function (p) { return p.getAttribute("data-pick") === v; }); };
      var want = current.arg;
      if (!want || !has(want)) { want = load("qd-pick:" + name); }
      if (!want || !has(want)) { want = panes[0].getAttribute("data-pick"); }
      panes.forEach(function (p) { p.hidden = p.getAttribute("data-pick") !== want; });
      each(g, "[data-pick-to]", function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-pick-to") === want ? "true" : "false");
      });
      save("qd-pick:" + name, want);
    });
  }

  // ---------------------------------------------------------------- tabs (APG, automatic activation)
  var chosenTabs = {};
  function tabsOf(tab) { var list = tab.closest('[role="tablist"]'); return list ? Array.prototype.slice.call(list.querySelectorAll('[role="tab"]')) : []; }
  function selectTab(tab, focus) {
    tabsOf(tab).forEach(function (x) {
      var sel = x === tab;
      x.setAttribute("aria-selected", sel ? "true" : "false");
      x.setAttribute("tabindex", sel ? "0" : "-1");
      var panel = document.getElementById(x.getAttribute("aria-controls"));
      if (panel) { panel.hidden = !sel; }
    });
    var all = tabsOf(tab); if (all.length) { chosenTabs[all[0].id] = tab.id; }
    if (focus) { tab.focus(); }
  }
  function initTabs() {
    each(main, '[role="tablist"]', function (list) {
      var first = list.querySelector('[role="tab"]');
      var want = first && chosenTabs[first.id] && document.getElementById(chosenTabs[first.id]);
      if (want && list.contains(want)) { selectTab(want, false); }
    });
  }

  // ---------------------------------------------------------------- clamp, freshness
  function initClamps() {
    each(main, "[data-clamp]", function (c) {
      var text = c.querySelector(".clamp-text"), btn = c.querySelector("[data-clamp-toggle]");
      if (!text || !btn || c.hasAttribute("data-expanded")) { return; }
      btn.hidden = !(text.scrollHeight > text.clientHeight + 1);
    });
  }
  function toggleClamp(btn) {
    var c = btn.closest("[data-clamp]"); if (!c) { return; }
    var open = !c.hasAttribute("data-expanded");
    if (open) { c.setAttribute("data-expanded", ""); } else { c.removeAttribute("data-expanded"); }
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.textContent = t(open ? "clamp.less" : "clamp.more");
  }
  function ago(sec) {
    if (sec < 60) { return t("fresh.ago_s", { n: Math.max(0, Math.floor(sec)) }); }
    if (sec < 3600) { return t("fresh.ago_min", { n: Math.floor(sec / 60) }); }
    return t("fresh.ago_h", { n: Math.floor(sec / 3600) });
  }
  function tickFreshness() {
    var now = Date.now() / 1000, wentStale = false;
    each(document, "time[data-ts]", function (el) {
      var ts = Number(el.getAttribute("data-ts")), cad = Number(el.getAttribute("data-cadence") || "0");
      if (!isFinite(ts)) { return; }
      var age = now - ts, text = ago(age);
      if (cad > 0 && age > 2 * cad) {
        if (!el.hasAttribute("data-stale")) { wentStale = true; el.setAttribute("data-stale", ""); }
        el.textContent = t("fresh.stale", { age: text });
      } else { el.removeAttribute("data-stale"); el.textContent = text; }
    });
    if (wentStale) { announce(t("fresh.went_stale")); }
  }

  function initView() { initFilters(); initPick(); initTabs(); initClamps(); tickFreshness(); }

  // ---------------------------------------------------------------- menu
  function menuButton() { return document.querySelector("[data-menu]"); }
  function setMenu(open) {
    var b = menuButton(); if (!b) { return; }
    var nav = document.getElementById(b.getAttribute("aria-controls"));
    b.setAttribute("aria-expanded", open ? "true" : "false");
    if (nav) { if (open) { nav.setAttribute("data-open", ""); } else { nav.removeAttribute("data-open"); } }
  }

  // ---------------------------------------------------------------- one set of delegated listeners
  document.addEventListener("click", function (ev) {
    var el = ev.target && ev.target.closest ? ev.target : null; if (!el) { return; }
    var hit;
    if ((hit = el.closest("[data-theme-toggle]"))) {
      applyTheme(THEMES[(THEMES.indexOf(theme()) + 1) % THEMES.length]); return;
    }
    if ((hit = el.closest("[data-menu]"))) { setMenu(hit.getAttribute("aria-expanded") !== "true"); return; }
    if ((hit = el.closest(".skip-link"))) { ev.preventDefault(); if (main) { main.focus(); } return; }
    if ((hit = el.closest("[data-nav]"))) { setMenu(false); return; }
    if ((hit = el.closest("[data-dialog-cancel]"))) { closeDialog(hit.closest("dialog")); return; }
    if ((hit = el.closest("[data-dialog-confirm]"))) { confirmDialog(hit.closest("dialog")); return; }
    if ((hit = el.closest("[data-retry], [data-reload]"))) { fetchView({ navigate: true }); return; }
    if ((hit = el.closest("[data-clamp-toggle]"))) { toggleClamp(hit); return; }
    if ((hit = el.closest('[role="tab"]'))) { selectTab(hit, true); return; }
    if ((hit = el.closest("[data-pick-to]"))) {
      location.hash = "#" + encodeURIComponent(current.view) + "/" + encodeURIComponent(hit.getAttribute("data-pick-to"));
      return;
    }
    if ((hit = el.closest("button[data-filter]"))) { filterChip(hit); return; }
    if ((hit = el.closest("[data-post]"))) { if (!hit.disabled) { act(hit); } return; }
  });
  document.addEventListener("input", function (ev) {
    var el = ev.target;
    if (el && el.matches && el.matches("input[data-filter], textarea[data-filter]")) { filterInput(el); }
  });
  document.addEventListener("keydown", function (ev) {
    var el = ev.target;
    if (ev.key === "Escape") {
      var b = menuButton();
      if (b && b.getAttribute("aria-expanded") === "true") { setMenu(false); b.focus(); return; }
    }
    if (el && el.getAttribute && el.getAttribute("role") === "tab") {
      var all = tabsOf(el), i = all.indexOf(el), j = -1;
      if (ev.key === "ArrowRight") { j = (i + 1) % all.length; }
      else if (ev.key === "ArrowLeft") { j = (i - 1 + all.length) % all.length; }
      else if (ev.key === "Home") { j = 0; }
      else if (ev.key === "End") { j = all.length - 1; }
      if (j >= 0) { ev.preventDefault(); selectTab(all[j], true); }
      return;
    }
    if (ev.key === "Enter" && !ev.shiftKey && el && el.id && /^(INPUT|TEXTAREA)$/.test(el.tagName)) {
      var target = null;
      each(document, "[data-text-from]", function (b) { if (!target && b.getAttribute("data-text-from") === el.id) { target = b; } });
      if (target) { ev.preventDefault(); if (!target.disabled) { act(target); } }
    }
  });
  // a dialog closed any way (Escape, cancel, confirm) returns focus to the button that opened it
  document.addEventListener("close", function (ev) {
    var dlg = ev.target;
    if (!dlg || dlg.tagName !== "DIALOG") { return; }
    var ae = document.activeElement;
    if (!ae || ae === document.body || dlg.contains(ae)) { returnFocus(dlg); } // Escape: the native close
    dlg._qd = null; dlg._qdInvoker = null;
  }, true);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { tickFreshness(); } });
  window.addEventListener("hashchange", function () { route(false); });

  // ---------------------------------------------------------------- start
  applyTheme(theme());
  setInterval(tickFreshness, 5000);
  if (main) { route(true); }
})();
