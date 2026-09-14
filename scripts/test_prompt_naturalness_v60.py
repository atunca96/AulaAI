from pathlib import Path
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_prompt_naturalness_v60.py"), run_name="__main__")

import services.material_generation_prompt as mgp
mgp = importlib.reload(mgp)
system_prompt, _ = mgp.build_material_prompts(
    language="Russian",
    level="A1",
    topic="Alphabet",
    topic_type="pronunciation",
    official_institution="Example Institute",
)

for marker in (
    "Write learner-facing prose as natural authored language, not as template narration",
    "Do not use artificial authority framing",
    "Every Turkish learner-facing title, subtitle, section heading",
    "Never emit an English duplicate heading",
    "Target-language dialogue/text fields must remain in the target language",
    "no unnecessary native-speaker authority framing",
):
    assert marker in system_prompt, marker

from services.publication_leaf_sanitizer import sanitize_publication_leaves
fixture = {
    "pages": [
        {
            "type": "overview",
            "title_tr": "Present Tense: First Conjugation Verbs (-at/-yat)",
            "text_tr": "Ana dili Rusça olan konuşucuların temel diyaloglarda sert ve yumuşak ünlüleri nasıl telaffuz ettiğini inceleyin.",
        },
        {
            "type": "dialogue",
            "dialogue": [
                {
                    "speaker": "Öğretmen",
                    "text": "«Задание» — это task или exercise.",
                    "line_tr": "'Zadanie', ödev veya alıştırma demektir.",
                }
            ],
        },
    ]
}
out = sanitize_publication_leaves(fixture, "Russian", "tr")
assert len(out["pages"]) == 2
assert out["pages"][0]["title_tr"] == "Şimdiki/Geniş Zaman: Birinci Grup Fiiller (-ать/-ять)"
assert out["pages"][0]["text_tr"].startswith("Temel diyaloglarda ")
assert "Ana dili Rusça olan konuşucuların" not in out["pages"][0]["text_tr"]
assert out["pages"][1]["dialogue"][0]["text"] == "«Задание» — это упражнение или учебная задача."
assert out["pages"][1]["dialogue"][0]["line_tr"] == "'Zadanie', ödev veya alıştırma demektir."

print("[V60-NATURALNESS] prompt + leaf-only leakage regressions PASSED")
