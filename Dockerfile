FROM python:3.12-slim

WORKDIR /app

# System deps (includes libgomp for LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
