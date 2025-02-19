FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL development files
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    postgresql-server-dev-all \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
