FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update -qq && apt-get install -y -qq \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-deu \
    tesseract-ocr-fra \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-rus \
    tesseract-ocr-chi-sim \
    tesseract-ocr-jpn \
    tesseract-ocr-ara \
    tesseract-ocr-tur \
    tesseract-ocr-nld \
    tesseract-ocr-swe \
    tesseract-ocr-kor \
    tesseract-ocr-ell \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python scripts/patch_pdf_title_localization.py \
    && python scripts/patch_pdf_zero_ai_export.py \
    && python scripts/patch_pdf_picker_ui.py \
    && python scripts/patch_pdf_academic_renderer.py \
    && python scripts/patch_pdf_academic_renderer_v4.py \
    && python scripts/patch_pdf_academic_renderer_v5.py \
    && python scripts/patch_pdf_academic_renderer_v6.py \
    && python scripts/patch_pdf_academic_renderer_v7.py \
    && python scripts/patch_pdf_academic_renderer_v8.py \
    && python scripts/patch_bilingual_finalizer_stall.py \
    && python scripts/patch_material_mcq_bilingual.py \
    && python scripts/patch_material_mcq_existing_shuffle.py \
    && python scripts/patch_assessment_persistence.py \
    && python scripts/patch_pdf_semantic_integrity_v9.py \
    && python scripts/patch_assignment_results_parity.py \
    && python scripts/patch_quality_convergence_v10b.py \
    && python scripts/patch_material_quality_gate_v12.py \
    && python -m py_compile server.py worker.py services/ai_engine.py services/bilingual_finisher.py services/pdf_academic_renderer.py services/pdf_renderer_v12.py \
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
    && python scripts/patch_pdf_target_language_header_v25.py \
    && python scripts/patch_pdf_polish_v26.py \
    && python scripts/patch_pdf_runtime_localization_v31.py \
    && python scripts/patch_actual_pdf_export_v34.py \
    && python -m py_compile server.py worker.py runtime_bootstrap.py services/ai_engine.py services/bilingual_finisher.py services/pdf_academic_renderer.py services/legacy/pdf_pipeline.py

CMD ["python", "runtime_bootstrap.py"]
