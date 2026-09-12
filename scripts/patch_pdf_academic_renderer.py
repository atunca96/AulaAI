from pathlib import Path

# Emergency rollback switch: keep the stable existing PDF export path active.
# The experimental academic renderer remains in the repository for later work,
# but this build patch intentionally does not inject it into server.py.
path = Path('server.py')
if not path.exists():
    raise RuntimeError('server.py missing')
print('Academic PDF renderer disabled; using stable existing PDF export path')
