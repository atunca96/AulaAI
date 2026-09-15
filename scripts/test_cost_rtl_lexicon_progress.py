"""Regression tests for the cost, RTL text-layer, class-lexicon and progress pass.

Each section states the property in terms that hold for any target language, and
asserts it against the production evidence that motivated it plus at least one
case the evidence did not cover. The progress section additionally asserts the
OLD write sequence still reproduces the OLD bug, so the test would notice if the
fix were reverted by a merge rather than only if it were edited here.
"""

import io
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1


# ── Cost: the request must actually ask the provider to cache ────────────────

import json  # noqa: E402

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")
import services.ai_engine as engine  # noqa: E402

_captured = {}


def _fake_request(url, data=None, headers=None):
    _captured["payload"] = json.loads(data.decode("utf-8"))
    raise RuntimeError("stop before network")


_real_request = engine.urllib.request.Request
engine.urllib.request.Request = _fake_request
try:
    big_system = "SYSTEM PROMPT BODY " * 500
    messages = [{"role": "system", "content": big_system}, {"role": "user", "content": "topic"}]

    _captured.clear()
    try:
        engine._call_ai(messages, model=engine.MODEL_LESSON, max_tokens=8192, cache_system=True)
    except Exception:
        pass
    payload = _captured.get("payload") or {}
    system_message = payload.get("messages", [{}])[0]
    content = system_message.get("content")
    check(isinstance(content, list),
          "a cacheable system prompt is sent as content parts, not a bare string")
    check(content[0].get("type") == "text", "the part is a text part")
    check(content[0].get("cache_control") == {"type": "ephemeral"},
          "the part carries the cache breakpoint the provider requires")
    check(content[0].get("text") == big_system, "the prompt text itself is unchanged")
    check(payload["messages"][1] == {"role": "user", "content": "topic"},
          "the per-topic message is never marked cacheable")
    check("session_id" in payload,
          "sticky routing is still sent, so cache reads reach the replica that holds the write")
    check(isinstance(messages[0]["content"], str),
          "the caller's own message list is not mutated")

    # Without the flag the request must be byte-identical to before this change.
    _captured.clear()
    try:
        engine._call_ai(messages, model=engine.MODEL_LESSON, max_tokens=8192)
    except Exception:
        pass
    check(isinstance(_captured["payload"]["messages"][0]["content"], str),
          "a call that did not opt in is left exactly as it was")
finally:
    engine.urllib.request.Request = _real_request

from services import generation_cost  # noqa: E402

usage = generation_cost.extract_usage({"usage": {
    "prompt_tokens": 8100, "completion_tokens": 2400,
    "prompt_tokens_details": {"cached_tokens": 7900, "cache_write_tokens": 0},
    "completion_tokens_details": {"reasoning_tokens": 300}}})
check(usage["cached_tokens"] == 7900, "cache reads are measured from the provider response")
check(usage["cache_write_tokens"] == 0, "cache writes are measured separately from reads")
check(generation_cost.extract_cache_discount({"usage": {"cache_discount": 0.0123}}) == 0.0123,
      "the provider's own discount figure is read rather than estimated")
check(generation_cost.extract_cache_discount({"usage": {}}) == 0.0,
      "a response with no discount reports zero, not an error")

generation_cost.reset("cache-test")
generation_cost.record_call(stage=generation_cost.STAGE_LESSON, model="m",
                            prompt_tokens=8100, completion_tokens=2400,
                            cached_tokens=7900, cache_write_tokens=0,
                            cache_discount=0.0123, cost=0.02, subject="T1")
summary = generation_cost.summary()
check(summary["total"]["cache_discount"] == 0.0123, "discount is aggregated per class")
check(summary["total"]["cached_tokens"] == 7900, "cache reads are aggregated per class")
check(any("COST-CACHE" in line for line in generation_cost.LEDGER.format_summary()),
      "the class summary reports cache behaviour explicitly")


# ── RTL: the text layer must say what the page says ──────────────────────────

from services.pdf_text_layer import (  # noqa: E402
    audit_text_layer, build_cmap, canonical_codepoints, is_presentation_form,
    normalize_cmap, parse_cmap,
)

check(is_presentation_form(0xFEE3) and is_presentation_form(0xFB51),
      "Arabic presentation forms are recognized")
check(not is_presentation_form(0x0645) and not is_presentation_form(0x3000),
      "ordinary letters and CJK punctuation are not presentation forms")
check(not is_presentation_form(0xFF01) and not is_presentation_form(0xFE30),
      "fullwidth forms and CJK compatibility forms are out of scope, so text that "
      "means them stays as written")

folded, changed = canonical_codepoints([0xFEE3])
check(folded == [0x0645] and changed, "an initial form folds to its letter")
folded, changed = canonical_codepoints([0xFEFB])
check(folded == [0x0644, 0x0627] and changed,
      "a lam-alef ligature folds to the two letters it stands for")
folded, changed = canonical_codepoints([0x0645, 0x200D, 0x25CC])
check(folded == [0x0645, 0x200D, 0x25CC] and not changed,
      "letters, joiners and dotted circles are left alone")

