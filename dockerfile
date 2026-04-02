FROM python:3.12-slim

# Установка системных зависимостей (минимально, для psycopg2-binary не нужно, но оставлено для совместимости)
# Устанавливаем компилятор и необходимые инструменты для сборки llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Устанавливаем PyTorch с CUDA 12.4 через Alibaba Cloud
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    torch==2.5.1+cu124 torchvision torchaudio \
    -f https://download.pytorch.org/whl/cu124/torch_stable.html

# 2. Устанавливаем llama-cpp-python с CUDA 12.4
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
    llama-cpp-python==0.3.16

# Копируем код приложения
COPY . .

# 3. Устанавливаем остальные зависимости через Alibaba Cloud
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --default-timeout=300 \
    --retries=5 \
    -r requirements.txt

# (Опционально) Запуск скрипта и uvicorn
CMD ["sh", "-c", "echo \"1\" | python3.12 ./app/upgo_rag_system/setup_rag.py && python3.12 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]