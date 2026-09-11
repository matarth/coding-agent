#!/usr/bin/env python3
"""
Renders docblock_report.json into a self-contained docblock_report.html
(see docblock-audit skill). The JSON is inlined into the page so it opens
directly from disk via file:// - no server, no fetch()/CORS to worry
about.

Usage: generate_report.py [path/to/docblock_report.json]
Defaults to reports/docblock_report.json next to this script; writes
reports/docblock_report.html alongside it.
"""
import json
import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Docblock audit report</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #f7f7f8; color: #1a1a1a; }
  h1 { font-size: 1.3rem; margin: 0 0 4px; }
  .meta { color: #666; font-size: 0.85rem; margin-bottom: 16px; }
  .controls { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .controls input, .controls select { padding: 6px 10px; font-size: 0.9rem; border: 1px solid #ccc; border-radius: 6px; }
  .counts { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .count-badge { padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 0.9rem; vertical-align: top; }
  th { background: #efeff1; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; color: #555; }
  tr.row { cursor: pointer; }
  tr.row:hover { background: #fafafa; }
  tr.detail { display: none; }
  tr.detail.open { display: table-row; }
  tr.detail td { background: #fbfbfc; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
  .badge-match { background: #dcf7e3; color: #1b7a3d; }
  .badge-mismatch { background: #fbdada; color: #b3261e; }
  .badge-partial { background: #fdf0c8; color: #8a6100; }
  .badge-unverifiable { background: #e5e5e8; color: #555; }
  .finding { margin-bottom: 8px; padding: 8px 10px; background: #fff; border: 1px solid #eee; border-radius: 6px; }
  .finding div { margin-bottom: 2px; }
  code { background: #f0f0f2; padding: 1px 4px; border-radius: 4px; }
  @media (prefers-color-scheme: dark) {
    body { background: #17181a; color: #e8e8ea; }
    table, .finding { background: #1f2023; }
    th { background: #232427; color: #a0a0a6; }
    td { border-bottom-color: #2b2c30; }
    tr.row:hover { background: #232427; }
    tr.detail td { background: #1a1b1d; }
    .controls input, .controls select { background: #1f2023; border-color: #3a3b3f; color: #e8e8ea; }
    code { background: #2b2c30; }
    .meta { color: #999; }
  }
</style>
</head>
<body>
<h1>Docblock audit report</h1>
<div class="meta" id="meta"></div>
<div class="counts" id="counts"></div>
<div class="controls">
  <input type="text" id="search" placeholder="Filter by file or symbol...">
  <select id="statusFilter">
    <option value="">All statuses</option>
    <option value="match">match</option>
    <option value="mismatch">mismatch</option>
    <option value="partial">partial</option>
    <option value="unverifiable">unverifiable</option>
  </select>
</div>
<table>
  <thead>
    <tr><th>File</th><th>Symbol</th><th>Status</th><th>Last checked</th></tr>
  </thead>
  <tbody id="rows"></tbody>
</table>

<script>
const REPORT = __REPORT_JSON__;

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function render() {
  const search = document.getElementById("search").value.toLowerCase();
  const statusFilter = document.getElementById("statusFilter").value;
  const entries = Object.entries(REPORT.entries || {})
    .map(([key, e]) => {
      // Entries are keyed "<file>#<symbol>" and don't repeat those as fields - derive them here.
      const sep = key.lastIndexOf("#");
      const file = sep === -1 ? key : key.slice(0, sep);
      const symbol = sep === -1 ? "" : key.slice(sep + 1);
      return { key, file, symbol, ...e };
    })
    .sort((a, b) => (a.file + a.symbol).localeCompare(b.file + b.symbol));

  const counts = {};
  for (const e of entries) counts[e.status] = (counts[e.status] || 0) + 1;
  document.getElementById("counts").innerHTML = Object.entries(counts)
    .map(([status, n]) => `<span class="count-badge badge-${status}">${status}: ${n}</span>`)
    .join("");

  const filtered = entries.filter(e => {
    if (statusFilter && e.status !== statusFilter) return false;
    if (search && !(`${e.file} ${e.symbol}`.toLowerCase().includes(search))) return false;
    return true;
  });

  const rows = document.getElementById("rows");
  rows.innerHTML = "";
  filtered.forEach((e, i) => {
    const row = document.createElement("tr");
    row.className = "row";
    row.innerHTML = `
      <td><code>${escapeHtml(e.file)}:${escapeHtml(e.line)}</code></td>
      <td>${escapeHtml(e.symbol)}</td>
      <td><span class="badge badge-${e.status}">${escapeHtml(e.status)}</span></td>
      <td>${escapeHtml((e.last_checked || "").slice(0, 10))}</td>
    `;
    const detail = document.createElement("tr");
    detail.className = "detail";
    const findingsHtml = (e.findings && e.findings.length)
      ? e.findings.map(f => `
          <div class="finding">
            <div><strong>Claim:</strong> ${escapeHtml(f.claim)}</div>
            <div><strong>Reality:</strong> ${escapeHtml(f.reality)}</div>
            <div><strong>Evidence:</strong> <code>${escapeHtml(f.evidence)}</code></div>
          </div>`).join("")
      : "<em>No findings.</em>";
    detail.innerHTML = `<td colspan="4">${findingsHtml}</td>`;
    row.addEventListener("click", () => detail.classList.toggle("open"));
    rows.appendChild(row);
    rows.appendChild(detail);
  });
}

document.getElementById("meta").textContent =
  `Generated ${REPORT.generated_at || "?"} - staleness threshold: ${REPORT.staleness_days || "?"} days - ${Object.keys(REPORT.entries || {}).length} docblocks tracked`;
document.getElementById("search").addEventListener("input", render);
document.getElementById("statusFilter").addEventListener("change", render);
render();
</script>
</body>
</html>
"""


def generate(json_path: Path, html_path: Path) -> None:
    report = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {"entries": {}}
    # Escape "</" so a finding containing e.g. a literal "</script>" can't break out of the inline <script> block.
    report_json = json.dumps(report).replace("</", "<\\/")
    html = PAGE_TEMPLATE.replace("__REPORT_JSON__", report_json)
    html_path.write_text(html, encoding="utf-8")


def main() -> None:
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPORTS_DIR / "docblock_report.json"
    html_path = json_path.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    generate(json_path, html_path)
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
