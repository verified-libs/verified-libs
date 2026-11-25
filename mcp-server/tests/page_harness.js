// Runs site/compare.js itself, without a browser, for the parity test
// (tests/test_parity.py). A small stand-in for the page gives the script what
// it asks for; after each load the table is read back as text.
//
//   gjs page_harness.js COMPARE_JS DATA_JSON FRAGMENTS_FILE
//   (compare.js with libs.json, or compare-crc.js with crc.json)
//
// FRAGMENTS_FILE: one address fragment per line. Output: one JSON line per
// fragment: {hash, written, header, rows, seps, count, src, note}, and first one
// line with the engine's order of the printable ASCII characters.
const GLib = imports.gi.GLib;

function read(path) {
  const [ok, bytes] = GLib.file_get_contents(path);
  if (!ok) throw new Error("cannot read " + path);
  return new TextDecoder().decode(bytes);
}

function Node(tag) {
  this.tag = tag; this.text = null; this.children = []; this.className = ""; this.listeners = {};
  const self = this;
  this.classList = { add: function (c) { self.className += " " + c; } };
}
Object.defineProperty(Node.prototype, "textContent", {
  get: function () { return flat(this).join(""); },
  set: function (v) { this.children = []; this.text = v === "" ? null : String(v); }
});
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.setAttribute = function () {};
Node.prototype.addEventListener = function (name, fn) { this.listeners[name] = fn; };

// The texts of a node, in document order: its own, then its children's.
function flat(n) {
  let out = n.text != null ? [n.text] : [];
  n.children.forEach(function (c) { out = out.concat(flat(c)); });
  return out;
}

function run(src, data, fragment) {
  // the ring buffers' page reads #libdata, the CRC page (compare-crc.js) #crcdata
  const byId = { libdata: { textContent: data }, crcdata: { textContent: data } };
  const document = {
    getElementById: function (id) { return byId[id] || (byId[id] = new Node("#" + id)); },
    createElement: function (tag) { return new Node(tag); },
    createTextNode: function (t) { const n = new Node("#text"); n.text = String(t); return n; }
  };
  const location = { hash: fragment };
  let written = null;
  const history = { replaceState: function (a, b, h) { written = h; } };
  const window = { addEventListener: function () {} };
  new Function("document", "location", "history", "window", src)(document, location, history, window);

  const table = byId["cmp-table"], thead = table.children[0], tbody = table.children[1];
  const rows = [], seps = [];
  tbody.children.forEach(function (tr) {
    if (tr.className === "sep") seps.push([rows.length, tr.children[0].textContent]);
    else rows.push(tr.children.map(flat));
  });
  return {
    hash: fragment, written: written,
    header: thead.children[0].children.map(function (th) { return th.textContent; }),
    rows: rows, seps: seps,
    count: byId["cmp-count"].textContent, src: byId["cmp-src"].textContent,
    note: byId["cmp-note"] ? byId["cmp-note"].textContent : null
  };
}

const src = read(ARGV[0]), data = read(ARGV[1]);
const chars = [];
for (let c = 32; c < 127; c++) chars.push(String.fromCharCode(c));
chars.sort(function (a, b) { return a.localeCompare(b); });
print(JSON.stringify({ ascii_order: chars.join("") }));
read(ARGV[2]).split("\n").forEach(function (line) {
  if (line !== "") print(JSON.stringify(run(src, data, line)));
});
