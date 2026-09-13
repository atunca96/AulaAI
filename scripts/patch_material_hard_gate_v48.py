from pathlib import Path

root = Path(__file__).resolve().parents[1]
ai_path = root / 'services' / 'ai_engine.py'
pipe_path = root / 'services' / 'legacy' / 'pdf_pipeline.py'
gate = (root / 'config' / 'material_hard_gate_v48.txt').read_text(encoding='utf-8').strip()

ai = ai_path.read_text(encoding='utf-8')
tag = 'AULAAI_RELEASE_HARD_GATE_V48'

# Put the gate above every other lesson-quality instruction.
anchor = 'system_prompt = f"""<role>'
if tag not in ai:
    if anchor not in ai:
        raise RuntimeError('v48 lesson system prompt anchor missing')
    gate_for_fstring = gate.replace('{', '{{').replace('}', '}}')
    replacement = 'system_prompt = f"""<' + tag + '>\n' + gate_for_fstring + '\n</' + tag + '>\n\n<role>'
    ai = ai.replace(anchor, replacement, 1)

# Require a tiny same-call PASS attestation in the generated object. It is removed
# by the deterministic guard before persistence/PDF rendering.
schema_anchor = 'Return ONLY valid JSON matching this schema:\n{{\n  "pages": ['
schema_replacement = 'Return ONLY valid JSON matching this schema:\n{{\n  "release_gate": {{"1":"PASS","2":"PASS","3":"PASS","4":"PASS"}},\n  "pages": ['
if '"release_gate": {{"1":"PASS"' not in ai:
    if schema_anchor not in ai:
        raise RuntimeError('v48 output schema anchor missing')
    ai = ai.replace(schema_anchor, schema_replacement, 1)

# Fail closed after the single generation call. No model call/retry is introduced.
old_helper = '''    from services.material_quality_guard import enforce_material_integrity
    return enforce_material_integrity(data) if isinstance(data, dict) else data
'''
new_helper = '''    from services.material_quality_guard import enforce_material_integrity, enforce_release_hard_gate
    if not isinstance(data, dict):
        return data
    data = enforce_release_hard_gate(data, language)
    return enforce_material_integrity(data)
'''
if 'enforce_release_hard_gate(data, language)' not in ai:
    if old_helper not in ai:
        raise RuntimeError('v48 deterministic release helper anchor missing')
    ai = ai.replace(old_helper, new_helper, 1)

# The hard gate must never add another semantic model call.
start = ai.find('def _material_release_integrity_v37(')
end = ai.find('\ndef ', start + 5)
body = ai[start:end if end > start else len(ai)]
if '_call_ai(' in body:
    raise RuntimeError('v48 hard gate must be deterministic-only after generation')
if tag not in ai or 'enforce_release_hard_gate(data, language)' not in ai:
    raise RuntimeError('v48 AI gate verification failed')
ai_path.write_text(ai, encoding='utf-8')

# One rejected topic rejects the whole classroom release; do not silently publish
# a partial class/PDF. Other unrelated topic errors preserve legacy behavior.
pipe = pipe_path.read_text(encoding='utf-8')
old_topic = '''                except Exception as e:
                    _log(f"Topic Error: {e}")
'''
new_topic = '''                except Exception as e:
                    if 'MATERIAL_RELEASE_HARD_GATE:' in str(e):
                        raise RuntimeError(str(e))
                    _log(f"Topic Error: {e}")
'''
if "if 'MATERIAL_RELEASE_HARD_GATE:' in str(e):" not in pipe:
    if old_topic not in pipe:
        raise RuntimeError('v48 topic failure anchor missing')
    pipe = pipe.replace(old_topic, new_topic, 1)

# Preserve failed state and propagate the hard rejection so the caller never reaches
# the normal 'classroom ready' release path.
old_fatal = '''        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0, build_stage = 'failed', build_message = ? WHERE id = ?", (f"Build error: {str(e)[:120]}", course_id))
            db.commit()


def process_pdf_to_classroom'''
new_fatal = '''        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0, build_stage = 'failed', build_message = ? WHERE id = ?", (f"Build error: {str(e)[:120]}", course_id))
            db.commit()
        if 'MATERIAL_RELEASE_HARD_GATE:' in str(e):
            raise


def process_pdf_to_classroom'''
if "if 'MATERIAL_RELEASE_HARD_GATE:' in str(e):\n            raise\n\n\ndef process_pdf_to_classroom" not in pipe:
    if old_fatal not in pipe:
        raise RuntimeError('v48 fatal propagation anchor missing')
    pipe = pipe.replace(old_fatal, new_fatal, 1)

pipe_path.write_text(pipe, encoding='utf-8')
print('Applied v48: four-rule same-call hard gate + fail-closed classroom release')
