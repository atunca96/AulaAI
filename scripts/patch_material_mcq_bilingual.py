from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
ai_path = root / "services" / "ai_engine.py"
bi_path = root / "services" / "bilingual_finisher.py"
app_path = root / "public" / "js" / "app.js"

# --- 1) Lesson-generation schema + deterministic answer-position normalization ---
src = ai_path.read_text(encoding="utf-8")

schema_old = '''      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "answer": "Correct answer",
      "distractors": ["Distractor 1", "Distractor 2", "Distractor 3"],'''
schema_new = '''      "options": ["Canonical option 1", "Canonical option 2", "Canonical option 3", "Canonical option 4"],
      "options_en": ["English display for option 1", "English display for option 2", "English display for option 3", "English display for option 4"],
      "options_tr": ["Turkish display for option 1", "Turkish display for option 2", "Turkish display for option 3", "Turkish display for option 4"],
      "answer": "Exact canonical correct option (must equal one item in options)",
      "correct_index": 0,
      "distractors": ["Distractor 1", "Distractor 2", "Distractor 3"],'''
if schema_old not in src:
    raise RuntimeError("MCQ output schema anchor missing")
src = src.replace(schema_old, schema_new, 1)

reason_anchor = '''6. Strict Grammar Rules & Comparisons Source Boundary (pages[].rules & pages[].comparisons):'''
reason_insert = '''6. MATERIAL-INTERNAL MCQ LOCALIZATION & ANSWER-POSITION RULES (CRITICAL):
   - Every MCQ page MUST provide all three question fields: `prompt` in the target language, `prompt_en` in natural English, and `prompt_tr` in natural Turkish. Never leave `prompt_en` or `prompt_tr` blank.
   - `options` is the canonical answer-value array used for grading. `answer` MUST exactly equal one item in `options` and there must be exactly one defensible correct answer.
   - `options_en` and `options_tr` MUST each contain exactly the same number of entries as `options`, index-aligned one-to-one.
   - If an option itself is target-language linguistic material being tested (a word, phrase, sentence, character, inflection, pronunciation form, etc.), copy that option unchanged into BOTH `options_en` and `options_tr`; do not translate away the thing being tested.
   - If an option is explanatory/meta-language prose (for example, a description such as "It changes to the second tone"), localize that display text naturally into English in `options_en` and Turkish in `options_tr`.
   - Do NOT systematically put the correct answer first. Vary the correct option position across questions; post-processing may also reorder options while preserving index alignment.
7. Strict Grammar Rules & Comparisons Source Boundary (pages[].rules & pages[].comparisons):'''
if reason_anchor not in src:
    raise RuntimeError("MCQ reasoning anchor missing")
src = src.replace(reason_anchor, reason_insert, 1)

start_marker = '            # Synchronize MCQ options and distractors so both are always fully available\n'
end_marker = '            # Preserve authentic descriptive title if present, otherwise assign a clean title\n'
start = src.find(start_marker)
end = src.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("MCQ normalization block anchors missing")
new_block = '''            # Synchronize MCQ options, bilingual display labels, and answer position.
            # Canonical `options` are used for grading; localized arrays are display-only.
            if p.get("type") == "mcq" or p.get("prompt"):
                p["type"] = "mcq"
                ans = str(p.get("answer", "")).strip()
                opts = p.get("options")
                distrs = p.get("distractors")

                if opts and isinstance(opts, list) and len(opts) > 1:
                    clean_opts = [str(o).strip() for o in opts if str(o).strip()]
                elif distrs and isinstance(distrs, list) and len(distrs) > 0:
                    clean_distrs = [str(d).strip() for d in distrs if str(d).strip()]
                    clean_opts = ([ans] if ans else []) + clean_distrs
                else:
                    clean_opts = []

                # Recover answer from an explicit index if the model supplied one.
                raw_idx = p.get("correct_index")
                if not ans and isinstance(raw_idx, int) and 0 <= raw_idx < len(clean_opts):
                    ans = clean_opts[raw_idx]
                if not ans and clean_opts:
                    ans = clean_opts[0]
                if ans and ans not in clean_opts:
                    clean_opts = [ans] + clean_opts

                # Keep localized arrays aligned with the pre-shuffle canonical option order.
                opts_en = p.get("options_en") if isinstance(p.get("options_en"), list) else []
                opts_tr = p.get("options_tr") if isinstance(p.get("options_tr"), list) else []
                opts_en = [str(x).strip() for x in opts_en] if len(opts_en) == len(clean_opts) else list(clean_opts)
                opts_tr = [str(x).strip() for x in opts_tr] if len(opts_tr) == len(clean_opts) else list(clean_opts)

                # Stable deterministic shuffle: avoids the historical all-A pattern while
                # producing the same persisted order for the same generated question.
                if len(clean_opts) > 1:
                    seed = f"{topic}|{p.get('prompt','')}|{ans}"
                    order = sorted(
                        range(len(clean_opts)),
                        key=lambda i: hashlib.sha256(f"{seed}|{i}".encode("utf-8")).hexdigest(),
                    )
                    clean_opts = [clean_opts[i] for i in order]
                    opts_en = [opts_en[i] for i in order]
                    opts_tr = [opts_tr[i] for i in order]

                p["options"] = clean_opts
                p["options_en"] = opts_en
                p["options_tr"] = opts_tr
                p["answer"] = ans
                p["correct_index"] = clean_opts.index(ans) if ans in clean_opts else -1
                p["distractors"] = [o for o in clean_opts if o != ans]

'''
src = src[:start] + new_block + src[end:]

