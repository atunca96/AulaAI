from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

needle = "MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.\n"
addition = """MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.

FINAL-RELEASE PRINCIPLES:
- A correct answer or final form with an incorrect explanation is still a publication defect. Verify the linguistic CAUSE, not only the conclusion.
- Never explain lexical exceptions, indeclinable words, irregular forms, pronunciation exceptions, or conventional constructions as if they followed an ordinary surface-ending rule.
- Every MCQ must be answerable primarily from taught target-language knowledge. Reject questions whose answer is really determined by common sense, object-function guessing, family relationships, arithmetic, stereotypes, trivia, or other world knowledge.
- Mere occurrence in an example does not make a form testable. The required grammar, vocabulary meaning, and carrier language must have been explicitly taught before the question.
- Prefer contextual application and comprehension over bare dictionary translation when the lesson already supplies a natural taught context.
- Phonetic/transcription claims must distinguish exact facts from learner approximations; do not overstate simplified pronunciation cues as exact phonetics.
"""
if "FINAL-RELEASE PRINCIPLES:" not in s and needle in s:
    s = s.replace(needle, addition, 1)

s = s.replace("max_tokens=1800,", "max_tokens=3200,", 1)

# One strong whole-lesson publication audit is intentional. Older builds ran it twice;
# that doubled latency without guaranteeing detection of a different error class.
call = "    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n"
while s.count(call) > 1:
    s = s.replace(call + call, call, 1)

required = {
    "final principles": "FINAL-RELEASE PRINCIPLES:" in s,
    "single audit": s.count(call) == 1,
    "full payload": "payload = payload[:26000]" not in s,
    "repair budget": "max_tokens=3200," in s,
}
missing = [name for name, ok in required.items() if not ok]
if missing:
    raise RuntimeError("v29 final material gate incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v29: one full-strength publication audit with causal/grounding checks")
