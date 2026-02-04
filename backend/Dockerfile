FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install heavy ML deps first (cached layer)
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install sentence-transformers \
 && pip install -r requirements.txt

# Copy app AFTER deps (so code changes don't re-trigger ML install)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY run_eval.sh .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


