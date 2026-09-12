from pathlib import Path

# Safe visual-only PDF patch. No translation calls, DB reads, runtime network work,
# or PDF content mutation. This only overrides export CSS after the stable patch.
server_path = Path("server.py")
src = server_path.read_text(encoding="utf-8")

anchor = '''.mcq-opts { margin-left: 10px; }
"""
'''
replacement = '''.mcq-opts { margin-left: 10px; }

/* AulaAI PDF visual cleanup — intentionally simple for PyMuPDF Story stability. */
.cover {
  border-bottom: 1.5px solid #6366f1;
  padding-bottom: 14px;
  margin-bottom: 14px;
}
.unit-card {
  background: transparent;
  border: none;
  border-left: 3px solid #6366f1;
  border-bottom: 0.6px solid #c7d2fe;
  padding: 5px 8px;
  margin: 16px 0 9px 0;
}
.unit-title {
  color: #312e81;
  font-size: 11.5pt;
  line-height: 1.25;
}
.topic-card {
  margin: 10px 0 14px 0;
  padding: 0;
  border: none;
  background: transparent;
}
.topic-title {
  background: transparent;
  color: #111827;
  border: none;
  border-bottom: 0.6px solid #c7d2fe;
  padding: 0 0 4px 0;
  margin: 0 0 8px 0;
  font-size: 10.5pt;
  line-height: 1.25;
}
.badge {
  background: transparent;
  color: #6366f1;
  border: none;
  padding: 0;
  margin-left: 6px;
  font-size: 6.6pt;
  vertical-align: baseline;
}
.sec-h {
  background: transparent;
  color: #4338ca;
  border: none;
  border-bottom: 0.5px solid #e5e7eb;
  padding: 0 0 2px 0;
  margin: 9px 0 5px 0;
  line-height: 1.25;
}
.text-block {
  background: transparent;
  border: none;
  border-left: 2px solid #c7d2fe;
  padding: 5px 8px;
  margin: 5px 0 8px 0;
  line-height: 1.35;
}
.cmp-box,
.mcq-box {
  background: transparent;
  border: 0.6px solid #dbeafe;
  padding: 6px 8px;
  margin: 6px 0 8px 0;
}
.mcq-box { border-color: #bbf7d0; }
.mcq-q { margin-bottom: 4px; }
.mcq-opt { margin: 2px 0; }
.mcq-expl { border-top: 0.5px solid #e5e7eb; }
.diag-line {
  display: block;
  margin: 3px 0;
  line-height: 1.35;
}
.spkr,
.said,
.said-tr { display: inline; }

table.vt {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 5px 0 9px 0;
  font-size: 7.5pt;
}
table.vt th {
  background: #eef2ff;
  color: #312e81;
  border: 0.4px solid #c7d2fe;
  padding: 4px 5px;
  line-height: 1.2;
}
table.vt td {
  background: #ffffff;
  border: 0.4px solid #e2e8f0;
  padding: 4px 5px;
  line-height: 1.25;
  overflow-wrap: anywhere;
  word-wrap: break-word;
}
table.vt tr:nth-child(even) td { background: #f8fafc; }
.term, .phon, .trans, .ex, .ex-tr {
  overflow-wrap: anywhere;
  word-wrap: break-word;
}
"""
'''

count = src.count(anchor)
if count != 1:
    raise RuntimeError(f"PDF visual CSS anchor matched {count} times")
src = src.replace(anchor, replacement, 1)
server_path.write_text(src, encoding="utf-8")
print("Applied safe visual-only PDF layout cleanup")
