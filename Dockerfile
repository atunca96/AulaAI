FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update -qq && apt-get install -y -qq \
    tesseract-ocr tesseract-ocr-spa tesseract-ocr-deu tesseract-ocr-fra \
    tesseract-ocr-ita tesseract-ocr-por tesseract-ocr-rus tesseract-ocr-chi-sim \
    tesseract-ocr-jpn tesseract-ocr-ara tesseract-ocr-tur tesseract-ocr-nld \
    tesseract-ocr-swe tesseract-ocr-kor tesseract-ocr-ell poppler-utils \
    fontconfig fonts-noto-core fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN python scripts/patch_pdf_cache_bust_v39.py \
    && python scripts/patch_pdf_build_prereqs_v43.py \
    && python scripts/patch_pdf_single_path_v13.py \
    && python scripts/patch_pdf_unicode_fonts_v14.py \
    && python scripts/patch_bilingual_finalizer_stall.py \
    && python scripts/patch_material_mcq_bilingual.py \
    && python scripts/patch_material_mcq_existing_shuffle.py \
    && python scripts/patch_assessment_persistence.py \
    && python scripts/patch_assignment_results_parity.py \
    && python scripts/patch_quality_convergence_v10b.py \
    && python scripts/patch_material_quality_gate_v12.py \
    && python scripts/smoke_test_pdf_renderer.py \
    && python scripts/patch_material_locale_stability_v17.py \
    && python scripts/patch_material_locale_exact_v18.py \
    && python scripts/patch_material_locale_source_v19.py \
    && python scripts/patch_material_persist_pronunciation_v20.py \
    && python scripts/patch_disable_bilingual_runtime_v21.py \
    && python scripts/patch_generation_efficiency_v22.py \
    && python scripts/patch_lesson_quality_v24.py \
    && python scripts/patch_lesson_quality_v24b.py \
    && python scripts/patch_material_final_gate_v29.py \
    && python scripts/patch_material_absolute_quality_v30.py \
    && python scripts/patch_material_language_necessity_v32.py \
    && python scripts/patch_material_quality_v33.py \
    && python scripts/patch_native_script_v35.py \
    && python scripts/patch_material_generation_residual_v36.py \
    && python scripts/patch_material_release_integrity_v37.py \
    && python scripts/patch_material_cost_guard_v34.py \
    && python scripts/patch_material_payload_compact_v45.py \
    && python scripts/patch_openrouter_prompt_cache_v47.py \
    && python scripts/patch_consolidate_prompt_contract_v49.py \
    && python scripts/patch_release_hardening_v50.py \
    && python scripts/test_release_hardening_v50.py \
    && python scripts/patch_release_hardening_v52.py \
    && python scripts/patch_release_hardening_v53.py \
    && python scripts/patch_v54_build_compat.py \
    && python scripts/patch_release_hardening_v54.py \
    && python scripts/test_release_hardening_v52.py \
    && python scripts/test_release_hardening_v54.py \
    && python scripts/patch_canonical_material_prompt.py \
    && python scripts/test_material_release_integrity_v37.py \
    && python scripts/test_universal_quality.py \
    && python -m py_compile server.py worker.py runtime_bootstrap.py services/ai_engine.py services/material_generation_prompt.py services/bilingual_finisher.py services/pdf_renderer_v12.py services/material_quality_guard.py services/legacy/pdf_pipeline.py

CMD ["python", "runtime_bootstrap.py"]
