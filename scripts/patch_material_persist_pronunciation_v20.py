from pathlib import Path

root = Path(__file__).resolve().parents[1]
ai_path = root / 'services' / 'ai_engine.py'
ai = ai_path.read_text(encoding='utf-8')

old = '''                        clean_items.append({
                            "term": it.get("term") or it.get("word") or "",
                            "phonetic": it.get("phonetic") or "",
                            "translation": it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_tr": it.get("translation_tr") or "",
                            "example": it.get("example") or "",
                            "example_en": it.get("example_en") or it.get("translation_example") or "",
                            "example_tr": it.get("example_tr") or "",
                            "explanation": it.get("explanation") or it.get("tip") or "",
                            "explanation_tr": it.get("explanation_tr") or ""
                        })'''
new = '''                        _expl_en = it.get("explanation_en") or it.get("explanation") or it.get("tip") or ""
                        clean_items.append({
                            "term": it.get("term") or it.get("word") or "",
                            "phonetic": it.get("phonetic") or it.get("phonetic_en") or "",
                            "phonetic_en": it.get("phonetic_en") or it.get("phonetic") or "",
                            "phonetic_tr": it.get("phonetic_tr") or "",
                            "translation": it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_en": it.get("translation_en") or it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_tr": it.get("translation_tr") or "",
                            "example": it.get("example") or "",
                            "example_en": it.get("example_en") or it.get("translation_example") or "",
                            "example_tr": it.get("example_tr") or "",
                            "explanation": _expl_en,
                            "explanation_en": _expl_en,
                            "explanation_tr": it.get("explanation_tr") or ""
                        })'''
count = ai.count(old)
if count != 1:
    raise RuntimeError(f'v20 primary item normalizer anchor expected 1, found {count}')
ai = ai.replace(old, new, 1)

old2 = '''                clean_items.append({
                    "term": v.get("term") or v.get("word") or "",
                    "phonetic": v.get("phonetic") or "",
                    "translation": v.get("translation") or v.get("meaning") or "",
                    "translation_tr": v.get("translation_tr") or "",
                    "example": v.get("example") or "",
                    "example_en": v.get("example_en") or v.get("translation_example") or "",
                    "example_tr": v.get("example_tr") or "",
                    "explanation": v.get("explanation") or v.get("tip") or "",
                    "explanation_tr": v.get("explanation_tr") or ""
                })'''
new2 = '''                _expl_en = v.get("explanation_en") or v.get("explanation") or v.get("tip") or ""
                clean_items.append({
                    "term": v.get("term") or v.get("word") or "",
                    "phonetic": v.get("phonetic") or v.get("phonetic_en") or "",
                    "phonetic_en": v.get("phonetic_en") or v.get("phonetic") or "",
                    "phonetic_tr": v.get("phonetic_tr") or "",
                    "translation": v.get("translation") or v.get("meaning") or "",
                    "translation_en": v.get("translation_en") or v.get("translation") or v.get("meaning") or "",
                    "translation_tr": v.get("translation_tr") or "",
                    "example": v.get("example") or "",
                    "example_en": v.get("example_en") or v.get("translation_example") or "",
                    "example_tr": v.get("example_tr") or "",
                    "explanation": _expl_en,
                    "explanation_en": _expl_en,
                    "explanation_tr": v.get("explanation_tr") or ""
                })'''
count2 = ai.count(old2)
if count2 != 1:
    raise RuntimeError(f'v20 fallback item normalizer anchor expected 1, found {count2}')
ai = ai.replace(old2, new2, 1)

# Hard guarantee: generated pronunciation metadata must survive normalization.
if '"explanation_en": _expl_en' not in ai or '"phonetic_tr": it.get("phonetic_tr")' not in ai:
    raise RuntimeError('v20 persisted pronunciation fields missing after patch')

ai_path.write_text(ai, encoding='utf-8')
print('Applied material pronunciation persistence v20')