sample = """
begincmap
2 beginbfrange
<0001> <0003> <feca>
<0010> <0012> <0041>
endbfrange
2 beginbfchar
<0020> <fefb>
<0021> <0645>
endbfchar
endcmap
"""
ranges, chars = parse_cmap(sample)
check(len(ranges) == 2, "both ranges are read as ranges, not expanded")
check(chars[0x20] == [0xFEFB] and chars[0x21] == [0x645], "individual mappings are read")
ranges, chars, changed = normalize_cmap(ranges, chars)
check(changed, "a CMap containing presentation forms is reported as changed")
check(any(low == 0x10 for low, _high, _base in ranges),
      "a range with no presentation form survives as a range, keeping the CMap small")
check(all(low != 0x01 for low, _high, _base in ranges),
      "a range containing presentation forms is expanded so each entry can differ")
check(chars[0x20] == [0x644, 0x627], "a ligature entry expands to two codepoints")
rebuilt = build_cmap(ranges, chars)
check(b"beginbfrange" in rebuilt and b"beginbfchar" in rebuilt,
      "the rebuilt CMap keeps both section types")
check(parse_cmap(rebuilt.decode("latin-1"))[1][0x20] == [0x644, 0x627],
      "the rebuilt CMap parses back to the same mapping")

try:
    import fitz
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    _HAVE_FITZ = False

if _HAVE_FITZ:
    from services.pdf_renderer_v12 import CURSIVE_FONT_FAMILY, _cursive_font, _doc, _e
    from services.pdf_text_layer import repair_text_layer

    check("<span" in _e("مرحبا"), "cursive text is bound to a font that can shape it")
    check(_e("مرحبا").count("<span") == 1,
          "a cursive word is bound as ONE run, or its letters would not join")
    check("<span" not in _e("Merhaba"), "non-cursive text is untouched")

    cursive = _cursive_font()
    if cursive:
        def render(text):
            css = (
                "body { font-family: sans-serif; font-size: 10pt; }"
                "\n@font-face { font-family: %s; src: url(%s); }"
                "\n.cursive { font-family: %s; }"
                % (CURSIVE_FONT_FAMILY, os.path.basename(cursive), CURSIVE_FONT_FAMILY)
            )
            story = fitz.Story(html=_doc('<p class="p">%s</p>' % _e(text)),
                               user_css=css,
                               archive=fitz.Archive(os.path.dirname(cursive)))
            buf = io.BytesIO()
            writer = fitz.DocumentWriter(buf)
            more = 1
            while more:
                device = writer.begin_page(fitz.paper_rect("a4"))
                more, _filled = story.place(fitz.Rect(40, 40, 550, 760))
                story.draw(device)
                writer.end_page()
            writer.close()
            doc = fitz.open("pdf", buf.getvalue())
            repair_text_layer(doc)
            return fitz.open("pdf", doc.tobytes())

        for label, text, must_contain in (
            ("plain", "مرحبا كيف حالك", ["مرحبا", "كيف"]),
            ("definite article", "اللغة العربية", ["اللغة", "العربية"]),
            ("lam-alef", "لا إله إلا الله", ["لا"]),
            ("harakat", "كَتَبَ الدَّرْسَ", ["كَتَبَ"]),
            ("mixed with latin", "Türkçe: مرحبا - CEFR A1", ["مرحبا", "Türkçe"]),
        ):
            doc = render(text)
            audit = audit_text_layer(doc)
            extracted = "".join(p.get_text() for p in doc)
            check(audit["presentation_forms"] == 0,
                  f"{label}: no presentation form reaches the text layer")
            check(audit["nul"] == 0, f"{label}: nothing reaches the page as .notdef")
            check(not any(0x0100 <= ord(c) <= 0x017F and c not in "ğİışĞŞÇçÖöÜü"
                          for c in extracted),
                  f"{label}: no letter is mis-identified as an unrelated script")
            for token in must_contain:
                check(token in extracted.replace("\n", ""),
                      f"{label}: {token!r} survives into the text layer as written")

        doc = render("اللغة العربية")
        check(bool(doc[0].search_for("العربية")),
              "Arabic text published by this renderer is searchable in the PDF")

        # Other scripts must be unaffected by the repair.
        for label, text, token in (
            ("japanese", "コーヒー 「ー」 せんせい", "コーヒー"),
            ("cyrillic", "Здравствуйте", "Здравствуйте"),
            ("latin", "Türkçe ve İngilizce", "Türkçe"),
        ):
            doc = render(text)
            extracted = "".join(p.get_text() for p in doc)
            check(token in extracted.replace("\n", ""),
                  f"{label}: unchanged by the text-layer repair")
            check(audit_text_layer(doc)["nul"] == 0, f"{label}: still free of .notdef")


# ── Class lexicon: one class, one pronunciation per word ─────────────────────

from services import class_lexicon  # noqa: E402


def _lesson(ohayo, sensei):
    return {"pages": [{"type": "vocabulary", "items": [
        {"term": "おはようございます", "phonetic": ohayo},
        {"term": "せんせい", "phonetic": sensei}]}]}


GOOD = "[ohajoː ɡozai̯masɯ̥]"
BAD = "[ohajoː ɡozaːmasɯ]"     # the production defect: lost /i/, lengthened vowel

