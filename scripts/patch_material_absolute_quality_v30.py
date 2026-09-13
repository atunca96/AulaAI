from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

# Add residual failure modes to the existing final editor.
anchor = "- Phonetic/transcription claims must distinguish exact facts from learner approximations; do not overstate simplified pronunciation cues as exact phonetics.\n"
extra = """- If a question tests target-language knowledge, the decisive stem/options must contain target-language evidence; do not use material-language-only options as a substitute.
- TARGET-LANGUAGE OPTION INVARIANT: if the keyed answer is a target-language word, phrase, sentence, inflected form, or cultural expression being learned as language, ALL answer options must be expressed in the target language (except genuinely language-neutral numerals/symbols). A translated gloss may appear in the stem only as support; it may never replace the target-language answer set.
- Reject MCQs solvable mainly by common sense, object-function guessing, family relations, arithmetic, stereotypes, or trivia; knowing the taught target language must be necessary.
- Reject shallow dictionary/category recall when a natural taught-language context can test the same objective. Prefer contextual comprehension or use over 'Which word means X?' and category trivia such as 'which item is a fruit?'.
- Replace subjective claims that a language/culture is beautiful, logical, melodic, easy, hard, superior, etc. with neutral communicative examples.
- Verify the rule that CAUSES a form, not only the final answer; exceptions and indeclinables must not be justified by superficial spelling.
- MORPHOLOGICAL CAUSALITY: never infer a prefix, suffix, root boundary, derivation, etymology, or morpheme function merely from a visible letter sequence. Only give a decomposition when it is certainly valid for that lexical item. For loanwords, fossilized forms, or uncertain analyses, explain the observable pronunciation/grammar fact without inventing morphology.
- PHONETIC EPISTEMIC LABELING: keep exact phonetic transcription separate from learner-friendly respelling. Do not state a broad allophonic rule as an exact one-symbol substitution when realization depends on stress, position, neighboring sounds, speech style, or dialect. If using a pedagogical approximation, label it explicitly as approximate and never present it as exact IPA/phonetic truth.
"""
if "TARGET-LANGUAGE OPTION INVARIANT" not in s and anchor in s:
    s = s.replace(anchor, anchor + extra, 1)

