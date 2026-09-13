from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'services'/'ai_engine.py'
s=p.read_text(encoding='utf-8')
rule=(root/'config'/'material_generation_residual_v36.txt').read_text(encoding='utf-8').strip()
tag='AULAAI_GENERATION_RESIDUAL_V36'
if tag not in s:
    anchor='<output_schema>\n'
    if anchor not in s: raise RuntimeError('v36 anchor missing')
    s=s.replace(anchor,tag+': '+rule+'\n\n'+anchor,1)
p.write_text(s,encoding='utf-8')
print('Applied v36 universal residual generation policy')