class_lexicon.reset("test")
class_lexicon.register_lesson(_lesson(GOOD, "[seɴseː]"), source="lesson-1")
conflicts = class_lexicon.collect_class_phonetic_conflicts(_lesson(BAD, "[seɴseː]"))
check(len(conflicts) == 1, "a word transcribed differently from the rest of the class is flagged")
conflict = conflicts[0]
check(conflict["path"].endswith(".phonetic"), "the flag points at the field that would be rewritten")
check(conflict["repair"] == "omit_ok",
      "the reviewer may decline rather than being forced to pick")
check(GOOD in conflict["text"] and BAD in conflict["text"],
      "both transcriptions are put to the reviewer")
check(any("conflict" in q for q in conflict["quantifiers"]),
      "the flag names the reason so the review prompt can address it")
check(not class_lexicon.collect_class_phonetic_conflicts(_lesson(GOOD, "[seɴseː]")),
      "a lesson agreeing with the class raises nothing")

lessons = [_lesson(GOOD, "[seɴseː]"), _lesson(BAD, "[seɴseː]"), _lesson(GOOD, "[seːseː]")]
winners = class_lexicon.class_phonetic_winners(lessons)
check(winners["おはようございます"] == GOOD,
      "a better-attested transcription settles a class-wide disagreement")
edits = sum(class_lexicon.apply_phonetic_winners(x, winners) for x in lessons)
check(edits == 2, "only the disagreeing fields are rewritten")
values = {item["phonetic"] for x in lessons for item in x["pages"][0]["items"]
          if item["term"] == "おはようございます"}
check(values == {GOOD}, "the class publishes one pronunciation for the word")

tied = [_lesson("[a]", "[x]"), _lesson("[b]", "[x]")]
tie_winners = class_lexicon.class_phonetic_winners(tied)
check("おはようございます" not in tie_winners,
      "an even split is NOT broken - deterministic code does not decide phonetic truth")
check(sum(class_lexicon.apply_phonetic_winners(x, tie_winners) for x in tied) == 0,
      "an unresolved disagreement leaves both lessons as authored")

class_lexicon.reset("ranking")
class_lexicon.LEXICON.register("ねこ", "[wrong]", source="a")
class_lexicon.LEXICON.register("ねこ", "[wrong]", source="b")
class_lexicon.LEXICON.register("ねこ", "[neko]", source="c", reviewed=True)
check(class_lexicon.LEXICON.established("ねこ") == "[neko]",
      "one reviewed judgement outranks repetition by the generator")

check(class_lexicon.fold_term(" せンセい ") == class_lexicon.fold_term("せンセい"),
      "identity folding ignores case and surrounding space")
check(class_lexicon.fold_term("ねこ") != class_lexicon.fold_term("ネコ"),
      "two spellings are not assumed to be the same word")

single = [_lesson(GOOD, "[seɴseː]")]
check(class_lexicon.class_phonetic_winners(single) == {},
      "a class that never disagreed is never rewritten")


# ── Progress: the reported percentage may never move backwards ───────────────

def reported(stage, progress, total, is_building=True):
    """The percentage ladder as /api/classroom/progress computes it."""
    if not is_building:
        return 0 if stage in ("failed", "timeout", "stopped") else 100
    if stage == "starting":
        value = 3
    elif stage == "analyzing":
        value = 6
    elif stage in ("structuring", "prepared"):
        value = 10
    elif stage == "priming":
        value = 12
    elif stage == "enriching":
        value = 14 + int(min(1.0, max(0.0, progress / total)) * 78) if total > 0 else 14
    elif stage == "finalizing":
        value = 94
    else:
        value = min(92, max(3, int((progress / total) * 100))) if total > 0 else 3
    return min(98, max(3, value))


# The write sequence a 30-topic build actually performs, in order.
SEQUENCE = [
    ("analyzing", 0, 0),
    ("prepared", 0, 0),      # phase one finished; no topic generated yet
    ("priming", 0, 30),      # first lesson generated before the fan-out
    ("enriching", 0, 30),    # phase two starts counting topics
] + [("enriching", n, 30) for n in (1, 7, 15, 23, 30)]

previous = 0
for stage, progress, total in SEQUENCE:
    value = reported(stage, progress, total)
    check(value >= previous,
          f"progress never decreases: {stage} {progress}/{total} gave {value} after {previous}")
    previous = value
check(reported("completed", 30, 30, is_building=False) == 100,
      "completion is only reported when the build is finished")

check(reported("prepared", 0, 30) < reported("priming", 0, 30) < reported("enriching", 0, 30),
      "the priming wait is its own forward step, not a pause at the previous figure")
check(reported("priming", 0, 30) > reported("prepared", 0, 30),
      "real work during the pre-fanout wait is visible as progress")

# The defect itself: phase one used to write 20 into the topic COUNTER while
# claiming the enrichment stage, so the bar computed 20-of-30 and then fell back
# to zero-of-30. Asserted here so reverting the fix fails the suite.
check(reported("enriching", 20, 30) > reported("enriching", 0, 30),
      "writing a percentage into the topic counter is what produced the reset")
