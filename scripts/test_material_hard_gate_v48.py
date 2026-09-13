from services.material_quality_guard import enforce_release_hard_gate, MaterialReleaseRejected
from pathlib import Path

valid = {
    'release_gate': {'1':'PASS','2':'PASS','3':'PASS','4':'PASS'},
    'pages': [
        {'type':'examples','example':'Привет!'},
        {'type':'mcq','prompt':'Выберите правильный ответ.', 'options':['Да','Нет','Привет','Пока'], 'answer':'Да', 'correct_index':0, 'explanation_tr':'Doğru cevap Да.'}
    ]
}
out = enforce_release_hard_gate(valid, 'Russian')
assert 'release_gate' not in out

bad_script = {
    'release_gate': {'1':'PASS','2':'PASS','3':'PASS','4':'PASS'},
    'pages': [{'type':'examples','example':'Привeт'}]
}
try:
    enforce_release_hard_gate(bad_script, 'Russian')
    raise AssertionError('mixed script was not rejected')
except MaterialReleaseRejected as exc:
    assert ':1:' in str(exc)

bad_key = {
    'release_gate': {'1':'PASS','2':'PASS','3':'PASS','4':'PASS'},
    'pages': [{'type':'mcq','prompt':'Выберите.', 'options':['Да','Нет','Привет','Пока'], 'answer':'Да', 'correct_index':1}]
}
try:
    enforce_release_hard_gate(bad_key, 'Russian')
    raise AssertionError('answer mismatch was not rejected')
except MaterialReleaseRejected as exc:
    assert ':4:' in str(exc)

engine = Path('services/ai_engine.py').read_text(encoding='utf-8')
assert 'AULAAI_RELEASE_HARD_GATE_V48' in engine
assert '"release_gate": {"1":"PASS","2":"PASS","3":"PASS","4":"PASS"}' in engine.replace('{{','{').replace('}}','}')
assert 'enforce_release_hard_gate(data, language)' in engine
print('v48 hard gate self-test passed: 1-2-3-4 PASS contract enforced with zero extra model calls')
