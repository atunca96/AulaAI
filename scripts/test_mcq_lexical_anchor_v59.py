"""Production-shaped regression tests for the V59 lexical-anchor guard.

Hard invariants:
- only the hidden-translation pronoun/gender MCQ is removed;
- Russian lexical anchors keep valid grammar questions;
- substantive pages and unrelated MCQs are preserved;
- no content is rewritten or invented.
"""
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
runpy.run_path(str(ROOT / "scripts" / "patch_mcq_lexical_anchor_v59.py"), run_name="__main__")

import services.material_quality_guard as guard
guard = importlib.reload(guard)


def _topic():
    return {
        "pages": [
            {
                "type": "vocabulary",
                "title_tr": "İsimler",
                "items": [{"term": "газета", "translation_tr": "gazete"}],
            },
            {
                "type": "grammar",
                "title_tr": "Gramatik cinsiyet",
                "text_tr": "Dişil isimlerin yerine она zamiri gelebilir.",
            },
            {
                "type": "dialogue",
                "dialogue": [{"speaker": "Анна", "text": "Где газета?", "line_tr": "Gazete nerede?"}],
            },
            {
                "type": "mcq",
                "prompt_en": "Where is the newspaper? — ___ is on the table.",
                "prompt_tr": "Gazete nerede? — ___ masada.",
                "options": ["Он", "Оно", "Они", "Она"],
                "answer": "Она",
                "explanation_tr": "Газета dişil olduğu için Она kullanılır.",
            },
            {
                "type": "mcq",
                "prompt": "Где газета? — ___ на столе.",
                "prompt_tr": "Boşluğa doğru zamiri seçiniz.",
                "options": ["Он", "Оно", "Они", "Она"],
                "answer": "Она",
                "explanation_tr": "Газета dişil olduğu için Она kullanılır.",
            },
            {
                "type": "mcq",
                "prompt_tr": "«газета» kelimesinin yerine hangi zamir gelmelidir?",
                "options": ["Он", "Оно", "Они", "Она"],
                "answer": "Она",
                "explanation_tr": "Газета dişildir.",
            },
            {
                "type": "mcq",
                "prompt_tr": "'Bu ne anlama geliyor?' anlamına gelen Rusça ifade hangisidir?",
                "options": ["Как это по-русски?", "Что это значит?", "У меня есть вопрос.", "Можно войти?"],
                "answer": "Что это значит?",
                "explanation_tr": "Anlam sorma kalıbıdır.",
            },
        ]
    }


def run():
    topic = _topic()
    before_non_mcq = [p for p in topic["pages"] if p.get("type") != "mcq"]
    before_mcq = [p for p in topic["pages"] if p.get("type") == "mcq"]
    assert len(before_non_mcq) == 3
    assert len(before_mcq) == 4

    out = guard._v56_release_cleanup(copy.deepcopy(topic), "Russian")
    after_non_mcq = [p for p in out["pages"] if p.get("type") != "mcq"]
    after_mcq = [p for p in out["pages"] if p.get("type") == "mcq"]

    assert len(after_non_mcq) == 3, out
    assert [p.get("type") for p in after_non_mcq] == ["vocabulary", "grammar", "dialogue"]
    assert len(after_mcq) == 3, [p.get("prompt_tr") or p.get("prompt") for p in after_mcq]

    joined = "\n".join((p.get("prompt") or "") + "\n" + (p.get("prompt_tr") or "") for p in after_mcq)
    assert "Where is the newspaper" not in joined, joined
    assert "Где газета?" in joined, joined
    assert "«газета»" in joined, joined
    assert "Что это значит" in "\n".join(" ".join(p.get("options") or []) for p in after_mcq)

    # Direct detector assertions: only the hidden-translation item is unsafe.
    bad = topic["pages"][3]
    good_target = topic["pages"][4]
    good_meta = topic["pages"][5]
    unrelated = topic["pages"][6]
    assert guard._v59_unstated_lexical_bridge(bad) is True
    assert guard._v59_unstated_lexical_bridge(good_target) is False
    assert guard._v59_unstated_lexical_bridge(good_meta) is False
    assert guard._v59_unstated_lexical_bridge(unrelated) is False

    print("[V59-MCQ-ANCHOR] hidden-translation pronoun MCQ regression tests PASSED")


if __name__ == "__main__":
    run()
