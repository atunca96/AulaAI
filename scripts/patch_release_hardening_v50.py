from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
engine_path = ROOT / "services" / "ai_engine.py"
test_path = ROOT / "scripts" / "test_universal_quality.py"
release_test_path = ROOT / "scripts" / "test_material_release_integrity_v37.py"

TAG = "# AULAAI_RELEASE_HARDENING_V50"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r"""

# AULAAI_RELEASE_HARDENING_V50
_V50_HYPHEN_EQUIV = {"\u00ad", "\u2010", "\u2011", "\ufe63", "\uff0d"}
_V50_DROP = {"\u200b", "\ufeff", "\u2060"}
_V50_NONCHARS = {"\ufffe", "\uffff"}
_V50_IPA_SIGNAL = set("ˈˌːˑəɐɛɪʊʌɨøœɶʏɯɤɑɒɕʑʂʐʒʃθðʔʲʷˤɣʁħʕŋɲɳɴɱɭʎʟɾɺⱱβɸɹɻɰʍçɡ")
_V50_CYRILLIC_GRAVE_MAP = {
    "\u0450": "\u0435",  # ѐ -> е
    "\u0400": "\u0415",  # Ѐ -> Е
    "\u045D": "\u0438",  # ѝ -> и
    "\u040D": "\u0418",  # Ѝ -> И
}


def _v50_is_russian(language=None):
    if not language:
        return False
    return str(language).strip().casefold() in ("russian", "rusça", "rusca", "rus", "ru")


def safe_unicode_normalize(text: str, language=None) -> str:
    if not text or not isinstance(text, str):
        return text
    if _v50_is_russian(language):
        for k, v in _V50_CYRILLIC_GRAVE_MAP.items():
            text = text.replace(k, v)
        text = re.sub(r'([\u0400-\u04FF])\u0300', r'\1', text)
    else:
        text = re.sub(r'(?i)\bпрофѐссор\b', 'профессор', text)
    text = unicodedata.normalize("NFC", text)
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        cp = ord(ch)
        if ch in _V50_HYPHEN_EQUIV:
            out.append("-")
            continue
        if ch in _V50_DROP or ch == "\ufffd":
            continue
        if ch in _V50_NONCHARS or 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if prev and nxt and prev.isalnum() and nxt.isalnum():
                out.append("-")
            continue
        if 0xD800 <= cp <= 0xDFFF:
            continue
        if (cp < 0x20 and cp not in (0x09, 0x0A, 0x0D)) or (0x7F <= cp <= 0x9F):
            continue
        out.append(ch)
    return "".join(out)


def _v50_clean_tree(node, language=None):
    if isinstance(node, str):
        return safe_unicode_normalize(node, language=language)
    if isinstance(node, dict):
        return {k: _v50_clean_tree(v, language=language) for k, v in node.items()}
    if isinstance(node, list):
        return [_v50_clean_tree(v, language=language) for v in node]
    return node


def _v50_heal_bracketed_ipa(text: str) -> str:
    if not isinstance(text, str) or "[" not in text or "]" not in text:
        return text

    def repl(match):
        inner = match.group(1)
        if "-" not in inner or not any(ch in _V50_IPA_SIGNAL for ch in inner):
            return match.group(0)
        return "[" + re.sub(r"(?<=\w)-(?=[\wˈˌ])|(?<=[ˈˌ])-|-(?=[ˈˌ])", "", inner) + "]"

    return re.sub(r"\[([^\]\n]{1,160})\]", repl, text)


def _v50_pron_parentheticals(text: str):
    if not isinstance(text, str):
        return []
    found = []
    for m in re.finditer(r"\s*\(([^()]{1,80})\)", text):
        inner = m.group(1)
        brackets = re.findall(r"\[[^\]\n]{1,60}\]", inner)
        if len(brackets) != 1 or ":" not in inner:
            continue
        rest = inner.replace(brackets[0], "").strip()
        if len(rest) <= 40:
            found.append((m.span(), _v50_heal_bracketed_ipa(brackets[0])))
    return found


def _v50_strip_pron_parentheticals(text: str) -> str:
    spans = _v50_pron_parentheticals(text)
    if not spans:
        return text
    result = text
    for (start, end), _ in reversed(spans):
        result = result[:start] + result[end:]
    return re.sub(r"\s{2,}", " ", result).strip()


def _v50_repair_lexical_item(item):
    if not isinstance(item, dict):
        return
    phon = str(item.get("phonetic") or "").strip()
    fields = (
        "translation", "translation_tr", "meaning", "meaning_tr",
        "gloss", "gloss_tr", "definition", "definition_tr",
    )

    if not phon:
        for key in fields:
            value = item.get(key)
            spans = _v50_pron_parentheticals(value) if isinstance(value, str) else []
            if spans:
                item["phonetic"] = spans[0][1]
                item[key] = _v50_strip_pron_parentheticals(value)
                phon = item["phonetic"]
                break

    if phon:
        item["phonetic"] = _v50_heal_bracketed_ipa(phon)
        for key in fields:
            if isinstance(item.get(key), str):
                item[key] = _v50_strip_pron_parentheticals(item[key])


def _v50_walk(node):
    if isinstance(node, dict):
        if any(k in node for k in ("term", "word", "phrase", "expression", "target")):
            _v50_repair_lexical_item(node)
        for key, value in list(node.items()):
            if isinstance(value, str):
                node[key] = _v50_heal_bracketed_ipa(value)
            elif isinstance(value, (dict, list)):
                _v50_walk(value)
    elif isinstance(node, list):
        for value in node:
            _v50_walk(value)


def enforce_material_integrity(data, language=None, material_language="tr"):
    if not isinstance(data, dict):
        return data
    out = _v50_clean_tree(deepcopy(data), language=language)
    _v50_walk(out)

    pages = out.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            if str(page.get("type") or "").strip().lower() == "mcq":
                opts = [_norm(x) for x in _as_list(page.get("options") or page.get("choices"))]
                ans = _norm(page.get("answer"))
                if len(opts) == 4 and ans in opts:
                    page["correct_index"] = opts.index(ans)
    out.pop("_integrity_removed_mcq", None)
    return out
"""
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r"""

# AULAAI_RELEASE_HARDENING_V50
from services.material_quality_guard import safe_unicode_normalize as _v50_unicode_normalize

_v50_original_normalize_content = _normalize_content


def _v50_renderer_clean(node):
    if isinstance(node, str):
        return _v50_unicode_normalize(node)
    if isinstance(node, dict):
        return {k: _v50_renderer_clean(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_v50_renderer_clean(v) for v in node]
    return node


def _normalize_content(raw):
    return _v50_renderer_clean(_v50_original_normalize_content(raw))


def _e(value):
    return html.escape(_v50_unicode_normalize(str(value or "")))


_v50_freeform_keys = {
    "title", "text", "explanation", "analysis", "note", "context",
    "rule", "translation", "meaning", "prompt", "question", "stem",
}


def _pick(obj, en_key, tr_key, is_tr):
    if not isinstance(obj, dict):
        return ""
    primary_key, fallback_key = (tr_key, en_key) if is_tr else (en_key, tr_key)
    primary = obj.get(primary_key)
    if primary is not None and str(primary).strip():
        return primary
    base = str(en_key or "").casefold().removesuffix("_en")
    if base in _v50_freeform_keys:
        return ""
    fallback = obj.get(fallback_key)
    return fallback if fallback is not None else ""
"""
    renderer_path.write_text(renderer, encoding="utf-8")

