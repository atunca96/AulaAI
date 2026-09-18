from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.authoring.legacy_text import _v57_unsafe_mcq, enforce_material_integrity
from services import pdf_renderer_v12 as renderer


def run():
    name_gender = {
        "type": "mcq",
        "prompt_tr": "Bu Marina. ______ kimdir?",
        "options": ["она", "мы", "он", "они"],
        "answer": "она",
        "explanation_tr": "'Марина' bir kadın ismi olduğu için üçüncü tekil dişil şahıs zamiri olan 'она' seçilmelidir.",
    }
    birthplace_nationality = {
        "type": "mcq",
        "prompt_tr": "Анна родилась в Турции, она — ______",
        "options": ["турчанка", "в Турции", "турок", "по-турецки"],
        "answer": "турчанка",
        "explanation_tr": "Özne dişil olduğu için dişil milliyet ismi olan 'турчанка' gereklidir.",
    }
    safe_explicit = {
        "type": "mcq",
        "prompt_tr": "Viktor bu soruda açıkça erkek olarak verilmiştir. Doğru zamiri seçiniz.",
        "options": ["он", "она", "оно", "они"],
        "answer": "он",
        "explanation_tr": "Özne açıkça erkek olduğu için eril zamir seçilir.",
    }

    assert _v57_unsafe_mcq(name_gender) is True
    assert _v57_unsafe_mcq(birthplace_nationality) is True
    assert _v57_unsafe_mcq(safe_explicit) is False

    lesson = {
        "pages": [
            {"type": "overview", "title_tr": "Konu", "text_tr": "Açıklama"},
            name_gender,
            safe_explicit,
            birthplace_nationality,
        ]
    }
    out = enforce_material_integrity(lesson, language="Russian", material_language="tr")
    assert len(out["pages"]) == 2
    assert out["pages"][0]["type"] == "overview"
    assert out["pages"][1]["answer"] == "он"

    assert renderer._v57_tr_meta("он (masculine) vs. она (feminine) vs. оно (neuter)") == "он (eril) vs. она (dişil) vs. оно (nötr)"
    assert renderer._v57_tr_meta("чай (nominative = accusative)") == "чай (Yalın Hâl = Belirtme Hâli)"
    assert renderer._v57_tr_meta("Prepositional Case") == "Edat Durumu"
    assert renderer._v57_tr_meta("Belirtme Hâli (Belirtme Hâli)") == "Belirtme Hâli"
    assert renderer._v57_tr_meta("İlgi/İlgi/Tamlayan Hâli") == "İlgi/Tamlayan Hâli"
    assert renderer._v57_tr_meta("Accusative (Belirtme Hâli)") == "Belirtme Hâli"
    assert renderer._v57_tr_meta("ехать fiili çekimde -д- gövdesi alır") == "ехать fiili çekimde gövde 'ед-' biçimine dönüşür"
    assert renderer._v57_tr_meta("Bu fiil -д- gövdesi alır") == "Bu fiil -д- gövdesi alır"

    assert renderer._v57_display_phonetic("ja") == "[ja]"
    assert renderer._v57_display_phonetic("[b] / [bʲ]") == "[b] / [bʲ]"
    assert renderer._v57_display_phonetic("") == ""

    alphabet = [{"term": f"{u} {l}"} for u, l in zip("ABCDE", "abcde")]
    assert renderer._v57_is_grapheme_inventory(alphabet) is True

    page = {
        "comparisons": [{"target": "он (masculine) vs. она (feminine)", "translation_tr": "eril ve dişil"}]
    }
    html = " ".join(renderer._comparison_blocks(page, True))
    assert "masculine" not in html.lower()
    assert "feminine" not in html.lower()
    assert "eril" in html and "dişil" in html

    # These two items must never reach a learner, and they no longer do it by
    # being quietly pruned on the way to the page. `_normalize_pages` used to
    # drop them with a predicate that neither the render loop nor the
    # publication gate consulted, so a ten-question assessment could print as
    # eight from a course the gate had passed. The render contract now owns the
    # decision: `_normalize_pages` hands every stored page to the loop, and the
    # gate refuses the course before it can become READY.
    from services.authoring import render_contract as RC

    normalized = renderer._normalize_pages(
        {"pages": [name_gender, safe_explicit, birthplace_nationality]})
    assert len(normalized) == 3
    for is_tr in RC.EXPORT_LOCALES:
        assert RC.page_is_renderable(name_gender, is_tr)[0] is False
        assert RC.page_is_renderable(birthplace_nationality, is_tr)[0] is False
    # The safe item is answerable, and the contract keeps it in the export it
    # has a stem for. These fixtures carry `prompt_tr` only, so the English
    # export has nothing to print — which is the locale-dependent stem loss the
    # contract exists to surface, not a judgement about the question.
    assert RC.page_is_renderable(safe_explicit, True)[0] is True
    assert RC.page_is_renderable(safe_explicit, False) == (
        False, "no stem resolves in the en export")

    source = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    assert "Harf / İşaret" in source
    assert "Temel Ses (IPA)" in source
    assert "_v57_display_phonetic" in source

    print("[V57] final publication regression tests PASSED")


if __name__ == "__main__":
    run()
