from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

old = '        digest = "\\n".join(prior)[-7000:]\n'
new = '        digest = "\\n".join(prior)[-7000:] if isinstance(page, dict) and page.get("type") == "mcq" else ""\n'
if old not in s:
    raise RuntimeError("v36 audit digest anchor missing")
s = s.replace(old, new, 1)

# The prior-taught digest is only required for MCQ grounding/language-necessity checks.
# Every page is still reviewed by the same Gemini 3.7 structural model with the same
# linguistic, translation, phonetic, CEFR and validity contract.
if 'page.get("type") == "mcq"' not in s:
    raise RuntimeError("v36 audit efficiency verification failed")

p.write_text(s, encoding="utf-8")
print("Applied v36: prior context only on MCQ release-audit calls")
