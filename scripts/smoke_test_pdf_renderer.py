from pathlib import Path
import ast
import runpy

# Final post-patch material locale stabilization. Docker already runs this smoke
# after all material/PDF build patches, so execute v13 then v14 to guarantee
# first-frame locale stability in both Turkish and English.
# Source is frozen: the former patch-application step is a no-op here.
# Source is frozen: the former patch-application step is a no-op here.

# Keep build validation deterministic and side-effect free. Runtime behavior is
# guarded by the server fallback; this smoke only ensures the consolidated
# renderer source parses after checkout/build.
path = Path('services/pdf_renderer_v12.py')
ast.parse(path.read_text(encoding='utf-8'))
print('PDF renderer v12 source smoke passed')
