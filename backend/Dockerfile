FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# The demo image skips local OCR (EasyOCR + PyTorch) to fit small free-tier instances.
COPY requirements-demo.txt .
RUN pip install --no-cache-dir -r requirements-demo.txt

COPY app ./app

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010} --proxy-headers --forwarded-allow-ips='*'"]
