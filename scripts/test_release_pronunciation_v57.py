"""Production-shaped regression tests for the V57 pronunciation layer.

Hard invariants:
- exact curated lexical overrides only;
- unmatched IPA is left untouched (no semantic guessing);
- no dict/list/item/page is deleted or created;
- the same correction is applied at integrity and renderer boundaries.
"""
from pathlib import Path
import copy
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Recreate the effective build order used before V57.
runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56_compat.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56_quality.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "patch_release_pronunciation_v57.py"), run_name="__main__")

from services.pronunciation_lexicon import lookup_canonical_ipa
import services.material_quality_guard as guard
guard = importlib.reload(guard)


def _topic():
    return {
        "pages": [
            {
                "type": "vocabulary",
                "title_tr": "Haftanın günleri",
                "items": [
                    {"term": "четве́рг", "phonetic": "[tɕɪtˈfvʲerk]", "translation_tr": "Perşembe"},
                    {"term": "пя́тница", "phonetic": "[ˈpʲætʲnʲɪt͡sə]", "translation_tr": "Cuma"},
                    {"term": "Ч ч", "phonetic": "[t͡ɕ]", "translation_tr": "Ç harfi"},
                    {"term": "Щ щ", "phonetic": "[ɕː]", "translation_tr": "Şç harfi"},
                    {"term": "неизвестно", "phonetic": "[nʲɪɪzˈvʲesnə]", "translation_tr": "bilinmeyen test girdisi"},
                    {"term": "четверг", "translation_tr": "fonetik alanı yok; eklenmemeli"},
                ],
            },
            {
                "type": "grammar",
                "title_tr": "Sayılar",
                "items": [
                    {"term": "пятьдеся́т", "phonetic": "[pʲɪdʲdʲɪˈsʲat]", "translation_tr": "elli"},
                    {"term": "со́рок", "phonetic": "[ˈsorək]", "translation_tr": "kırk"},
                ],
                "text_tr": "Bu sayfa yapısal olarak korunmalıdır.",
            },
            {
                "type": "dialogue",
                "dialogue": [
                    {"speaker": "Анна", "text": "В четверг будет концерт.", "line_tr": "Perşembe konser olacak."},
                    {"speaker": "Иван", "text": "Хорошо.", "line_tr": "Tamam."},
                ],
            },
            {
                "type": "mcq",
                "prompt_tr": "Какой сегодня день?",
                "options": ["понедельник", "вторник", "среда", "четверг"],
                "answer": "четверг",
                "explanation_tr": "Test sorusu korunmalıdır.",
            },
        ]
    }


def _assert_shape_preserved(before, after):
    assert len(after["pages"]) == len(before["pages"]), after
    for p_before, p_after in zip(before["pages"], after["pages"]):
        assert p_after.get("type") == p_before.get("type")
        if isinstance(p_before.get("items"), list):
            assert len(p_after.get("items") or []) == len(p_before["items"]), p_after
        if isinstance(p_before.get("dialogue"), list):
            assert len(p_after.get("dialogue") or []) == len(p_before["dialogue"]), p_after


def _assert_pronunciation_results(out):
    vocab = out["pages"][0]
    items = vocab["items"]
    thu = next(i for i in items if i.get("term") == "четве́рг")
    fri = next(i for i in items if i.get("term") == "пя́тница")
    ch = next(i for i in items if i.get("term") == "Ч ч")
    shch = next(i for i in items if i.get("term") == "Щ щ")
    unknown = next(i for i in items if i.get("term") == "неизвестно")
    no_phonetic = next(i for i in items if i.get("term") == "четверг" and "phonetic" not in i)

    assert thu["phonetic"] == "[t͡ɕɪtˈvʲerk]", thu
    assert fri["phonetic"] == "[ˈpʲætʲnʲɪt͡sə]", fri
    assert ch["phonetic"] == "[t͡ɕ]", ch
    assert shch["phonetic"] == "[ɕː]", shch
    # No universal semantic IPA guessing: unknown lexical IPA stays byte-for-byte.
    assert unknown["phonetic"] == "[nʲɪɪzˈvʲesnə]", unknown
    assert "phonetic" not in no_phonetic, no_phonetic

    fifty = out["pages"][1]["items"][0]
    forty = out["pages"][1]["items"][1]
    assert fifty["phonetic"] == "[pʲɪdʲɪˈsʲat]", fifty
    assert forty["phonetic"] == "[ˈsorək]", forty


def run():
    assert lookup_canonical_ipa("Russian", "четве́рг") == "[t͡ɕɪtˈvʲerk]"
    assert lookup_canonical_ipa("Rusça", "пятьдеся́т") == "[pʲɪdʲɪˈsʲat]"
    assert lookup_canonical_ipa("German", "четверг") is None
    assert lookup_canonical_ipa("Russian", "четверг test") is None
    assert lookup_canonical_ipa("Russian", "неизвестно") is None

    topic = _topic()
    out = guard.enforce_material_integrity(copy.deepcopy(topic), language="Russian", material_language="tr")
    _assert_shape_preserved(topic, out)
    _assert_pronunciation_results(out)

    import services.pdf_renderer_v12 as renderer
    renderer = importlib.reload(renderer)
    rendered = renderer._normalize_content(copy.deepcopy(topic), "Russian")
    _assert_shape_preserved(topic, rendered)
    _assert_pronunciation_results(rendered)

    # Language gate: same spelling under another target language must not be rewritten.
    german = renderer._normalize_content(copy.deepcopy(topic), "German")
    assert german["pages"][0]["items"][0]["phonetic"] == "[tɕɪtˈfvʲerk]", german
    assert len(german["pages"]) == len(topic["pages"])

    print("[V57-PRONUNCIATION] exact lexicon + leaf-only integrity/render regression tests PASSED")


if __name__ == "__main__":
    run()