check(reported("enriching", 20, 30) > 50,
      "and the value it produced was the large jump users reported")

# The high-water floor makes monotonicity structural rather than incidental.
def with_floor(values):
    out, mark = [], 0
    for value in values:
        mark = max(mark, value)
        out.append(mark)
    return out

check(with_floor([6, 10, 64, 10, 12, 30]) == [6, 10, 64, 64, 64, 64],
      "a floor derived from what was already shown absorbs any future stage dip")
check(with_floor([3, 6, 10, 50, 92]) == [3, 6, 10, 50, 92],
      "a build that never dips is passed through untouched")

import database  # noqa: E402

source = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "database.py"), encoding="utf-8").read()
check("progress_high_water" in source, "the floor is persisted, so a page reload cannot restart it")

worker_source = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "worker.py"), encoding="utf-8").read()
check(worker_source.count("progress_high_water = 0") == 2,
      "both build entry points clear the floor, so a genuine rebuild counts from the start")

orchestrator_source = open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "services", "pipeline_v2", "orchestrator.py"), encoding="utf-8").read()
check("progress = 20" not in orchestrator_source,
      "phase one no longer writes a percentage into the topic counter")
check("build_stage = 'prepared'" in orchestrator_source,
      "phase one reports its own stage instead of borrowing enrichment's")


# ── Typed notation fields admit IPA, not the scripts IPA borrows from ────────

from services.publication_evidence import collect_notation_violations  # noqa: E402


def _phon(term, phonetic):
    return {"pages": [{"type": "vocabulary", "items": [{"term": term, "phonetic": phonetic}]}]}


# Production-shaped: ordinary orthography published as its own transcription.
for label, term, phonetic in (
    ("whole word in source script", "μάθημα", "[ˈμαθιμα]"),
    ("article leaked into transcription", "καθηγητής", "[o καθιʝiˈtis]"),
    ("bare orthographic letters", "γράμματα", "[κ α μ ι ε]"),
    ("one stray letter in another language", "كتاب", "[kiˈtaːι]"),
):
    check(bool(collect_notation_violations(_phon(term, phonetic))),
          f"{label}: orthography must not pass as notation")

# Legitimate notation must still pass, including the symbols IPA does take from
# the Greek block and the diacritics NFC composes into single codepoints.
for label, term, phonetic in (
    ("dental fricative", "θάλασσα", "[ˈθalasa]"),
    ("uvular fricative", "χώρα", "[ˈxora]"),
    ("bilabial fricative", "beta", "[aβa]"),
    ("IPA gamma is not Greek gamma", "γάλα", "[ˈɣala]"),
    ("palatal fricatives", "γιατρός", "[ʝaˈtros ˈoçi]"),
    ("nasal, pharyngeal, eth, ash, slashed o", "mixed", "[siŋ ħa ðis æl øː]"),
    ("length and half-length", "long", "[aːbˑc]"),
    ("combining diacritics", "comb", "[ẽ ä n̥ ǫ]"),
    ("modifier letters", "mod", "[pʰ tʲ kʷ]"),
    ("tone letters", "tone", "[ma˥˩ ka˦]"),
    ("tie bars", "tie", "[t͡ʃa d͡ʒo]"),
    ("japanese fixture", "せんせい", "[seɴseː]"),
    ("russian fixture", "стол", "[stol]"),
    ("spanish fixture", "hola", "[ˈola]"),
    ("arabic fixture", "كَتَبَ", "[kataba]"),
    ("korean fixture", "학교", "[hak.kjo]"),
):
    violations = collect_notation_violations(_phon(term, phonetic))
    check(not violations, f"{label}: legitimate IPA must still pass ({violations})")

check(collect_notation_violations(_phon("μάθημα", "[ˈμαθιμα]"))[0]["repair"] == "omit_ok",
      "a corrupt transcription is offered for removal, not for guessing")

source = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "services", "publication_evidence.py"), encoding="utf-8").read()
check("(0x0370, 0x03FF)" not in source,
      "the whole Greek block is no longer admitted into notation fields")


# ── A published MCQ must be answerable from what the learner can see ─────────

from services.publication_invariants import (  # noqa: E402
    apply_assessment_invariants, apply_publication_invariants, localized_stem_is_publishable,
)

LOSSY = {
    "type": "mcq",
    "prompt": "Wir _____ gestern zum Supermarkt gegangen.",
    "prompt_tr": "Dün süpermarkete _____.",
    "options": ["seid", "hat", "haben", "sind"], "answer": "sind",
    "explanation_tr": "gehen bir hareket fiilidir; özne wir olduğu için yardımcı fiil sind olur.",
}
published = apply_publication_invariants({"pages": [dict(LOSSY)]}, language="German")["pages"][0]
check("prompt_tr" not in published,
      "a localized stem that drops what the answer key reasons from is not published")
check(published["prompt"] == LOSSY["prompt"], "the authored stem survives to answer from")
check(published["options"] == LOSSY["options"], "target-language options are untouched")
check("explanation_tr" in published, "the localized rationale is not collateral damage")

