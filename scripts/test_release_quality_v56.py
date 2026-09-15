"""Production-shaped regression tests for the V56 quality overlay.

Hard invariant: only pages whose OWN type is exactly "mcq" may be pruned.
All vocabulary/grammar/dialogue pages must survive, even with an unrepairable
mixed-script token. Remaining publication fixes are leaf-only or display-only.
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
# Source is frozen: the former patch-application step is a no-op here.

import services.material_quality_guard as guard
guard = importlib.reload(guard)


def _topic():
    return {
        "pages": [
            {
                "type": "vocabulary",
                "title_tr": "Alfabe ve örnekler",
                "items": [
                    {"term": "Ч ч", "phonetic": "[t͡ɕː]", "example": "чай"},
                    {"term": "Щ щ", "phonetic": "[ɕː]", "example": "борщ"},
                    {"term": "стwл", "phonetic": "[stol]", "example": "Книга на столе."},
                ],
            },
            {
                "type": "grammar",
                "title_tr": "Ötümsüzleşme",
                "text": "Örnek: клуб [клуп], город [горат].",
                "rules": [{"target": "клуб [клуп]", "translation_tr": "kulüp"}],
            },
            {
                "type": "dialogue",
                "title_tr": "Diyalog",
                "dialogue": [
                    {"speaker": "Анна", "text": "Привет!", "line_tr": "Merhaba!"},
                    {"speaker": "Олег", "text": "Привет!", "line_tr": "Merhaba!"},
                ],
            },
            {
                "type": "mcq",
                "prompt_tr": "Это очень ___ рыба.",
                "options": ["вкусное", "вкусная", "вкусные", "вкусный"],
                "answer": "вкусная",
                "explanation_tr": "'Рыба' ismi dilbilgisel olarak dişildir; doğru biçim вкусная.",
            },
            {
                "type": "mcq",
                "prompt_tr": "Мой папа очень ___.",
                "options": ["красивый", "красивая", "красивое", "красивые"],
                "answer": "красивый",
                "explanation_tr": "'Папа' bir erkeği ifade ettiği için dilbilgisel olarak erildir.",
            },
            {
                "type": "mcq",
                "prompt_tr": "Вчера Анна весь вечер ______ новую книгу.",
                "options": ["читало", "читали", "читал", "читала"],
                "answer": "читала",
                "explanation_tr": "Özne tekil dişil olan 'Анна' olduğu için читала kullanılır.",
            },
            {
                "type": "mcq",
                "prompt_tr": "Каждый вечер я ______ ужин дома.",
                "options": ["готовит", "готовлю", "готовишь", "готовю"],
                "answer": "готовлю",
                "explanation_tr": "'готовю' araya gelmesi zorunlu 'л' sesini içermediği için yanlıştır.",
            },
            {
                "type": "mcq",
                "prompt_tr": "Ты часто ______ в парк пешком?",
                "options": ["хожу", "ходят", "ходишь", "ходим"],
                "answer": "ходишь",
                "explanation_tr": "Ты zamiri ikinci tekil şahıs biçimi olan ходишь gerektirir.",
            },
        ]
    }


def run():
    topic = _topic()
    before_non_mcq = [p for p in topic["pages"] if p.get("type") != "mcq"]
    assert len(before_non_mcq) == 3

    out = guard._v56_release_cleanup(copy.deepcopy(topic), "Russian")
    pages = out["pages"]
    after_non_mcq = [p for p in pages if p.get("type") != "mcq"]
    after_mcq = [p for p in pages if p.get("type") == "mcq"]

    assert len(after_non_mcq) == len(before_non_mcq), out
    assert sorted(p["type"] for p in after_non_mcq) == ["dialogue", "grammar", "vocabulary"]

    vocab = next(p for p in after_non_mcq if p["type"] == "vocabulary")
    assert any(i.get("term") == "стwл" for i in vocab["items"]), vocab

    ch = next(i for i in vocab["items"] if i.get("term") == "Ч ч")
    shch = next(i for i in vocab["items"] if i.get("term") == "Щ щ")
    assert ch["phonetic"] == "[t͡ɕ]", ch
    assert shch["phonetic"] == "[ɕː]", shch

    grammar = next(p for p in after_non_mcq if p["type"] == "grammar")
    assert "[клуп]" not in grammar["text"] and "[горат]" not in grammar["text"], grammar
    assert "клуб" in grammar["text"] and "город" in grammar["text"], grammar

    assert len(after_mcq) == 3, [p.get("prompt_tr") for p in after_mcq]
    joined = "\n".join(p.get("prompt_tr", "") for p in after_mcq)
    assert "Анна" not in joined, joined
    assert "готов" not in joined.casefold(), joined
    assert "рыба" in joined, joined
    assert "папа" in joined, joined
    assert any("Ты часто" in p.get("prompt_tr", "") for p in after_mcq)

    import services.pdf_renderer_v12 as renderer
    renderer = importlib.reload(renderer)
    rendered = renderer._normalize_content(copy.deepcopy(topic), "Russian")
    assert len([p for p in rendered["pages"] if p.get("type") != "mcq"]) == 3, rendered
    assert len([p for p in rendered["pages"] if p.get("type") == "mcq"]) == 3, rendered

    assert renderer._v56q_display_option("[ɐ] (similar to an unstressed 'a')", "Russian") == "[ɐ]"
    assert renderer._v56q_display_option("[ɪ] (short i-like sound due to Ikan'e)", "Russian") == "[ɪ]"
    assert renderer._v56q_display_option("[т]", "Russian") == "[t]"
    assert renderer._v56q_display_option("[дʲ]", "Russian") == "[dʲ]"
    sample = "[ɐ] (similar to an unstressed 'a')"
    assert renderer._v56q_display_option(sample, "German") == sample

    defaulted = renderer._normalize_content(copy.deepcopy(topic))
    assert len(defaulted["pages"]) == len(topic["pages"]), defaulted

    print("[V56-QUALITY] mcq-only pruning + publication quality regression tests PASSED")


if __name__ == "__main__":
    run()
