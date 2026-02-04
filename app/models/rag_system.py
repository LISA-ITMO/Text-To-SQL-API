# rag_system.py (улучшенная версия)
import logging
from typing import List, Dict, Any
import requests
from sentence_transformers import SentenceTransformer
from datetime import datetime


logger = logging.getLogger(__name__)


class UpgoRAGSystem:
    """RAG система для базы данных upgo"""

    def __init__(self, collection_name: str = "upgo_database_schema",
                 qdrant_url: str = "http://localhost:6333",
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.collection_name = collection_name
        self.qdrant_url = qdrant_url
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

        from app.models.lemmatizer import QueryLemmatizer
        from app.services.database_connector import DatabaseConnector

        self.lemmatizer = QueryLemmatizer()
        self.db_connector = DatabaseConnector(database='upgo')

        # Контекст для генерации ответов
        self.rag_context = {
            "found_tables": [],
            "table_details": {},
            "question_type": "",
            "timestamp": None
        }

    def answer_question(self, question: str, limit: int = 10) -> str:
        """Отвечает на вопрос с предварительной лемматизацией"""
        logger.info(f"Получен вопрос: {question}")

        # Очищаем контекст перед новым вопросом
        self._clear_context()
        self.rag_context["timestamp"] = datetime.now().isoformat()

        # Лемматизация
        if self.lemmatizer.is_available():
            lemmatized_question = self.lemmatizer.lemmatize_query(question)
        else:
            lemmatized_question = question

        question_lower = lemmatized_question.lower()

        # Определяем тип вопроса
        question_type = self._determine_question_type(question_lower)
        self.rag_context["question_type"] = question_type

        # Поиск в векторной БД
        enhanced_query = self._enhance_query(question, lemmatized_question)
        vector_results = self._search_vector_db(enhanced_query, question, lemmatized_question, limit=20)

        if not vector_results:
            return "К сожалению, не удалось найти информацию по вашему запросу."

        # Формируем ответ с 10 таблицами
        answer = self._generate_enhanced_answer(question, vector_results, limit=10)

        return answer

    def _clear_context(self):
        """Очищает контекст RAG"""
        self.rag_context = {
            "found_tables": [],
            "table_details": {},
            "question_type": "",
            "timestamp": None
        }

    def _determine_question_type(self, question_lower: str) -> str:
        """Определяет тип вопроса"""
        if self._is_staffing_related(question_lower):
            return "staffing"
        elif any(term in question_lower for term in ["сколько", "количество", "count", "число"]):
            return "count"
        elif any(term in question_lower for term in ["структура", "столбец", "колонка", "поле", "тип"]):
            return "structure"
        elif any(term in question_lower for term in ["связь", "отношение", "ключ", "foreign", "ссылаться"]):
            return "relations"
        elif any(term in question_lower for term in ["назначение", "описание", "для чего", "зачем"]):
            return "purpose"
        elif any(term in question_lower for term in ["столбец", "колонка", "поле"]):
            return "columns"
        else:
            return "general"

    def _is_staffing_related(self, question_lower: str) -> bool:
        """Проверяет, относится ли вопрос к штатному расписанию"""
        staffing_keywords = [
            "штат", "штатное", "расписание", "кадровый", "вакансия",
            "ставка", "численность", "планирование", "фонд", "оклад",
            "надбавка", "staff", "staffing", "headcount", "vacancy"
        ]
        return any(keyword in question_lower for keyword in staffing_keywords)

    def _enhance_query(self, original_query: str, lemmatized_query: str) -> str:
        """Улучшает запрос с помощью ключевых слов"""
        query_lower = lemmatized_query.lower()
        enhanced_parts = [lemmatized_query]

        # Базовые синонимы
        keyword_mapping = {
            "пользователь": ["user", "account", "аутентификация"],
            "сотрудник": ["employee", "staff", "personnel"],
            "должность": ["position", "job", "role"],
            "организация": ["organization", "department", "division"],
            "образование": ["education", "training", "learning"],
            "доход": ["income", "salary", "finance"],
            "комиссия": ["commission", "expert", "аттестация"],
            "адрес": ["address", "location", "место"],
            "документ": ["document", "report", "отчет"],
            "структура": ["structure", "schema", "таблица"]
        }

        for keyword, synonyms in keyword_mapping.items():
            if keyword in query_lower:
                enhanced_parts.extend(synonyms[:3])

        # Для E5 моделей добавляем префикс
        if 'e5' in self.model_name.lower():
            enhanced_query = f"query: {' '.join(set(enhanced_parts))}"
        else:
            enhanced_query = ' '.join(set(enhanced_parts))

        return enhanced_query

    def _search_vector_db(self, enhanced_query: str, original_query: str,
                          lemmatized_query: str, limit: int = 20) -> List[Dict]:
        """Ищет документы в векторной БД"""
        # Для E5 моделей уже должен быть добавлен префикс в enhanced_query
        query_embedding = self.model.encode([enhanced_query], show_progress_bar=False)[0].tolist()

        search_url = f"{self.qdrant_url}/collections/{self.collection_name}/points/search"
        search_data = {
            "vector": query_embedding,
            "limit": limit,
            "with_payload": True,
            "score_threshold": 0.20
        }

        try:
            response = requests.post(search_url, json=search_data, timeout=30)
            results = response.json().get("result", [])

            if not results:
                # Попробуем поиск без форматирования для E5
                if 'e5' in self.model_name.lower():
                    original_embedding = self.model.encode([f"query: {original_query}"],
                                                           show_progress_bar=False)[0].tolist()
                else:
                    original_embedding = self.model.encode([original_query],
                                                           show_progress_bar=False)[0].tolist()

                search_data["vector"] = original_embedding
                response = requests.post(search_url, json=search_data, timeout=30)
                results = response.json().get("result", [])

            if not results:
                return []

            # Фильтруем и группируем результаты
            filtered_results = self._filter_and_group_results(results, lemmatized_query, original_query)

            # Рассчитываем релевантность (только для логов)
            self._log_relevance_scores(filtered_results, lemmatized_query)

            # Заполняем контекст найденными таблицами
            self._populate_context_with_tables(filtered_results)

            return filtered_results

        except Exception as e:
            logger.error(f"Ошибка поиска в векторной БД: {e}")
            return []

    def _filter_and_group_results(self, results: List, lemmatized_query: str,
                                  original_query: str) -> List[Dict]:
        """Фильтрует и группирует результаты"""
        query_lower = lemmatized_query.lower()
        original_lower = original_query.lower()

        grouped_results = {}

        for result in results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            score = result.get("score", 0)

            table_name = metadata.get("full_name", "database_overview")
            doc_type = metadata.get("type", "unknown")

            key = f"{table_name}_{doc_type}"

            if key not in grouped_results or score > grouped_results[key]["score"]:
                relevance = self._calculate_relevance(query_lower, original_lower,
                                                      payload.get("content", ""), metadata)
                grouped_results[key] = {
                    "result": result,
                    "score": score,
                    "relevance": relevance,
                    "table_name": table_name,
                    "doc_type": doc_type
                }

        filtered = list(grouped_results.values())
        filtered.sort(key=lambda x: (x["relevance"], x["score"]), reverse=True)

        return [item["result"] for item in filtered]

    def _calculate_relevance(self, lemmatized_query: str, original_query: str,
                             content: str, metadata: Dict) -> float:
        """
        Вычисляет релевантность документа запросу.
        Релевантность рассчитывается на основе:
        1. Совпадения типа документа с типом запроса (структура, связи и т.д.)
        2. Наличия ключевых слов в названии таблицы
        3. Текстового совпадения терминов запроса с содержимым
        4. Специальных коэффициентов для HR-систем (штатное расписание и т.д.)

        Каждый фактор добавляет определенный вес к итоговой релевантности.
        """
        relevance = 0.0

        content_lower = content.lower()
        table_name = metadata.get("full_name", "").lower()
        doc_type = metadata.get("type", "").lower()

        # 1. Соответствие типа документа типу запроса
        query_terms = lemmatized_query.split()

        if "структур" in lemmatized_query and doc_type == "table_structure":
            relevance += 0.8
        if "связ" in lemmatized_query and doc_type == "table_relations":
            relevance += 0.8
        if "описан" in lemmatized_query and doc_type == "table_description":
            relevance += 0.5
        if "обзор" in lemmatized_query and doc_type == "database_overview":
            relevance += 0.5

        # 2. Специальные коэффициенты для HR-систем
        if self._is_staffing_related(lemmatized_query):
            staffing_indicators = [
                'staff', 'штат', 'position', 'должность', 'salary', 'оклад',
                'vacancy', 'вакансия', 'rate', 'ставка', 'headcount', 'численность'
            ]

            for indicator in staffing_indicators:
                if indicator in table_name:
                    relevance += 1.2
                    break

        # 3. Совпадение ключевых таблиц
        key_tables = {
            'accounts_user': ['пользователь', 'user', 'аккаунт'],
            'employee': ['сотрудник', 'employee', 'работник'],
            'organization': ['организация', 'organization', 'подразделение'],
            'position': ['должность', 'position', 'позиция'],
            'education': ['образование', 'education', 'обучение'],
            'income': ['доход', 'income', 'декларация'],
            'commission': ['комиссия', 'commission', 'эксперт'],
            'staff': ['штат', 'staff', 'штатное', 'расписание'],
            'vacancy': ['вакансия', 'vacancy', 'открытая позиция'],
            'salary': ['оклад', 'salary', 'зарплата', 'оплата']
        }

        for table_key, keywords in key_tables.items():
            if table_key in table_name:
                for keyword in keywords:
                    if keyword in lemmatized_query:
                        relevance += 1.0
                        break

        # 4. Текстовое совпадение терминов
        content_terms = set(content_lower.split()[:100])
        matches = len(set(query_terms).intersection(content_terms))
        relevance += matches * 0.1

        return relevance

    def _log_relevance_scores(self, results: List[Dict], query: str):
        """Логирует оценки релевантности (только для отладки)"""
        logger.info("=" * 60)
        logger.info("РАСЧЕТ РЕЛЕВАНТНОСТИ")
        logger.info("=" * 60)
        logger.info(f"Запрос: {query}")
        logger.info(f"Найдено документов: {len(results)}")

        for i, result in enumerate(results[:5], 1):
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            score = result.get("score", 0)

            table_name = metadata.get("full_name", "Unknown").split('.')[-1]
            doc_type = metadata.get("type", "unknown")

            logger.info(f"{i}. {table_name} (тип: {doc_type})")
            logger.info(f"   Сходство векторов: {score:.3f}")
            logger.info(f"   Столбцов: {metadata.get('column_count', 'N/A')}")
            logger.info(f"   Записей: {metadata.get('row_count', 'N/A')}")

        logger.info("=" * 60)

    def _populate_context_with_tables(self, results: List[Dict]):
        """Заполняет контекст информацией о найденных таблицах"""
        tables_info = {}

        for result in results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            content = payload.get("content", "")

            table_name = metadata.get("full_name", "")
            if not table_name or table_name == "database_overview":
                continue

            if table_name not in tables_info:
                tables_info[table_name] = {
                    "display_name": table_name.split('.')[-1],
                    "full_name": table_name,
                    "category": metadata.get("category", ""),
                    "column_count": metadata.get("column_count", 0),
                    "row_count": metadata.get("row_count", 0),
                    "purpose": metadata.get("table_purpose", ""),
                    "columns": [],
                    "content_snippets": []
                }

            # Извлекаем информацию о столбцах из контента
            doc_type = metadata.get("type", "")
            if doc_type in ["table_structure", "table_description"]:
                columns = self._extract_columns_from_content(content)
                tables_info[table_name]["columns"].extend(columns)

            # Сохраняем сниппет контента
            if content:
                snippet = content[:300] + "..." if len(content) > 300 else content
                tables_info[table_name]["content_snippets"].append(snippet)

        # Сохраняем информацию о таблицах в контекст
        self.rag_context["found_tables"] = list(tables_info.keys())[:10]
        self.rag_context["table_details"] = tables_info

        # Логируем информацию о контексте
        logger.info(f"Контекст RAG обновлен: {len(tables_info)} таблиц")

    def _extract_columns_from_content(self, content: str) -> List[Dict]:
        """Извлекает информацию о столбцах из текстового содержимого"""
        columns = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()

            # Ищем строки с описанием столбцов
            if (line.startswith('•') or line.startswith('-') or
                    (any(line.startswith(f"{i}.") for i in range(1, 20)))):

                # Очищаем строку
                clean_line = line.lstrip('•-1234567890. ').strip()

                if "(" in clean_line and ")" in clean_line:
                    # Извлекаем имя и тип столбца
                    col_name = clean_line.split("(")[0].strip()
                    col_type = clean_line.split("(")[1].split(")")[0].split()[0]

                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "description": clean_line
                    })
                elif clean_line and len(clean_line.split()) > 0:
                    # Простое имя столбца
                    col_name = clean_line.split()[0]
                    columns.append({
                        "name": col_name,
                        "type": "unknown",
                        "description": clean_line
                    })

        return columns

    def _generate_enhanced_answer(self, question: str, results: List[Dict], limit: int = 10) -> str:
        """Генерирует улучшенный ответ с 10 таблицами и их столбцами"""
        answer_parts = []

        # Используем информацию из контекста
        table_details = self.rag_context.get("table_details", {})
        found_tables = self.rag_context.get("found_tables", [])[:limit]

        if not found_tables:
            return "Информация по вашему запросу не найдена."

        answer_parts.append("Найдены следующие таблицы:\n")

        for i, table_name in enumerate(found_tables, 1):
            table_info = table_details.get(table_name, {})
            if not table_info:
                continue

            answer_parts.append(f"{i}. Таблица: {table_info['display_name']}")
            answer_parts.append(f"   • Полное имя: {table_info['full_name']}")

            if table_info['category']:
                answer_parts.append(f"   • Категория: {table_info['category']}")

            if table_info['row_count']:
                answer_parts.append(f"   • Количество записей: {table_info['row_count']}")

            if table_info['column_count']:
                answer_parts.append(f"   • Количество столбцов: {table_info['column_count']}")

            if table_info['purpose']:
                answer_parts.append(f"   • Назначение: {table_info['purpose']}")

            # Выводим столбцы
            columns = table_info.get("columns", [])
            if columns:
                answer_parts.append("   • Основные столбцы:")

                # Убираем дубликаты столбцов
                unique_columns = {}
                for col in columns:
                    if col['name'] not in unique_columns:
                        unique_columns[col['name']] = col

                for j, (col_name, col_info) in enumerate(list(unique_columns.items())[:15], 1):
                    if col_info['type'] and col_info['type'] != 'unknown':
                        answer_parts.append(f"     {j}. {col_name} ({col_info['type']})")
                    else:
                        answer_parts.append(f"     {j}. {col_name}")

                if len(unique_columns) > 15:
                    answer_parts.append(f"     ... и ещё {len(unique_columns) - 15} столбцов")
            else:
                answer_parts.append("   • Столбцы: информация отсутствует в кэше")

            answer_parts.append("")

        # Добавляем рекомендации
        answer_parts.append("Для получения более подробной информации:")
        answer_parts.append("• Уточните запрос о конкретной таблице")
        answer_parts.append("• Запросите связи таблицы с другими")
        answer_parts.append("• Узнайте о назначении конкретных столбцов")

        return "\n".join(answer_parts)

    def get_table_info_directly(self, table_name: str) -> str:
        """Получает информацию о таблице напрямую из БД"""
        try:
            table_info = self.db_connector.get_table_info(table_name)

            if not table_info:
                return f"Таблица {table_name} не найдена."

            response = [
                f"Таблица {table_info['full_name']}:",
                f"Количество записей: {table_info.get('row_count', 0)}",
                f"Количество столбцов: {table_info.get('column_count', 0)}"
            ]

            if table_info.get('last_update'):
                response.append(f"Последнее обновление: {table_info['last_update']}")

            if table_info.get('comment'):
                response.append(f"Описание: {table_info['comment']}")

            columns = table_info.get('columns', [])
            if columns:
                response.append("\nСтолбцы:")
                for col in columns:
                    col_info = f"  • {col['name']} ({col['type']})"

                    if not col['nullable']:
                        col_info += " NOT NULL"

                    if col['default']:
                        default_str = str(col['default'])[:30]
                        if len(str(col['default'])) > 30:
                            default_str += "..."
                        col_info += f" DEFAULT: {default_str}"

                    if col['comment']:
                        comment = col['comment'][:50]
                        if len(col['comment']) > 50:
                            comment += "..."
                        col_info += f" | {comment}"

                    response.append(col_info)

            foreign_keys = table_info.get('foreign_keys', [])
            if foreign_keys:
                response.append("\nВнешние ключи:")
                for fk in foreign_keys[:7]:
                    response.append(f"  {fk['column']} -> {fk['references_table']}.{fk['references_column']}")

                if len(foreign_keys) > 7:
                    response.append(f"  ... и еще {len(foreign_keys) - 7} связей")

            return "\n".join(response)

        except Exception as e:
            logger.error(f"Ошибка получения информации о таблице: {e}")
            return f"Ошибка получения информации о таблице {table_name}."