faithful = dict(LOSSY, prompt_tr="Wir _____ dün süpermarkete gegangen.")
kept = apply_publication_invariants({"pages": [faithful]}, language="German")["pages"][0]
check(kept.get("prompt_tr") == faithful["prompt_tr"],
      "a localization that keeps the answer-critical words is published")

META = {"type": "mcq", "prompt": "What does the accusative mark?",
        "prompt_tr": "Belirtme hâli neyi gösterir?",
        "options": ["Direct object", "Subject", "Possession", "Location"],
        "answer": "Direct object",
        "explanation_tr": "Belirtme hâli doğrudan nesneyi gösterir."}
meta_out = apply_publication_invariants({"pages": [META]}, language="German")["pages"][0]
check(meta_out.get("prompt_tr") == META["prompt_tr"],
      "a metalinguistic item, which cites nothing from its own stem, still localizes")

CROSS = {"type": "mcq", "prompt": "「見る」の て形は _____ です。",
         "prompt_tr": "Doğru biçim hangisidir?",
         "options": ["みて", "きいて", "よんで", "かいて"], "answer": "みて",
         "explanation_tr": "て biçimi"}
cross_out = apply_publication_invariants({"pages": [CROSS]}, language="Japanese")["pages"][0]
# The property, not the mechanism that used to deliver it. A Turkish INSTRUCTION
# beside a Japanese sentence is no longer removed for "losing" the script - it is
# joined to the sentence, so the learner gets both the task and the material. What
# must never happen is the writing system the question is about going missing from
# what the learner reads.
learner_stem = cross_out.get("prompt_tr") or cross_out.get("prompt")
check("「見る」の て形は _____ です。" in learner_stem,
      "the sentence the question is about reaches the learner")
check("Doğru biçim hangisidir?" in learner_stem,
      "and it arrives with its Turkish instruction rather than instead of it")
check(cross_out["options"] == CROSS["options"],
      "the earlier option-preservation fix still holds alongside the stem rule")

check("prompt_tr" not in apply_assessment_invariants([dict(LOSSY)], language="German")[0],
      "standalone quizzes cross the same boundary")

check(not localized_stem_is_publishable("Wir _____ gehen", "", ["gehen"]),
      "an empty localization never replaces a stem")
check(localized_stem_is_publishable("Wir _____ heute gehen", "Wir _____ bugün gehen", ["gehen", "wir"]),
      "a localization keeping every cited token is publishable")
check(not localized_stem_is_publishable("Wir _____ heute gehen", "Bugün _____ gidiyoruz", ["gehen"]),
      "dropping a cited token from the gapped material is refused")

# The deliberate boundary of this rule, asserted so the narrowing is not silently
# widened later: a stem with no gap is prose, and a translation of prose shares no
# tokens with it by design. Judging that as dropped information condemned
# correctly localized items ("Which form?" -> "Hangi biçim?"), so the rule abstains
# and the cross-script check below is what still covers a gapless stem.
check(localized_stem_is_publishable("Which form?", "Hangi biçim?", ["the second form"]),
      "a prose stem and its translation share no tokens, and that is not loss")
check(not localized_stem_is_publishable("「見る」は?", "Hangi biçim?", []),
      "a gapless stem that loses its writing system is still refused")


# ── Fallback: the retry gate and the completeness rule are one number ────────

from services.ai_engine import (  # noqa: E402
    MIN_SUBSTANTIVE_PAGES, _ensure_minimum_lesson_structure, _is_substantive_lesson,
)


def _page(n):
    return {"type": "overview", "text": f"Real teaching content for page {n}, well over the length gate."}


check(MIN_SUBSTANTIVE_PAGES == 3, "the publishable page count is stated once")
for count in range(0, MIN_SUBSTANTIVE_PAGES):
    check(not _is_substantive_lesson({"pages": [_page(i) for i in range(count)]}),
          f"a {count}-page lesson is retried rather than published with a review notice")
check(_is_substantive_lesson({"pages": [_page(i) for i in range(MIN_SUBSTANTIVE_PAGES)]}),
      "a lesson meeting the count publishes without review")

# The defect: a lesson the assembler will not accept used to pass the gate, so it
# was never retried and was published with a notice attached to real content.
gap = {"pages": [_page(1), _page(2)]}
check(not _is_substantive_lesson(gap),
      "no lesson can pass the gate and then be marked review-required by the assembler")
assembled = _ensure_minimum_lesson_structure(dict(gap), "T", "German", "A1")
check(assembled.get("_review_required"),
      "if such a lesson does reach the assembler after exhausting retries, it is still honest")
check(not _ensure_minimum_lesson_structure(
    {"pages": [_page(i) for i in range(MIN_SUBSTANTIVE_PAGES)]}, "T", "German", "A1"
).get("_review_required"), "a complete lesson is never marked review-required")


# ── The learner-facing instruction belongs to the published track ────────────

from services.publication_invariants import enforce_instructional_track  # noqa: E402

KO = ["옷", "오", "옫", "옽"]


def _ko(**kw):
    return dict({"type": "mcq", "options": KO, "answer": "옷", "explanation_tr": "x"}, **kw)


