# vector_db_manager.py
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

class VectorDatabaseManager:
    """Менеджер векторной базы данных Qdrant"""

    def __init__(self, qdrant_url: str = "http://localhost:6333",
                 collection_name: str = "upgo_database_schema"):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.backup_dir = "vector_db_backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def check_connection(self) -> bool:
        """Проверяет соединение с Qdrant"""
        try:
            response = requests.get(self.qdrant_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Qdrant доступен: {self.qdrant_url}")
                return True
        except Exception as e:
            logger.error(f"Qdrant недоступен: {e}")
            return False
        return False

    def save_to_vector_db(self, documents: List[Dict], embeddings_model) -> bool:
        """Сохраняет документы в векторную БД"""
        if not documents:
            logger.error("Нет документов для сохранения")
            return False

        try:
            logger.info(f"Сохранение {len(documents)} документов в Qdrant...")

            if not self._create_collection(embeddings_model.dimension):
                return False

            metadata_backup = self._backup_metadata(documents)

            points = []
            for i, doc in enumerate(tqdm(documents, desc="Создание эмбеддингов")):
                embedding = embeddings_model.embed_query(doc['content'])

                point = {
                    "id": i,
                    "vector": embedding,
                    "payload": {
                        "content": doc['content'],
                        "metadata": doc['metadata']
                    }
                }
                points.append(point)

            if not self._upload_points(points):
                return False

            self._save_collection_info(documents)

            logger.info("Схема БД успешно сохранена в Qdrant")
            self._print_statistics(documents)

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения в Qdrant: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_collection(self, vector_size: int) -> bool:
        """Создает коллекцию в Qdrant"""
        try:
            check_url = f"{self.qdrant_url}/collections/{self.collection_name}"
            response = requests.get(check_url, timeout=10)

            if response.status_code == 200:
                logger.info(f"Коллекция '{self.collection_name}' уже существует")
                requests.delete(check_url, timeout=10)
                logger.info(f"Коллекция '{self.collection_name}' удалена для пересоздания")

            create_url = f"{self.qdrant_url}/collections/{self.collection_name}"
            create_data = {
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine",
                }
            }

            response = requests.put(create_url, json=create_data, timeout=30)

            if response.status_code in [200, 201]:
                logger.info(f"Коллекция '{self.collection_name}' создана")
                return True
            else:
                logger.error(f"Не удалось создать коллекцию: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Ошибка создания коллекции: {e}")
            return False

    def _backup_metadata(self, documents: List[Dict]) -> str:
        """Создает резервную копию метаданных"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"metadata_backup_{timestamp}.json")

        metadata_list = []
        for doc in documents:
            metadata_list.append({
                "content_hash": hash(doc['content']),
                "metadata": doc['metadata'],
                "content_preview": doc['content'][:200]
            })

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_list, f, ensure_ascii=False, indent=2)

        logger.info(f"Метаданные сохранены в {backup_file}")
        return backup_file

    def _save_collection_info(self, documents: List[Dict]):
        """Сохраняет информацию о коллекции"""
        info_file = os.path.join(self.backup_dir, "collection_info.json")

        collection_info = {
            "collection_name": self.collection_name,
            "created_at": datetime.now().isoformat(),
            "total_documents": len(documents),
            "document_types": {},
            "tables_covered": set(),
            "statistics": {
                "database_overviews": 0,
                "table_descriptions": 0,
                "table_structures": 0,
                "table_relations": 0,
                "total_tables": 0,
                "total_columns": 0,
                "total_rows": 0
            }
        }

        for doc in documents:
            metadata = doc['metadata']
            doc_type = metadata.get('type', 'unknown')

            collection_info["document_types"][doc_type] = collection_info["document_types"].get(doc_type, 0) + 1

            if doc_type == 'database_overview':
                collection_info["statistics"]["database_overviews"] += 1
                collection_info["statistics"]["total_rows"] += metadata.get('total_rows', 0)
                collection_info["statistics"]["total_columns"] += metadata.get('total_columns', 0)
                collection_info["statistics"]["total_tables"] = metadata.get('table_count', 0)
            elif doc_type == 'table_description':
                collection_info["statistics"]["table_descriptions"] += 1
                table_name = metadata.get('full_name')
                if table_name:
                    collection_info["tables_covered"].add(table_name)
                collection_info["statistics"]["total_rows"] += metadata.get('row_count', 0)
                collection_info["statistics"]["total_columns"] += metadata.get('column_count', 0)
            elif doc_type == 'table_structure':
                collection_info["statistics"]["table_structures"] += 1
                collection_info["statistics"]["total_columns"] += metadata.get('column_count', 0)
            elif doc_type == 'table_relations':
                collection_info["statistics"]["table_relations"] += 1

        collection_info["tables_covered"] = list(collection_info["tables_covered"])

        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(collection_info, f, ensure_ascii=False, indent=2)

        logger.info(f"Информация о коллекции сохранена в {info_file}")

    def _upload_points(self, points: List[Dict]) -> bool:
        """Загружает точки в Qdrant"""
        try:
            batch_size = 50
            total_batches = (len(points) + batch_size - 1) // batch_size

            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                batch_num = i // batch_size + 1

                upload_url = f"{self.qdrant_url}/collections/{self.collection_name}/points"
                response = requests.put(upload_url, json={"points": batch}, timeout=60)

                if response.status_code != 200:
                    logger.error(f"Ошибка загрузки батча {batch_num}/{total_batches}: {response.text}")
                    return False
                else:
                    logger.info(f"Загружен батч {batch_num}/{total_batches} ({len(batch)} точек)")

            logger.info(f"Всего загружено {len(points)} точек в коллекцию '{self.collection_name}'")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки точек: {e}")
            return False

    def _print_statistics(self, documents: List[Dict]):
        """Выводит статистику по сохраненным документам"""
        logger.info("=" * 60)
        logger.info("СТАТИСТИКА СОХРАНЕННЫХ ДАННЫХ")
        logger.info("=" * 60)
        logger.info(f"Всего документов: {len(documents)}")

        doc_types = {}
        for doc in documents:
            doc_type = doc['metadata']['type']
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        for doc_type, count in doc_types.items():
            logger.info(f"  - {doc_type}: {count}")

        tables_info = {}
        total_columns = 0
        for doc in documents:
            metadata = doc['metadata']
            table_name = metadata.get('full_name')
            if table_name:
                if table_name not in tables_info:
                    tables_info[table_name] = {'documents': 0, 'columns': 0, 'rows': 0}
                tables_info[table_name]['documents'] += 1
                tables_info[table_name]['columns'] = max(
                    tables_info[table_name]['columns'], metadata.get('column_count', 0)
                )
                tables_info[table_name]['rows'] = max(
                    tables_info[table_name]['rows'], metadata.get('row_count', 0)
                )
                total_columns += metadata.get('column_count', 0)

        logger.info(f"\nОбработано таблиц: {len(tables_info)}")
        logger.info(f"Общее количество столбцов: {total_columns}")
        logger.info("\nПримеры таблиц:")
        for table_name, info in list(tables_info.items())[:10]:
            logger.info(f"  - {table_name}: {info['documents']} док., {info['columns']} кол., {info['rows']} зап.")

        if len(tables_info) > 10:
            logger.info(f"  ... и еще {len(tables_info) - 10} таблиц")

        logger.info("=" * 60)