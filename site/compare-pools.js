// Interactive comparison of the pools kind (compare-pools.html). Data: the JSON
// in #poolsdata, written by site/pools_data.py from records/pools. No external
// code. State lives in the URL fragment, so a view can be linked. No ranking of
// ours: without weights the rows are in the order of the configuration list (or
// sorted by name or an exact column, flash or RAM bytes); with the reader's
// weights they are ordered by a score that is a range, as the numbers are, and
// a score that overlaps the one above it is marked. Our reference free list
// with interrupts off (role "ours": not a library) is a row of the same table,
// labelled in its name cell every time; with weights it is scored like any
// row, and the filter on the kind of row leaves it out. What each library
// documents about use from interrupts is shown as documented, and used in no
// score. With records of the concurrency series (D.isr_source) a second column
// says what that series observed, in its classes (passed, or a finding;
// outside the library's documentation only what was observed; our controls
// caught), and a filter keeps the rows that passed within their documentation;
// it is never part of a score. Without them the page is as before. The reference free list, the baseline,
// stays apart, last. mcp-server/poolsquery.py is a port of this script, tested
// against it.
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("poolsdata").textContent);
  var REPO = "https://github.com/verified-libs/verified-libs/blob/main/";
  var SCENS = ["pair", "pair_full", "fill_drain_lifo", "fill_drain_fifo", "mixed", "empty"];
  var SORTS = ["name", "flash", "ram"];
  var SORT_TEXT = { name: "name", flash: "flash bytes", ram: "RAM bytes" };
  var LANGS = ["C", "C++", "Rust"];
  var KINDS = ["library", "ours"];
  // The weights: cycles of one alloc and of one free in the chosen scenario, bytes (flash + RAM).
  var WEIGHTS = [{ id: "alloc", label: "Cycles, one alloc" }, { id: "free", label: "Cycles, one free" },
                 { id: "bytes", label: "Bytes, flash + RAM" }];
  var OURS_LABEL = "our reference free list with interrupts off; not a library";
  var BASE_TEXT = "Reference free list (baseline), not a library";
  var NOT_PUBLISHED = "The first board series of this kind is not published yet: there are no records, so there is nothing to compare.";
  var ISR = !!D.isr_source;   // records of the concurrency series
  var VARIANT_TEXT = "a build of its own, not the one timed here: ";
  var ISR_FILTER = "use from interrupts: tested within its documentation, and passed";
  var st;

  function $(id) { return document.getElementById(id); }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function num(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f"); }
  function dec1(n) { return n.toFixed(1); }
  // A range as shown: one number where both ends show the same.
  function rangeText(r, f) {
    if (!r) return "–";
    var a = f(r[0]), b = f(r[1]);
    return a === b ? a : a + "–" + b;
  }
  // The ends of a range as shown (whole cycles), for the overlap marks.
  function shownCycles(r) { return r ? [Math.round(r[0]), Math.round(r[1])] : null; }
  function overlap(a, b) { return !!a && !!b && a[0] <= b[1] && b[0] <= a[1]; }
  // The score is shown to one decimal; its marks are judged on the score before rounding (closed ranges),
  // so that a mark never says "not told apart" where the series tells the rows apart.
  function scoreOverlap(a, b) { return overlap(a, b); }
  function scoreText(r) { return r ? rangeText(r, dec1) : "–"; }

  function defaults() {
    return { board: D.boards.length ? D.boards[0].id : "", scen: "pair", cache: "on", lang: "", kind: "", isr: "",
             sort: "", dir: 1, row: "", w: { alloc: 0, free: 0, bytes: 0 } };
  }
  function dec(v) { try { return decodeURIComponent(v); } catch (e) { return null; } }

  function readHash() {
    st = defaults();
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var p = kv.split("="), k = p[0], v = dec(p[1] || "");
      if (v === null) return;
      if (k === "board" && D.boards.some(function (b) { return b.id === v; })) st.board = v;
      else if (k === "scen" && SCENS.indexOf(v) >= 0) st.scen = v;
      else if (k === "cache" && (v === "on" || v === "off")) st.cache = v;
      else if (k === "lang" && LANGS.indexOf(v) >= 0) st.lang = v;
      else if (k === "kind" && KINDS.indexOf(v) >= 0) st.kind = v;
      else if (k === "isr" && ISR && v === "passed") st.isr = v;
      else if (k === "sort") {
        var s = v.replace(/^-/, "");
        if (SORTS.indexOf(s) >= 0) { st.sort = s; st.dir = v.charAt(0) === "-" ? -1 : 1; }
      }
      else if (k === "row") st.row = v;
      else if (k === "w") v.split(",").forEach(function (x, i) { if (WEIGHTS[i]) st.w[WEIGHTS[i].id] = Math.max(0, Math.min(10, parseInt(x, 10) || 0)); });
    });
    tidy();
  }
  // A chosen configuration that is not measured on the chosen board is dropped.
  function tidy() { if (!rowOf(st.board, st.row)) st.row = ""; }
  function hashOf() {
    var parts = ["board=" + st.board, "scen=" + st.scen, "cache=" + st.cache];
    if (weighted()) parts.push("w=" + WEIGHTS.map(function (m) { return st.w[m.id]; }).join(","));
    if (st.lang) parts.push("lang=" + encodeURIComponent(st.lang));
    if (st.kind) parts.push("kind=" + st.kind);
    if (st.isr) parts.push("isr=" + st.isr);
    if (st.sort) parts.push("sort=" + (st.dir < 0 ? "-" : "") + st.sort);
    if (st.row) parts.push("row=" + encodeURIComponent(st.row));
    return "#" + parts.join("&");
  }

  function rowOf(board, adapter) {
    for (var i = 0; i < D.rows.length; i++) if (D.rows[i].board === board && D.rows[i].adapter === adapter) return D.rows[i];
    return null;
  }
  function baselineOf() {
    for (var i = 0; i < D.baseline.length; i++) if (D.baseline[i].board === st.board) return D.baseline[i];
    return null;
  }
  function weighted() { return WEIGHTS.some(function (m) { return st.w[m.id] > 0; }); }
  function cyc(r, op) { return r.cycles[st.cache][op === "init" ? "init" : st.scen + "/" + op]; }
  function bytesOf(r) { return r.flash_bytes == null || r.ram_bytes == null ? null : r.flash_bytes + r.ram_bytes; }
  // A row's value of each weight as a range [lower end, upper end]; bytes are exact.
  function valuesOf(r) {
    var b = bytesOf(r);
    return { alloc: cyc(r, "alloc"), free: cyc(r, "free"), bytes: b == null ? null : [b, b] };
  }
  // The score as on the other comparison pages (smallest value / own value, weighted mean x 100), as a range:
  // the smallest value is the smallest lower end among the rows shown; a row's lowest score uses its upper
  // ends, its highest score its lower ends. A value that is missing counts 0.
  function score(xs) {
    var wsum = WEIGHTS.reduce(function (a, m) { return a + st.w[m.id]; }, 0), best = {};
    WEIGHTS.forEach(function (m) {
      xs.forEach(function (x) {
        var v = valuesOf(x.r)[m.id];
        if (v && v[0] > 0 && (best[m.id] == null || v[0] < best[m.id])) best[m.id] = v[0];
      });
    });
    xs.forEach(function (x) {
      var lo = 0, hi = 0, v = valuesOf(x.r);
      WEIGHTS.forEach(function (m) {
        if (!st.w[m.id] || !v[m.id] || !(v[m.id][0] > 0)) return;
        lo += st.w[m.id] * best[m.id] / v[m.id][1];
        hi += st.w[m.id] * best[m.id] / v[m.id][0];
      });
      x.score = [100 * lo / wsum, 100 * hi / wsum];
    });
  }

  // The configurations measured on the chosen board, filtered, in list order or sorted.
  function shown() {
    var all = [], out;
    D.configurations.forEach(function (c, i) { var r = rowOf(st.board, c.adapter); if (r) all.push({ c: c, r: r, i: i }); });
    out = all.filter(function (x) {
      if (st.lang && x.c.lang !== st.lang) return false;
      if (st.kind && x.c.role !== st.kind) return false;
      if (st.isr && !(x.r.isr && x.r.isr.passed)) return false;
      return true;
    });
    if (weighted()) score(out);
    if (!st.sort && weighted()) out.sort(function (a, b) {
      var c = b.score[1] - a.score[1];
      return (c > 0) - (c < 0) || a.i - b.i;
    });
    if (st.sort) out.sort(function (a, b) {
      var c = 0;
      if (st.sort === "name") c = st.dir * a.c.name.localeCompare(b.c.name);
      else {
        var k = st.sort === "flash" ? "flash_bytes" : "ram_bytes", x = a.r[k], y = b.r[k];
        if (x == null && y == null) c = 0;
        else if (x == null) return 1;
        else if (y == null) return -1;
        else c = st.dir * (x - y);
      }
      return c || a.i - b.i;
    });
    return { all: all, rows: out };
  }

  function header() {
    function h(key, text) { return st.sort === key ? text + (st.dir < 0 ? " ↓" : " ↑") : text; }
    return [h("name", "Configuration")].concat(weighted() ? ["Score (your weights)"] : []).concat(
      ["Library", "Version", "Lang.", "Lock as built", h("flash", "Flash bytes"), h("ram", "RAM bytes"),
       "Cycles, init", "Cycles, alloc (" + st.scen + ")", "Cycles, free (" + st.scen + ")"]).concat(
      ISR ? ["Use from interrupts: documented", "Use from interrupts: observed (concurrency series)"]
          : ["Documented use from interrupts (not tested)"]);
  }
  function claimCell(td, c) {
    var d = c.documented_interrupts;
    td.appendChild(el("span", d ? d.text : "–"));
    if (d && d.source) td.appendChild(el("div", "source: " + d.source, "sub"));
  }

  function render() {
    var t = $("cmp-table");
    if (ISR) $("pools-isr-board-note").textContent = (D.isr_source.board_notes || {})[st.board] || "";
    t.textContent = "";
    if (!D.published) {
      $("cmp-count").textContent = NOT_PUBLISHED;
      $("cmp-note").textContent = "";
      $("cmp-src").textContent = "";
      return;
    }
    var v = shown(), rs = v.rows, base = baselineOf();
    var chosen = null;
    rs.forEach(function (x) { if (x.c.adapter === st.row) chosen = x; });
    var thead = el("thead"), htr = el("tr");
    var wd = weighted() ? 1 : 0;
    header().forEach(function (text, i) {
      var th = el("th"), key = i === 0 ? "name" : i === 5 + wd ? "flash" : i === 6 + wd ? "ram" : null;
      if (key) {
        var b = el("button", text, "sortb");
        b.type = "button";
        b.addEventListener("click", function () {
          if (st.sort !== key) { st.sort = key; st.dir = 1; }
          else if (st.dir > 0) st.dir = -1;
          else { st.sort = ""; st.dir = 1; }
          update();
        });
        th.appendChild(b);
      } else th.textContent = text;
      htr.appendChild(th);
    });
    thead.appendChild(htr);
    t.appendChild(thead);
    var tb = el("tbody");
    var cs = chosen && wd ? chosen.score : null, byScore = wd && !st.sort;
    function numbers(tr, r, isChosen) {
      ["init", "alloc", "free"].forEach(function (op) {
        var td = el("td", rangeText(cyc(r, op), num), "n");
        if (chosen && !isChosen && overlap(shownCycles(cyc(chosen.r, op)), shownCycles(cyc(r, op)))) td.appendChild(el("div", "overlaps", "sub"));
        tr.appendChild(td);
      });
    }
    rs.forEach(function (x, j) {
      var tr = el("tr"), c = x.c, r = x.r, td = el("td"), isChosen = chosen === x;
      var nb = el("button", c.name, "sortb");
      nb.type = "button";
      nb.addEventListener("click", function () { st.row = st.row === c.adapter ? "" : c.adapter; update(); });
      td.appendChild(nb);
      var rec = el("div", null, "sub"), a = el("a", "record");
      a.href = REPO + r.record;
      rec.appendChild(a);
      td.appendChild(rec);
      if (c.role === "ours") td.appendChild(el("div", OURS_LABEL, "sub"));
      if (isChosen) td.appendChild(el("div", "chosen", "sub"));
      tr.appendChild(td);
      if (wd) {
        var sc = el("td", scoreText(x.score), "n score");
        if (byScore && j > 0 && scoreOverlap(rs[j - 1].score, x.score)) sc.appendChild(el("div", "overlaps above", "sub"));
        if (cs && !isChosen && scoreOverlap(cs, x.score)) sc.appendChild(el("div", "overlaps", "sub"));
        tr.appendChild(sc);
      }
      tr.appendChild(el("td", c.library == null ? "–" : c.library));
      tr.appendChild(el("td", c.pin == null ? "–" : c.pin));
      tr.appendChild(el("td", c.lang));
      tr.appendChild(el("td", c.lock == null ? "–" : c.lock));
      tr.appendChild(el("td", r.flash_bytes == null ? "–" : num(r.flash_bytes), "n"));
      tr.appendChild(el("td", r.ram_bytes == null ? "–" : num(r.ram_bytes), "n"));
      numbers(tr, r, isChosen);
      var ct = el("td");
      claimCell(ct, c);
      tr.appendChild(ct);
      if (ISR) {
        var it = el("td", r.isr ? r.isr.text : "–");
        // another build of the same library in the concurrency series (C_Allocator with its lock option)
        (r.isr_variants || []).forEach(function (v) { it.appendChild(el("div", v.name + ", " + VARIANT_TEXT + v.text, "sub")); });
        tr.appendChild(it);
      }
      tb.appendChild(tr);
    });
    if (base) {
      var sep = el("tr", null, "sep"), std = el("td", BASE_TEXT);
      std.colSpan = 11 + wd + (ISR ? 1 : 0);
      sep.appendChild(std);
      tb.appendChild(sep);
      var btr = el("tr");
      ["reference free list (ours)"].concat(wd ? ["–"] : []).concat(["–", "–", "C", "none", "–", "–"]).forEach(function (s) { btr.appendChild(el("td", s)); });
      numbers(btr, base, false);
      var bc = el("td");
      claimCell(bc, { documented_interrupts: D.baseline_documented });
      btr.appendChild(bc);
      if (ISR) {
        var bi = (D.baseline_isr || []).filter(function (x) { return x.board === st.board; })[0];
        btr.appendChild(el("td", bi ? "our control without a lock: " + bi.text : "–"));
      }
      tb.appendChild(btr);
    }
    t.appendChild(tb);
    $("cmp-count").textContent = rs.length + " of " + v.all.length + " rows shown, " +
      (st.sort ? "sorted by " + SORT_TEXT[st.sort] + (st.dir < 0 ? ", descending" : "")
               : wd ? "ordered by the score of your weights, its highest end first; a score marked “overlaps above” is not told apart from the row above by this series"
               : "in the order of the configuration list; this is not a ranking") +
      (st.row && !chosen ? ". The chosen configuration is not shown: nothing is marked" : "") + ".";
    var bd = D.boards.filter(function (x) { return x.id === st.board; })[0];
    var sc = D.scenarios.filter(function (x) { return x.key === st.scen; })[0];
    $("cmp-note").textContent = [D.SYNTHETIC ? "SYNTHETIC: " + D.SYNTHETIC + "." : "",
      D.SYNTHETIC_ISR ? "SYNTHETIC: " + D.SYNTHETIC_ISR + "." : "",
      st.isr ? "Shown: the rows that passed the concurrency series within their documentation (" + ISR_FILTER + "); not a score." : "",
      st.scen + ": " + sc.text + ".", st.scen === "empty" ? "No block is freed in this scenario." : "",
      st.cache === "off" && bd.note_cache_off ? bd.note_cache_off : ""]
      .filter(function (x) { return x; }).join(" ");
    $("cmp-src").textContent = bd.name + " (" + bd.core + ", " + Math.round(bd.clock_hz / 1e6) + " MHz). Records: " +
      D.source.records + ", series at commit " + D.source.commits.join(", ") + ", toolchain " + D.source.toolchain_image.join(", ") +
      ". Each number is the mean of the scenario's calls, the first included, in cycles less the counter-read overhead, " +
      "as min–max over the eight placements, first pass; init is one call.";
  }

  function syncControls() {
    WEIGHTS.forEach(function (m) { $("w-" + m.id).value = st.w[m.id]; $("wv-" + m.id).textContent = st.w[m.id]; });
    $("pools-board").value = st.board; $("pools-scen").value = st.scen; $("pools-cache").value = st.cache;
    $("pools-lang").value = st.lang; $("pools-kind").value = st.kind;
    if (ISR) $("pools-isr").value = st.isr;
  }
  function update() { tidy(); syncControls(); history.replaceState(null, "", hashOf()); render(); }

  function build() {
    var bs = $("pools-board");
    D.boards.forEach(function (b) { var o = el("option", b.name + " (" + b.core + ")"); o.value = b.id; bs.appendChild(o); });
    [["pools-board", "board"], ["pools-scen", "scen"], ["pools-cache", "cache"], ["pools-lang", "lang"],
     ["pools-kind", "kind"]].forEach(function (p) {
      $(p[0]).addEventListener("change", function (e) { st[p[1]] = e.target.value; update(); });
    });
    if (ISR) {   // the filter on the concurrency series, beside the filter on the kind of row
      var lab = el("label", "Use from interrupts "), sel = el("select");
      sel.id = "pools-isr";
      [["", "every row"], ["passed", ISR_FILTER]].forEach(function (o) { var op = el("option", o[1]); op.value = o[0]; sel.appendChild(op); });
      sel.addEventListener("change", function (e) { st.isr = e.target.value; update(); });
      lab.appendChild(sel);
      $("pools-isr-box").appendChild(lab);
      var bn = el("p");   // what one board's cells need beside them (site/pools_isr.py BOARD_NOTE)
      bn.id = "pools-isr-board-note";
      $("pools-isr-box").appendChild(bn);
      // the box above the table: the series is in (the results page says the same, site/pools_tables.py)
      var box = $("pools-onectx"), a = el("a", "method");
      box.textContent = "";
      box.appendChild(el("strong", "Use from interrupts was tested"));
      box.appendChild(el("span", " in a series of its own, the concurrency series: an interrupt at every cycle of a call, " +
        "on every board, with controls that must be caught ("));
      a.href = "method-pools.html#use-from-interrupts";
      box.appendChild(a);
      box.appendChild(el("span", "). The last column says what it observed; a library used in a way it does not document " +
        "is never called failing, and the column is part of no score. The cycles are of one context."));
    }
    var wbox = $("pools-weights");
    WEIGHTS.forEach(function (m) {
      var lab = el("label", null, "w"), inp = el("input"), out = el("output", "0");
      lab.appendChild(el("span", m.label));
      inp.type = "range"; inp.min = 0; inp.max = 10; inp.step = 1; inp.id = "w-" + m.id; out.id = "wv-" + m.id;
      inp.addEventListener("input", function () { st.w[m.id] = parseInt(inp.value, 10); update(); });
      lab.appendChild(inp); lab.appendChild(out); wbox.appendChild(lab);
    });
    $("pools-reset").addEventListener("click", function () { st = defaults(); update(); });
    readHash();
    update();
    window.addEventListener("hashchange", function () { readHash(); syncControls(); render(); });
  }
  build();
})();