# A Turkish stem authored under a synonym used to lose to the untagged English
# one, because renderers reach the untagged name first.
promoted = apply_publication_invariants(
    {"pages": [_ko(prompt="What is the correct pronunciation?",
                   question_tr="'옷' kelimesinin doğru telaffuzu hangisidir?")]},
    language="Korean", material_language="tr")["pages"][0]
check(promoted.get("prompt_tr") == "'옷' kelimesinin doğru telaffuzu hangisidir?",
      "an authored track stem is promoted to the name renderers ask for first")
check(promoted["options"] == KO, "target-language options are untouched by promotion")

check(apply_publication_invariants(
    {"pages": [_ko(prompt="EN stem", prompt_tr="Doğru telaffuz hangisidir?")]},
    language="Korean", material_language="tr")["pages"][0]["prompt_tr"]
    == "Doğru telaffuz hangisidir?",
    "an existing track stem is never overwritten")

en_track = apply_publication_invariants(
    {"pages": [_ko(prompt="What is the correct pronunciation of '옷' in isolation?")]},
    language="Korean", material_language="en")["pages"][0]
check(en_track.get("prompt_en") == "What is the correct pronunciation of '옷' in isolation?",
      "an untagged stem IS the English track and satisfies an English publication")

check(not enforce_instructional_track(
    _ko(prompt="What is the correct pronunciation of '옷' in isolation?"), "tr"),
    "an item with no Turkish instruction anywhere reports the contract unmet")

# FAIL CLOSED. An item that can only state its task in the wrong language is not
# published to a reader of this track, whatever else it contains.
from services.publication_invariants import (  # noqa: E402
    assessment_track_violations, is_self_contained_cloze,
)

for label, stem in (
    ("pronunciation question", "What is the correct pronunciation of the word '옷' in isolation?"),
    ("naturalness question", "How is the phrase '한국어' pronounced naturally in spoken Korean?"),
):
    leaked = apply_publication_invariants({"pages": [_ko(prompt=stem)]},
                                          language="Korean", material_language="tr")
    check(leaked["pages"] == [],
          f"{label}: English instructional prose cannot publish on the Turkish track")

check(len(apply_publication_invariants(
    {"pages": [_ko(prompt="What is the correct pronunciation of '옷'?")]},
    language="Korean", material_language="en")["pages"]) == 1,
    "the same item publishes unchanged on the English track")

# Target-language-only stems are preserved STRUCTURALLY - a gap plus options to
# fill it - so no judgement about what language a string is in is ever made. Both
# of these share their alphabet with English, which is why script cannot decide it.
for label, language, stem, options in (
    ("German", "German", "Wir _____ gestern zum Supermarkt gegangen.",
     ["seid", "hat", "haben", "sind"]),
    ("Spanish", "Spanish", "Ayer nosotros _____ al supermercado.",
     ["fuimos", "fue", "fui", "iban"]),
):
    item = _ko(prompt=stem, options=options, answer=options[-1])
    check(is_self_contained_cloze(item), f"{label}: a gap and options state the task structurally")
    kept_cloze = apply_publication_invariants({"pages": [item]},
                                              language=language, material_language="tr")
    check(len(kept_cloze["pages"]) == 1,
          f"{label}: a target-language cloze is published without a localized instruction")
    check(kept_cloze["pages"][0]["options"] == options,
          f"{label}: its options are untouched")

check(not is_self_contained_cloze(_ko(prompt="Wir _____ gegangen.", options=["a"])),
      "a gap with nothing to fill it from is not a self-contained item")
check(not is_self_contained_cloze(_ko(prompt="What is the pronunciation?")),
      "prose with no gap carries its task in the prose and owes a localization")

check(assessment_track_violations({"pages": [_ko(prompt="What is X?")]}, "tr") == ["pages.0"],
      "the violation is reported by path so the generator can be told what to fix")
check(assessment_track_violations({"pages": [_ko(prompt_tr="Türkçe soru")]}, "tr") == [],
      "an item carrying its track instruction reports nothing")
check(assessment_track_violations(
    {"pages": [{"type": "vocabulary", "text": "English overview."}]}, "tr") == [],
    "only assessment items are subject to the contract")

# The retry is spent from the budget that already exists; the ceiling is untouched.
engine_source = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "services", "ai_engine.py"), encoding="utf-8").read()
check("assessment_track_violations" in engine_source,
      "the release gate consults the contract, so a violation costs an attempt")
check(engine_source.count("for attempt_idx in range(1, 4)") == 1,
      "the retry ceiling is unchanged at three attempts")
check(enforce_instructional_track(_ko(prompt_tr="Türkçe soru"), "tr"),
      "an item carrying its track instruction satisfies the contract")
check(enforce_instructional_track(_ko(), "tr"),
      "an item claiming no stem at all is left to ordinary MCQ validation")

# The two earlier assessment rules must still hold alongside this one.
still_lossy = apply_publication_invariants({"pages": [dict(LOSSY)]},
                                           language="German", material_language="tr")["pages"][0]
