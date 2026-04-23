import os
import warnings
import subprocess
from langchain_community.chat_models import ChatLlamaCpp, ChatOpenAI
from llama_cpp import Llama

llm = None

def is_cuda_available_llama():
    """
    Проверяет доступность CUDA через llama-cpp-python, без использования PyTorch.
    Возвращает (bool, str): (доступна_ли_CUDA, сообщение_о_статусе)
    """
    try:
        # 1. Ищем видеокарту через nvidia-smi (быстрая предварительная проверка)
        has_nvidia_gpu = False
        gpu_name = ""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                has_nvidia_gpu = True
                gpu_name = result.stdout.strip().split('\n')[0]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # nvidia-smi не установлен - не критично

        # 2. ПРЯМАЯ ПРОВЕРКА: пробуем импортировать llama_cpp и проверить бэкенды
        try:
            import llama_cpp
            
            # СПОСОБ 1: Через llama_get_available_backends() (для новых версий)
            try:
                from llama_cpp.llama_cpp import LLAMA_BACKEND_CUDA, llama_get_available_backends
                available_backends = llama_get_available_backends()
                
                if LLAMA_BACKEND_CUDA in available_backends:
                    if has_nvidia_gpu:
                        return True, f"CUDA доступна (подтверждено: {gpu_name} + llama.cpp бэкенд)"
                    return True, "CUDA доступна (llama.cpp бэкенд активирован)"
                else:
                    if has_nvidia_gpu:
                        return False, f"Найдена {gpu_name}, но llama.cpp собран БЕЗ поддержки CUDA"
                    return False, "CUDA недоступна (llama.cpp не имеет CUDA бэкенда)"
                    
            except ImportError:
                # СПОСОБ 2: Для старых версий - проверяем через llama_build_info
                if hasattr(llama_cpp, 'llama_build_info'):
                    build_info = llama_cpp.llama_build_info()
                    # Ищем ключевые слова CUDA в информации о сборке
                    cuda_keywords = ['CUDA', 'cuBLAS', 'cuda', 'cublas']
                    if any(keyword in build_info for keyword in cuda_keywords):
                        if has_nvidia_gpu:
                            return True, f"CUDA доступна ({gpu_name}, сборка: {build_info})"
                        return True, f"CUDA доступна (сборка: {build_info})"
                
                # СПОСОБ 3: Последний вариант - проверяем версию библиотеки
                # Если версия llama-cpp-python >= 0.2.0, она почти наверняка собрана с CUDA
                # (если вы устанавливали с флагом CUDA)
                version = llama_cpp.__version__
                if has_nvidia_gpu:
                    return True, f"Версия {version}, {gpu_name} - предполагаем, что CUDA доступна"
                return False, f"Версия {version}, нет видеокарты NVIDIA"
                
        except ImportError:
            # llama_cpp не установлен вообще
            return False, "Библиотека llama-cpp-python не установлена"
            
    except Exception as e:
        # Любая другая ошибка
        return False, f"Ошибка при проверке: {str(e)[:100]}"

