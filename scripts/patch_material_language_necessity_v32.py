from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

old = "7) LANGUAGE-NECESSITY TEST: the learner must need taught {language} knowledge to answer. Reject common-sense/object-function/family-tree/arithmetic/stereotype/trivia/category-guessing questions."
new = """7) COUNTERFACTUAL LANGUAGE-NECESSITY TEST (SURGICAL): the learner must need explicitly taught {language} knowledge to identify the keyed answer. Before accepting each MCQ, mentally REMOVE OR OBFUSCATE all target-language words/forms from the stem and options while preserving the material-language scenario, real-world facts, visual/common-sense cues, and number sequence. If the keyed answer can still be identified with high confidence, the item FAILS and must be rewritten. Reject specifically: object-function inference (e.g. 'what do you write with?'), room/object commonsense (e.g. 'what is found in a bedroom?'), family-relation deduction, arithmetic or sequence completion (e.g. 9, 10, __, 12), stereotypes, trivia, and category guessing whose decisive evidence is outside the taught language. Rewrite only the defective MCQ so that the decisive evidence becomes a previously taught target-language form, meaning, grammatical contrast, or communicative function. DO NOT reject a legitimate real-life context merely because it depicts ordinary life: reject it only when world knowledge rather than taught {language} supplies the decisive answer. This test changes MCQ cognitive evidence only; it must not alter lesson content, translations, vocabulary scope, CEFR scope, distractor policy, or any non-MCQ page."""

count = s.count(old)
if count != 1:
    raise RuntimeError(f"v32 expected exactly one LANGUAGE-NECESSITY anchor, found {count}")

s = s.replace(old, new, 1)

# Verify surgical scope: only the intended contract is added.
if "COUNTERFACTUAL LANGUAGE-NECESSITY TEST (SURGICAL)" not in s:
    raise RuntimeError("v32 replacement missing")
if old in s:
    raise RuntimeError("v32 stale language-necessity contract remains")

p.write_text(s, encoding="utf-8")
print("Applied v32: surgical counterfactual language-necessity gate only")
