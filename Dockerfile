FROM python:3.13-slim
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required by maturin / fastuuid)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

# Cloud Run sets PORT environment variable - app will use it
# Expose common ports for documentation
EXPOSE 8000 8080

# Set default PORT if not provided by Cloud Run
ENV PORT=8080

CMD ["python", "main.py"]