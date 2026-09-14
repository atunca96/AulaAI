"""Production-shaped regression tests for V58 leaf-only publication hygiene."""
from pathlib import Path
import copy
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56_compat.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56_quality.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_pronunciation_v57.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_leaf_hygiene_v58.py"), run_name="__main__")

import services.material_quality_guard as guard
guard = importlib.reload(guard)


def _topic():
    return {
        "pages": [
            {
                "type": "vocabulary",
                "title_tr": "Sert ve ince ünlüler",
                "items": [
                    {
                        "term": "Hard vowel indicators: А, О, У, Ы, Э",
                        "phonetic": "[a], [o], [u], [ɨ], [ɛ]",
                        "translation_tr": "Önceki ünsüzün sert okunacağını gösteren ünlüler",
                    },
                    {
                        "term": "Soft vowel indicators: Я, Ё, Ю, И, Е",
                        "phonetic": "[[jæ] / [æ], [jo] / [o], [ju] / [u], [i], [je] / [e]]",
                        "translation_tr": "Önceki ünsüzün ince okunacağını gösteren ünlüler",
                    },
                    {
                        "term": "Ь (мягкий знак)",
                        "phonetic": "[-]",
                        "translation_tr": "İncelik işareti",
                    },
                    {
                        "term": "четве́рг",
                        "phonetic": "[tɕɪtˈfvʲerk]",
                        "translation_tr": "Perşembe",
                    },
                    {
                        "term": "неизве́стное",
                        "phonetic": "[nʲɪɪzˈvʲesnəjə]",
                        "translation_tr": "bilinmeyen",
                    },
                ],
            },
            {
                "type": "grammar",
                "title_tr": "Çoğul",
                "text": "Örnek: пес́ня → пе́сни.",
                "rules": [{"example": "пес́ня", "explanation_tr": "Şarkı örneği."}],
            },
            {
                "type": "dialogue",
                "dialogue": [{"speaker": "Анна", "text": "Привет!", "line_tr": "Merhaba!"}],
            },
            {
                "type": "mcq",
                "prompt_tr": "Hangi biçim doğrudur?",
                "options": ["пе́сня", "кни́га", "стол", "окно́"],
                "answer": "пе́сня",
            },
        ]
    }


def run():
    topic = _topic()
    before_types = [p.get("type") for p in topic["pages"]]
    before_counts = {
        "pages": len(topic["pages"]),
        "vocab_items": len(topic["pages"][0]["items"]),
        "mcq_options": len(topic["pages"][3]["options"]),
    }

    out = guard.enforce_material_integrity(copy.deepcopy(topic), language="Russian", material_language="tr")
    assert [p.get("type") for p in out["pages"]] == before_types, out
    assert len(out["pages"]) == before_counts["pages"], out

    vocab = out["pages"][0]
    assert len(vocab["items"]) == before_counts["vocab_items"], vocab
    hard = vocab["items"][0]
    soft = vocab["items"][1]
    sign = vocab["items"][2]
    thursday = vocab["items"][3]
    unknown = vocab["items"][4]

    assert hard["term"].startswith("Sert ünlü göstergeleri:"), hard
    assert hard["phonetic"] == "[a], [o], [u], [ɨ], [ɛ]", hard
    assert soft["term"].startswith("Yumuşak ünlü göstergeleri:"), soft
    assert soft["phonetic"] == "", soft
    assert sign["phonetic"] == "", sign
    assert thursday["phonetic"] == "[t͡ɕɪtˈvʲerk]", thursday
    assert unknown["phonetic"] == "[nʲɪɪzˈvʲesnəjə]", unknown

    grammar = out["pages"][1]
    assert "пес́ня" not in grammar["text"] and "пе́сня" in grammar["text"], grammar
    assert grammar["rules"][0]["example"] == "пе́сня", grammar

    mcq = out["pages"][3]
    assert len(mcq["options"]) == before_counts["mcq_options"], mcq
    assert mcq["answer"] == "пе́сня", mcq

    # Fake silence placeholders are publication-invalid regardless of target language.
    # This fixture intentionally uses a Russian sign under a German language context to
    # prove the universal placeholder rule does not depend on Russian language scoping.
    german = guard.enforce_material_integrity(
        {"pages": [{"type": "vocabulary", "items": [{"term": "Ь (мягкий знак)", "phonetic": "[-]"}]}]},
        language="German",
        material_language="tr",
    )
    assert german["pages"][0]["items"][0]["phonetic"] == "", german

    import services.pdf_renderer_v12 as renderer
    renderer = importlib.reload(renderer)
    rendered = renderer._normalize_content(copy.deepcopy(topic), "Russian")
    assert len(rendered["pages"]) == before_counts["pages"], rendered
    assert rendered["pages"][0]["items"][1]["phonetic"] == "", rendered
    assert rendered["pages"][0]["items"][2]["phonetic"] == "", rendered
    assert rendered["pages"][0]["items"][3]["phonetic"] == "[t͡ɕɪtˈvʲerk]", rendered

    print("[V58] leaf-only publication hygiene regression tests PASSED")


if __name__ == "__main__":
    run()
