# app/services/rag_service.py
import sys
import os
from pathlib import Path
import logging
from typing import Optional

# Настройка логирования
#logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Глобальный экземпляр RAG системы
_rag_system = None


def get_rag_system():
    """Возвращает экземпляр RAG системы (синглтон)"""
    global _rag_system
    if _rag_system is None:
        try:
            logger.info("Инициализация RAG системы...")
            # Пробуем импортировать из новой модульной структуры
            try:
                from app.models.lemmatizer import QueryLemmatizer
                from app.models.rag_system import UpgoRAGSystem
                _rag_system = UpgoRAGSystem()
                logger.info("RAG система загружена из модульной структуры")
            except ImportError:
                # Пробуем из старого расположения
                try:
                    from app.models.rag_system import UpgoRAGSystem as LegacyRAGSystem
                    _rag_system = LegacyRAGSystem()
                    logger.info("RAG система загружена из старого расположения")
                except ImportError:
                    logger.error("Не удалось найти модуль RAG системы")
                    raise

        except Exception as e:
            logger.error(f"Ошибка инициализации RAG системы: {e}")
            raise
    return _rag_system


def get_context_from_rag(user_question: str) -> str:
    """
    Получает контекст из RAG системы для пользовательского вопроса.
    """
    try:
        rag_system = get_rag_system()

        # Проверяем доступные методы
        if hasattr(rag_system, 'get_context_from_query'):
            context = rag_system.get_context_from_query(user_question)
        elif hasattr(rag_system, 'get_simple_context'):
            context = rag_system.get_simple_context(user_question)
        else:
            # Используем старый метод как запасной вариант
            rag_answer = rag_system.answer_question(user_question, limit=3)
            context = f"Информация из базы данных:\n{rag_answer}"

        return context
    except Exception as e:
        logger.error(f"Ошибка получения контекста из RAG: {e}")
        return f"Ошибка получения контекста из базы данных: {str(e)}\nПопробуйте задать вопрос по-другому."


def setup_rag_system():
    """Настройка RAG системы (векторизация схемы БД)"""
    try:
        # Динамический импорт чтобы избежать циклических зависимостей
        from upgo_rag_system.setup_rag import setup_vector_database
        success = setup_vector_database()
        return success
    except ImportError:
        logger.error("Модуль upgo_rag_system не установлен. Установите зависимости RAG системы.")
        return False
    except Exception as e:
        logger.error(f"Ошибка настройки RAG системы: {e}")
        return False


def test_rag_system():
    """Тестирование RAG системы"""
    try:
        rag_system = get_rag_system()
        test_question = "Какие таблицы с пользователями есть в базе?"
        result = rag_system.answer_question(test_question, limit=2)
        return {
            "status": "success",
            "question": test_question,
            "answer_preview": result[:500] if len(result) > 500 else result,
            "answer_length": len(result)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }