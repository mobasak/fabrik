/* The command-centre dashboard's one script (plan 2026-10-17-plan-1, T01). Plain ES2017, no framework.
   Views never carry JavaScript: they declare data-* attributes (components.py) and this file gives them
   behaviour — theme, hash routing, the per-view refresh, posts and their dialogs, filters, the repo
   picker, tabs, the clamp toggle, the menu button, loading timers and freshness stamps.
   Every word shown comes from the catalogue the shell embeds as #qd-strings. */
(function () {
  "use strict";

  var has = function (o, k) { return Object.prototype.hasOwnProperty.call(o, k); };
  var S = null;
  try { S = JSON.parse(document.getElementById("qd-strings").textContent); } catch (e) { S = null; }
  if (!S || typeof S !== "object") {
    console.error("qd: the #qd-strings catalogue is missing or unreadable; showing fallback words");
    S = {};
  }
  function fallbackWord(key) {
    // the key's last segment as a word ("act.refuse.text" -> "Text"), never the raw key
    var last = String(key).split(".").pop().replace(/_/g, " ");
    return last.charAt(0).toUpperCase() + last.slice(1);
  }
  function t(key, fields) {
    var s = has(S, key) && typeof S[key] === "string" ? S[key] : fallbackWord(key);
    return s.replace(/\{(\w+)\}/g, function (m, k) {
      return fields && has(fields, k) ? String(fields[k]) : m;
    });
  }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, value) {
    try { if (value === null) { localStorage.removeItem(key); } else { localStorage.setItem(key, value); } } catch (e) {}
  }
  function loadJSON(key) { try { return JSON.parse(load(key) || "null"); } catch (e) { return null; } }
  function plainObject(o) { return !!o && typeof o === "object" && !Array.isArray(o); }
  function each(root, sel, fn) { Array.prototype.forEach.call(root.querySelectorAll(sel), fn); }
  function decode(s) { try { return decodeURIComponent(s); } catch (e) { return null; } }

  var main = document.getElementById("view");
  var live = document.getElementById("live");
  function announce(msg) { if (live) { live.textContent = msg; } }

  // ---------------------------------------------------------------- theme: system -> light -> dark
  var THEMES = ["system", "light", "dark"];
  function theme() { var v = load("qd-theme"); return v === "light" || v === "dark" ? v : "system"; }
  function labelTheme(v) { each(document, "[data-theme-toggle]", function (b) { b.textContent = t("shell.theme." + v); }); }
  function applyTheme(v) {
    if (v === "system") { document.documentElement.removeAttribute("data-theme"); save("qd-theme", null); }
    else { document.documentElement.setAttribute("data-theme", v); save("qd-theme", v); }
    labelTheme(v);
  }

  // ---------------------------------------------------------------- routing
  var CADENCE = { overview: 20, work: 20, accounts: 20 };
  var MIN_REFRESH_S = 5;
  var known = {};
  each(document, "[data-nav]", function (a) { known[a.getAttribute("data-nav")] = true; });
  var defaultView = (main && main.getAttribute("data-view")) || "overview";
  var current = { view: defaultView, arg: "" };

  function parseHash() {
    var h = (location.hash || "").replace(/^#\/?/, "");
    var parts = h.split("/");
    var view = parts[0] ? decode(parts[0]) : "";
    var arg = parts.length > 1 ? decode(parts.slice(1).join("/")) : "";
    if (view === null || arg === null) { return { view: defaultView, arg: "" }; } // malformed: the default
    if (!view) { view = defaultView; }
    if (!has(known, view)) { return null; } // own names only: "#constructor" is no view
    return { view: view, arg: arg };
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
  var loading = null; // {seq, force, navigate} of the view fetch in flight
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
    // a new load replaces the one in flight, and never loses its force flag
    var force = opts.force === true || (loading !== null && loading.force);
    var navigating = opts.navigate === true || (loading !== null && loading.navigate);
    var my = ++seq;
    clearTimers();
    if (controller) { try { controller.abort(); } catch (e) {} }
    controller = typeof AbortController === "function" ? new AbortController() : null;
    var ctl = controller;
    loading = { seq: my, force: force, navigate: navigating };
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
        seq++; loading = null; showState("qd-state-error"); schedule();
      }, 30000));
    }
    var init = { cache: "no-store", headers: { "X-Quota-Dash": "1" } };
    if (ctl) { init.signal = ctl.signal; }
    fetch("/v/" + encodeURIComponent(current.view), init)
      .then(function (r) { return r.ok ? r.text() : Promise.reject(new Error(String(r.status))); })
      .then(function (text) {
        if (my !== seq) { return; }
        clearTimers(); loading = null;
        if (document.querySelector("dialog[open]")) {
          // the operator opened a dialog while this fetch was out: never swap under it (INV-5) —
          // drop the response and refresh, forced, once the dialog closes
          pendingForce = true; schedule(); return;
        }
        try {
          swap(text, force || navigating);
          var anchor = landAt ? document.getElementById(landAt) : null;
          landAt = null;
          if (anchor && main.contains(anchor)) { anchor.scrollIntoView(); }
        } catch (e) {
          console.error("qd: the view could not be shown", e);
          showState("qd-state-broken");
        }
        schedule();
      }, function () {
        if (my !== seq) { return; }
        clearTimers(); loading = null;
        if (navigating || !main.firstElementChild) { showState("qd-state-failed"); }
        schedule();
      });
  }

  var restoreFocus = null; // the control the operator acted on, re-focused after the refresh it causes
  function stampOf(root) { var s = root.querySelector("[data-stamp]"); return s ? s.getAttribute("data-stamp") : null; }
  function postKey(el) { return "post:" + el.getAttribute("data-post") + "|" + (el.getAttribute("data-body") || ""); }
  function fieldKey(f) { return f.id ? "#" + f.id : (f.name ? "n:" + f.name : null); }
  function focusKey(el) {
    if (!el || !main.contains(el)) { return null; }
    if (el.id) { return "#" + el.id; }
    if (el.hasAttribute("data-post")) { return postKey(el); }
    if (el.name && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) { return "n:" + el.name; }
    return null;
  }
  function findKey(key) {
    if (!key) { return null; }
    if (key.charAt(0) === "#") { return document.getElementById(key.slice(1)); }
    var hit = null;
    if (key.indexOf("n:") === 0) {
      each(main, "input[name], textarea[name], select[name]", function (f) { if (!hit && !f.id && "n:" + f.name === key) { hit = f; } });
      return hit;
    }
    each(main, "[data-post]", function (el) { if (!hit && postKey(el) === key) { hit = el; } });
    return hit;
  }
  function summaryText(d) {
    // the count app.js writes into [data-filter-count] is not part of a section's identity
    var s = d.querySelector("summary"); if (!s) { return ""; }
    var c = s.cloneNode(true);
    each(c, "[data-filter-count]", function (x) { x.parentNode.removeChild(x); });
    return c.textContent;
  }
  function detailsKey(d) { return d.id ? "#" + d.id : "s:" + summaryText(d); }
  // a field's value as the markup ships it (a SELECT has no defaultValue: its default is the defaultSelected option)
  function fieldDefault(f) {
    if (f.tagName !== "SELECT") { return f.defaultValue; }
    var d = null;
    Array.prototype.forEach.call(f.options, function (o) { if (d === null && o.defaultSelected) { d = o.value; } });
    return d !== null ? d : (f.options.length && !f.multiple ? f.options[0].value : "");
  }
  function clampKey(c) { if (c.id) { return "#" + c.id; } var p = c.querySelector(".clamp-text"); return "t:" + (p ? p.textContent : ""); }

  function swap(text, force) {
    var tpl = document.createElement("template");
    tpl.innerHTML = text;
    var fresh = tpl.content;
    var ns = stampOf(fresh), cs = stampOf(main);
    if (!force && ns !== null && cs !== null && ns === cs) { return; }
    // carry across: typed text (by id, else by name), open disclosures and clamps, scroll, focus
    var kept = {};
    each(main, "input, textarea, select", function (f) {
      var k = fieldKey(f);
      if (k && f.type !== "hidden" && f.value !== fieldDefault(f)) { kept[k] = f.value; }
    });
    var open = {};
    each(main, "details[open]", function (d) { open[detailsKey(d)] = true; });
    var expanded = {};
    each(main, "[data-clamp][data-expanded]", function (c) { expanded[clampKey(c)] = true; });
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
    each(main, "input, textarea, select", function (f) {
      var k = fieldKey(f);
      if (k && has(kept, k)) { f.value = kept[k]; }
    });
    each(main, "details", function (d) { if (open[detailsKey(d)]) { d.open = true; } });
    each(main, "[data-clamp]", function (c) { if (expanded[clampKey(c)]) { setClamp(c, true); } });
    each(main, '[role="region"][aria-labelledby]', function (r) {
      var s = regions[r.getAttribute("aria-labelledby")]; if (s) { r.scrollLeft = s[0]; r.scrollTop = s[1]; }
    });
    // a post still in flight keeps its control disabled in the new markup
    each(main, "[data-post]", function (el) { if (has(inflight, postKey(el))) { el.disabled = true; } });
    initView();
    // focus first (it may scroll its element into view), THEN put the page back where the operator had it
    var back = findKey(fk); if (back) { try { back.focus(); } catch (e) {} }
    window.scrollTo(0, y);
  }

  // ---------------------------------------------------------------- refresh: the INV-5 skips
  var inflight = {}; // postKey -> true while that post is on the wire
  var POST_TIMEOUT_MS = 60000; // a post the board never answers is aborted, never left holding the view
  var pendingForce = false; // a forced refresh deferred while a dialog is open
  function skipTick() {
    if (document.hidden) { return true; }
    // a post in flight holds the refresh only while its control is in this view
    if (Object.keys(inflight).some(function (k) { var el = findKey(k); return !!el && main.contains(el); })) { return true; }
    var a = document.activeElement;
    if (a && main.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) { return true; }
    if (document.querySelector("dialog[open]")) { return true; }
    var sel = window.getSelection ? String(window.getSelection()) : "";
    return sel !== "";
  }
  function refresh(force) {
    if (force === true) {
      // the refresh after the operator's own write passes every skip but an open dialog (INV-5)
      if (document.querySelector("dialog[open]")) { pendingForce = true; return; }
      fetchView({ force: true });
      return;
    }
    if (loading !== null) { return; } // a load is in flight: the tick never replaces it
    if (skipTick()) { return; }
    fetchView({ force: false });
  }
  var tickTimer = null, tickPeriod = 0;
  function schedule() {
    // the period comes from the content now in <main>, else the view's own cadence
    var root = main && main.querySelector("[data-refresh-s]");
    var s = root ? Number(root.getAttribute("data-refresh-s")) : NaN;
    if (!isFinite(s) || s < MIN_REFRESH_S) { s = CADENCE[current.view] || 0; }
    if (s === tickPeriod && tickTimer) { return; }
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
    tickPeriod = s;
    if (s > 0) { tickTimer = setInterval(function () { refresh(false); }, s * 1000); }
  }
  function stopTicks() { if (tickTimer) { clearInterval(tickTimer); tickTimer = null; } tickPeriod = 0; }
  var landAt = null; // an in-view anchor a reload named (the Overview's summary links: #ov-…)
  function route(first) {
    var r = parseHash();
    if (!r) {
      // a hash naming no view is an anchor inside one: a click on it is the browser's own scroll,
      // but a LOAD on it must still open the default view (and refresh it), then land on the anchor
      if (first !== true) { return; }
      landAt = (location.hash || "").replace(/^#/, "");
      r = { view: defaultView, arg: "" };
    }
    // the first route fetches unless the server already rendered this view into <main>
    var rendered = main.firstElementChild && main.getAttribute("data-view") === r.view;
    var needFetch = first === true ? !rendered : r.view !== current.view || !main.firstElementChild;
    current = r;
    markNav(r.view);
    main.setAttribute("data-view", r.view);
    if (needFetch) { stopTicks(); fetchView({ navigate: true }); } else { initView(); schedule(); }
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
  function refuse(btn, msg) { inlineError(btn, msg); announce(msg); }
  var INT = /^-?\d+$/, DEC = /^-?(\d+\.?\d*|\.\d+)$/; // every spelling a number input yields
  function readNumber(spec) {
    // "<key>:<int|float>:<min>:<max>:<nullable|required>:<input id>"
    var p = spec.split(":");
    var key = p[0], kind = p[1], min = p[2] === "" ? -Infinity : Number(p[2]), max = p[3] === "" ? Infinity : Number(p[3]);
    var nullable = p[4] === "nullable", el = document.getElementById(p.slice(5).join(":"));
    if (!el || !("value" in el)) { return { error: t("act.refuse.no_field") }; }
    var raw = el.value.trim();
    var fields = { min: p[2], max: p[3] };
    var word = kind === "int" ? (nullable ? "act.refuse.whole_or_empty" : "act.refuse.whole")
      : (nullable ? "act.refuse.range_or_empty" : "act.refuse.range");
    // typed text the browser could not read as a number reads as "": never post it as a clear
    if (el.validity && el.validity.badInput) { return { error: t(word, fields) }; }
    if (raw === "") { return nullable ? { key: key, value: null } : { error: t(word, fields) }; }
    if (!(kind === "int" ? INT : DEC).test(raw)) { return { error: t(word, fields) }; }
    var n = Number(raw);
    if (!isFinite(n) || n < min || n > max) { return { error: t(word, fields) }; }
    return { key: key, value: n };
  }
  function collect(btn) {
    var body = {};
    try { body = JSON.parse(btn.getAttribute("data-body") || "{}"); } catch (e) { body = {}; }
    if (!plainObject(body)) { body = {}; }
    var from = btn.getAttribute("data-text-from");
    if (from) {
      var f = document.getElementById(from);
      if (!f || !("value" in f)) { return { error: t("act.refuse.no_field") }; }
      var v = f.value.trim();
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
  function setBusy(key, busy) {
    if (busy) { inflight[key] = true; } else { delete inflight[key]; }
    each(document, "[data-post]", function (el) { if (postKey(el) === key) { el.disabled = busy; } });
  }
  function post(btn, body) {
    var path = btn.getAttribute("data-post") || "", u = null;
    // resolve as the browser will: "/\\host" and "//host" leave the origin, so the resolved origin decides
    try { u = new URL(path, location.href); } catch (e) { u = null; }
    if (path.charAt(0) !== "/" || !u || u.origin !== location.origin) { refuse(btn, t("act.refuse.path")); return null; }
    var key = postKey(btn);
    if (has(inflight, key)) { return null; }
    restoreFocus = focusKey(btn);
    setBusy(key, true);
    clearInline(btn);
    function live_(b) { return document.contains(b) ? b : findKey(key) || b; } // the control after any swap
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, POST_TIMEOUT_MS) : null;
    var init = {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Quota-Dash": "1" },
      body: JSON.stringify(body)
    };
    if (ctl) { init.signal = ctl.signal; }
    return fetch(u.pathname + u.search, init).then(function (r) {
      clearTimeout(timer);
      return r.text().then(function (txt) { return { r: r, txt: txt }; }, function () { return { r: r, txt: "" }; });
    }, function () {
      // the request never reached the board, its answer never came back, or it timed out
      clearTimeout(timer);
      setBusy(key, false);
      var b = live_(btn); restoreFocus = null; b.focus();
      refuse(b, t("act.unreachable"));
      return null;
    }).then(function (res) {
      if (!res) { return; }
      var r = res.r, j = null;
      try { j = JSON.parse(res.txt); } catch (e) { j = null; }
      setBusy(key, false);
      var b = live_(btn);
      if (r.status >= 200 && r.status < 300) {
        var from = b.getAttribute("data-text-from"), f = from && document.getElementById(from);
        if (f) { f.value = ""; f.defaultValue = ""; }
        announce(t("act.done"));
        refresh(true);
        return;
      }
      // "diverged": the board's checkout and the repo's main disagree about the item — a reload cannot
      // cure it, so it is said inline and the card stays; any other 409 means the item moved: re-fetch
      if (r.status === 409 && j && j.error === "diverged") { restoreFocus = null; b.focus(); refuse(b, t("act.diverged")); return; }
      if (r.status === 409) { announce(t("act.changed")); refresh(true); return; }
      restoreFocus = null; b.focus();
      var err = (j && (j.error || j.message)) || String(r.status);
      refuse(b, t("act.failed", { error: err }));
    }).catch(function (e) {
      // a fault in this script after the answer arrived: the write may have landed, so say nothing false
      console.error("qd: after the post", e);
    });
  }
  function openDialog(btn, dlg, body) {
    each(dlg, "[data-value-of]", function (s) {
      var f = document.getElementById(s.getAttribute("data-value-of"));
      var v = f && "value" in f ? f.value.trim() : "";
      s.textContent = v || t("act.clear");
    });
    var err = dlg.querySelector("[data-dialog-error]"); if (err) { err.textContent = ""; err.hidden = true; }
    var note = dlg.querySelector("[data-dialog-note]"); if (note) { note.value = ""; }
    dlg._qd = { invoker: btn, body: body };
    dlg._qdInvoker = btn;
    dlg.showModal();
  }
  function returnFocus(dlg) {
    var inv = dlg._qdInvoker;
    if (inv && document.contains(inv) && !inv.disabled) { inv.focus(); }
  }
  // focus goes back to the invoker synchronously: the close event is queued, and a late focus()
  // from it would steal a field the operator has already moved to
  function closeDialog(dlg) { if (dlg && dlg.open) { dlg.close(); returnFocus(dlg); } }
  function confirmDialog(dlg) {
    if (!dlg) { return; } // a confirm button outside any dialog confirms nothing
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
    if (btn.disabled || has(inflight, postKey(btn))) { return; }
    var c = collect(btn);
    if (c.error) { refuse(btn, c.error); return; }
    clearInline(btn);
    var dlgId = btn.getAttribute("data-confirm");
    var note = btn.getAttribute("data-note");
    if (dlgId !== null) {
      var dlg = dlgId ? document.getElementById(dlgId) : null;
      if (!dlg || dlg.tagName !== "DIALOG" || typeof dlg.showModal !== "function") {
        refuse(btn, t("act.refuse.confirm")); return; // fail closed: no dialog, no post
      }
      if (note === "required" && !dlg.querySelector("[data-dialog-note]")) { refuse(btn, t("act.refuse.no_reason")); return; }
      openDialog(btn, dlg, c.body);
      return;
    }
    if (note === "required") { refuse(btn, t("act.refuse.no_reason")); return; } // a reason needs its dialog
    post(btn, c.body);
  }

  // ---------------------------------------------------------------- filters
  function filterControls(g) {
    var out = [];
    each(g, "[data-filter]", function (el) { if (el.closest("[data-filter-group]") === g) { out.push(el); } });
    return out;
  }
  function tokens(s) { return s.split(/\s+/).filter(function (x) { return x !== ""; }); }
  function matches(f, have) {
    if (f.mode === "token") {
      var pad = " " + have + " ";
      return tokens(f.v).every(function (tok) { return pad.indexOf(" " + tok + " ") >= 0; });
    }
    return have.toLowerCase().indexOf(f.v.toLowerCase()) >= 0;
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
        if (!matches(f, el.getAttribute("data-f-" + n) || "")) { show = false; }
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
    applySections(g);
  }
  // The groups a filter opens. The ids it opened live in qd-filter-open:<group> (a list), NEVER inside
  // qd-filter:<group>, whose every key validFilterState reads as a field filter. With a filter on, a
  // [data-filter-section] holding a shown [data-filter-item] opens (an already-open one is the
  // operator's and is left alone), one holding none is hidden; with the filter off, or once a group
  // stops matching, every recorded group closes and the hidden ones return.
  var openedMem = {}; // group -> the opened ids, kept beside storage so a blocked store cannot lose the record
  function saveOpened(g) {
    var name = g.getAttribute("data-filter-group");
    openedMem[name] = (g._qdOpened || []).slice();
    save("qd-filter-open:" + name, JSON.stringify(g._qdOpened || []));
  }
  function applySections(g) {
    var state = g._qdFilter || {};
    // a filter acts only through controls: a render of the group with none filters nothing
    var active = filterControls(g).length > 0 && Object.keys(state).some(function (n) { return state[n] && state[n].v !== ""; });
    var secs = [], per = [], total = 0, shown = 0;
    each(g, "[data-filter-section]", function (sec) {
      if (sec.closest("[data-filter-group]") === g) { secs.push(sec); per.push({ n: 0, total: 0 }); }
    });
    each(g, "[data-filter-item]", function (it) {
      if (it.closest("[data-filter-group]") !== g) { return; }
      var vis = !it.hidden, sec = it.closest("[data-filter-section]"), i = sec ? secs.indexOf(sec) : -1;
      total++; if (vis) { shown++; }
      if (i >= 0) { per[i].total++; if (vis) { per[i].n++; } }
    });
    var rec = g._qdOpened || [], next = [];
    secs.forEach(function (sec, i) {
      // sections are recorded by id (the components always give one); an id-less one is filtered, never opened
      var hit = per[i].n > 0, mine = rec.indexOf(sec.id) >= 0;
      sec.hidden = active && !hit;
      if (active && hit) {
        if (sec.id && !sec.open) { sec.open = true; mine = true; }
        if (mine) { next.push(sec.id); }
      } else if (mine) { sec.open = false; }
      sec._qdExpect = sec.open; // the state this script left it in: a later toggle to another is the operator's
      var cnt = sec.querySelector("[data-filter-count]");
      if (cnt) { cnt.textContent = t("filter.group_count", { n: per[i].n, total: per[i].total }); }
    });
    var changed = JSON.stringify(next) !== JSON.stringify(rec);
    g._qdOpened = next;
    if (changed) { saveOpened(g); } else { openedMem[g.getAttribute("data-filter-group")] = next.slice(); }
    each(g, "[data-filter-status]", function (st) {
      if (st.closest("[data-filter-group]") === g) { st.textContent = t("filter.shown", { n: shown, total: total }); }
    });
  }
  function validFilterState(state) {
    if (!plainObject(state)) { return false; }
    return Object.keys(state).every(function (n) {
      var f = state[n];
      return plainObject(f) && typeof f.v === "string" && (f.mode === "token" || f.mode === "substr");
    });
  }
  function initFilters() {
    each(main, "[data-filter-group]", function (g) {
      var name = g.getAttribute("data-filter-group"), skey = "qd-filter:" + name;
      var state = loadJSON(skey);
      if (state === null) { state = {}; }
      else if (!validFilterState(state)) { state = {}; save(skey, "{}"); } // a corrupt store resets
      var okey = "qd-filter-open:" + name, raw = load(okey), rec = [];
      if (has(openedMem, name)) { rec = openedMem[name].slice(); } // this page's own record is the freshest
      else if (raw !== null) {
        try { rec = JSON.parse(raw); } catch (e) { rec = null; }
        if (!Array.isArray(rec)) {
          rec = []; save(okey, "[]"); // a corrupt record resets alone; the filter store is not its business
        }
      }
      g._qdOpened = rec;
      var controls = filterControls(g), dirty = false;
      // with a control bar rendered, the state holds only keys a control names: nothing else could clear one
      if (controls.length) {
        Object.keys(state).forEach(function (n) {
          var f = state[n];
          var there = f.chip
            ? controls.some(function (el) { return el.getAttribute("data-filter") === n + ":" + f.v; })
            : controls.some(function (el) { return el.getAttribute("data-filter") === n; });
          if (!there) { delete state[n]; dirty = true; }
        });
      }
      g._qdFilter = state;
      controls.forEach(function (el) {
        var spec = el.getAttribute("data-filter");
        if (spec.indexOf(":") < 0 && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) {
          var f = state[spec], v = f && !f.chip ? f.v : "";
          if (el.tagName === "SELECT") {
            var offers = function (x) { return Array.prototype.some.call(el.options, function (o) { return o.value === x; }); };
            if (v !== "" && offers(v)) { el.value = v; }
            else {
              // no value, or one no option offers, is NO filter: drop the key and show "all" (every filter select offers it)
              if (f && !f.chip) { delete state[spec]; dirty = true; }
              el.value = "";
            }
          } else { el.value = v; }
        }
      });
      if (dirty) { save(skey, JSON.stringify(state)); }
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
      var hasPane = function (v) { return panes.some(function (p) { return p.getAttribute("data-pick") === v; }); };
      var want = current.arg;
      if (!want || !hasPane(want)) { want = load("qd-pick:" + name); }
      if (typeof want !== "string" || !hasPane(want)) { want = panes[0].getAttribute("data-pick"); }
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
    initClamps(); // a clamp in a panel just shown can only be measured now
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
      if (!text.offsetParent) { btn.hidden = true; return; } // hidden: no toggle until measured on show
      btn.hidden = !(text.scrollHeight > text.clientHeight + 1);
    });
  }
  function setClamp(c, open) {
    var btn = c.querySelector("[data-clamp-toggle]");
    if (open) { c.setAttribute("data-expanded", ""); } else { c.removeAttribute("data-expanded"); }
    if (btn) {
      btn.hidden = false;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.textContent = t(open ? "clamp.less" : "clamp.more");
    }
  }
  function toggleClamp(btn) {
    var c = btn.closest("[data-clamp]"); if (!c) { return; }
    setClamp(c, !c.hasAttribute("data-expanded"));
  }
  function ago(sec) {
    if (sec < 60) { return t("fresh.ago_s", { n: Math.max(0, Math.floor(sec)) }); }
    if (sec < 3600) { return t("fresh.ago_min", { n: Math.floor(sec / 60) }); }
    return t("fresh.ago_h", { n: Math.floor(sec / 3600) });
  }
  var staleSeen = {}; // stamps already announced stale, kept across swaps
  function tickFreshness() {
    var now = Date.now() / 1000, wentStale = false, still = {};
    each(document, "time[data-ts]", function (el) {
      var ts = Number(el.getAttribute("data-ts")), cad = Number(el.getAttribute("data-cadence") || "0");
      if (!isFinite(ts)) { return; }
      var age = now - ts, text = ago(age), key = (el.id || "") + "|" + ts + "|" + cad;
      if (cad > 0 && age > 2 * cad) {
        el.setAttribute("data-stale", "");
        if (!has(staleSeen, key)) { wentStale = true; }
        still[key] = true;
        el.textContent = t("fresh.stale", { age: text });
      } else { el.removeAttribute("data-stale"); el.textContent = text; }
    });
    staleSeen = still;
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
    if ((hit = el.closest("[data-retry]"))) { fetchView({ navigate: true }); return; }
    if ((hit = el.closest("[data-clamp-toggle]"))) { toggleClamp(hit); return; }
    if ((hit = el.closest('[role="tab"]'))) { selectTab(hit, true); return; }
    if ((hit = el.closest("[data-pick-to]"))) {
      location.hash = "#" + encodeURIComponent(current.view) + "/" + encodeURIComponent(hit.getAttribute("data-pick-to"));
      return;
    }
    if ((hit = el.closest("button[data-filter]"))) { filterChip(hit); return; }
    if ((hit = el.closest("[data-post]"))) { act(hit); return; }
  });
  document.addEventListener("input", function (ev) {
    var el = ev.target;
    if (el && el.matches && el.matches("input[data-filter], textarea[data-filter]")) { filterInput(el); }
  });
  document.addEventListener("change", function (ev) {
    var el = ev.target;
    if (el && el.matches && el.matches("select[data-filter]")) { filterInput(el); }
  });
  // a section toggled to a state this script did not leave it in is the operator's act: it is no longer the
  // filter's to close
  document.addEventListener("toggle", function (ev) {
    var sec = ev.target;
    if (!sec || !sec.matches || !sec.matches("details[data-filter-section]") || sec.open === sec._qdExpect) { return; }
    sec._qdExpect = sec.open;
    var g = sec.closest("[data-filter-group]"), at = g ? (g._qdOpened || []).indexOf(sec.id) : -1;
    if (at >= 0) { g._qdOpened.splice(at, 1); saveOpened(g); }
  }, true);
  document.addEventListener("keydown", function (ev) {
    var el = ev.target;
    var modal = ev.key === "Tab" ? document.querySelector("dialog[open]") : null;
    if (modal) {
      // a native modal keeps focus off the page but lets Tab run off its end into the browser:
      // wrap it, so the dialog's stops are a loop (spec § Components, Confirm dialog)
      var stops = Array.prototype.filter.call(
        modal.querySelectorAll("button, input, textarea, select, a[href], [tabindex]:not([tabindex='-1'])"),
        function (s) { return !s.disabled && !s.hidden && s.offsetParent !== null; });
      if (stops.length) {
        var at = stops.indexOf(document.activeElement);
        var to = ev.shiftKey ? (at <= 0 ? stops.length - 1 : -1) : (at === -1 || at === stops.length - 1 ? 0 : -1);
        if (to >= 0) { ev.preventDefault(); stops[to].focus(); }
      }
      return;
    }
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
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing && el && el.id && /^(INPUT|TEXTAREA)$/.test(el.tagName)) {
      var target = null;
      each(document, "[data-text-from]", function (b) { if (!target && b.getAttribute("data-text-from") === el.id) { target = b; } });
      if (target) { ev.preventDefault(); act(target); }
    }
  });
  // a dialog closed any way (Escape, cancel, confirm) returns focus to the button that opened it
  document.addEventListener("close", function (ev) {
    var dlg = ev.target;
    if (!dlg || dlg.tagName !== "DIALOG") { return; }
    var ae = document.activeElement;
    if (!ae || ae === document.body || dlg.contains(ae)) { returnFocus(dlg); } // Escape: the native close
    dlg._qd = null; dlg._qdInvoker = null;
    if (pendingForce && !document.querySelector("dialog[open]")) { pendingForce = false; refresh(true); }
  }, true);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { tickFreshness(); refresh(false); }
  });
  window.addEventListener("hashchange", function () { route(false); });

  // ---------------------------------------------------------------- start
  applyTheme(theme()); // relabels the toggle from the stored theme (the server renders "system")
  setInterval(tickFreshness, 5000);
  if (main) { route(true); }
})();
