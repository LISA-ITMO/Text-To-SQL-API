# app/services/embeddings_manager.py
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List

from app.config.config import MODEL_CONFIG

logger = logging.getLogger(__name__)

class SentenceTransformerEmbeddings:
    """Класс для создания эмбеддингов"""

    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = MODEL_CONFIG['model_name']
        logger.info(f"Загрузка модели эмбеддингов: {model_name}")
        try:
            self.model = SentenceTransformer(model_name)
            self.dimension = MODEL_CONFIG.get('dimension') or self.model.get_sentence_embedding_dimension()
            logger.info(f"Модель загружена успешно. Размерность: {self.dimension}")

        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """Создание эмбеддинга для запроса"""
        try:
            return self.model.encode([text], show_progress_bar=False)[0].tolist()
        except Exception as e:
            logger.error(f"Ошибка создания эмбеддинга: {e}")
            return np.random.randn(self.dimension).tolist()