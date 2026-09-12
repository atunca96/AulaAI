from pathlib import Path

path = Path('public/js/app.js')
src = path.read_text(encoding='utf-8')

quiz_start_marker = 'async function viewQuiz(quizId, title) {'
quiz_end_marker = '\nfunction switchQuizViewTab('
assign_start_marker = 'async function viewAssignment(assignmentId, title) {'
assign_end_marker = '\nasync function previewAssignment('

quiz_start = src.find(quiz_start_marker)
if quiz_start < 0:
    raise RuntimeError('viewQuiz start not found')
quiz_end = src.find(quiz_end_marker, quiz_start)
if quiz_end < 0:
    raise RuntimeError('viewQuiz end not found')

assign_start = src.find(assign_start_marker)
if assign_start < 0:
    raise RuntimeError('viewAssignment start not found')
assign_end = src.find(assign_end_marker, assign_start)
if assign_end < 0:
    raise RuntimeError('viewAssignment end not found')

quiz_fn = src[quiz_start:quiz_end]
clone = quiz_fn

# Keep the assignment panel structurally identical to the quiz panel. Only the
# data source, state slot, DOM namespace, and assessment-specific wording differ.
clone = clone.replace(
    'async function viewQuiz(quizId, title) {',
    'async function viewAssignment(assignmentId, title) {',
    1,
)
clone = clone.replace(
    'window._currentViewingQuiz = { id: quizId, title: title };\n  window._currentViewingAssignment = null;',
    'window._currentViewingAssignment = { id: assignmentId, title: title };\n  window._currentViewingQuiz = null;',
    1,
)
clone = clone.replace("api('/quiz/take?quiz_id=' + quizId)", "api('/assignment/take?assignment_id=' + assignmentId)")
clone = clone.replace("api('/quiz/responses?quiz_id=' + quizId)", "api('/assignment/responses?assignment_id=' + assignmentId)")
clone = clone.replace('quizData', 'assignmentData')
clone = clone.replace('quizId', 'assignmentId')
clone = clone.replace('qv-', 'av-')
clone = clone.replace('Sınav Devam Ediyor', 'Ödev Devam Ediyor')
clone = clone.replace('Sınav devam ediyor', 'Ödev devam ediyor')

# The clone must point at assignment endpoints and must not retain the original
# quiz state assignment. Fail the build rather than silently shipping a mixed UI.
required = [
    "api('/assignment/take?assignment_id=' + assignmentId)",
    "api('/assignment/responses?assignment_id=' + assignmentId)",
    'window._currentViewingAssignment = { id: assignmentId, title: title };',
    "id=\"av-questions\"",
    "id=\"av-responses\"",
]
for token in required:
    if token not in clone:
        raise RuntimeError(f'assignment parity verification failed: {token}')
if "api('/quiz/take?quiz_id='" in clone or 'window._currentViewingQuiz = { id:' in clone:
    raise RuntimeError('assignment parity clone still contains quiz-only state/endpoint')

src = src[:assign_start] + clone + src[assign_end:]
path.write_text(src, encoding='utf-8')
print('Applied assignment results parity: assignment review now mirrors quiz review panel')
