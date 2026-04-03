FROM python:3.12-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем папку с предварительно скачанными wheel-файлами
COPY ./wheel-packages /wheel_packages

# 1. Устанавливаем PyTorch и связанные пакеты из локальной папки
RUN pip install --no-cache-dir \
    --find-links=/wheel_packages \
    torch==2.5.1+cpu \
    torchvision==0.20.1+cpu \
    torchaudio==2.5.1+cpu

# 2. Устанавливаем llama-cpp-python из исходников (НЕ из локального wheel)
RUN CMAKE_ARGS="-DLLAMA_METAL=OFF" pip install --no-cache-dir \
    --default-timeout=300 \
    --retries=5 \
    llama-cpp-python==0.3.16 \
    --force-reinstall \
    --no-binary llama-cpp-python

# Копируем requirements.txt (для кеширования)
COPY requirements.txt .

# 3. Устанавливаем остальные зависимости (используем ТО ЖЕ зеркало)
RUN pip install --no-cache-dir \
    --default-timeout=300 \
    --retries=5 \
    -r requirements.txt

# Копируем код приложения
COPY . .

# Запуск
CMD ["sh", "-c", "echo \"1\" | python3.12 ./app/upgo_rag_system/setup_rag.py && python3.12 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]