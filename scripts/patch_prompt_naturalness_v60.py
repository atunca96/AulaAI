from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
prompt_path = ROOT / "services" / "material_generation_prompt.py"
TAG = "AULAAI_PROMPT_NATURALNESS_V60"

text = prompt_path.read_text(encoding="utf-8")
if TAG not in text:
    natural_anchor = "- Prefer realistic adult situations and communicative value over decorative complexity.\n"
    natural_insert = natural_anchor + (
        "- AULAAI_PROMPT_NATURALNESS_V60: Write learner-facing prose as natural authored language, not as template narration or translated meta-commentary. "
        "State the linguistic fact directly. Do not use artificial authority framing such as 'native speakers say/use/pronounce...', "
        "'speakers whose native language is X...', or Turkish calques like 'Ana dili X olan konuşucular...' when the same fact can be stated directly.\n"
        "- Avoid filler lead-ins such as 'in practice', 'in real life', 'native speakers typically', or 'observe how native speakers...' unless the sociolinguistic identity of speakers is itself the lesson topic and materially necessary.\n"
    )
    if natural_anchor not in text:
        raise RuntimeError("natural_authenticity anchor not found")
    text = text.replace(natural_anchor, natural_insert, 1)

    bilingual_anchor = "- Do not compare target sounds to English words in Turkish fields.\n"
    bilingual_insert = bilingual_anchor + (
        "- Every Turkish learner-facing title, subtitle, section heading, table/category label, instruction, note and gloss must be idiomatic Turkish. Never emit an English duplicate heading or English pedagogical label in the Turkish track.\n"
        "- Turkish pedagogical prose must sound natively authored in Turkish; avoid literal translation patterns, bureaucratic calques, and phrases built around 'X dilinin ana dili konuşucuları'. Prefer direct forms such as 'Rusçada...', 'Günlük Rusçada...', or the concrete rule itself.\n"
    )
    if bilingual_anchor not in text:
        raise RuntimeError("bilingual anchor not found")
    text = text.replace(bilingual_anchor, bilingual_insert, 1)

    cleanliness_anchor = "- Target-language quotations/examples, proper nouns, IPA and deliberate multilingual comparisons are exempt.\n"
    cleanliness_insert = cleanliness_anchor + (
        "- Target-language dialogue/text fields must remain in the target language. Never insert English or Turkish explanatory gloss words inside a target-language utterance (for example, 'это task или exercise'); put the explanation only in the instructional-language translation/explanation field.\n"
        "- Do not justify ordinary grammar or pronunciation by invoking 'native speakers'. Describe the form, context or rule directly unless speaker identity is genuinely contrastive evidence.\n"
    )
    if cleanliness_anchor not in text:
        raise RuntimeError("instructional_cleanliness anchor not found")
    text = text.replace(cleanliness_anchor, cleanliness_insert, 1)

    final_anchor = "Verify: canonical spelling/Unicode; factual phonology and standard IPA; one pronunciation system; localized instructional language and same-language semantic MCQ options; internal counts/list/category consistency; grammatical labels/functions; rule-example consistency; CEFR proportionality; natural dialogue; and MCQ entailment/key validity.\n"
    final_insert = (
        "Verify: canonical spelling/Unicode; factual phonology and standard IPA; one pronunciation system; localized instructional language and same-language semantic MCQ options; "
        "natural non-template instructional prose with no unnecessary native-speaker authority framing; no English pedagogical headings/glosses in Turkish learner-facing fields; "
        "no instructional-language gloss inside target-language dialogue; internal counts/list/category consistency; grammatical labels/functions; rule-example consistency; CEFR proportionality; natural dialogue; and MCQ entailment/key validity.\n"
    )
    if final_anchor not in text:
        raise RuntimeError("final check anchor not found")
    text = text.replace(final_anchor, final_insert, 1)

    prompt_path.write_text(text, encoding="utf-8")

print("Applied V60 natural instructional-language prompt contract")
