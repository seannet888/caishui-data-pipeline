FROM python:3.11-slim

WORKDIR /app

# 系统依赖（pymupdf 需要的运行时库一般已随 wheel 提供；保留 build-essential 以防源码编译）
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
