import torch
import os
import warnings
from langchain_community.chat_models import ChatLlamaCpp

llm = None

#Функция для подбора наиболее эффективного способа загрузки LLM. 
#Если есть GPU, то CUDA, если нет или какие-то проблемы, то CPU.
def get_optimal_settings():
    settings = {
        'n_ctx': 2048,
        'n_batch': 512,
        'n_threads': None,
        'n_gpu_layers': 0,
        'verbose': False
    }

    cuda_available = False
    try:
        cuda_available = torch.cuda.is_available()
    except:
        pass

    if cuda_available:
        try:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory
            if gpu_memory >= 8 * 1024**3:
                settings['n_gpu_layers'] = -1
                settings['n_batch'] = 1024
            elif gpu_memory >= 4 * 1024**3:
                settings['n_gpu_layers'] = 20
                settings['n_batch'] = 512
            elif gpu_memory >= 2 * 1024**3:
                settings['n_gpu_layers'] = 10
                settings['n_batch'] = 512
                
            print(f"CUDA доступна, оптимальные настройки подобраны. Слои на GPU: {settings['n_gpu_layers']}.")
            
        except Exception as e:
            print(f"Ошибка при определении оптимальных настроек CUDA: {e}.")
            cuda_available = False

    cpu_threads = os.cpu_count()
    if cpu_threads:
        settings['n_threads'] = max(1, cpu_threads - 2)
        print(f"CPU потоков: {cpu_threads}, будет использовано: {settings['n_threads']}.")
   
    return settings, cuda_available


#Загрузка модели gguf через langchain 
def load_model(model_path: str):
    global llm
    try:
        settings, cuda_available = get_optimal_settings()

        if cuda_available:
            try:
                llm = ChatLlamaCpp(
                    model_path=model_path,
                    n_ctx=settings['n_ctx'],
                    n_threads=settings['n_threads'],
                    n_batch=settings['n_batch'],
                    n_gpu_layers=settings['n_gpu_layers'],
                    verbose=settings['verbose']
                )
                print(f"Модель успешно загружена с GPU ускорением.")
                return llm
            except Exception as gpu_error:
                warnings.warn(f"Не удалось загрузить на GPU.")
                settings['n_gpu_layers'] = 0
                cuda_available = False
        
        if not cuda_available:
            llm = ChatLlamaCpp(
                model_path=model_path,
                n_ctx=settings['n_ctx'],
                n_threads=settings['n_threads'],
                n_batch=settings['n_batch'],
                n_gpu_layers=0,
                verbose=settings['verbose']
            )
            print("Модель успешно загружена на CPU.")
            return llm
                
    except Exception as e:
        print(f"Ошибка загрузки LLM: {e}")
        raise

#Передача переменной для доступа к функциям LLM.
def get_llm():
    global llm
    if llm is None:
        raise ValueError("Модель не загружена. Сначала вызовите load_model().")
    return llm
