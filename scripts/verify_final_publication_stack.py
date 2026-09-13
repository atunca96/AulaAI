from pathlib import Path

root = Path(__file__).resolve().parents[1]
ai = (root / "services" / "ai_engine.py").read_text(encoding="utf-8")
pdf = (root / "services" / "pdf_academic_renderer.py").read_text(encoding="utf-8")

checks = {
    "final audit principles installed": "FINAL-RELEASE PRINCIPLES:" in ai,
    "publication audit invoked twice": ai.count("lesson_dict = _material_publication_audit(lesson_dict, language, level)") >= 2,
    "full audit payload retained": "payload = payload[:26000]" not in ai,
    "expanded audit repair budget": "max_tokens=3000" in ai,
    "target language label helper installed": "def _target_language_label(" in pdf,
    "generic target-language header removed": "'Hedef Dilde Örnek' if is_tr else 'Target-Language Example'" not in pdf,
    "localized footer installed": "footer_text = 'AulaAI Eğitim Sistemi" in pdf,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("Final publication stack verification failed: " + "; ".join(failed))

print("Final publication stack verified: material double-audit + deterministic PDF localization active")
