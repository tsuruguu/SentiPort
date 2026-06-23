FROM python:3.11-slim

WORKDIR /workspace

# Podstawowe zależności systemowe (przydatne przy GIS/Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiowanie i instalacja paczek z folderu backendu
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Kopiowanie reszty aplikacji backendowej
COPY . .

EXPOSE 8000

# Komenda uruchomieniowa uvicorna z auto-reloadingiem
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]