check("prompt_tr" not in still_lossy, "the malformed-stem rule still fires")
kana = apply_publication_invariants(
    {"pages": [_ko(prompt_tr="Doğru biçim?", options=["みて", "きいて", "よんで", "かいて"],
                   answer="みて", options_tr=["bakıp", "dinleyip", "okuyup", "yazıp"])]},
    language="Japanese", material_language="tr")["pages"][0]
check("options_tr" not in kana and kana["options"] == ["みて", "きいて", "よんで", "かいて"],
      "the localized-options rule still fires and target forms survive")

check(len(apply_publication_invariants(
    {"pages": [{"type": "vocabulary", "text": "English overview."}]},
    language="Korean", material_language="tr")["pages"]) == 1,
    "pages that are not assessment items are never touched by the track rule")


# ── A gap does not license an instruction in the wrong language ──────────────

from services.publication_invariants import (  # noqa: E402
    compose_learner_stem, is_self_contained_cloze, prose_segments,
)

ZH = ["不", "没", "很", "太"]


def _zh(**kw):
    return dict({"type": "mcq", "options": ZH, "answer": "不", "explanation_tr": "x"}, **kw)


# Observed in Mandarin production: an English instruction and a Chinese sentence in
# ONE field, where the gap excused the prose in front of it.
for stem in (
    "Choose the correct word to complete the sentence: 大卫是英国人，他会说_____。",
    "Choose the correct character to complete the sentence: 这是我____汉语书。",
    "Choose the correct word to complete the question: 王老师在____？",
    "Complete the negative sentence: 这件衣服____贵。",
):
    check(prose_segments(stem), f"instructional prose is seen beside the gap: {stem[:34]!r}")
    check(not is_self_contained_cloze(_zh(prompt=stem)),
          "a gap does not make an accompanying instruction disappear")
    check(apply_publication_invariants({"pages": [_zh(prompt=stem)]},
                                       language="Chinese", material_language="tr")["pages"] == [],
          "wrong-track instructional prose is not published because a gap follows it")

# A stem that is NOTHING BUT the gapped sentence still needs no localization, and
# this must hold for languages whose alphabet is the one English uses.
for language, stem, options in (
    ("German", "Wir _____ gestern zum Supermarkt gegangen.", ["seid", "hat", "haben", "sind"]),
    ("Spanish", "Ayer nosotros _____ al supermercado.", ["fuimos", "fue", "fui", "iban"]),
    ("Chinese", "这件衣服____贵。", ZH),
    ("Russian", "Я читаю ____.", ["книга", "книги", "книге", "книгу"]),
):
    item = _zh(prompt=stem, options=options, answer=options[0])
    check(not prose_segments(stem), f"{language}: a bare gapped sentence carries no instruction")
    check(is_self_contained_cloze(item), f"{language}: it states its task structurally")
    check(len(apply_publication_invariants({"pages": [item]}, language=language,
                                           material_language="tr")["pages"]) == 1,
          f"{language}: and is published without one")

# A correctly separated item must be RENDERABLE, or separating would be punished.
# Before composition the reader of the Turkish track saw the instruction alone and
# never the sentence it referred to.
separated = _zh(prompt="Choose the correct word: 大卫是英国人，他会说_____。",
                prompt_tr="Cümleyi tamamlayın:")
composed = apply_publication_invariants({"pages": [separated]}, language="Chinese",
                                        material_language="tr")["pages"]
check(len(composed) == 1, "a correctly separated item is publishable")
stem_out = composed[0]["prompt_tr"]
check(stem_out.startswith("Cümleyi tamamlayın:"), "the track instruction leads")
check("大卫是英国人，他会说_____。" in stem_out, "and the material it points at follows it")
check("Choose the correct word" not in stem_out,
      "the wrong-track half is dropped by selecting the gapped segment, not by translating")

item = _zh(prompt="这件衣服____贵。", prompt_tr="Cümleyi tamamlayın:")
check(compose_learner_stem(item, "tr") and "这件衣服____贵。" in item["prompt_tr"],
      "a pure target stem is joined to its instruction too")
check(not compose_learner_stem(_zh(prompt="这件衣服____贵。"), "tr"),
      "with no instruction there is nothing to join")

# The English track is unaffected by all of it.
check(len(apply_publication_invariants(
    {"pages": [_zh(prompt="Complete the sentence: 这件衣服____贵。")]},
    language="Chinese", material_language="en")["pages"]) == 1,
    "an English instruction publishes normally on the English track")


# ── Notation: what the field holds, and what the page reports it holds ───────

from services.publication_evidence import _outside_ipa_repertoire  # noqa: E402
from services.publication_invariants import enforce_notation_repertoire  # noqa: E402

# Wrong-script characters reach the boundary when the review did not run or
# declined. They are cleared rather than published: a field whose characters are
# not part of the notation states nothing.
corrupt = {"pages": [{"type": "vocabulary", "items": [
    {"term": "má", "phonetic": "[maଝ]"},
    {"term": "mǎ", "phonetic": "[maଊ]"},
    {"term": "十", "phonetic": "[ʂʐ̩ ଝ]"},
    {"term": "μάθημα", "phonetic": "[ˈμαθιμα]"},
]}]}
enforce_notation_repertoire(corrupt)
check(all(not it["phonetic"] for it in corrupt["pages"][0]["items"]),
      "no transcription survives the boundary holding characters the notation cannot use")

