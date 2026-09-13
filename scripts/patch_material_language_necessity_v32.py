from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

anchor = "- Reject MCQs solvable mainly by common sense, object-function guessing, family relations, arithmetic, stereotypes, or trivia; knowing the taught target language must be necessary.\n"
rule = """- COUNTERFACTUAL LANGUAGE-NECESSITY TEST (SURGICAL): for every MCQ, mentally remove or obfuscate the target-language words/forms from stem and options while preserving the material-language scenario, real-world facts, commonsense cues and number sequence. If the keyed answer can still be identified with high confidence, rewrite the item so a previously taught target-language form, meaning, grammatical contrast or communicative function becomes decisive. Reject object-function inference, room/object commonsense, family-relation deduction, arithmetic/sequence completion, stereotypes, trivia and category guessing when external knowledge supplies the answer. Keep legitimate real-life contexts when taught language remains necessary.\n"""
if "COUNTERFACTUAL LANGUAGE-NECESSITY TEST (SURGICAL)" not in s:
    if anchor not in s:
        raise RuntimeError("v32 single-audit language-necessity anchor missing")
    s = s.replace(anchor, anchor + rule, 1)

# Performance invariant: v32 must not recreate the removed per-page semantic audit.
if "_material_page_release_audit(" in s:
    raise RuntimeError("v32 found legacy per-page audit; single-audit architecture required")
if s.count("COUNTERFACTUAL LANGUAGE-NECESSITY TEST (SURGICAL)") != 1:
    raise RuntimeError("v32 counterfactual rule must appear exactly once")

p.write_text(s, encoding="utf-8")
print("Applied v32: counterfactual language-necessity gate folded into single publication audit")
