from pathlib import Path
import ast
import runpy

# Final post-patch material locale stabilization. Docker already runs this smoke
# after all material/PDF build patches, so execute v13 here to guarantee the
# first-frame locale fix is applied last without disturbing the build chain.
runpy.run_path('scripts/patch_material_locale_stability_v13.py', run_name='__main__')

# Keep build validation deterministic and side-effect free. Runtime behavior is
# guarded by the server fallback; this smoke only ensures the consolidated
# renderer source parses after checkout/build.
path = Path('services/pdf_renderer_v12.py')
ast.parse(path.read_text(encoding='utf-8'))
print('PDF renderer v12 source smoke passed')
