FROM python:3.10-slim

# Cài đặt thư viện hệ thống cần cho psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ dữ liệu (bao gồm file Data2_merged_clean.csv)
COPY . .

# Chạy file nạp dữ liệu
CMD ["python", "vectordb.py"]
