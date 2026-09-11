from types import SimpleNamespace

from services import runtime_content_integrity_guard as guard


def test_runtime_guard_contains_canonical_letter_and_mcq_paths(tmp_path):
    bundle = tmp_path / "bilingual_materials.js"
    bundle.write_text("window.TEST = true;\n", encoding="utf-8")
    module = SimpleNamespace(BUNDLE_FILE=str(bundle), rebuild_bilingual_bundle=lambda: None)

    guard.install(module)
    text = bundle.read_text(encoding="utf-8")

    assert "AULA_RUNTIME_CONTENT_INTEGRITY_V2" in text
    assert "getClientLetterPhonetics" in text
    assert "options_tr" in text
    assert "options_en" in text
    assert "answer_tr" in text
    assert "answer_en" in text
    assert "activeStudyTopicId" in text
    assert "showStudyTopic" in text
    assert "toggleLanguage" in text


def test_runtime_guard_is_idempotent(tmp_path):
    bundle = tmp_path / "bilingual_materials.js"
    bundle.write_text("window.TEST = true;\n", encoding="utf-8")
    module = SimpleNamespace(BUNDLE_FILE=str(bundle), rebuild_bilingual_bundle=lambda: None)

    guard.install(module)
    guard._append(module)
    text = bundle.read_text(encoding="utf-8")
    assert text.count("/* AULA_RUNTIME_CONTENT_INTEGRITY_V2 */") == 1
