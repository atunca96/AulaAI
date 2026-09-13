from pathlib import Path
import runpy

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

s = s.replace(
    '- Keep every lesson strictly appropriate to CEFR {level}. Depth must come from clarity, useful examples, contrasts, dialogues and practice, not from unnecessary advanced content.',
    '- Keep every lesson strictly appropriate to CEFR {level}. At A1, exclude specialist phonology/prosody, lexical pitch-accent systems, dialect detail, historical linguistics, rare exceptions and advanced register theory unless the curriculum explicitly requires that exact topic. Depth must come from clarity, high-frequency examples, contrasts, dialogues and practice, not advanced theory.',
    1,
)

s = s.replace(
    '- Preserve names, speaker identities, gender where relevant, roles, relationships, places, numbers, dates, times, quantities and polarity consistently across target-language, English and Turkish fields.',
    '- Preserve names, speaker identities, gender where relevant, roles, relationships, places, numbers, dates, times, quantities and polarity consistently across target-language, English and Turkish fields. Once a person/place is introduced, lock its target-script form, canonical romanized/localized name and role; reuse that identity exactly and never mutate it into a similar-looking name during localization.',
    1,
)

s = s.replace(
    '6. SELF-CONTAINED EDITORIAL QUALITY\n',
    '6. SELF-CONTAINED EDITORIAL QUALITY\n- Cultural notes must be high-confidence and narrowly worded; never turn a tendency into an absolute such as always/everyone/never unless literally exceptionless.\n',
    1,
)

s = s.replace(
    '8. CEFR AND LANGUAGE LOAD\n',
    '8. CEFR AND LANGUAGE LOAD\n- If an advanced side-topic accidentally appears in lesson prose, do not legitimize it through assessment; at A1 never test specialist pitch-accent/prosody theory, dialect detail, rare exceptions or advanced register distinctions unless explicitly required by the curriculum.\n',
    1,
)

s = s.replace(
    '- Prefer omission or simplification over any uncertain linguistic claim.\n</final_material_preflight_v24>',
    '- Prefer omission or simplification over any uncertain linguistic claim.\n- Final quality floor: silently rate Accuracy, Naturalness, CEFR Fit, Pedagogy, Grounding, Localization Fidelity, Entity Consistency and Classroom Usability; revise or omit any failing content until every category is at least 9.5/10.\n</final_material_preflight_v24>',
    1,
)

p.write_text(s, encoding='utf-8')
print('Applied v24b: tighter A1 scope, identity lock, culture safety and quality floor')

# Keep Dockerfile stable: chain the next quality layers from this already-enabled build step.
root = Path(__file__).resolve().parents[1]
for patch_name in ('patch_lesson_quality_v24c.py', 'patch_material_publication_audit_v27.py'):
    patch_path = root / 'scripts' / patch_name
    if patch_path.exists():
        runpy.run_path(str(patch_path), run_name='__main__')
    else:
        print(f'v24b chain warning: {patch_name} not found')
