// Interactive comparison of the CRC kind (compare-crc.html). Data: the JSON in
// #crcdata, written by site/crc_data.py from records/crc. No external code.
// State lives in the URL fragment, so a view can be linked. No ranking of
// ours: without weights the rows are in the order of the configuration list
// (or sorted by name or an exact column, flash or RAM bytes); with the
// reader's weights they are ordered by a score that is a range, as the
// numbers are, and a score that overlaps the one above it is marked. The
// board's CRC unit (role "hardware": driven by our code, not a library) is a
// row of the same table, after the libraries of its CRC, labelled in its name
// cell every time; with weights it is scored like any row, and the filter on
// the kind of row leaves it out (decided 2026-11-26). Nothing on a board
// without one, and a line that says so. The reference stays apart, last.
// mcp-server/crcquery.py is a port of this script, tested against it.
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("crcdata").textContent);
  var REPO = "https://github.com/verified-libs/verified-libs/blob/main/";
  var LENS = ["4", "16", "64", "256", "1024"];
  var SORTS = ["name", "flash", "ram"];
  var SORT_TEXT = { name: "name", flash: "flash bytes", ram: "RAM bytes" };
  var LANGS = ["C", "C++", "Rust"];
  var TABLES = ["flash", "RAM", "none"];
  var KINDS = ["library", "hardware"];
  // The weights: cycles at the chosen length, cycles per byte, bytes (flash + RAM).
  var WEIGHTS = [{ id: "cyc", label: "Cycles, one call" }, { id: "pb", label: "Cycles per byte" },
                 { id: "bytes", label: "Bytes, flash + RAM" }];
  var st;
  var HW_LABEL = "the board\u2019s CRC unit, driven by our code; not a library";

  function $(id) { return document.getElementById(id); }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function num(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function dec1(n) { return n.toFixed(1); }
  // A range as shown: one number where both ends show the same.
  function rangeText(r, f) {
    if (!r) return "–";
    var a = f(r[0]), b = f(r[1]);
    return a === b ? a : a + "–" + b;
  }
  // The ends of a range as shown, for the overlap marks.
  function shownCycles(r) { return r ? [Math.round(r[0]), Math.round(r[1])] : null; }
  function shownPerByte(r) { return r ? [parseFloat(r[0].toFixed(1)), parseFloat(r[1].toFixed(1))] : null; }
  function overlap(a, b) { return !!a && !!b && a[0] <= b[1] && b[0] <= a[1]; }
  // The score is shown to one decimal; its marks are judged on the score before rounding (closed ranges),
  // so that a mark never says "not told apart" where the series tells the rows apart.
  function scoreOverlap(a, b) { return overlap(a, b); }
  function scoreText(r) { return r ? rangeText(r, dec1) : "–"; }
  function tableWhere(t) { return /^RAM/.test(t) ? "RAM" : t === "none" ? "none" : "flash"; }

  function defaults() {
    return { crc: D.crcs[0], board: D.boards[0].id, len: "16", off: "0", cache: "on",
             lang: "", cls: "", tbl: "", kind: "", sort: "", dir: 1, row: "", w: { cyc: 0, pb: 0, bytes: 0 } };
  }
  // The rows of a CRC: its libraries in list order, then the board's CRC unit (crc.json holds them in that order).
  function configsOf(crc) { return D.configurations.filter(function (c) { return c.crc === crc; }); }
  function classesOf(crc) {
    var out = [];
    configsOf(crc).forEach(function (c) { if (out.indexOf(c["class"]) < 0) out.push(c["class"]); });
    return out;
  }
  function dec(v) { try { return decodeURIComponent(v); } catch (e) { return null; } }

  function readHash() {
    st = defaults();
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var p = kv.split("="), k = p[0], v = dec(p[1] || "");
      if (v === null) return;
      if (k === "crc" && D.crcs.indexOf(v) >= 0) st.crc = v;
      else if (k === "board" && D.boards.some(function (b) { return b.id === v; })) st.board = v;
      else if (k === "len" && LENS.indexOf(v) >= 0) st.len = v;
      else if (k === "off" && (v === "0" || v === "1")) st.off = v;
      else if (k === "cache" && (v === "on" || v === "off")) st.cache = v;
      else if (k === "lang" && LANGS.indexOf(v) >= 0) st.lang = v;
      else if (k === "class") st.cls = v;
      else if (k === "table" && TABLES.indexOf(v) >= 0) st.tbl = v;
      else if (k === "kind" && KINDS.indexOf(v) >= 0) st.kind = v;
      else if (k === "sort") {
        var s = v.replace(/^-/, "");
        if (SORTS.indexOf(s) >= 0) { st.sort = s; st.dir = v.charAt(0) === "-" ? -1 : 1; }
      }
      else if (k === "row") st.row = v;
      else if (k === "w") v.split(",").forEach(function (x, i) { if (WEIGHTS[i]) st.w[WEIGHTS[i].id] = Math.max(0, Math.min(10, parseInt(x, 10) || 0)); });
    });
    // a class or a chosen configuration of another CRC is dropped
    if (classesOf(st.crc).indexOf(st.cls) < 0) st.cls = "";
    if (!configsOf(st.crc).some(function (c) { return c.adapter === st.row; })) st.row = "";
  }
  function hashOf() {
    var parts = ["crc=" + encodeURIComponent(st.crc), "board=" + st.board, "len=" + st.len, "off=" + st.off, "cache=" + st.cache];
    if (weighted()) parts.push("w=" + WEIGHTS.map(function (m) { return st.w[m.id]; }).join(","));
    if (st.lang) parts.push("lang=" + encodeURIComponent(st.lang));
    if (st.cls) parts.push("class=" + encodeURIComponent(st.cls));
    if (st.tbl) parts.push("table=" + st.tbl);
    if (st.kind) parts.push("kind=" + st.kind);
    if (st.sort) parts.push("sort=" + (st.dir < 0 ? "-" : "") + st.sort);
    if (st.row) parts.push("row=" + encodeURIComponent(st.row));
    return "#" + parts.join("&");
  }

  function rowOf(board, adapter) {
    for (var i = 0; i < D.rows.length; i++) if (D.rows[i].board === board && D.rows[i].adapter === adapter) return D.rows[i];
    return null;
  }
  function baselineOf() {
    for (var i = 0; i < D.baseline.length; i++) if (D.baseline[i].board === st.board && D.baseline[i].crc === st.crc) return D.baseline[i];
    return null;
  }
  function weighted() { return WEIGHTS.some(function (m) { return st.w[m.id] > 0; }); }
  function cyclesOf(r) { return r.cycles[st.cache][st.off][st.len]; }
  function bytesOf(r) { return r.flash_bytes == null || r.ram_bytes == null ? null : r.flash_bytes + r.ram_bytes; }
  // A row's value of each weight as a range [lower end, upper end]; bytes are exact.
  function valuesOf(r) {
    var b = bytesOf(r);
    return { cyc: cyclesOf(r), pb: perByteOf(r), bytes: b == null ? null : [b, b] };
  }
  // The score as on the ring buffers' page (smallest value / own value, weighted mean x 100), as a range:
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
  function perByteOf(r) { return r.per_byte[st.cache][st.off]; }

  // The configurations of the chosen CRC measured on the chosen board, filtered, in list order or sorted.
  function shown() {
    var all = [], out;
    configsOf(st.crc).forEach(function (c, i) { var r = rowOf(st.board, c.adapter); if (r) all.push({ c: c, r: r, i: i }); });
    out = all.filter(function (x) {
      if (st.lang && x.c.lang !== st.lang) return false;
      if (st.cls && x.c["class"] !== st.cls) return false;
      if (st.tbl && tableWhere(x.c.table) !== st.tbl) return false;
      if (st.kind && x.c.role !== st.kind) return false;
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
      ["Library", "Lang.", "Class", "Table", h("flash", "Flash bytes"), h("ram", "RAM bytes"),
       "Cycles, " + st.len + " bytes", "Cycles per byte"]);
  }

  function render() {
    var v = shown(), rs = v.rows, base = baselineOf();
    var chosen = null;
    rs.forEach(function (x) { if (x.c.adapter === st.row) chosen = x; });
    var t = $("cmp-table");
    t.textContent = "";
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
    var cc = chosen ? shownCycles(cyclesOf(chosen.r)) : null, cp = chosen ? shownPerByte(perByteOf(chosen.r)) : null;
    var cs = chosen && wd ? chosen.score : null, byScore = wd && !st.sort;
    function numbers(tr, r, isChosen) {
      var c1 = el("td", rangeText(cyclesOf(r), num), "n"), c2 = el("td", rangeText(perByteOf(r), dec1), "n");
      if (chosen && !isChosen && overlap(cc, shownCycles(cyclesOf(r)))) c1.appendChild(el("div", "overlaps", "sub"));
      if (chosen && !isChosen && overlap(cp, shownPerByte(perByteOf(r)))) c2.appendChild(el("div", "overlaps", "sub"));
      tr.appendChild(c1); tr.appendChild(c2);
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
      if (c.role === "hardware") td.appendChild(el("div", HW_LABEL, "sub"));
      if (isChosen) td.appendChild(el("div", "chosen", "sub"));
      tr.appendChild(td);
      if (wd) {
        var sc = el("td", scoreText(x.score), "n score");
        if (byScore && j > 0 && scoreOverlap(rs[j - 1].score, x.score)) sc.appendChild(el("div", "overlaps above", "sub"));
        if (cs && !isChosen && scoreOverlap(cs, x.score)) sc.appendChild(el("div", "overlaps", "sub"));
        tr.appendChild(sc);
      }
      tr.appendChild(el("td", c.library == null ? "–" : c.library));
      tr.appendChild(el("td", c.lang));
      tr.appendChild(el("td", c["class"]));
      tr.appendChild(el("td", c.table));
      tr.appendChild(el("td", r.flash_bytes == null ? "–" : num(r.flash_bytes), "n"));
      tr.appendChild(el("td", r.ram_bytes == null ? "–" : num(r.ram_bytes), "n"));
      numbers(tr, r, isChosen);
      tb.appendChild(tr);
    });
    if (base) {
      var sep = el("tr", null, "sep"), std = el("td", "Reference (baseline), not a library");
      std.colSpan = 9 + wd;
      sep.appendChild(std);
      tb.appendChild(sep);
      var btr = el("tr");
      ["reference, bitwise"].concat(wd ? ["–"] : []).concat(["–", "C", "bitwise", "none", "–", "–"]).forEach(function (s) { btr.appendChild(el("td", s)); });
      numbers(btr, base, false);
      tb.appendChild(btr);
    }
    t.appendChild(tb);
    $("cmp-count").textContent = rs.length + " of " + v.all.length + " rows of " + st.crc + " shown, " +
      (st.sort ? "sorted by " + SORT_TEXT[st.sort] + (st.dir < 0 ? ", descending" : "")
               : wd ? "ordered by the score of your weights, its highest end first; a score marked \u201coverlaps above\u201d is not told apart from the row above by this series"
               : "in the order of the configuration list; this is not a ranking") +
      (st.row && !chosen ? ". The chosen configuration is not shown: nothing is marked" : "") + ".";
    var bd = D.boards.filter(function (x) { return x.id === st.board; })[0];
    var hasUnit = v.all.some(function (x) { return x.c.role === "hardware"; });
    $("cmp-note").textContent = [st.cache === "off" && bd.note_cache_off ? bd.note_cache_off : "",
      hasUnit ? "" : "No CRC unit of the " + bd.name + " was measured for " + st.crc + ": the table holds libraries only."]
      .filter(function (x) { return x; }).join(" ");
    $("cmp-src").textContent = bd.name + " (" + bd.core + ", " + Math.round(bd.clock_hz / 1e6) + " MHz). Records: " +
      D.source.records + ", series at commit " + D.source.commits.join(", ") + ", toolchain " + D.source.toolchain_image.join(", ") +
      ". Each number is the mean of the scenario's 256 calls, the first included, as min–max over the eight placements, first pass; " +
      "per byte from the means at 256 and 1024 bytes, at the chosen start.";
  }

  function syncControls() {
    WEIGHTS.forEach(function (m) { $("w-" + m.id).value = st.w[m.id]; $("wv-" + m.id).textContent = st.w[m.id]; });
    $("crc-crc").value = st.crc; $("crc-board").value = st.board; $("crc-len").value = st.len;
    $("crc-off").value = st.off; $("crc-cache").value = st.cache; $("crc-lang").value = st.lang; $("crc-table").value = st.tbl;
    $("crc-kind").value = st.kind;
    var cs = $("crc-class");
    cs.textContent = "";
    var any = el("option", "any"); any.value = ""; cs.appendChild(any);
    classesOf(st.crc).forEach(function (c) { var o = el("option", c); o.value = c; cs.appendChild(o); });
    cs.value = st.cls;
  }
  function update() {
    if (classesOf(st.crc).indexOf(st.cls) < 0) st.cls = "";
    if (!configsOf(st.crc).some(function (c) { return c.adapter === st.row; })) st.row = "";
    syncControls(); history.replaceState(null, "", hashOf()); render();
  }

  function build() {
    var cs = $("crc-crc");
    D.crcs.forEach(function (c) { var o = el("option", c); o.value = c; cs.appendChild(o); });
    var bs = $("crc-board");
    D.boards.forEach(function (b) { var o = el("option", b.name + " (" + b.core + ")"); o.value = b.id; bs.appendChild(o); });
    [["crc-crc", "crc"], ["crc-board", "board"], ["crc-len", "len"], ["crc-off", "off"], ["crc-cache", "cache"],
     ["crc-lang", "lang"], ["crc-class", "cls"], ["crc-table", "tbl"], ["crc-kind", "kind"]].forEach(function (p) {
      $(p[0]).addEventListener("change", function (e) { st[p[1]] = e.target.value; update(); });
    });
    var wbox = $("crc-weights");
    WEIGHTS.forEach(function (m) {
      var lab = el("label", null, "w"), inp = el("input"), out = el("output", "0");
      lab.appendChild(el("span", m.label));
      inp.type = "range"; inp.min = 0; inp.max = 10; inp.step = 1; inp.id = "w-" + m.id; out.id = "wv-" + m.id;
      inp.addEventListener("input", function () { st.w[m.id] = parseInt(inp.value, 10); update(); });
      lab.appendChild(inp); lab.appendChild(out); wbox.appendChild(lab);
    });
    $("crc-reset").addEventListener("click", function () { st = defaults(); update(); });
    readHash();
    update();
    window.addEventListener("hashchange", function () { readHash(); syncControls(); render(); });
  }
  build();
})();
