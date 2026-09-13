from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")
changes = []

# 1) Keep the proven Gemini 3.7 lesson generator and its full 8192-token ceiling.
# No generation-model or visible-content budget change is made here.

# 2) Remove duplicated planning prose from the per-topic user prompt. The same
# quality/grounding requirements already live in the system prompt via v24/v24b.
pat = re.compile(
    r'REASONING DIRECTIVE:\n.*?Then generate the complete, exhaustive JSON lesson structure\.\n\n',
    re.S,
)
s2, n = pat.subn(
    'QUALITY DIRECTIVE:\nSilently plan a coherent teach-before-test progression and enforce every system quality rule before returning JSON.\n\n',
    s,
    count=1,
)
if n:
    s = s2
    changes.append("compact-user-prompt")

# 3) For a single-language classroom, do not spend premium output tokens writing
# a second full textbook in the inactive localization track. Keep mirror fields
# present and valid for downstream compatibility, but concise. The active track
# remains complete; material_language=all remains fully bilingual.
marker = "</bilingual_pedagogical_tracks>"
policy = '''\nCOST-EFFICIENT LOCALIZATION POLICY:\n- material_language=\"tr\": Turkish pedagogical fields are the complete learner-facing lesson. Keep English mirror fields valid and non-empty, but use only direct titles/translations and at most one short sentence for English explanation/analysis/context/note/pitfall fields. Never shorten Turkish content, target-language examples, rules, dialogues, vocabulary coverage, or assessment quality.\n- material_language=\"en\": apply the same compact-mirror rule to Turkish fields while keeping English complete.\n- material_language=\"all\": keep both localization tracks complete.\n'''
if "COST-EFFICIENT LOCALIZATION POLICY" not in s and marker in s:
    s = s.replace(marker, policy + marker, 1)
    changes.append("compact-inactive-mirror")

# 4) Preserve the single publication audit, but run this secondary patch-only
# pass on Flash-Lite instead of paying Gemini 3.7 prices for each topic review.
# Main lesson generation is untouched.
a = s.find("def _material_publication_audit(")
b = s.find("\ndef generate_full_lesson(", a)
if a >= 0 and b > a:
    seg = s[a:b]
    old = seg
    seg = seg.replace("model=MODEL_STRUCTURAL,", 'model="google/gemini-2.5-flash-lite",', 1)
    seg = seg.replace("max_tokens=1800,", "max_tokens=1000,", 1)
    if seg != old:
        s = s[:a] + seg + s[b:]
        changes.append("cheap-publication-audit")

p.write_text(s, encoding="utf-8")
print("Applied final Gemini 3.7 cost pass: " + (", ".join(changes) if changes else "already applied/no compatible anchors"))
