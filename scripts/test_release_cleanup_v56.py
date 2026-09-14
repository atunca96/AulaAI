from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_release_cleanup_v56_compat.py"), run_name="__main__")

from services.material_quality_guard import _v56_russian_text, _v56_turkish_text


def run():
    sample = "\u0412 \u0441\u0443\u0431\u0431\u043etu test"
    fixed, unsafe = _v56_russian_text(sample)
    assert "\u0441\u0443\u0431\u0431\u043e\u0442\u0443" in fixed.casefold(), fixed
    assert not unsafe, fixed

    typo = "\u0412 \u043a\u043e\u0437\u0438\u0301\u043d\u0435"
    fixed, _ = _v56_russian_text(typo)
    assert "\u043a\u043e\u0440\u0437\u0438\u043d\u0435" in fixed.casefold().replace("\u0301", ""), fixed

    assert "Physik" not in _v56_turkish_text("O Physik odada bes kisi var.")
    print("[V56] cleanup regression tests PASSED")


if __name__ == "__main__":
    run()