def get_optimal_settings():
    """
    Подбирает наиболее эффективные настройки для загрузки модели.
    Теперь проверяет CUDA через llama-cpp-python, а не через PyTorch.
    """
    settings = {
        'n_ctx': 2048,
        'n_batch': 512,
        'n_threads': None,
        'n_gpu_layers': 0,
        'verbose': False
    }

    # Проверяем доступность CUDA через llama-cpp-python
    cuda_available, status_message = is_cuda_available_llama()
    print(f"Проверка CUDA: {status_message}")

    if cuda_available:
        try:
            # Получаем информацию о GPU через nvidia-smi (если доступно)
            try:
                nvidia_smi_output = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                    text=True
                ).strip()
                
                if nvidia_smi_output:
                    # Берем память первой видеокарты
                    gpu_memory_mb = int(nvidia_smi_output.split('\n')[0])
                    gpu_memory_bytes = gpu_memory_mb * 1024 * 1024
                    
                    # Подбираем настройки на основе объема памяти GPU
                    if gpu_memory_bytes >= 10 * 1024**3:  # 10 ГБ и больше
                        settings['n_gpu_layers'] = -1    # Все слои на GPU
                        settings['n_batch'] = 8182
                        settings['n_ctx'] = 16384
                    elif gpu_memory_bytes >= 5 * 1024**3:  # 5-10 ГБ
                        settings['n_gpu_layers'] = 20
                        settings['n_batch'] = 4096
                        settings['n_ctx'] = 8192
                    elif gpu_memory_bytes >= 2 * 1024**3:  # 2-5 ГБ
                        settings['n_gpu_layers'] = 10
                        settings['n_batch'] = 512
                        settings['n_ctx'] = 2048
                    
                    print(f"GPU память: {gpu_memory_mb} МБ. Будут использованы {settings['n_gpu_layers']} слоёв на GPU.")
                    
            except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
                # Если nvidia-smi недоступен, используем консервативные настройки
                print("Не удалось определить память GPU. Используются консервативные настройки.")
                settings['n_gpu_layers'] = 10
                
        except Exception as e:
            print(f"Ошибка при определении настроек GPU: {e}. Используем CPU.")
            cuda_available = False
            settings['n_gpu_layers'] = 0

    # Настройки CPU (оставляем как было)
    cpu_threads = os.cpu_count()
    if cpu_threads:
        settings['n_threads'] = max(1, cpu_threads - 2)
        print(f"CPU потоков: {cpu_threads}, будет использовано: {settings['n_threads']}.")
    
    return settings, cuda_available

# Загрузка модели из Hugging Face
def load_model_from_hf(repo_id: str, filename: str = None, local_model_path: str = None):
    global llm
    try:
        settings, cuda_available = get_optimal_settings()

        # Подготавливаем параметры для загрузки
        model_kwargs = {
            'n_ctx': settings['n_ctx'],
            'n_threads': settings['n_threads'],
            'n_batch': settings['n_batch'],
            'n_gpu_layers': settings['n_gpu_layers'] if cuda_available else 0,
            'verbose': settings['verbose']
        }

        # Загружаем модель (с Hugging Face или локально)
        if repo_id and filename:
            print(f"Загрузка модели {repo_id}/{filename} из Hugging Face...")
            # Создаем экземпляр Llama напрямую
            llm_raw = Llama.from_pretrained(
                repo_id=repo_id,
                filename=filename,
                **model_kwargs
            )
            
            # Оборачиваем в ChatLlamaCpp для совместимости с LangChain
            # Сохраняем путь к загруженной модели
            model_path = llm_raw.model_path
            
            #Чистим память от загруженной модели
            del llm_raw

            #Загружаем скачанную модель и оборачиваем заново
            llm = ChatLlamaCpp(
                model_path=model_path,
                **model_kwargs
            )
            print(f"Модель успешно загружена из Hugging Face.")
            
        elif local_model_path:
            print(f"Загрузка локальной модели из {local_model_path}...")
            llm = ChatLlamaCpp(
                model_path=local_model_path,
                **model_kwargs
            )
            print(f"Локальная модель успешно загружена.")
        else:
            raise ValueError("Необходимо указать либо (repo_id и filename), либо local_model_path")

        return llm
                
    except Exception as e:
        print(f"Ошибка загрузки LLM: {e}")
        raise

#Загрузка модели с локального или облачного сервера 
def load_model_from_server(url:str, api_key: str = None, model: str = "NoName"):
    """
    Загружает модель с локального или облачного сервера
    """
    global llm
    try:
        llm = ChatOpenAI(
            base_url=url,
            api_key=api_key,
            model=model,
            temperature=0.1,
            max_tokens=16384
        )
        print(f"Соединение с сервером LLM успешно установлено.")
        return llm
    except Exception as e:
        print(f"Ошибка при подключении к серверу с LLM: {e}")
        return None 
    
# Передача переменной для доступа к функциям LLM.
def get_llm():
    global llm
    if llm is None:
        raise ValueError("Модель не загружена. Сначала загрузите её доступным способом.")
    return llm