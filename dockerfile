FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Установка часового пояса, чтобы не зависала сборка
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Moscow

# Системные зависимости
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    libreadline-dev \
    liblzma-dev \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libsqlite3-dev \
    libpq-dev \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python 3.12 из deadsnakes
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.12 python3.12-dev python3.12-venv && \
    # Создаём симлинки для удобства
    ln -s /usr/bin/python3.12 /usr/local/bin/python3 && \
    ln -s /usr/bin/python3.12 /usr/local/bin/python && \
    # Устанавливаем pip через ensurepip (встроен в Python)
    python3.12 -m ensurepip --upgrade && \
    # Обновляем pip, setuptools и wheel через зеркало (ВАЖНО!)
    python3.12 -m pip install --upgrade \
        --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
        pip setuptools wheel

# Проверяем установку Python и pip (опционально, для отладки)
RUN python3.12 --version && python3.12 -m pip --version

# Копируем файлы проекта
COPY . .

# СНАЧАЛА ставим llama-cpp-python с CUDA (исправленное зеркало)
RUN pip3.12 install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
    llama-cpp-python

# ПОТОМ ставим остальные зависимости (используем то же зеркало)
RUN pip3.12 install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# Torch CUDA
RUN pip3.12 install --no-cache-dir torch==2.5.1+cu124 torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu124

# В CMD тоже используем python3.12 (исправлено для предупреждения)
CMD ["sh", "-c", "echo \"1\" | python3.12 ./app/upgo_rag_system/setup_rag.py && python3.12 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]