from pathlib import Path
import copy
import importlib
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_universal_quality_v61.py"), run_name="__main__")

from services.material_generation_prompt import build_material_prompts
from services.publication_leaf_sanitizer import sanitize_publication_leaves
import services.material_quality_guard as guard
guard = importlib.reload(guard)

system_prompt, _ = build_material_prompts(
    language="Example Language", level="A1", topic="Basics", topic_type="grammar", official_institution="Example Institute"
)
for marker in (
    "A1/A2: concrete, high-frequency",
    "BASIC SOUND VALUE(S) IN STANDARD IPA",
    "Use one authoritative learner-facing pronunciation system for a given function",
    "personal name alone never establishes grammatical gender",
    "all semantic answer options and the keyed answer must be in that same instructional language",
    "common-sense world knowledge",
    "unstated translation bridge",
    "Japanese ー",
    "Because shared `options` cannot carry separate English and Turkish semantic choices",
):
    assert marker in system_prompt, marker

# Universal phonetic hygiene: no fake silence placeholders; no guessed replacement.
spanish = {"pages": [{"type": "vocabulary", "items": [
    {"term": "H, h", "phonetic": "[-]"},
    {"term": "U, u", "phonetic": "[u] / [-]"},
]}]}
sp = sanitize_publication_leaves(spanish, "Spanish", "tr")
assert sp["pages"][0]["items"][0]["phonetic"] == ""
assert sp["pages"][0]["items"][1]["phonetic"] == "[u]"

# Multiword orthography copied verbatim into phonetic is not IPA evidence.
turkish = {"pages": [{"type": "vocabulary", "items": [{"term": "nitelikte olmak", "phonetic": "[nitelikte olmak]"}]}]}
tu = sanitize_publication_leaves(turkish, "Turkish", "en")
assert tu["pages"][0]["items"][0]["phonetic"] == ""

# Japanese grapheme preservation + localized category; structure unchanged.
japanese = {"pages": [{"type": "overview", "label": "Theory", "text_tr": "Uzun ünlüleri göstermek için kullanılan '' uzatma çizgisi (çōonpu) önemlidir. Yatay çizgi olan '' sesi uzatır."}]}
ja = sanitize_publication_leaves(japanese, "Japanese", "tr")
assert len(ja["pages"]) == 1
assert ja["pages"][0]["label"] == "Kuram"
assert "「ー」" in ja["pages"][0]["text_tr"]

# Production-shaped assessment fixture: substantive pages survive; only clear
# locale-leak MCQs are removed.
fixture = {"pages": [
    {"type": "vocabulary", "items": [{"term": "окно", "translation_tr": "pencere"}]},
    {"type": "grammar", "text_tr": "Vurgu ve ünlü indirgenmesi."},
    {"type": "dialogue", "dialogue": [{"speaker": "Анна", "text": "Где окно?"}]},
    {"type": "mcq", "prompt_tr": "«окно» sözcüğündeki ilk о nasıl telaffuz edilir?", "options": ["As a full, long [o] sound", "As an open [ɐ] sound because it is before the stress", "It is completely silent", "As an [u] sound"], "answer": "As an open [ɐ] sound because it is before the stress"},
    {"type": "mcq", "prompt": "Где окно? — ___ здесь.", "prompt_tr": "Doğru zamiri seçiniz.", "options": ["Он", "Она", "Оно", "Они"], "answer": "Оно"},
]}
out = guard._v56_release_cleanup(copy.deepcopy(fixture), "Russian")
non_mcq = [p for p in out["pages"] if p.get("type") != "mcq"]
mcq = [p for p in out["pages"] if p.get("type") == "mcq"]
assert len(non_mcq) == 3
assert [p["type"] for p in non_mcq] == ["vocabulary", "grammar", "dialogue"]
assert len(mcq) == 1
assert mcq[0]["answer"] == "Оно"

print("[V61-UNIVERSAL] prompt + leaf hygiene + MCQ regressions PASSED")
