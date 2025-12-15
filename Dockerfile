# دليل العصر - Dockerfile
# =========================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Pillow and fonts
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    fonts-dejavu-core \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot script
COPY dalilaleasr_bot.py .

# Create data directory for database
RUN mkdir -p /app/data

# Set environment variables defaults
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Riyadh

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sqlite3; conn = sqlite3.connect('/app/data/history.db'); conn.close()" || exit 1

# Run the bot
CMD ["python", "-u", "dalilaleasr_bot.py"]
