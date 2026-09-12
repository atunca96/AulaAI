# Obsolete compatibility shim.
# The production endpoint now uses services/pdf_renderer_v12.py directly, so the
# old build-time renderer mutation is intentionally disabled. Keeping this file
# as a no-op lets older Docker build chains remain deployable without rollback.
print('PDF runtime v11 shim skipped; consolidated renderer v12 is active')
