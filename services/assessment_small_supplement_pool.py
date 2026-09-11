"""Assessment-only small supplementary pool tuning.

Keeps the stable legacy candidate pipeline unchanged for normal quiz generation.
Only tiny completion requests (1-4 missing questions) receive extra first-pass
candidate headroom so one rejected item does not leave the final quiz short.
Lesson/material generation is not involved.
"""


def install():
    from services import assessment_legacy_calibration as calibration

    if getattr(calibration, "_small_supplement_pool_installed", False):
        return

    original = calibration._candidate_count

    def candidate_count(guard, args, kwargs, requested):
        try:
            requested = max(1, int(requested))
        except Exception:
            requested = 1

        # content_engine may ask only for the final 1-4 missing questions. Asking the
        # model for exactly one candidate is fragile because any quality rejection
        # leaves the completed quiz short and triggers another repair chain.
        if requested <= 4:
            return {1: 6, 2: 6, 3: 8, 4: 10}[requested]

        return original(guard, args, kwargs, requested)

    calibration._candidate_count = candidate_count
    calibration._small_supplement_pool_installed = True
