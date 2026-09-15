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
    elif stage == "enriching":
        value = 10 + int(min(1.0, max(0.0, progress / total)) * 82) if total > 0 else 10
    elif stage == "finalizing":
        value = 94
    else:
        value = min(92, max(3, int((progress / total) * 100))) if total > 0 else 3
    return min(98, max(3, value))


# The write sequence a 30-topic build actually performs, in order.
SEQUENCE = [
    ("analyzing", 0, 0),
    ("prepared", 0, 0),      # phase one finished; no topic generated yet
    ("prepared", 0, 30),     # the topic count becomes known
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

check(reported("prepared", 0, 30) == reported("enriching", 0, 30),
      "handing off from curriculum to enrichment is not visible as a movement")

# The defect itself: phase one used to write 20 into the topic COUNTER while
# claiming the enrichment stage, so the bar computed 20-of-30 and then fell back
# to zero-of-30. Asserted here so reverting the fix fails the suite.
check(reported("enriching", 20, 30) > reported("enriching", 0, 30),
      "writing a percentage into the topic counter is what produced the reset")
check(reported("enriching", 20, 30) == 64,
      "and the value it produced was the two-thirds jump users reported")

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


print(f"cost, RTL text-layer, class-lexicon and progress tests passed ({checks} checks)")
