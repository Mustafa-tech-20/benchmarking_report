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


EXPOSE 8080

CMD ["python", "main.py"]