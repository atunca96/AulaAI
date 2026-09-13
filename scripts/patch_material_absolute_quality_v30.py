from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

anchor = "- Phonetic/transcription claims must distinguish exact facts from learner approximations; do not overstate simplified pronunciation cues as exact phonetics.\n"
extra = """- If a question tests target-language knowledge, the decisive stem/options must contain target-language evidence; do not use material-language-only options as a substitute.
- TARGET-LANGUAGE OPTION INVARIANT: if the keyed answer is a target-language word, phrase, sentence, inflected form, or cultural expression being learned as language, ALL answer options must be expressed in the target language (except genuinely language-neutral numerals/symbols). A translated gloss may appear in the stem only as support; it may never replace the target-language answer set.
- Reject MCQs solvable mainly by common sense, object-function guessing, family relations, arithmetic, stereotypes, or trivia; knowing the taught target language must be necessary.
- Reject shallow dictionary/category recall when a natural taught-language context can test the same objective. Prefer contextual comprehension or use over bare recall.
- Replace subjective claims that a language/culture is beautiful, logical, melodic, easy, hard, superior, etc. with neutral communicative examples.
- Verify the rule that CAUSES a form, not only the final answer; exceptions and indeclinables must not be justified by superficial spelling.
- MORPHOLOGICAL CAUSALITY: never infer a prefix, suffix, root boundary, derivation, etymology, or morpheme function merely from a visible letter sequence. Only give a decomposition when it is certainly valid for that lexical item.
- PHONETIC EPISTEMIC LABELING: keep exact phonetic transcription separate from learner-friendly respelling. If using a pedagogical approximation, label it explicitly and never present it as exact IPA/phonetic truth.
"""
if "TARGET-LANGUAGE OPTION INVARIANT" not in s:
    if anchor not in s:
        raise RuntimeError("v30 publication prompt anchor missing")
    s = s.replace(anchor, anchor + extra, 1)

# v30 used to run an additional model call for every page. All of those semantic
# invariants are now part of the single whole-lesson publication audit, so the
# page-by-page model loop is deliberately absent.
if "_material_page_release_audit(" in s:
    raise RuntimeError("legacy per-page release audit unexpectedly present before v30")

required = [
    "TARGET-LANGUAGE OPTION INVARIANT",
    "MORPHOLOGICAL CAUSALITY",
    "PHONETIC EPISTEMIC LABELING",
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v30 verification failed: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v30: absolute-quality invariants folded into the single publication audit")
