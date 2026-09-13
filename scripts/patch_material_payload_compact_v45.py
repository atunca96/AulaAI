from pathlib import Path
import runpy

p=Path(__file__).resolve().parents[1]/'services'/'ai_engine.py'
s=p.read_text(encoding='utf-8')
old='    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))\n'
new='''    def _compact_review_payload(value):
        if isinstance(value, list):
            return [_compact_review_payload(v) for v in value]
        if isinstance(value, dict):
            return {k: _compact_review_payload(v) for k, v in value.items() if k not in {"correct_index", "distractors", "id", "uuid", "source_hash", "content_hash", "generated_at", "updated_at"} and not str(k).startswith("_")}
        return value
    payload = json.dumps(_compact_review_payload(data), ensure_ascii=False, separators=(",", ":"))
'''
if old not in s:
    raise RuntimeError('payload anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('Applied compact material review payload')

# v46 folds the same semantic release contract into the existing generation call,
# then removes the redundant full-context post-generation model pass.
runpy.run_path(str(Path(__file__).resolve().parent / 'patch_material_inline_quality_v46.py'), run_name='__main__')
