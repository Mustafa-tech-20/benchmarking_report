FROM python:3.13-slim
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required by maturin / fastuuid)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
# ENV PATH="/root/.cargo/bin:$PATH"

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add non-root user
# RUN adduser --disabled-password --gecos "" myuser
COPY . .
# RUN chown -R myuser:myuser /app

# USER myuser
# ENV PATH="/home/myuser/.local/bin:$PATH"

# # Set environment variables with hardcoded values
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV GOOGLE_CLOUD_PROJECT=srv-ad-nvoc-dev-445421
ENV GOOGLE_CLOUD_LOCATION=asia-south1
ENV SERVE_WEB_INTERFACE=true

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
