from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")
changes = []

# Final cost patch: deliberately surgical. Never regex across ai_engine.py and
# never replace/move function blocks. The previous broad REASONING DIRECTIVE
# regex could consume code between distant prompt fragments during Docker build.

# Keep Gemini 3.7 lesson generation and its existing visible-content budget.

# Make only the existing publication-audit call cheaper. Restrict the edit to
# the audit function slice so no other model call or function can be affected.
a = s.find("def _material_publication_audit(")
b = s.find("\ndef generate_full_lesson(", a)
if a >= 0 and b > a:
    seg = s[a:b]
    old = seg
    if "model=MODEL_STRUCTURAL," in seg:
        seg = seg.replace(
            "model=MODEL_STRUCTURAL,",
            'model="google/gemini-2.5-flash-lite",',
            1,
        )
    if "max_tokens=1800," in seg:
        seg = seg.replace("max_tokens=1800,", "max_tokens=1000,", 1)
    if seg != old:
        s = s[:a] + seg + s[b:]
        changes.append("cheap-publication-audit")

# Startup-import guard: do not write a mutated file if any public function that
# server.py depends on disappeared. This turns future patch mistakes into a build
# failure before deployment instead of a 502/runtime ImportError.
required_public_functions = (
    "ai_generate_report_insights",
    "ai_generate_activity_batch",
    "ai_explain_word",
    "ai_explain_activity",
)
missing = [name for name in required_public_functions if f"def {name}(" not in s]
if missing:
    raise RuntimeError("v30 safety guard: missing ai_engine exports: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied safe final cost pass: " + (", ".join(changes) if changes else "already applied/no compatible audit anchor"))
