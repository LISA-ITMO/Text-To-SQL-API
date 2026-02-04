# config.py
import os
import logging
import sys

# Настройка кодировки для Windows
if sys.platform == "win32":
    import locale
    if locale.getpreferredencoding().upper() != "UTF-8":
        os.environ["PYTHONUTF8"] = "1"
        os.environ["PYTHONIOENCODING"] = "utf-8"

# Настройки базы данных
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'upgo',
    'user': 'postgres',
    'password': 'postgres'
}

# Настройки Qdrant
QDRANT_CONFIG = {
    'url': 'http://localhost:6333',
    'collection_name': 'upgo_database_schema',
    'backup_dir': 'vector_db_backups'
}

# Настройки модели
MODEL_CONFIG = {
    'name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
}

# Настройка логирования
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('upgo_rag_system.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()