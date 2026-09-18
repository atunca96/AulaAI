"""
Regression coverage for the V56 release-cleanup page-deletion boundary.

This test exists because of a real production incident: a single fabricated
MCQ distractor, or a single unrepairable mixed-script token anywhere in a
page's text, caused entire vocabulary/grammar/dialogue pages - and in some
generations, whole topics - to be silently dropped at PDF-render time. The
root cause was an "unsafe" flag computed deep inside a page's nested content
that was allowed to bubble all the way up to "delete this page", with no
boundary at the individual assessment-item level.

This test builds a realistic nested lesson JSON shape and asserts the product
invariants:
  1. Pruning a bad MCQ item removes ONLY that MCQ page.
  2. Every non-assessment page in the same topic survives untouched, even if
     it contains an orthographic defect the cleanup cannot safely repair.
  3. The number of substantive non-MCQ pages never decreases.
  4. Russian-specific corrections never fire for other languages or when the
     language is unspecified.
"""
from pathlib import Path
import copy
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Source is frozen: the former patch-application step is a no-op here.
# Source is frozen: the former patch-application step is a no-op here.

import services.authoring.legacy_text as guard
guard = importlib.reload(guard)
_v56_release_cleanup = guard._v56_release_cleanup


def _sample_topic():
    return {
        "pages": [
            {
                "type": "grammar",
                "title_tr": "Genitif ile ilgili kurallar",
                "rules": [{
                    "target": "У меня нет книги.",
                    "translation_tr": "Kitabım yok.",
                    "explanation_tr": "İlgi/Tamlayan Hâli kullanılır.",
                }],
            },
            {
                "type": "vocabulary",
                "title_tr": "Ev eşyaları",
                "items": [
                    {
                        "term": "стwл",
                        "example": "Книга лежит на столе.",
                        "translation_tr": "Kitap masanın üzerinde duruyor.",
                    },
                    {"term": "окно", "example": "Окно открыто.", "translation_tr": "Pencere açık."},
                ],
            },
            {
                "type": "dialogue",
                "title_tr": "Kısa diyalog",
                "dialogue": [
                    {"speaker_tr": "Anna", "line_tr": "Привет! Как дела?"},
                    {"speaker_tr": "Oleg", "line_tr": "Хорошо, спасибо!"},
                ],
            },
            {
                "type": "mcq",
                "prompt_tr": "'Стол' kelimesinin doğru çoğulu hangisidir?",
                "options": ["столы", "городи", "столов", "столе"],
                "answer": "столы",
                "explanation_tr": "Çoğul hâli 'столы' şeklindedir.",
            },
            {
                "type": "mcq",
                "prompt_tr": "'Окно' kelimesinin anlamı nedir?",
                "options": ["pencere", "kapı", "masa", "sandalye"],
                "answer": "pencere",
                "explanation_tr": "'Окно' Türkçede 'pencere' demektir.",
            },
        ]
    }


def run():
    topic = _sample_topic()
    before_substantive = sum(1 for p in topic["pages"] if p["type"] != "mcq")
    before_mcq_count = sum(1 for p in topic["pages"] if p["type"] == "mcq")
    assert before_substantive == 3
    assert before_mcq_count == 2

    out = _v56_release_cleanup(copy.deepcopy(topic), "Russian")

    after_pages = out["pages"]
    after_substantive = [p for p in after_pages if p.get("type") != "mcq"]
    after_mcq = [p for p in after_pages if p.get("type") == "mcq"]

    assert len(after_substantive) == before_substantive, (
        f"non-mcq pages were dropped: had {before_substantive}, now {len(after_substantive)}"
    )
    types_before = sorted(p["type"] for p in topic["pages"] if p["type"] != "mcq")
    types_after = sorted(p["type"] for p in after_substantive)
    assert types_before == types_after, (types_before, types_after)

    vocab_page = next(p for p in after_substantive if p["type"] == "vocabulary")
    assert len(vocab_page["items"]) == 2, vocab_page

    assert len(after_mcq) == 1, after_mcq
    assert "городи" not in str(after_mcq[0].get("options")), after_mcq
    assert out.get("_integrity_removed_mcq"), "expected the drop to be recorded"
    assert len(out["_integrity_removed_mcq"]) == 1

    tr_topic = {
        "pages": [
            {"type": "vocabulary", "title_tr": "Test", "items": [{"term": "masa", "example": "Masa büyük."}]},
            {
                "type": "mcq",
                "prompt_tr": "Test?",
                "options": ["masa", "sandalye", "şehir", "pencere"],
                "answer": "masa",
                "explanation_tr": "Doğru cevap masa.",
            },
        ]
    }
    out_tr = _v56_release_cleanup(copy.deepcopy(tr_topic), "Turkish")
    assert len(out_tr["pages"]) == 2, "Turkish content must be untouched by Russian-only pruning"

    out_default = _v56_release_cleanup(copy.deepcopy(topic), "")
    assert len(out_default["pages"]) == len(topic["pages"]), (
        "an empty/unspecified language must not silently behave as Russian"
    )

    import services.pdf_renderer_v12 as renderer
    renderer = importlib.reload(renderer)
    rendered = renderer._normalize_content(copy.deepcopy(topic), "Russian")
    rendered_substantive = [p for p in rendered["pages"] if p.get("type") != "mcq"]
    rendered_mcq = [p for p in rendered["pages"] if p.get("type") == "mcq"]
    assert len(rendered_substantive) == before_substantive, rendered
    assert len(rendered_mcq) == 1, rendered

    rendered_default = renderer._normalize_content(copy.deepcopy(topic))
    assert len(rendered_default["pages"]) == len(topic["pages"]), rendered_default

    print("[V56-PAGE-INTEGRITY] page-level + renderer-boundary regression tests PASSED")


if __name__ == "__main__":
    run()
