FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update -qq && apt-get install -y -qq \
    tesseract-ocr tesseract-ocr-spa tesseract-ocr-deu tesseract-ocr-fra \
    tesseract-ocr-ita tesseract-ocr-por tesseract-ocr-rus tesseract-ocr-chi-sim \
    tesseract-ocr-jpn tesseract-ocr-ara tesseract-ocr-tur tesseract-ocr-nld \
    tesseract-ocr-swe tesseract-ocr-kor tesseract-ocr-ell poppler-utils patch \
    fontconfig fonts-noto-core fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# services/publication_invariants.py is now a normal checked-in module: it used to be
# reassembled here from .deploy/publication-invariants.src.* byte fragments, which made
# the runtime source of the publication boundary invisible to review and to git history.
RUN cat \
       .deploy/publication-grade.part01.patch \
       .deploy/publication-grade.part02.patch \
       .deploy/publication-grade.part03a.patch \
       .deploy/publication-grade.part03b.patch \
       .deploy/publication-grade.part04a.patch \
       .deploy/publication-grade.part04b.patch \
       .deploy/publication-grade.tail.patch \
       > /tmp/publication-grade.patch \
    && patch -p2 --batch < /tmp/publication-grade.patch \
    && patch -p1 --batch < .deploy/generalization-v2.patch \
    && python scripts/run_build_pipeline.py

CMD ["python", "runtime_bootstrap.py"]