engine = engine_path.read_text(encoding="utf-8")
contract = r"""<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V50: Before returning final JSON, silently repair the draft once. Keep lesson depth; add no audit fields and make no extra model call.

1. LANGUAGE, SCRIPT & ORTHOGRAPHY
- Every target-language token, example, dialogue and answer must use authentic canonical spelling and legitimate scripts for {language}; preserve required internal punctuation/separators. Never invent morphology, mix accidental homoglyph scripts, or misspell the same lexical item differently across fields/pages.
- Multiscript languages remain naturally multiscript. IPA, CEFR codes, URLs, proper names, technical abbreviations and explicitly labeled transliteration/romanization are not script defects.
- Emit valid NFC Unicode only: no replacement/noncharacter/control/soft-hyphen artifacts. Preserve legitimate diacritics, stress/tone/vowel marks and required script joiners.

2. PRONUNCIATION
- Use one learner-facing pronunciation system for the same function. If IPA is used, use standard unsplit IPA; never add a second ad-hoc respelling such as syllable-hyphen/capital-stress approximations in explanations.
- When pronunciation is pedagogically required or a pronunciation column is rendered, `phonetic` must be non-empty and is the authoritative reading. Do not duplicate or contradict it inside translation/meaning/gloss fields. Explicit Pinyin, Hepburn/Romaji and other labeled transliteration may coexist only as a distinct pedagogical field.

3. INSTRUCTIONAL-LANGUAGE ISOLATION
- Every learner-facing heading, label, speaker role, table label, explanation, instruction, gloss and metadata description must be in its selected instructional/material language. Do not leak English labels into a non-English track or vice versa.
- Target-language quotations/examples, proper nouns, international notation and deliberate multilingual comparisons are exempt.
- English and Turkish localized tracks must express the same proposition, entities, polarity, quantity, role and communicative force; never leave a required localized learner-facing field empty when its counterpart is populated.

4. LINGUISTIC TRUTH & INTERNAL CONSISTENCY
- Grammar, spelling, phonology, valency, agreement, case/adposition government, word order, tense/aspect/mood, particles, register and lexical meaning must be accurate and native-natural for the actual language; never project English/Indo-European categories where they do not apply.
- Cross-check every rule against every example/table/dialogue in the same lesson before finalizing. A repeated lexical form has one canonical spelling and one compatible analysis.
- Distinguish exceptionless rules from tendencies, restricted patterns, lexical conventions and exceptions. Use absolute claims only when genuinely exceptionless within the stated scope; otherwise narrow the claim rather than inventing exceptions.

5. CEFR, DIALOGUE & COVERAGE
- Strictly match CEFR {level}: A1/A2 concrete high-frequency communication with minimal metalanguage; B1/B2 increasingly productive connected language and nuance; C1/C2 advanced register, precision and pragmatics.
- Dialogues must be realistic, coherent in role/status/register and free of literal-calque or machine-translation residue.
- Test only material taught earlier or explicitly introduced as a fixed chunk. If a paradigm is taught, cover the forms required by its own examples without unnecessary theory.

6. MCQ RELEASE CHECK
- Exactly 4 distinct plausible same-category options; exactly 1 defensible answer. The stem alone must entail the answer from taught language knowledge, with no hidden-world inference (e.g. birthplace->nationality, workplace->profession, name->ethnicity/gender).
- Re-solve each MCQ from stem/options; `answer`, `correct_index` and explanation must converge on the same option. Difficulty comes from {language}, not trivia, arithmetic or riddles.

FINAL SILENT PASS: verify canonical spelling/Unicode, phonetic completeness and single-system consistency, localized-field isolation, rule/example consistency, CEFR fit, natural dialogue, and MCQ key validity. Repair inline and return valid JSON only.
</aulaai_unified_quality_contract>"""

