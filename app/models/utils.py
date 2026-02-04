# utils.py
import subprocess
import sys

def install_dependencies():
    """Устанавливает необходимые зависимости"""
    print("\n" + "=" * 80)
    print("УСТАНОВКА ЗАВИСИМОСТЕЙ ДЛЯ UPGО RAG СИСТЕМЫ")
    print("=" * 80)

    dependencies = [
        ("psycopg2-binary", "psycopg2", "Подключение к PostgreSQL"),
        ("sentence-transformers", "sentence_transformers", "Создание эмбеддингов"),
        ("requests", "requests", "Работа с HTTP запросами"),
        ("numpy", "numpy", "Математические операции"),
        ("tqdm", "tqdm", "Индикатор выполнения"),
        ("pymorphy2", "pymorphy2", "Лемматизация русского языка"),
        ("pymorphy2-dicts-ru", "pymorphy2_dicts_ru", "Словари для лемматизации"),
    ]

    print("\nПроверка зависимостей:")
    missing_deps = []

    for pip_name, import_name, description in dependencies:
        try:
            __import__(import_name)
            print(f"✓ {import_name} - {description}")
        except ImportError:
            print(f"✗ {import_name} - {description}")
            missing_deps.append((pip_name, import_name, description))

    if missing_deps:
        print(f"\nНайдено {len(missing_deps)} отсутствующих зависимостей.")
        install_all = input("Установить все? (y/n): ").strip().lower()

        if install_all == 'y':
            for pip_name, import_name, description in missing_deps:
                print(f"\nУстановка {import_name}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
                    print(f"✓ {import_name} установлен успешно")
                except Exception as e:
                    print(f"✗ Ошибка установки {import_name}: {e}")
        else:
            print("\nУстановите зависимости вручную:")
            for pip_name, import_name, description in missing_deps:
                print(f"  pip install {pip_name}  # {description}")
    else:
        print("\n✓ Все зависимости установлены!")

    print("\n" + "=" * 80)
    print("Установка зависимостей завершена!")
    print("Перезапустите программу.")