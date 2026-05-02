FROM python:3.11-slim

# Set unbuffered output for logging
ENV PYTHONUNBUFFERED=1

# Install Tesseract and language packs
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the server
CMD ["python", "server.py"]
