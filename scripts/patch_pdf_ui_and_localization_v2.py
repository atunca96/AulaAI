from pathlib import Path

# Visual-only PDF patch. Keep pagination conservative: PyMuPDF Story can create
# large blank areas when whole text/table blocks are marked unsplittable. Only keep
# genuinely small units (question boxes and individual table/dialogue rows) intact.
server_path = Path("server.py")
src = server_path.read_text(encoding="utf-8")

anchor = '''.mcq-opts { margin-left: 10px; }
"""
'''
replacement = '''.mcq-opts { margin-left: 10px; }

/* AulaAI PDF print cleanup: neutral styling + compact natural flow. */
.cover {
  border: none;
  padding-bottom: 12px;
  margin-bottom: 14px;
}
.unit-card {
  background: transparent;
  border: none;
  border-left: 2.5px solid #64748b;
  padding: 5px 8px;
  margin: 16px 0 9px 0;
  page-break-after: avoid;
  break-after: avoid;
}
.unit-title { color: #1f2937; font-size: 11.5pt; line-height: 1.25; }
.topic-card { margin: 10px 0 14px 0; padding: 0; border: none; background: transparent; }
.topic-title {
  background: transparent;
  color: #111827;
  border: none;
  padding: 0;
  margin: 0 0 8px 0;
  font-size: 10.5pt;
  line-height: 1.25;
  page-break-after: avoid;
  break-after: avoid;
}
.badge {
  background: transparent;
  color: #64748b;
  border: none;
  padding: 0;
  margin-left: 6px;
  font-size: 6.6pt;
  vertical-align: baseline;
}
.sec-h {
  background: transparent;
  color: #374151;
  border: none;
  padding: 0;
  margin: 9px 0 5px 0;
  line-height: 1.25;
  page-break-after: avoid;
  break-after: avoid;
}
.text-block {
  background: transparent;
  border: none;
  border-left: 1.5px solid #d1d5db;
  padding: 5px 8px;
  margin: 5px 0 8px 0;
  line-height: 1.35;
  page-break-inside: auto;
  break-inside: auto;
}
.cmp-box {
  background: transparent;
  border: 0.5px solid #d1d5db;
  padding: 6px 8px;
  margin: 6px 0 8px 0;
  page-break-inside: auto;
  break-inside: auto;
}
.mcq-box {
  background: transparent;
  border: 0.5px solid #d1d5db;
  padding: 6px 8px;
  margin: 6px 0 8px 0;
  page-break-inside: avoid;
  break-inside: avoid;
}
.mcq-q { margin-bottom: 4px; }
.mcq-opts { margin-left: 10px; }
.mcq-opt { margin: 2px 0; background: transparent; border: none; }
.mcq-expl { border: none; }
.diag-line {
  display: block;
  margin: 3px 0;
  line-height: 1.35;
  page-break-inside: avoid;
  break-inside: avoid;
}
.spkr, .said, .said-tr { display: inline; }

table.vt {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 5px 0 9px 0;
  font-size: 7.5pt;
  page-break-inside: auto;
  break-inside: auto;
}
table.vt tr {
  page-break-inside: avoid;
  break-inside: avoid;
}
table.vt th {
  background: #ffffff;
  color: #1f2937;
  border: 0.4px solid #d1d5db;
  padding: 4px 5px;
  line-height: 1.2;
}
table.vt td {
  background: #ffffff;
  border: 0.4px solid #e5e7eb;
  padding: 4px 5px;
  line-height: 1.25;
  overflow-wrap: anywhere;
  word-wrap: break-word;
}
table.vt tr:nth-child(even) td { background: #ffffff; }
.term, .phon, .trans, .ex, .ex-tr { overflow-wrap: anywhere; word-wrap: break-word; }

/* Headings should stay with what follows, but content itself may flow naturally. */
.sec-h + table.vt,
.sec-h + .text-block,
.sec-h + .mcq-box,
.sec-h + .cmp-box {
  page-break-before: avoid;
  break-before: avoid;
}
"""
'''

count = src.count(anchor)
if count != 1:
    raise RuntimeError(f"PDF visual CSS anchor matched {count} times")
src = src.replace(anchor, replacement, 1)
server_path.write_text(src, encoding="utf-8")
print("Applied compact PDF flow and neutral visual cleanup")
