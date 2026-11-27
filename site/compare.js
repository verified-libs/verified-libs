// Interactive comparison (compare.html). Data: the JSON in #libdata, written
// by site/gen_libdata.py. No external code. State lives in the URL fragment,
// so a view can be linked.
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("libdata").textContent);
  var METRICS = [
    { id: "push", label: "1-byte push", get: function (s) { return s.push; } },
    { id: "pop", label: "1-byte pop", get: function (s) { return s.pop; } },
    { id: "block", label: "64-byte block", get: function (s) { return s.block; } },
    { id: "dma", label: "Zero-copy (DMA) transfer", get: function (s) { return s.dma_w && s.dma_r ? (s.dma_w + s.dma_r) / 2 : null; } }
  ];
  var PERMISSIVE = /^(MIT|BSD-2-Clause|BSD-3-Clause|Apache-2\.0|CC0-1\.0)$/;
  var FLAGS = ["clean", "permissive", "block", "zc", "genmc", "contract", "nounsafe", "nosingle"];
  var TOPOS = ["SPSC", "MPSC", "SPMC", "MPMC"];
  // Benchmark version 2 (one image per configuration) is shown for every board the data has it for;
  // version 1 (all libraries in one image) is archived and only shown for a board without version 2.
  var HAS2 = D.boards.some(function (b) { return !!b.bench2; });
  var st = { board: D.boards[0].id, w: { push: 0, pop: 0, block: 0, dma: 0 }, f: { nosingle: true }, lang: "", topo: "", cores: "", sort: "name", dir: 1 };

  function $(id) { return document.getElementById(id); }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function num(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function dec1(n) { return n.toFixed(1); }
  // A speed cell: the value and, where the placement experiment moved it at the
  // precision shown, the lowest and highest mean over the placements below it.
  function speedCell(v, rng, fmt) {
    var td = el("td", v ? fmt(v) : "–", "n");
    if (v && rng && fmt(rng[0]) !== fmt(rng[1])) td.appendChild(el("div", fmt(rng[0]) + "–" + fmt(rng[1]), "sub"));
    return td;
  }

  function readHash() {
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) {
      var p = kv.split("="), k = p[0], v = decodeURIComponent(p[1] || "");
      if (k === "board" && D.boards.some(function (b) { return b.id === v; })) st.board = v;
      else if (k === "w") v.split(",").forEach(function (x, i) { if (METRICS[i]) st.w[METRICS[i].id] = Math.max(0, Math.min(10, parseInt(x, 10) || 0)); });
      else if (k === "f") v.split(",").forEach(function (x) { if (FLAGS.indexOf(x) >= 0) st.f[x] = true; else if (x === "two") st.cores = "2"; else if (x === "single") st.f.nosingle = false; });
      else if (k === "topo" && TOPOS.indexOf(v) >= 0) st.topo = v;
      else if (k === "cores" && (v === "1" || v === "2")) st.cores = v;
      else if (k === "lang" && (v === "C" || v === "C++" || v === "Rust")) st.lang = v;
      else if (k === "sort") { st.sort = v.replace(/^-/, ""); st.dir = v.charAt(0) === "-" ? -1 : 1; }
    });
  }
  function writeHash() {
    var parts = ["board=" + st.board];
    var w = METRICS.map(function (m) { return st.w[m.id]; });
    if (w.some(Boolean)) parts.push("w=" + w.join(","));
    // "hide single-context variants" is on by default: only its being off is written ("single")
    var f = FLAGS.filter(function (x) { return x !== "nosingle" && st.f[x]; });
    if (!st.f.nosingle) f.push("single");
    if (f.length) parts.push("f=" + f.join(","));
    if (st.topo) parts.push("topo=" + st.topo);
    if (st.cores) parts.push("cores=" + st.cores);
    if (st.lang) parts.push("lang=" + encodeURIComponent(st.lang));
    if (weighted() || st.sort !== "name" || st.dir !== 1) parts.push("sort=" + (st.dir < 0 ? "-" : "") + st.sort);
    history.replaceState(null, "", "#" + parts.join("&"));
  }

  // Stress result over all boards: "clean", "errors" or "untested".
  function stressState(lib) {
    var runs = 0, errs = 0;
    Object.keys(lib.stress).forEach(function (b) { runs += lib.stress[b].runs; errs += lib.stress[b].errors; });
    return errs ? "errors" : runs ? "clean" : "untested";
  }
  function weighted() { return METRICS.some(function (m) { return st.w[m.id] > 0; }); }

  // The speeds that apply to the chosen use: with MPSC, SPMC or MPMC those of that mode
  // (null where the mode does not exist on the board's core), otherwise the SPSC ones.
  function mpMode() { return st.topo && st.topo !== "SPSC" ? st.topo : ""; }
  // The one-core contract check of the chosen producer/consumer mode (verify/contract).
  function contractOf(l) { return l.contract ? l.contract[mpMode() || "SPSC"] : null; }
  function two() {
    return D.boards.some(function (b) { return b.id === st.board && !!b.bench2; });
  }
  function speedOf(l) {
    var mode = mpMode(), key = two() ? "speed2" : "speed";
    if (!mode) return (l[key] || {})[st.board] || null;
    if (!l.mp || l.mp.modes.indexOf(mode) < 0) return null;
    return ((l.mp[key] || {})[st.board] || {})[mode] || null;
  }

  // Flash and RAM the configuration adds on the chosen board (of the chosen mode), or null.
  function sizeOf(l) {
    var mode = mpMode();
    if (!mode) return (l.size || {})[st.board] || null;
    if (!l.mp || !l.mp.size || l.mp.modes.indexOf(mode) < 0) return null;
    return (l.mp.size[st.board] || {})[mode] || null;
  }

  function rows() {
    var best = {};
    METRICS.forEach(function (m) {
      D.libs.forEach(function (l) {
        var s = speedOf(l), v = s ? m.get(s) : null;
        if (v && (!best[m.id] || v < best[m.id])) best[m.id] = v;
      });
    });
    var wsum = METRICS.reduce(function (a, m) { return a + st.w[m.id]; }, 0);
    return D.libs.filter(function (l) {
      var s = speedOf(l) || {};
      if (l.boards_only && l.boards_only.indexOf(st.board) < 0) return false;   // tested on these boards only (its licence)
      if (st.f.clean && stressState(l) !== "clean") return false;
      if (st.f.permissive && !l.license.split(" OR ").some(function (x) { return PERMISSIVE.test(x); })) return false;   // a dual licence counts if one choice is permissive
      if (st.f.block && !s.block) return false;
      if (st.f.zc && (mpMode() ? !s.dma_w : !l.zero_copy)) return false;   // zero-copy is not timed in the MP modes
      if (st.topo === "SPSC" || !st.topo) {
        if (st.topo && l.single_context) return false;
        if (st.cores === "2" && !l.two_cores_documented) return false;
      } else {
        if (!l.mp || l.mp.modes.indexOf(st.topo) < 0) return false;
        if (st.cores === "2" && l.mp.cores < 2) return false;
      }
      if (st.f.genmc && !l.genmc) return false;
      if (st.f.contract && !(contractOf(l) && contractOf(l).verdict === "pass")) return false;
      if (st.f.nounsafe && l.unsafe_by_own_docs) return false;
      if (st.f.nosingle && l.single_context) return false;
      if (st.lang && l.lang !== st.lang) return false;
      return true;
    }).map(function (l) {
      var s = speedOf(l) || {}, r = { lib: l, s: s, state: stressState(l), score: null, missing: [], nomode: mpMode() && !speedOf(l) };
      METRICS.forEach(function (m) { r[m.id] = m.get(s); });
      r.z = sizeOf(l); r.size = r.z ? r.z.flash : null;
      if (wsum) {
        var acc = 0;
        METRICS.forEach(function (m) {
          if (!st.w[m.id]) return;
          if (r[m.id]) acc += st.w[m.id] * best[m.id] / r[m.id]; else r.missing.push(m.label);
        });
        r.score = 100 * acc / wsum;
      }
      return r;
    });
  }

  var GROUP = { clean: 0, untested: 1, errors: 2 };
  function sortRows(rs) {
    var k = st.sort, d = st.dir;
    rs.sort(function (a, b) {
      var x, y;
      // Whatever the order, the table is in three groups: error-free, not tested, with errors.
      if (GROUP[a.state] !== GROUP[b.state]) return GROUP[a.state] - GROUP[b.state];
      if (k === "score" && weighted()) return d * (b.score - a.score) || a.lib.name.localeCompare(b.lib.name);
      if (k === "name" || k === "license" || k === "lang") { x = a.lib[k].toLowerCase(); y = b.lib[k].toLowerCase(); return d * x.localeCompare(y) || a.lib.name.localeCompare(b.lib.name); }
      if (k === "stress") { x = (a.lib.stress[st.board] || {}).errors; y = (b.lib.stress[st.board] || {}).errors; }
      else { x = a[k]; y = b[k]; }
      if (x == null && y == null) return a.lib.name.localeCompare(b.lib.name);
      if (x == null) return 1;            // no value: always last
      if (y == null) return -1;
      return d * (x - y) || a.lib.name.localeCompare(b.lib.name);
    });
    return rs;
  }

  var COLS = [["name", "Library"], ["license", "License"], ["lang", "Lang."], ["push", "1 byte push"], ["pop", "1 byte pop"],
              ["block", "64-byte block, cycles/byte"], ["dma", "Zero-copy write / read, cycles"], ["size", "Code / RAM, bytes"],
              ["stress", "ISR stress errors, this board"], [null, "Two cores (Pico 2)"], [null, "GenMC (C11)"],
              [null, "One-core contract, every instruction"]];

  function render() {
    var rs = sortRows(rows()), w = weighted(), t = $("cmp-table");
    t.textContent = "";
    var hr = el("tr");
    (w ? [COLS[0], ["score", "Score (your weights)"]].concat(COLS.slice(1)) : COLS).forEach(function (c) {
      var th = el("th");
      if (c[0]) {
        var b = el("button", c[1] + (st.sort === c[0] ? (st.dir > 0 ? " ▲" : " ▼") : ""), "sortb");
        b.type = "button";
        b.addEventListener("click", function () {
          if (st.sort === c[0]) st.dir = -st.dir; else { st.sort = c[0]; st.dir = 1; }
          update();
        });
        th.setAttribute("aria-sort", st.sort === c[0] ? (st.dir > 0 ? "ascending" : "descending") : "none");
        th.appendChild(b);
      } else th.textContent = c[1];
      hr.appendChild(th);
    });
    t.appendChild(el("thead")).appendChild(hr);
    var tb = t.appendChild(el("tbody")), prev = null;
    rs.forEach(function (r) {
      var l = r.lib, tr = el("tr");
      if (prev !== r.state) {
        var sep = el("tr", null, "sep"), td = el("td", r.state === "errors" ? "Errors in the ISR stress test, on this or another board (listed after the rows above, whatever the order)"
          : r.state === "clean" ? "0 errors in the ISR stress test, on every board tested" : "Not in the ISR stress campaign shown here");
        td.colSpan = COLS.length + 1; sep.appendChild(td); tb.appendChild(sep);
      }
      prev = r.state;
      var name = el("td"), a = el("a", l.name);
      a.href = l.url; name.appendChild(a);
      name.appendChild(el("div", (l.version ? l.version + ", " : "") + l.commit, "sub"));
      if (l.own) {
        var own = el("div", null, "tag warn"), oa = el("a", "⚠ written by the project owner");
        oa.href = "method.html#conflict-of-interest"; own.appendChild(oa); name.appendChild(own);
      }
      if (l.stress_tested_commits) name.appendChild(el("div", "ISR stress column: campaign tested an earlier commit (" +
        l.stress_tested_commits.join(", ") + "), not " + l.commit, "tag warn"));
      if (l.boards_only) name.appendChild(el("div", "tested on " + l.boards_only.map(function (id) {
        return D.boards.filter(function (x) { return x.id === id; }).map(function (x) { return x.name; })[0] || id; }).join(", ") +
        " only: " + l.boards_only_why, "tag"));
      if (l.unsafe_by_own_docs) name.appendChild(el("div", "not ISR-safe in this configuration by its own documentation", "tag"));
      if (l.single_context) name.appendChild(el("div", "single-context variant (no ISR safety claimed)", "tag"));
      if (l.mp) name.appendChild(el("div", "also " + l.mp.modes.join(", ") + ": " + l.mp.via +
        (l.mp.cores < 2 ? "; one core" : "; also two cores") +
        (mpMode() ? (r.nomode ? "; not available on this board's core" : "; speeds shown are for " + mpMode() +
                     (l.mp.other_code ? "" : " (the same code as SPSC)"))
                  : (l.mp.other_code ? "; speeds shown are for SPSC, choose a mode above for its speeds" : "")), "tag"));
      tr.appendChild(name);
      if (w) {
        var s = el("td", r.score.toFixed(0), "n score");
        if (r.missing.length) s.appendChild(el("div", "no " + r.missing.join(", no "), "sub"));
        tr.appendChild(s);
      }
      tr.appendChild(el("td", l.license));
      tr.appendChild(el("td", l.lang));
      var rg = r.s.range || {};
      tr.appendChild(speedCell(r.push, rg.push, num));
      tr.appendChild(speedCell(r.pop, rg.pop, num));
      tr.appendChild(speedCell(r.block, rg.block, dec1));
      var dm = el("td", r.dma ? num(r.s.dma_w) + " / " + num(r.s.dma_r) : "–", "n");
      if (r.dma && rg.dma_w && rg.dma_r && (num(rg.dma_w[0]) !== num(rg.dma_w[1]) || num(rg.dma_r[0]) !== num(rg.dma_r[1])))
        dm.appendChild(el("div", num(rg.dma_w[0]) + "–" + num(rg.dma_w[1]) + " / " + num(rg.dma_r[0]) + "–" + num(rg.dma_r[1]), "sub"));
      tr.appendChild(dm);
      var zc = el("td", r.z ? num(r.z.flash) + " / " + num(r.z.ram) : "–", "n");
      if (r.z && r.z.heap) zc.appendChild(el("div", "+ heap", "sub"));
      tr.appendChild(zc);
      var sb = l.stress[st.board], sc;
      if (!sb) sc = el("td", "not tested", "mute");
      else if (sb.errors) sc = el("td", num(sb.errors) + " in " + sb.runs_with_errors + " of " + sb.runs + " runs", "bad");
      else {
        sc = el("td"); sc.appendChild(el("strong", "0")); sc.appendChild(document.createTextNode(" in " + sb.runs + " runs"));
        if (r.state === "errors") sc.appendChild(el("div", "errors on another board", "bad"));
      }
      if (sb && sb.not_counted) sc.appendChild(el("div", sb.not_counted + (sb.not_counted > 1 ? " runs" : " run") +
        " not counted: starved by the interrupt load", "sub"));
      sc.classList.add("r");
      tr.appendChild(sc);
      var sm = l.smp.pico2, tc;
      if (!sm) tc = el("td", "–", "mute");
      else if (!l.two_cores_documented) tc = el("td", "single-core design", "mute");
      else if (sm.errors) tc = el("td", num(sm.errors) + " in " + sm.runs_with_errors + " of " + sm.runs + " runs", "bad");
      else { tc = el("td"); tc.appendChild(el("strong", "0")); tc.appendChild(document.createTextNode(" in " + sm.runs + " runs")); }
      if (sm && l.two_cores_documented && sm.not_counted) tc.appendChild(el("div", sm.not_counted +
        (sm.not_counted > 1 ? " runs" : " run") + " not counted: starved", "sub"));
      tc.classList.add("r");
      tr.appendChild(tc);
      tr.appendChild(el("td", l.genmc || "–", l.genmc ? "" : "mute"));
      var ct = contractOf(l), cc;
      if (ct) {
        cc = el("td", ct.verdict, ct.verdict === "pass" ? "" : "bad");
        cc.appendChild(el("div", num(ct.trials) + " trials", "sub"));
        var rc = mpMode() === "MPSC" && l.contract["MPSC reserve/commit"];
        if (rc) cc.appendChild(el("div", "reserve/commit: " + rc.verdict + ", " + num(rc.trials) + " trials", "sub"));
      } else cc = el("td", l.single_context ? "not claimed" : "–", "mute");
      tr.appendChild(cc);
      tb.appendChild(tr);
    });
    $("cmp-count").textContent = rs.length + " of " + D.libs.length + " configurations shown" +
      (w ? "" : "; no weights set, so there is no ranking: the order is the column you sort by") +
      (mpMode() ? ". Speeds" + (w ? " and scores" : "") + " are those of each library's " + mpMode() + " mode, timed without contention " +
        "(one caller at a time), and compared among these libraries only; the ISR stress columns are still the SPSC test" : "");
    var b = D.boards.filter(function (x) { return x.id === st.board; })[0];
    // version 2's numbers: the clock of its records and their method version (site/series_info.py); version 1's: its record's clock
    $("cmp-src").textContent = b.name + " (" + b.core + ", " + (two() ? b.bench2.clock_mhz : b.clock_mhz) + " MHz). " +
      (two() && b.bench2.method_text ? b.bench2.method_text + " " : "") + "Speed: " +
      (two() ? "benchmark version 2, each configuration in an image of its own (" + b.bench2.records + ", commit " + b.bench2.commit +
        ", " + b.bench2.passes + " passes), " + b.bench2.compiler + " " + b.bench2.opt + " (Rust: " + b.bench2.rustc +
        ", same opt-level), code in flash" + (b.bench2.far_bytes ? ", library code that is not inlined at least " + b.bench2.far_bytes +
        " bytes from its caller" : "") + "; small numbers: lowest and highest mean with the image at " +
        b.bench2.placements.length + " placements. No other library's code is in the image, so with a cache this is the best case" +
        (b.size ? ". Code and RAM: " + b.size.record : "") :
      (mpMode() ? (b.mp_bench ? b.mp_bench.record : "no record of the modes on this board")
                 : b.bench.record + (b.rust_bench ? " and, for the Rust libraries, " + b.rust_bench.record : "") +
                   (b.nordic_bench ? "; for Nordic's nrf_ringbuf, " + b.nordic_bench.record : "")) + ", " +
      b.bench.compiler + " " + b.bench.opt + (b.rust_bench && b.rust_bench.rustc ? " (Rust: " + b.rust_bench.rustc.split(" (")[0] + ", same opt-level)" : "") +
      ", code in flash" +
      (!mpMode() && b.bench.placement ? "; small numbers: lowest and highest mean with the library code at " + b.bench.placement.shifts.length +
        " placements (moved by " + b.bench.placement.shifts[0] + " to " + b.bench.placement.shifts[b.bench.placement.shifts.length - 1] + " bytes)" : "") +
      (b.size ? ". Code and RAM: " + b.size.record : "")) +
      ". ISR stress: " +
      (b.stress ? b.stress.valid_runs + " valid runs, campaign " + b.stress.campaign : "no campaign") + "." +
      (D.contract ? " One-core contract check (same for every board): run of " + D.contract.date + " at commit " + D.contract.commit +
        ", up to " + D.contract.interrupts_per_call + " interrupts per call, " + num(D.contract.trials) + " trials." : "");
  }

  function syncControls() {
    $("cmp-board").value = st.board;
    METRICS.forEach(function (m) { $("w-" + m.id).value = st.w[m.id]; $("wv-" + m.id).textContent = st.w[m.id]; });
    FLAGS.forEach(function (f) { $("f-" + f).checked = !!st.f[f]; });
    $("cmp-lang").value = st.lang;
    $("cmp-topo").value = st.topo; $("cmp-cores").value = st.cores;
  }
  function update() { syncControls(); writeHash(); render(); }

  function build() {
    var sel = $("cmp-board");
    D.boards.forEach(function (b) { var o = el("option", b.name + " (" + b.core + ")"); o.value = b.id; sel.appendChild(o); });
    sel.addEventListener("change", function () { st.board = sel.value; update(); });
    var wbox = $("cmp-weights");
    METRICS.forEach(function (m) {
      var lab = el("label", null, "w"), inp = el("input"), out = el("output", "0");
      lab.appendChild(el("span", m.label));
      inp.type = "range"; inp.min = 0; inp.max = 10; inp.step = 1; inp.id = "w-" + m.id; out.id = "wv-" + m.id;
      inp.addEventListener("input", function () {
        var was = weighted();
        st.w[m.id] = parseInt(inp.value, 10);
        if (!was && weighted()) { st.sort = "score"; st.dir = 1; }       // first weight set: rank by it
        if (!weighted() && st.sort === "score") { st.sort = "name"; st.dir = 1; }
        update();
      });
      lab.appendChild(inp); lab.appendChild(out); wbox.appendChild(lab);
    });
    FLAGS.forEach(function (f) { $("f-" + f).addEventListener("change", function (e) { st.f[f] = e.target.checked; update(); }); });
    $("cmp-lang").addEventListener("change", function (e) { st.lang = e.target.value; update(); });
    if ($("cmp-v2-note")) $("cmp-v2-note").hidden = !HAS2;
    $("cmp-topo").addEventListener("change", function (e) { st.topo = e.target.value; update(); });
    $("cmp-cores").addEventListener("change", function (e) { st.cores = e.target.value; update(); });
    function reset() { st.w = { push: 0, pop: 0, block: 0, dma: 0 }; st.f = { nosingle: true }; st.lang = ""; st.topo = ""; st.cores = ""; st.sort = "name"; st.dir = 1; }
    function load() {
      reset(); st.sort = null; readHash();
      // an address with weights and no sort key is ranked by them
      if (st.sort === null) { st.sort = weighted() ? "score" : "name"; st.dir = 1; }
      if (st.sort === "score" && !weighted()) st.sort = "name";
    }
    $("cmp-reset").addEventListener("click", function () { reset(); update(); });
    load();
    update();
    window.addEventListener("hashchange", function () { load(); syncControls(); render(); });
  }
  build();
})();
