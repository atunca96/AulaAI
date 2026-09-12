from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"{label}: anchor not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied {label}")


finisher = Path("services/bilingual_finisher.py")
replace_once(
    finisher,
    'res = _call_ai([{"role": "user", "content": prompt}], model=model, max_tokens=2500, temperature=0.1, json_mode=True)',
    'res = _call_ai([{"role": "user", "content": prompt}], model=model, max_tokens=1200, temperature=0.1, json_mode=True)',
    "bounded bilingual translation output/timeout",
)
replace_once(
    finisher,
    'with ThreadPoolExecutor(max_workers=1) as executor:',
    'with ThreadPoolExecutor(max_workers=min(2, max(1, total_chunks))) as executor:',
    "parallel bilingual translation batches",
)

server = Path("server.py")
old_cleanup = '''        # 1. Reset Classroom Building flags (interrupted builds)\n        db.execute("""\n            UPDATE courses SET is_building = 0, build_stage = 'interrupted', build_message = 'Build interrupted by server restart'\n            WHERE is_building = 1\n        """)\n'''
new_cleanup = '''        # 1. Recover classrooms whose substantive build already finished and only the\n        # bilingual finalizer was still running when the process restarted.\n        db.execute("""\n            UPDATE courses\n            SET is_building = 0, build_stage = 'completed', progress = 100, build_message = 'Classroom is ready!'\n            WHERE is_building = 1\n              AND build_stage = 'finalizing'\n              AND total_steps > 0\n              AND progress >= total_steps\n        """)\n\n        # Reset genuinely interrupted classroom builds.\n        db.execute("""\n            UPDATE courses SET is_building = 0, build_stage = 'interrupted', build_message = 'Build interrupted by server restart'\n            WHERE is_building = 1\n        """)\n'''
replace_once(server, old_cleanup, new_cleanup, "finalizing-classroom startup recovery")
