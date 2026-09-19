assert RC.hidden_world_reason(page) == "", RC.explain_hidden_world(page)
assert RC.page_is_renderable(page, True)[0]
assert RC.page_is_renderable(page, False)[0]
assert seen[0][0].startswith(
    "publication_feedback_retry:2:Family Members and Possessive Adjectives"
)
assert seen[0][1] == ERROR
assert "identity fact inferred from a biographical one" in seen[1][1]
assert page["answer"] == "nuestra"
assert page["options"] == ["nuestra", "nuestro", "nuestras", "nuestros"]
print(
    "[PUBLICATION-FEEDBACK] refusal chain is fed back verbatim until the "
    "unchanged renderer contract is clean"
)


# The outer pipeline must keep content refusals in quality_review rather than
# writing the old terminal failed state before the retry prompt runs.
from services.legacy import pdf_pipeline as P  # noqa: E402
import inspect  # noqa: E402

source = inspect.getsource(P._run_publication_until_ready)
assert "publication_error = str(failure)" in source
assert "repair_publication_refusal_feedback" in source
assert "build_stage='quality_review'" in source
assert "UPDATE courses SET is_building=0, build_stage='failed'" not in source
assert "mark_failed(" not in source
assert "while True" in source
print("[PUBLICATION-FEEDBACK] outer publication loop has no content-retry ceiling")