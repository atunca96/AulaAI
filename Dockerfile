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
    && python -m py_compile server.py services/pdf_academic_renderer.py

CMD ["python", "server.py"]