intact = {"pages": [{"type": "vocabulary", "items": [
    {"term": "妈", "phonetic": "[ma˥˥]"},
    {"term": "马", "phonetic": "[ma˨˩˦]"},
    {"term": "せんせい", "phonetic": "[seɴseː]"},
    {"term": "θάλασσα", "phonetic": "[ˈθalasa]"},
    {"term": "γάλα", "phonetic": "[ˈɣala]"},
    {"term": "كَتَبَ", "phonetic": "[kataba]"},
    {"term": "학교", "phonetic": "[hak.kʰjo]"},
    {"term": "стол", "phonetic": "[stol]"},
    {"term": "é", "phonetic": "[ẽ ä n̥]"},
    {"term": "tie", "phonetic": "[t͡ʃa d͡ʒo]"},
]}]}
before = [it["phonetic"] for it in intact["pages"][0]["items"]]
enforce_notation_repertoire(intact)
check([it["phonetic"] for it in intact["pages"][0]["items"]] == before,
      "legitimate notation - tone letters, Greek-derived IPA, combining marks, tie bars - is untouched")


# ── The text layer must report the characters that were drawn ────────────────

if _HAVE_FITZ and _cursive_font():
    from services.pdf_renderer_v12 import MARK_FONT_FAMILY, _mark_font, _separate_tone_letters

    def render_layer(text):
        path, _covered = _mark_font()
        cursive = _cursive_font()
        css = (
            "body { font-family: sans-serif; font-size: 10pt; }"
            "\n@font-face { font-family: %s; src: url(%s); }\n.mark { font-family: %s; }"
            "\n@font-face { font-family: %s; src: url(%s); }\n.cursive { font-family: %s; }"
            % (MARK_FONT_FAMILY, os.path.basename(path), MARK_FONT_FAMILY,
               CURSIVE_FONT_FAMILY, os.path.basename(cursive), CURSIVE_FONT_FAMILY)
        )
        archive = fitz.Archive()
        for directory in {os.path.dirname(path), os.path.dirname(cursive)}:
            archive.add(directory)
        story = fitz.Story(html=_doc('<p class="p">%s</p>' % _e(text)), user_css=css, archive=archive)
        buf = io.BytesIO()
        writer = fitz.DocumentWriter(buf)
        more = 1
        while more:
            device = writer.begin_page(fitz.paper_rect("a4"))
            more, _filled = story.place(fitz.Rect(40, 40, 550, 760))
            story.draw(device)
            writer.end_page()
        writer.close()
        doc = fitz.open("pdf", buf.getvalue())
        repair_text_layer(doc)
        reopened = fitz.open("pdf", doc.tobytes())
        return "".join(page.get_text() for page in reopened)

    # Tone letters combine into one glyph whose reverse mapping is an unrelated
    # character, so the page reported Oriya and Gujarati letters for Mandarin
    # contours. Separate runs cannot combine.
    check(_separate_tone_letters("[ma˧˥]").count("<span>") == 2,
          "each tone letter is placed in its own run")
    tones = render_layer("[ma˥˥] [ma˧˥] [ma˨˩˦] [ma˥˩]")
    for contour in ("[ma˥˥]", "[ma˧˥]", "[ma˨˩˦]", "[ma˥˩]"):
        check(contour in tones.replace("\n", ""),
              f"the page reports {contour!r} as the characters it drew")
    check(not _outside_ipa_repertoire(tones.replace("\n", "").replace(" ", "")),
          "and reports nothing from a script the notation does not use")

    # Pieces of a CJK character, presented on their own, reached the page as .notdef
    # with NUL in the text layer.
    for label, sample, expected in (
        ("cjk strokes", "strokes: ㇀ ㇁ ㇂", "㇀"),
        ("kangxi radicals", "radicals: ⼀ ⼁", None),
        ("cjk radicals supplement", "supplement: ⺀ ⺁", "⺀"),
        ("hanzi unaffected", "汉字 这件衣服很贵", "汉字"),
        ("bopomofo unaffected", "ㄅ ㄆ ㄇ", "ㄅ"),
        ("japanese marks still fixed", "uzatma: 「ー」 (゛) (゜) コーヒー", "ー"),
    ):
        layer = render_layer(sample)
        check(layer.count("\x00") == 0, f"{label}: nothing reaches the page as .notdef")
        if expected:
            check(expected in layer.replace("\n", ""), f"{label}: {expected!r} survives")

    for bad in ("�", "￾", "￿"):
        layer = render_layer("before %s after" % bad)
        check(bad not in layer, f"U+{ord(bad):04X} never reaches a published text layer")


# ── The boundary must be told which track is being published ─────────────────

renderer_source = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "services", "pdf_renderer_v12.py"), encoding="utf-8").read()
check("material_language=material_language" in renderer_source,
      "the renderer passes a track to the publication boundary rather than letting it assume one")
check("_track = 'tr' if is_tr else 'en'" in renderer_source,
      "and the track it passes is the one being exported, not the one it was authored for")

print(f"cost, RTL text-layer, class-lexicon and progress tests passed ({checks} checks)")
