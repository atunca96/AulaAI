from types import SimpleNamespace

from services.runtime_content_integrity_guard import _MARKER, _runtime_js, install


def test_runtime_guard_contains_language_integrity_repairs():
    js = _runtime_js()
    assert _MARKER in js
    assert "Turkish" in js
    assert "Se escribe con 'e', 'l', 'e', 'n', 'a': Elena." in js
    assert "resolveStudyPrompt" in js
    assert "/api/translate/material" in js


def test_install_appends_guard_and_reappends_after_bundle_rebuild(tmp_path):
    bundle = tmp_path / "bilingual_materials.js"
    bundle.write_text("window.TEST = true;\n", encoding="utf-8")

    def rebuild():
        bundle.write_text("window.TEST = 'rebuilt';\n", encoding="utf-8")
        return "ok"

    module = SimpleNamespace(BUNDLE_FILE=str(bundle), rebuild_bilingual_bundle=rebuild)
    install(module)

    first = bundle.read_text(encoding="utf-8")
    assert _MARKER in first

    result = module.rebuild_bilingual_bundle()
    second = bundle.read_text(encoding="utf-8")
    assert result == "ok"
    assert _MARKER in second
