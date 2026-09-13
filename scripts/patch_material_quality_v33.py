from pathlib import Path

root = Path(__file__).resolve().parents[1]
engine = root / "services" / "ai_engine.py"
policy = (root / "config" / "material_quality_v33.txt").read_text(encoding="utf-8").strip()
policy = "Prefer preserving acceptable wording; change content only when correctness, meaning, consistency, or assessment validity is materially affected. " + policy
s = engine.read_text(encoding="utf-8")

# Prevent residual classes at generation time without another model call.
generation_tag = "<material_quality_v33_prevention>"
if generation_tag not in s:
    anchor = "<output_schema>\n"
    if anchor not in s:
        raise RuntimeError("v33 generation insertion point missing")
    prevention = '''<material_quality_v33_prevention>
Before JSON output, silently eliminate these residual defects: accidental instructional-language leakage; missing visible symbols after naming a grapheme/mark/sign; mixed or malformed IPA/romanization/transliteration; literal translations that distort pragmatic force; unjustified absolute words such as always/never/must/only; overgeneralization from irregular or lexicalized forms; mismatched vocabulary-table columns; dialogue turns with incoherent reference, role, politeness or demonstratives. Cross-check every declarative rule against every example, table, assessment and other rule in the lesson. Distinguish productive rules from regular tendencies, restricted patterns, lexical conventions and exceptions. Scope cultural/pragmatic tendencies rather than universalizing them. Re-check every bilingual pair for exact meaning plus native naturalness. If a precise linguistic claim is uncertain, simplify it rather than inventing detail.
</material_quality_v33_prevention>

'''
    s = s.replace(anchor, prevention + anchor, 1)

# All semantic release checks live in the one whole-lesson publication audit.
publication_anchor = "MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.\n"
publication_tag = "AULAAI_MATERIAL_QUALITY_V33_PUBLICATION"
if publication_tag not in s:
    i = s.find(publication_anchor)
    if i < 0:
        raise RuntimeError("v33 publication-audit insertion point missing")
    i += len(publication_anchor)
    s = s[:i] + publication_tag + ": " + policy + "\n" + s[i:]

if "_material_page_release_audit(" in s:
    raise RuntimeError("v33 found legacy per-page semantic audit")

required = (generation_tag, publication_tag)
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v33 verification failed: " + ", ".join(missing))

engine.write_text(s, encoding="utf-8")
print("Applied v33 quality prevention + single publication-audit policy")