helper = r'''
def _material_page_release_audit(data, language, level):
    """Focused per-page audit so long lessons cannot hide residual defects."""
    data = _material_deterministic_guard(data)
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return data
    prior = []
    system = f"""You are AulaAI's final senior proofreader for {language} CEFR {level}. Review ONE page deeply. Return ONLY JSON {{"patches":[{{"path":"pages.0.prompt","value":"replacement"}}],"remove":false}}. Paths must use the ABSOLUTE page index supplied. Fix only real defects.

NON-NEGOTIABLE RELEASE TESTS:
1) LINGUISTIC CORRECTNESS: grammar, morphology, case, agreement, valency, collocation, lexical choice, and native naturalness must all be defensible.
2) CAUSAL EXPLANATION: verify WHY a form behaves as claimed. Never invent morpheme boundaries, prefixes, suffixes, roots, derivations, etymologies, or lexical rules from spelling resemblance. A correct conclusion with a false explanation is a defect. If decomposition is uncertain, remove the decomposition and explain only the certain fact.
3) PHONETIC TRUTH: distinguish exact transcription from beginner approximation. Never turn context-sensitive allophony into a universal exact symbol replacement. Label pedagogical respelling as approximate; exact IPA-style claims must be genuinely exact enough for publication.
4) CEFR FIT: remove unnecessary specialist theory that does not help a {level} learner achieve the stated objective.
5) TRANSLATION/ENTITY FIDELITY: preserve person, number, gender where relevant, names, roles, quantities, polarity, time, place, and propositional meaning exactly.
6) MCQ GROUNDING: every tested fact must have been explicitly taught in PRIOR content, not merely seen incidentally in an example.
7) LANGUAGE-NECESSITY TEST: the learner must need taught {language} knowledge to answer. Reject common-sense/object-function/family-tree/arithmetic/stereotype/trivia/category-guessing questions.
8) TARGET-LANGUAGE OPTION INVARIANT: whenever the answer being tested is a {language} word, expression, sentence, grammatical form, or learned cultural phrase, ALL four options must themselves be in {language} (except language-neutral numerals/symbols). Never use four translated material-language meanings as the answer set. If a stem asks which {language} expression means something, the options must be actual {language} expressions.
9) ASSESSMENT VALUE: if a shallow dictionary-translation or category-recall item can be rewritten using previously taught {language} in a natural A1 context, rewrite it. Prefer comprehension/application over bare recall.
10) MCQ VALIDITY: exactly one answer, four distinct options, plausible same-category distractors, no malformed filler, no clue from option length/category/register.
11) NEUTRALITY: remove unsupported subjective claims about languages, peoples, cultures, or national character.

For an MCQ that cannot be repaired using PRIOR taught content without introducing new knowledge, set remove=true. Return surgical patches only; do not rewrite correct material for style."""
    remove = []
    for i in range(len(pages)):
        page = data["pages"][i]
        digest = "\n".join(prior)[-7000:]
        payload = json.dumps({"absolute_index": i, "prior_taught": digest, "page": page}, ensure_ascii=False, separators=(",", ":"))
        try:
            review = _call_ai([{"role":"system","content":system},{"role":"user","content":payload}], model=MODEL_STRUCTURAL, max_tokens=1700, temperature=0.0, json_mode=True, allow_fallback=False)
        except Exception as exc:
            print(f"[MATERIAL-QA-V30] page {i} skipped: {exc}")
            review = None
        if isinstance(review, dict):
            for patch in (review.get("patches") or [])[:50]:
                if isinstance(patch, dict):
                    path = str(patch.get("path") or "")
                    if path.startswith(f"pages.{i}."):
                        _apply_material_patch(data, path, patch.get("value"))
            if review.get("remove") is True and isinstance(page, dict) and page.get("type") == "mcq":
                remove.append(i)
        if isinstance(page, dict):
            title = str(page.get("title") or page.get("title_tr") or "")
            ptype = str(page.get("type") or "")
            taught = [f"P{i} {ptype} {title}"]
            if ptype == "vocabulary":
                for item in (page.get("items") or [])[:24]:
                    if isinstance(item, dict):
                        taught.append(str(item.get("term") or item.get("word") or "") + "=" + str(item.get("meaning") or item.get("translation") or item.get("translation_tr") or ""))
            for key in ("text","text_tr","rule","explanation"):
                if isinstance(page.get(key), str):
                    taught.append(page[key][:650])
            prior.append(" | ".join(taught))
    for i in reversed(remove):
        if len(data.get("pages", [])) > 3:
            data["pages"].pop(i)
    return _material_deterministic_guard(data)
'''

if "def _material_page_release_audit(" not in s:
    a = "\ndef generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language=\"tr\"):\n"
    if a not in s:
        raise RuntimeError("v30 lesson anchor missing")
    s = s.replace(a, "\n" + helper + a, 1)
else:
    # v30 is normally applied from a clean source at build time. Guard against
    # accidental double application by requiring the strengthened contract.
    pass

whole = "    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n"
page = "    lesson_dict = _material_page_release_audit(lesson_dict, language, level)\n"
if page not in s:
    if whole + whole in s:
        s = s.replace(whole + whole, whole + page + whole, 1)
    elif whole in s:
        s = s.replace(whole, whole + page, 1)
    else:
        raise RuntimeError("v30 audit call missing")

required = [
    "TARGET-LANGUAGE OPTION INVARIANT",
    "MORPHOLOGICAL CAUSALITY",
    "PHONETIC EPISTEMIC LABELING",
    "LANGUAGE-NECESSITY TEST",
    page.strip(),
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v30 verification failed: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v30: absolute page audit with linguistic causality + target-language MCQ enforcement")
