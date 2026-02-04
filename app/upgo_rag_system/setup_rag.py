#!/usr/bin/env python3
"""
Скрипт для настройки и первоначальной векторизации RAG системы
"""

import sys
import os
from pathlib import Path

# Добавляем путь к app для импорта
sys.path.append(str(Path(__file__).parent.parent))


def setup_vector_database():
    """Настраивает векторную базу данных"""
    try:
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from app.services.database_connector import DatabaseConnector
        from app.services.vectorizer import DatabaseVectorizer
        from app.services.embeddings_manager import SentenceTransformerEmbeddings
        from app.services.vector_db_manager import VectorDatabaseManager

        print("\n" + "=" * 80)
        print("НАСТРОЙКА ВЕКТОРНОЙ БАЗЫ ДАННЫХ ДЛЯ UPGО")
        print("=" * 80)

        # Подключаемся к БД
        db_connector = DatabaseConnector()
        if not db_connector.connect():
            print("Не удалось подключиться к базе данных")
            return False

        # Получаем схему
        db_schema = db_connector.get_database_schema()
        if not db_schema:
            print("Не удалось получить схему БД")
            return False

        print(f"Получена схема БД с {len(db_schema.get('tables', {}))} таблицами")

        # Создаем документы
        vectorizer = DatabaseVectorizer()
        documents = vectorizer.create_documents(db_schema)

        # Загружаем модель эмбеддингов
        embeddings_model = SentenceTransformerEmbeddings()

        # Сохраняем в Qdrant
        vector_db = VectorDatabaseManager()
        success = vector_db.save_to_vector_db(documents, embeddings_model)

        db_connector.close()
        return success

    except ImportError as e:
        print(f"Ошибка импорта модулей: {e}")
        print("Убедитесь, что установлены все зависимости для RAG системы:")
        print("pip install sentence-transformers qdrant-client pymorphy2 pymorphy2-dicts-ru")
        return False
    except Exception as e:
        print(f"Ошибка настройки: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_rag_system():
    """Проверяет работу RAG системы"""
    try:
        from app.services.rag_service import get_rag_system
        rag_system = get_rag_system()

        test_questions = [
            "Какие таблицы есть в базе?",
            "Структура таблицы users",
            "Сколько таблиц в базе?"
        ]

        for question in test_questions:
            print(f"\nВопрос: {question}")
            answer = rag_system.answer_question(question, limit=2)
            print(f"Ответ: {answer[:200]}...")

        return True
    except Exception as e:
        print(f"Ошибка проверки RAG: {e}")
        return False


if __name__ == "__main__":
    print("Выберите действие:")
    print("1. Настроить векторную БД (первый запуск)")
    print("2. Проверить работу RAG системы")
    print("3. Выход")

    choice = input("\nВаш выбор (1-3): ").strip()

    if choice == "1":
        success = setup_vector_database()
        if success:
            print("\n RAG система успешно настроена!")
        else:
            print("\n Не удалось настроить RAG систему")
    elif choice == "2":
        check_rag_system()
    else:
        print("Выход")