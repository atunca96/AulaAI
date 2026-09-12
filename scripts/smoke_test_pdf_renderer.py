from pathlib import Path
import ast

# Keep build validation deterministic and side-effect free. Runtime behavior is
# guarded by the server fallback; this smoke only ensures the consolidated
# renderer source parses after checkout/build.
path = Path('services/pdf_renderer_v12.py')
ast.parse(path.read_text(encoding='utf-8'))
print('PDF renderer v12 source smoke passed')
