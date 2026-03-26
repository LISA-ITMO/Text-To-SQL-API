FROM python:3.12-slim

# Установка системных зависимостей (минимально, для psycopg2-binary не нужно, но оставлено для совместимости)
# Устанавливаем компилятор и необходимые инструменты для сборки llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Устанавливаем PyTorch через зеркало TUNA (CPU версия)
#    Если нужна GPU, замените на нужный индекс CUDA (например, https://download.pytorch.org/whl/cu124)
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    torch==2.5.1

# 2. Устанавливаем llama-cpp-python (готовое колесо для CPU) – берём с официального индекса
#    Для GPU замените cpu на cu124 (или другую версию CUDA)
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    llama-cpp-python==0.3.16

# Копируем код приложения
COPY . .

# 5. Устанавливаем остальные зависимости через зеркало TUNA
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --default-timeout=300 \
    --retries=5 \
    -r requirements.txt

# (Опционально) Запуск скрипта и uvicorn
CMD ["sh", "-c", "echo \"1\" | python3.12 ./app/upgo_rag_system/setup_rag.py && python3.12 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]