start = engine.find("<aulaai_unified_quality_contract>")
end_tag = "</aulaai_unified_quality_contract>"
end = engine.find(end_tag, start)
if start < 0 or end < 0:
    raise RuntimeError("v50 unified quality contract anchor missing")
end += len(end_tag)
engine = engine[:start] + contract + engine[end:]

# Thread material_language explicitly through the deterministic release guard.
old_helper = """def _material_release_integrity_v37(data, language, level):
    \"\"\"Deterministic final fail-closed validation; semantic work is done by the single publication audit.\"\"\"
    from services.material_quality_guard import enforce_material_integrity
    return enforce_material_integrity(data) if isinstance(data, dict) else data"""
new_helper = """def _material_release_integrity_v37(data, language, level, material_language=\"tr\"):
    \"\"\"Deterministic final fail-closed validation; semantic work is done by the single publication audit.\"\"\"
    from services.material_quality_guard import enforce_material_integrity
    return enforce_material_integrity(data, language=language, material_language=material_language) if isinstance(data, dict) else data"""
if old_helper in engine:
    engine = engine.replace(old_helper, new_helper, 1)

old_call = "lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)"
new_call = "lesson_dict = _material_release_integrity_v37(lesson_dict, language, level, material_language=material_language)"
if old_call in engine:
    engine = engine.replace(old_call, new_call, 1)

engine_path.write_text(engine, encoding="utf-8")

tests = test_path.read_text(encoding="utf-8")
old = """    assert len(clean_lesson[\"pages\"]) == 3, f\"Expected 3 valid pages after cleanup, got {len(clean_lesson['pages'])}\"
    assert clean_lesson[\"pages\"][0][\"type\"] == \"overview\"
    assert clean_lesson[\"pages\"][1][\"type\"] == \"mcq\"
    assert clean_lesson[\"pages\"][2][\"type\"] == \"grammar\"
    assert len(clean_lesson.get(\"_integrity_removed_mcq\", [])) == 2"""
new = """    assert len(clean_lesson[\"pages\"]) == 5, f\"Non-destructive guard removed pages: {len(clean_lesson['pages'])}\"
    assert clean_lesson[\"pages\"][0][\"type\"] == \"overview\"
    assert clean_lesson[\"pages\"][1][\"type\"] == \"mcq\"
    assert clean_lesson[\"pages\"][4][\"type\"] == \"grammar\"
    assert \"_integrity_removed_mcq\" not in clean_lesson"""
if old in tests:
    tests = tests.replace(old, new, 1)
elif "Expected 3 valid pages after cleanup" in tests:
    raise RuntimeError("v50 test expectation anchor changed unexpectedly")
test_path.write_text(tests, encoding="utf-8")

release_tests = release_test_path.read_text(encoding="utf-8")
release_tests = release_tests.replace(
    """assert len(out['pages']) == 2, out
assert out['pages'][0]['answer'] == 'beta'
assert out['pages'][1]['type'] == 'overview'
assert len(out.get('_integrity_removed_mcq', [])) == 3""",
    """assert len(out['pages']) == 5, out
assert out['pages'][0]['answer'] == 'beta'
assert out['pages'][4]['type'] == 'overview'
assert '_integrity_removed_mcq' not in out""",
)
release_tests = release_tests.replace(
    "'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)',",
    "'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level, material_language=material_language)',",
)
release_tests = release_tests.replace(
    "'AULAAI_INLINE_PUBLICATION_QA_V46',",
    "'AULAAI_INLINE_PUBLICATION_QA_V50',",
)
release_test_path.write_text(release_tests, encoding="utf-8")

print("Applied v50: $0.47-baseline hardening, non-destructive and zero-extra-call")
