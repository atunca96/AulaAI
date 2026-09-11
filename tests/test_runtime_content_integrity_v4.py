from types import SimpleNamespace

from services import runtime_content_integrity_guard_v4 as guard


def test_runtime_v4_uses_persisted_bilingual_fields_and_no_async_note_rewrite(tmp_path):
    bundle = tmp_path / "bilingual_materials.js"
    bundle.write_text("window.TEST = true;\n", encoding="utf-8")
    module = SimpleNamespace(BUNDLE_FILE=str(bundle), rebuild_bilingual_bundle=lambda: None)

    guard.install(module)
    text = bundle.read_text(encoding="utf-8")

    assert "AULA_RUNTIME_CONTENT_INTEGRITY_V4" in text
    assert "explanation_en" in text
    assert "explanation_tr" in text
    assert "prompt_en" in text
    assert "prompt_tr" in text
    assert "options_en" in text
    assert "options_tr" in text
    assert "translateAsync" not in text


def test_runtime_v4_highlight_is_based_on_real_topic_id(tmp_path):
    js = guard._runtime_js()
    assert ".study-topic-btn[data-topic-id]" in js
    assert "aula_last_topic" in js
    assert "classList.contains('active')" in js
    assert "first" not in js.lower() or "first" not in "default-first-topic"


def test_runtime_v4_installs_early_instead_of_waiting_only_for_dom_ready():
    js = guard._runtime_js()
    assert "setInterval" in js
    assert "10" in js
    assert "installAll" in js