# Preserve localized option arrays in the flexible/fallback MCQ path as well.
fallback_old = '''            "options": opts,
            "distractors": distrs,
            "answer": ans,'''
fallback_new = '''            "options": opts,
            "options_en": mcq.get("options_en") or opts,
            "options_tr": mcq.get("options_tr") or opts,
            "distractors": distrs,
            "answer": ans,
            "correct_index": (opts.index(ans) if ans in opts else -1),'''
if fallback_old not in src:
    raise RuntimeError("Fallback MCQ anchor missing")
src = src.replace(fallback_old, fallback_new, 1)
ai_path.write_text(src, encoding="utf-8")

# --- 2) Bilingual finalizer: use real translation for missing English MCQ stems ---
bi = bi_path.read_text(encoding="utf-8")
anchor = '    to_translate_to_tr = []\n'
if anchor not in bi:
    raise RuntimeError("Bilingual collection anchor missing")
bi = bi.replace(anchor, '    to_translate_to_tr = []\n    to_translate_to_en = []\n', 1)

mcq_collect_old = '''            # MCQ
            if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                to_translate_to_tr.append(p["prompt"].strip())
            if p.get("explanation") and (not p.get("explanation_tr") or p.get("explanation_tr") == p.get("explanation")):
                to_translate_to_tr.append(p["explanation"].strip())
'''
mcq_collect_new = '''            # MCQ — collect missing UI-language stems in both directions.
            if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                to_translate_to_tr.append(p["prompt"].strip())
            if p.get("prompt") and (not p.get("prompt_en") or p.get("prompt_en") == p.get("prompt")):
                to_translate_to_en.append(p["prompt"].strip())
            if p.get("explanation") and (not p.get("explanation_tr") or p.get("explanation_tr") == p.get("explanation")):
                to_translate_to_tr.append(p["explanation"].strip())
'''
if mcq_collect_old not in bi:
    raise RuntimeError("Bilingual MCQ collection anchor missing")
bi = bi.replace(mcq_collect_old, mcq_collect_new, 1)

translate_old = '''    trans_map = batch_translate_strings(unique_needed, target_lang="tr")

    # Also record in title_pairs
'''
translate_new = '''    trans_map = batch_translate_strings(unique_needed, target_lang="tr")
    unique_needed_en = list(set(to_translate_to_en))
    trans_map_en = batch_translate_strings(unique_needed_en, target_lang="en") if unique_needed_en else {}

    # Also record in title_pairs
'''
if translate_old not in bi:
    raise RuntimeError("Bilingual translation-map anchor missing")
bi = bi.replace(translate_old, translate_new, 1)

apply_old = '''                # MCQ
                if p.get("prompt") and not p.get("prompt_en"):
                    p["prompt_en"] = to_english_study_prompt(p.get("prompt"), p.get("prompt_tr"))
                if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                    p["prompt_tr"] = trans_map.get(p["prompt"].strip(), p["prompt"])
'''
apply_new = '''                # MCQ
                if p.get("prompt") and (not p.get("prompt_en") or p.get("prompt_en") == p.get("prompt")):
                    p["prompt_en"] = trans_map_en.get(
                        p["prompt"].strip(),
                        to_english_study_prompt(p.get("prompt"), p.get("prompt_tr")),
                    )
                if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                    p["prompt_tr"] = trans_map.get(p["prompt"].strip(), p["prompt"])
'''
if apply_old not in bi:
    raise RuntimeError("Bilingual MCQ apply anchor missing")
bi = bi.replace(apply_old, apply_new, 1)
bi_path.write_text(bi, encoding="utf-8")

# --- 3) Frontend: display locale-specific option labels but grade canonical values ---
app = app_path.read_text(encoding="utf-8")
resolve_anchor = '''function resolveStudyPrompt(p, topic) {
  if (currentLang === 'tr') {
    if (p.prompt_tr) return translatePrompt(p.prompt_tr, 'tr');
    return translatePrompt(p.prompt || p.question || "Doğru seçeneği belirleyin:", 'tr');
  }
  // English mode (default)
  if (p.prompt_en) return getEnglishStudyPrompt(p.prompt_en, p.prompt_tr);
  return getEnglishStudyPrompt(p.prompt || p.question || '', p.prompt_tr);
}
'''
resolve_new = resolve_anchor + '''
function resolveStudyOptionLabel(p, canonicalOption) {
  const canonical = Array.isArray(p.options) ? p.options : [];
  const idx = canonical.indexOf(canonicalOption);
  if (idx < 0) return canonicalOption;
  const localized = currentLang === 'tr' ? p.options_tr : p.options_en;
  if (Array.isArray(localized) && localized.length === canonical.length && localized[idx]) {
    return localized[idx];
  }
  return canonicalOption;
}
'''
if resolve_anchor not in app:
    raise RuntimeError("Frontend study-prompt anchor missing")
app = app.replace(resolve_anchor, resolve_new, 1)

# Replace only the two option-label render sites; canonical `opt` remains in onclick/data-opt.
label_old = '${fixDiacritics(safeStr(opt))}'
label_new = '${fixDiacritics(safeStr(resolveStudyOptionLabel(p, opt)))}'
label_count = app.count(label_old)
if label_count < 2:
    raise RuntimeError(f"Expected >=2 material option label sites, found {label_count}")
app = app.replace(label_old, label_new, 2)
app_path.write_text(app, encoding="utf-8")

# Bust browser cache for the changed frontend asset.
for html_path in (root / "public").glob("*.html"):
    h = html_path.read_text(encoding="utf-8")
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260912_v212', h)
    if h2 != h:
        html_path.write_text(h2, encoding="utf-8")

print("Applied material MCQ bilingual localization and answer-position normalization")
