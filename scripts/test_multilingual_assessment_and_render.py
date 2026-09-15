"""Regression tests for the assessment, phonetic-ownership, render and cost passes.

Every case here is stated in terms of a property that must hold for any target
language, and the language-specific data in it is evidence, not a rule: the
Japanese and Spanish items reproduce failures observed in production, and the
German, Russian and Arabic items exist to prove the same property holds where the
observed failure did not occur. A fix that only satisfied the reproduced cases
would pass half of this file.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.publication_invariants import (  # noqa: E402
    apply_assessment_invariants,
    apply_publication_invariants,
    collect_target_surfaces,
    iter_claim_surfaces,
    localized_options_are_publishable,
    unify_phonetic_ownership,
)

checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1


# ── A. A localized option set may not replace the contrast being tested ──────

# Observed in production: four distinct Spanish constructions became the same
# Turkish sentence four times, told apart only by a parenthetical.
check(
    not localized_options_are_publishable(
        ["Pedro es enfermero", "Pedro está de enfermero",
         "Pedro trabaja de enfermero", "Pedro hace de enfermero"],
        ["Pedro hemşiredir (ser)", "Pedro hemşiredir (estar)",
         "Pedro hemşiredir (trabajar)", "Pedro hemşiredir (hacer)"],
    ),
    "a localization that collapses four options into one must be refused",
)

# Observed in production: the te-form contrast became four Turkish converbs. The
# options stayed distinct, so distinctness alone does not catch this - the lost
# writing system does.
check(
    not localized_options_are_publishable(
        ["みて", "きいて", "よんで", "かいて"],
        ["bakıp (bakınız)", "dinleyip (dinleyiniz)",
         "okuyup (okuyunuz)", "yazıp (yazınız)"],
    ),
    "a localization that drops the target script must be refused",
)

# Not observed, and must hold anyway: same property, different script.
check(
    not localized_options_are_publishable(
        ["книга", "книги", "книге", "книгу"],
        ["kitap", "kitabın", "kitaba", "kitabı"],
    ),
    "Cyrillic option forms must not be replaced by Latin glosses",
)
check(
    not localized_options_are_publishable(
        ["كَتَبَ", "يَكْتُبُ", "اُكْتُبْ", "كِتَاب"],
        ["yazdı", "yazıyor", "yaz", "kitap"],
    ),
    "Arabic option forms must not be replaced by Latin glosses",
)

# The legitimate case must survive: when the options are explanatory prose, the
# translated prose tests exactly the same thing.
check(
    localized_options_are_publishable(
        ["It marks the direct object", "It marks the subject",
         "It marks possession", "It marks location"],
        ["Belirtme hâlini gösterir", "Özneyi gösterir",
         "İyeliği gösterir", "Yer bildirir"],
    ),
    "metalinguistic options must still be localizable",
)

# A translation that keeps the target-language evidence quoted inside the prose is
# still a faithful parallel.
check(
    localized_options_are_publishable(
        ["The ending -ите is used", "The ending -ет is used",
         "The ending -ем is used", "The ending -ут is used"],
        ["-ите eki kullanılır", "-ет eki kullanılır",
         "-ем eki kullanılır", "-ут eki kullanılır"],
    ),
    "a translation that preserves quoted target evidence is publishable",
)
check(
    not localized_options_are_publishable(
        ["The ending -ите is used", "The ending -ет is used",
         "The ending -ем is used", "The ending -ут is used"],
        ["Birinci ek", "İkinci ek", "Üçüncü ek", "Dördüncü ek"],
    ),
    "a translation that discards the quoted target evidence is not publishable",
)

check(not localized_options_are_publishable(["a", "b", "c"], ["x", "y"]),
      "a length mismatch is not a parallel option set")
check(not localized_options_are_publishable(["a", "b"], ["x", ""]),
      "an empty localized option is not a parallel option set")

# A target language sharing the instructional language's script, whose glosses
# happen to stay distinct, passes both structural checks. Only the lesson's own
# evidence shows these options are target-language forms.
german = {"pages": [
    {"type": "vocabulary", "items": [
        {"term": "der Tisch"}, {"term": "dem Tisch"},
        {"term": "des Tisches"}, {"term": "den Tisch"}]},
    {"type": "mcq", "prompt": "Welche Form ist Akkusativ?",
     "options": ["der Tisch", "dem Tisch", "des Tisches", "den Tisch"],
     "options_tr": ["masa (yalın)", "masaya", "masanın", "masayı"],
     "answer": "den Tisch"},
]}
surfaces = collect_target_surfaces(german)
check("der tisch" in surfaces, "target surfaces are collected from item terms")
check(
    not localized_options_are_publishable(
        german["pages"][1]["options"], german["pages"][1]["options_tr"], surfaces),
    "options the lesson published as target-language material are never replaced",
)

# The same lesson must still localize a genuinely metalinguistic item.
check(
    localized_options_are_publishable(
        ["It marks the direct object", "It marks the subject",
         "It marks possession", "It marks the indirect object"],
        ["Doğrudan nesneyi gösterir", "Özneyi gösterir",
         "İyeliği gösterir", "Dolaylı nesneyi gösterir"],
        surfaces,
    ),
    "same-lesson evidence must not suppress a legitimate localization",
)

# The boundary, not the renderer, is what enforces this.
japanese_mcq = {"pages": [{
    "type": "mcq", "prompt": "Which te-form is correct?", "prompt_tr": "Hangi te-biçimi doğru?",
    "options": ["みて", "きいて", "よんで", "かいて"],
    "options_tr": ["bakıp", "dinleyip", "okuyup", "yazıp"],
    "answer": "みて", "explanation_tr": "て-biçimi kuralı",
}]}
released = apply_publication_invariants(japanese_mcq, language="Japanese")
page = released["pages"][0]
check("options_tr" not in page, "the boundary removes an unpublishable option set")
check(page["options"] == ["みて", "きいて", "よんで", "かいて"],
      "the authored options survive untouched")
check(page.get("explanation_tr") == "て-biçimi kuralı",
      "removing the option set must not remove the localized rationale")

# Standalone quizzes cross the same boundary.
quiz = apply_assessment_invariants([{
    "prompt": "Which form?", "options": ["みて", "きいて", "よんで", "かいて"],
    "options_tr": ["bakıp", "dinleyip", "okuyup", "yazıp"], "answer": "みて",
}], language="Japanese")
check("options_tr" not in quiz[0], "assessment items cross the same boundary")


# ── B. One term, one transcription ───────────────────────────────────────────

japanese_phon = {"pages": [
    {"type": "vocabulary", "items": [{"term": "せんせい", "phonetic": "[seɴseː]"}]},
    {"type": "pronunciation", "items": [{"term": "せんせい", "phonetic": "[seɰ̃seː]"}]},
    {"type": "practice", "items": [
        {"term": "せんせい", "phonetic": "[seɴseː]"},
        {"term": "がくせい", "phonetic": "[ɡakɯseː]"}]},
]}
unified = unify_phonetic_ownership(json.loads(json.dumps(japanese_phon)))
values = {it["phonetic"] for p in unified["pages"] for it in p["items"]
          if it["term"] == "せんせい"}
check(len(values) == 1, "a term must carry one transcription across the lesson")
check(values == {"[seɴseː]"}, "the transcription the lesson gave most often wins")
check(unified["pages"][2]["items"][1]["phonetic"] == "[ɡakɯseː]",
      "an unconflicted term is untouched")

russian_phon = unify_phonetic_ownership({"pages": [
    {"items": [{"term": "здравствуйте", "phonetic": "[ˈzdrastvujtʲe]"}]},
    {"items": [{"term": "Здравствуйте", "phonetic": "[zdrastvujtʲɪ]"}]},
]})
russian_values = {it["phonetic"] for p in russian_phon["pages"] for it in p["items"]}
check(len(russian_values) == 1,
      "case and script folding must not hide a conflict between two surfaces")
check(russian_values == {"[ˈzdrastvujtʲe]"},
      "with no majority, the earliest occurrence owns the transcription")

untouched = unify_phonetic_ownership({"pages": [{"items": [
    {"term": "hola", "phonetic": "[ˈola]"},
    {"term": "adiós"},
    {"term": "gracias", "phonetic": ""}]}]})
items = untouched["pages"][0]["items"]
check(items[0]["phonetic"] == "[ˈola]", "a single transcription is preserved")
check("phonetic" not in items[1], "a missing transcription is never invented")
check(items[2]["phonetic"] == "", "an empty transcription is never filled in")

once = apply_publication_invariants(json.loads(json.dumps(japanese_phon)), language="Japanese")
twice = apply_publication_invariants(json.loads(json.dumps(once)), language="Japanese")
check(json.dumps(once, sort_keys=True, ensure_ascii=False)
      == json.dumps(twice, sort_keys=True, ensure_ascii=False),
      "the boundary stays idempotent with phonetic ownership applied")


# ── G. A rationale is a claim surface under any of its field names ───────────

rationale_page = {"pages": [{
    "type": "mcq", "prompt": "Q?", "options": ["a", "b", "c", "d"], "answer": "a",
    "explanation": "explanation text", "why": "why text", "why_tr": "why metni",
    "feedback": "feedback text", "rationale": "rationale text",
    "answer_explanation": "answer explanation text",
}]}
found = {s["path"].rsplit(".", 1)[-1] for s in iter_claim_surfaces(rationale_page)
         if s["kind"] == "rationale"}
for field in ("explanation", "why", "why_tr", "feedback", "rationale", "answer_explanation"):
    check(field in found, f"page-level rationale field {field} must be a claim surface")


# ── E. Script-Common marks must survive to the rendered text layer ───────────

from services.pdf_renderer_v12 import (  # noqa: E402
    CSS, MARK_FONT_FAMILY, _doc, _e, _mark_font,
)

check("†" not in _e("゛") and "‡" not in _e("゜") and "¤" not in _e("ー"),
      "marks are never swapped for placeholder characters")
check(_e("コーヒー") == "コーヒー",
      "a mark inside a word already has a font and is left alone")

font = _mark_font()
if font:
    import fitz

    def render(text):
        path, _covered = font
        css = CSS + (
            "\n@font-face { font-family: %s; src: url(%s); }"
            "\n.mark { font-family: %s; }"
            % (MARK_FONT_FAMILY, os.path.basename(path), MARK_FONT_FAMILY)
        )
        story = fitz.Story(html=_doc('<p class="p">%s</p>' % _e(text)),
                           user_css=css, archive=fitz.Archive(os.path.dirname(path)))
        buf = io.BytesIO()
        writer = fitz.DocumentWriter(buf)
        more = 1
        while more:
            device = writer.begin_page(fitz.paper_rect("a4"))
            more, _filled = story.place(fitz.Rect(40, 40, 550, 760))
            story.draw(device)
            writer.end_page()
        writer.close()
        return fitz.open("pdf", buf.getvalue())[0].get_text()

    for label, sample, expected in (
        ("standalone in parentheses", "dakuten: (゛) handakuten: (゜) uzatma: (ー)", "゛゜ー"),
        ("standalone in brackets", "Japanese uses 「ー」 for long vowels", "ー"),
        ("two marks side by side", "mark pair: 「゛゜」 end", "゛゜"),
        ("inside words", "コーヒー ケーキ サービス", "ーコ"),
        ("mixed scripts", "Türkçe Здравствуйте 中文 한국어 コーヒー 「ー」", "ー中한"),
        ("ipa untouched", "phonetic: [seɴseː] [ɡozaimasɯ̥]", "ɴɯ"),
        ("combining marks", "é á が が ü ü", "éがü"),
    ):
        rendered = render(sample)
        check("\x00" not in rendered, f"{label}: no character reaches the page as .notdef")
        check("\xa0" not in rendered, f"{label}: word spacing stays copyable")
        for ch in expected:
            check(ch in rendered, f"{label}: {ch!r} survives into the text layer")

    check(not any(ch in render("dakuten (゛)") for ch in "†‡¤"),
          "no placeholder character reaches the finished page")

# There must be exactly one escaper: the defect this file covers survived because
# there were three and only the last one ran.
renderer_source = open(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "services", "pdf_renderer_v12.py"),
    encoding="utf-8",
).read()
check(renderer_source.count("\ndef _e(value)") == 1,
      "_e must be defined exactly once, or an edit to it may not be what runs")
check("add_redact_annot" not in renderer_source,
      "the placeholder-and-stamp repair must not come back")


# ── Cost ledger records discarded spend, not just successful spend ───────────

from services import generation_cost  # noqa: E402

generation_cost.reset("test")
kept = generation_cost.record_call(
    stage=generation_cost.STAGE_LESSON, model="m", prompt_tokens=7900,
    completion_tokens=2400, cached_tokens=7600, cost=0.02, subject="Topic A")
dropped = generation_cost.record_call(
    stage=generation_cost.STAGE_LESSON, model="m", prompt_tokens=7900,
    completion_tokens=2400, cost=0.02, subject="Topic B")
generation_cost.mark_outcome(dropped, generation_cost.OUTCOME_REJECTED)
generation_cost.record_call(
    stage=generation_cost.STAGE_CLAIM_REVIEW, model="m", prompt_tokens=900,
    completion_tokens=200, cost=0.002, subject="2 claim(s)")

summary = generation_cost.summary()
check(summary["total"]["calls"] == 3, "every charged call is recorded")
check(summary["total"]["wasted_calls"] == 1, "a discarded generation is counted as waste")
check(abs(summary["total"]["wasted_cost"] - 0.02) < 1e-9, "discarded spend is attributed")
check(summary["total"]["published_lessons"] == 1, "only kept lessons count as published")
check(summary["stages"]["claim_review"]["calls"] == 1, "spend decomposes by stage")
check(summary["total"]["cached_tokens"] == 7600, "cache hits are measured, not assumed")
check(kept["outcome"] == generation_cost.OUTCOME_OK, "a kept call stays marked ok")

usage = generation_cost.extract_usage({"usage": {
    "prompt_tokens": 100, "completion_tokens": 20,
    "prompt_tokens_details": {"cached_tokens": 80, "cache_write_tokens": 12},
    "completion_tokens_details": {"reasoning_tokens": 5}}})
check(usage == {"prompt_tokens": 100, "completion_tokens": 20,
                "cached_tokens": 80, "cache_write_tokens": 12, "reasoning_tokens": 5},
      "cached, written and reasoning tokens are read from the provider response")
check(generation_cost.extract_usage({"choices": []}) is None,
      "a response with no usage block is reported as unknown, not as zero")


print(f"multilingual assessment, phonetic ownership, render and cost tests passed ({checks} checks)")
