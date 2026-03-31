# app/models/rag_system.py
import logging
import re
from typing import List, Dict, Any
import requests
from sentence_transformers import SentenceTransformer
from datetime import datetime

from app.config.config import QDRANT_CONFIG, MODEL_CONFIG, RAG_CONFIG, LEMMATIZER_CONFIG, get_embeddings_model_path
from app.models.lemmatizer import QueryLemmatizer
from app.services.database_connector import DatabaseConnector

logger = logging.getLogger(__name__)

class UpgoRAGSystem:
    def __init__(self, collection_name=None, qdrant_url=None, model_name=None):
        self.collection_name = collection_name or QDRANT_CONFIG['collection_name']
        self.qdrant_url = qdrant_url or QDRANT_CONFIG['url']
        model_name = model_name or MODEL_CONFIG['model_name']
        self.model = SentenceTransformer(get_embeddings_model_path())
        self.model_name = model_name

        # Параметры из конфига
        self.score_threshold = QDRANT_CONFIG.get('score_threshold', 0.10)
        self.search_limit = QDRANT_CONFIG.get('search_limit', 30)
        self.answer_limit_tables = RAG_CONFIG.get('answer_limit_tables', 5)
        self.max_predicted_tables = RAG_CONFIG.get('max_predicted_tables', 3)
        self.max_predicted_columns = RAG_CONFIG.get('max_predicted_columns', 3)
        self.relevance_weights = RAG_CONFIG.get('relevance_weights', {})
        self.keyword_patterns = RAG_CONFIG.get('keyword_patterns', self._get_default_keyword_patterns())
        self.table_patterns = RAG_CONFIG.get('table_patterns', self._get_default_table_patterns())
        self.column_patterns = RAG_CONFIG.get('column_patterns', self._get_default_column_patterns())

        # Инициализация лемматизатора
        use_lemmatizer = RAG_CONFIG.get('use_lemmatizer', True) and LEMMATIZER_CONFIG.get('enabled', True)
        if use_lemmatizer:
            self.lemmatizer = QueryLemmatizer()
        else:
            self.lemmatizer = None
            logger.info("Лемматизация отключена")

        self.db_connector = DatabaseConnector()
        self.rag_context = {
            "found_tables": [],
            "table_details": {},
            "question_type": "",
            "timestamp": None
        }
        self.lemmatized_query = ""
        self._all_table_names = self._load_all_table_names()

    def _get_default_keyword_patterns(self):
        return {
            "structure": ["структура", "столбец", "колонка", "поле", "тип данных", "описание таблиц"],
            "relations": ["связь", "отношение", "ключ", "foreign", "ссылаться", "внешний"],
            "columns": ["столбец", "колонка", "поле", "атрибут", "показатель"],
            "data_query": ["вывести", "найти", "получить", "запрос", "select", "данные", "информацию"],
            "fio": ["фио", "фамилия", "имя", "отчество", "ф.и.о.", "full name"],
            "date": ["дата", "период", "время", "год", "месяц", "число", "срок"],
            "appointment": ["назначен", "назначение", "утвержден", "принят", "вступил в должность"],
            "manager": ["руководитель", "начальник", "директор", "заведующий", "управляющий"],
            "organization": ["организация", "подразделение", "отдел", "департамент", "служба"],
            "position": ["должность", "позиция", "звание", "ранг", "категория"]
        }

    def _get_default_table_patterns(self):
        return {
            "сотрудник|employee|staff|worker": ["staff_employee", "employee", "staff", "personnel"],
            "руководитель|chief|manager|director|head": ["chief", "manager", "director", "head"],
            "организация|organization|department|подразделение": ["organizations_organization", "department", "division"],
            "должность|position|job|role": ["organizations_position", "position", "job_title"],
            "штат|staffing|расписание|вакансия": ["staffing_department", "staffing", "staff_schedule"],
            "приказ|order|назначение|appointment": ["orders_order", "order", "appointment_order"],
            "резерв|reserve|кадр|personnel": ["staff_reserveinfo", "reserve", "personnel_reserve"],
            "наград|award|reward|медаль|орден": ["staff_employeeaward", "employee_award", "award", "reward", "honor", "decoration", "medal"]
        }

    def _get_default_column_patterns(self):
        return {
            "фио|фамилия|имя|отчество|fio|full.name": ["last_name", "first_name", "middle_name", "full_name", "surname", "given_name", "patronymic"],
            "дата|date|время|time|период|period": ["in_date", "appointment_date", "order_date", "start_date", "end_date", "created_at", "updated_at", "effective_date"],
            "должность|position|job|role|title": ["position_name", "job_title", "role_name", "title"],
            "подразделение|department|отдел|division": ["department_name", "division_name", "unit_name", "branch_name", "full_path", "department_path", "org_structure"],
            "статус|status|состояние|state": ["status", "state", "is_active", "is_current", "appointment_status", "employment_status"],
            "id|код|номер|number|code": ["id", "employee_id", "position_id", "department_id", "order_id"]
        }

    def _load_all_table_names(self) -> set:
        try:
            query = """
            SELECT table_schema || '.' || table_name as full_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
              AND table_type = 'BASE TABLE'
            """
            result = self.db_connector.execute_query(query)
            if result:
                return {row['full_name'] for row in result}
            return set()
        except Exception as e:
            logger.error(f"Не удалось загрузить список таблиц: {e}")
            return set()

    def answer_question(self, question: str, limit: int = None) -> str:
        logger.info(f"Получен вопрос: {question}")

        self._clear_context()
        self.rag_context["timestamp"] = datetime.now().isoformat()

        if self.lemmatizer and self.lemmatizer.is_available():
            lemmatized_question = self.lemmatizer.lemmatize_query(question)
            self.lemmatized_query = lemmatized_question
        else:
            self.lemmatized_query = question

        question_lower = self.lemmatized_query.lower()
        question_type = self._determine_question_type(question_lower)
        self.rag_context["question_type"] = question_type

        # Расширяем запрос
        enhanced_query = self._enhance_query_for_structure(question, self.lemmatized_query)

        # Поиск в векторной БД
        vector_results = self._search_vector_db_for_structure(
            enhanced_query, question, self.lemmatized_query, limit=self.search_limit
        )

        if not vector_results:
            return "К сожалению, не удалось найти информацию по вашему запросу."

        # Лимит для ответа (если не задан, используем из конфига)
        if limit is None:
            limit = self.answer_limit_tables
        answer = self._generate_structure_answer(question, vector_results, limit=limit)
        return answer

    def get_simple_context(self, question: str) -> str:
        """
        Выполняет поиск по вопросу и возвращает компактную строку,
        содержащую названия найденных таблиц и их столбцы.
        """
        logger.info(f"Получен запрос на контекст с таблицами и столбцами: {question}")

        self._clear_context()
        self.rag_context["timestamp"] = datetime.now().isoformat()

        if self.lemmatizer and self.lemmatizer.is_available():
            lemmatized_question = self.lemmatizer.lemmatize_query(question)
            self.lemmatized_query = lemmatized_question
        else:
            self.lemmatized_query = question

        question_lower = self.lemmatized_query.lower()
        question_type = self._determine_question_type(question_lower)
        self.rag_context["question_type"] = question_type

        enhanced_query = self._enhance_query_for_structure(question, self.lemmatized_query)

        vector_results = self._search_vector_db_for_structure(
            enhanced_query, question, self.lemmatized_query, limit=self.search_limit
        )

        if not vector_results:
            return "Информация не найдена."

        # Формируем контекст: названия таблиц и их столбцы
        lines = []
        for table_name in self.rag_context.get("found_tables", []):
            table_info = self.rag_context.get("table_details", {}).get(table_name, {})
            display_name = table_info.get("display_name", table_name)
            lines.append(f"Таблица: {display_name}")

            # Добавляем столбцы, если есть
            columns = table_info.get("columns", [])
            if columns:
                lines.append("  Столбцы:")
                for col in columns[:10]:  # ограничим первыми 10 для краткости
                    col_line = f"    - {col['name']}"
                    if col.get('type') and col['type'] != 'unknown':
                        col_line += f" ({col['type']})"
                    if col.get('comment'):
                        col_line += f" — {col['comment'][:50]}"
                    lines.append(col_line)
                if len(columns) > 10:
                    lines.append(f"    ... и ещё {len(columns) - 10} столбцов")
            else:
                lines.append("  Столбцы: информация отсутствует")
            lines.append("")  # пустая строка между таблицами

        return "\n".join(lines)

    # =================================================================
    # Альтернативная функция: возвращает только названия таблиц (без столбцов)
    # Чтобы использовать её, раскомментируйте код ниже и закомментируйте
    # функцию get_simple_context выше (или перенаправьте вызов).
    # =================================================================
    """
    def get_simple_context(self, question: str) -> str:
        # Возвращает только названия таблиц, релевантных вопросу.
        logger.info(f"Запрос на контекст только с таблицами: {question}")

        self._clear_context()
        self.rag_context["timestamp"] = datetime.now().isoformat()

        if self.lemmatizer and self.lemmatizer.is_available():
            lemmatized_question = self.lemmatizer.lemmatize_query(question)
            self.lemmatized_query = lemmatized_question
        else:
            self.lemmatized_query = question

        question_lower = self.lemmatized_query.lower()
        question_type = self._determine_question_type(question_lower)
        self.rag_context["question_type"] = question_type

        enhanced_query = self._enhance_query_for_structure(question, self.lemmatized_query)

        vector_results = self._search_vector_db_for_structure(
            enhanced_query, question, self.lemmatized_query, limit=self.search_limit
        )

        if not vector_results:
            return "Информация не найдена."

        # Формируем простой контекст: только названия таблиц
        lines = []
        for table_name in self.rag_context.get("found_tables", []):
            table_info = self.rag_context.get("table_details", {}).get(table_name, {})
            display_name = table_info.get("display_name", table_name)
            lines.append(f"Таблица: {display_name}")
            lines.append("")  # пустая строка между таблицами

        return "\n".join(lines)
    """

    def _clear_context(self):
        self.rag_context = {
            "found_tables": [],
            "table_details": {},
            "question_type": "",
            "timestamp": None
        }

    def _determine_question_type(self, question_lower: str) -> str:
        type_weights = {}
        for type_name, keywords in self.keyword_patterns.items():
            weight = sum(1 for keyword in keywords if keyword in question_lower)
            if weight > 0:
                type_weights[type_name] = weight
        if not type_weights:
            return "general"
        return max(type_weights.items(), key=lambda x: x[1])[0]

    def _enhance_query_for_structure(self, original_query: str, lemmatized_query: str) -> str:
        query_lower = lemmatized_query.lower()

        # Только важные слова (длина > 3, не стоп-слова)
        stop_words = {"вывести", "каждый", "указание", "тип", "группа", "категория", "информация", "данные"}
        important_words = [w for w in lemmatized_query.split()
                           if len(w) > 3 and w not in stop_words]
        enhanced_parts = important_words.copy()

        # Синонимы – только 1-2 самых частотных
        structure_synonyms = {
            "сотрудник": ["employee", "staff"],
            "руководитель": ["chief", "manager"],
            "фио": ["full name", "last name"],
            "организация": ["organization", "company"],
            "подразделение": ["department", "division"],
            "должность": ["position", "job"],
            "назначение": ["appointment", "assignment"],
            "приказ": ["order", "decree"],
            "дата": ["date", "datetime"],
            "период": ["period", "interval"],
            "таблица": ["table", "relation"],
            "столбец": ["column", "field"],
            "связь": ["relation", "link"],
            "ключ": ["key", "id"],
            "награда": ["award", "reward"],
            "награжден": ["awarded", "rewarded"],
            "медаль": ["medal", "badge"]
        }

        for term, synonyms in structure_synonyms.items():
            if term in query_lower:
                enhanced_parts.extend(synonyms)

        # Добавляем предсказанные таблицы
        expected_tables = self._predict_tables_from_query(query_lower)
        if expected_tables:
            enhanced_parts.extend(expected_tables)

        # Предсказанные столбцы – не более max_predicted_columns
        expected_columns = self._predict_columns_from_query(query_lower)
        enhanced_parts.extend(expected_columns[:self.max_predicted_columns])

        # Дедупликация и ограничение длины
        unique_parts = list(set(enhanced_parts))[:20]

        if 'e5' in self.model_name.lower():
            enhanced_query = f"query: {' '.join(unique_parts)}"
        else:
            enhanced_query = ' '.join(unique_parts)

        logger.info(f"Расширенный запрос: {enhanced_query}")
        return enhanced_query

    def _predict_tables_from_query(self, query_lower: str) -> List[str]:
        candidates = []
        for pattern, tables in self.table_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                candidates.extend(tables)

        # Оставляем только реально существующие таблицы (полное имя или короткое)
        real_tables = []
        for tbl in candidates:
            if tbl in self._all_table_names:
                real_tables.append(tbl)
            else:
                # Попробуем добавить схему public по умолчанию
                full_name = f"public.{tbl}"
                if full_name in self._all_table_names:
                    real_tables.append(full_name)

        # Возвращаем уникальные, сохраняя порядок
        unique_real = []
        for tbl in real_tables:
            if tbl not in unique_real:
                unique_real.append(tbl)

        return unique_real[:self.max_predicted_tables]

    def _predict_columns_from_query(self, query_lower: str) -> List[str]:
        predicted_columns = []
        for pattern, columns in self.column_patterns.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                predicted_columns.extend(columns[:self.max_predicted_columns])

        return list(set(predicted_columns))[:self.max_predicted_columns]

    def _search_vector_db_for_structure(self, enhanced_query: str, original_query: str,
                                        lemmatized_query: str, limit: int = None) -> List[Dict]:
        if limit is None:
            limit = self.search_limit

        query_embedding = self.model.encode([enhanced_query], show_progress_bar=False)[0].tolist()

        search_url = f"{self.qdrant_url}/collections/{self.collection_name}/points/search"
        search_data = {
            "vector": query_embedding,
            "limit": limit,
            "with_payload": True,
            "score_threshold": self.score_threshold
        }

        try:
            response = requests.post(search_url, json=search_data, timeout=30)
            results = response.json().get("result", [])

            if not results:
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

            filtered_results = self._filter_and_group_for_structure(results, lemmatized_query, original_query)
            self._log_relevance_scores(filtered_results, lemmatized_query, limit=self.answer_limit_tables)
            self._populate_context_with_tables(filtered_results)
            return filtered_results

        except Exception as e:
            logger.error(f"Ошибка поиска в векторной БД: {e}")
            return []

    def _filter_and_group_for_structure(self, results: List, lemmatized_query: str,
                                        original_query: str) -> List[Dict]:
        query_lower = lemmatized_query.lower()
        original_lower = original_query.lower()
        grouped_results = {}

        for result in results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            score = result.get("score", 0)
            table_name = metadata.get("full_name", "database_overview")
            doc_type = metadata.get("type", "unknown")

            relevance = self._calculate_structure_relevance(query_lower, original_lower,
                                                            payload.get("content", ""), metadata)

            key = f"{table_name}_{doc_type}"
            if key not in grouped_results or relevance > grouped_results[key]["relevance"]:
                grouped_results[key] = {
                    "result": result,
                    "score": score,
                    "relevance": relevance,
                    "table_name": table_name,
                    "doc_type": doc_type
                }

        filtered = list(grouped_results.values())
        filtered.sort(key=lambda x: (x["relevance"], x["score"]), reverse=True)
        return [item["result"] for item in filtered[:30]]

    def _calculate_structure_relevance(self, lemmatized_query: str, original_query: str,
                                       content: str, metadata: Dict) -> float:
        relevance = 0.0
        content_lower = content.lower()
        table_name = metadata.get("full_name", "").lower()
        table_display_name = table_name.split('.')[-1] if '.' in table_name else table_name

        # Веса из конфига
        table_match_weight = self.relevance_weights.get('table_match', 2.0)
        term_match_weight = self.relevance_weights.get('term_match', 0.3)
        russian_context_weight = self.relevance_weights.get('russian_context', 0.5)
        doc_type_structure_weight = self.relevance_weights.get('doc_type_structure', 1.0)
        doc_type_relations_weight = self.relevance_weights.get('doc_type_relations', 1.0)
        column_count_factor = self.relevance_weights.get('column_count_factor', 0.1)

        # Совпадение по ожидаемым таблицам
        expected_tables = self._predict_tables_from_query(lemmatized_query)
        for expected in expected_tables:
            expected_lower = expected.lower()
            if expected_lower in table_name or expected_lower in table_display_name:
                relevance += table_match_weight

        # Прямые совпадения терминов
        query_terms = set(lemmatized_query.lower().split())
        content_terms = set(content_lower.split())
        direct_matches = len(query_terms.intersection(content_terms))
        relevance += direct_matches * term_match_weight

        # Русскоязычный контекст
        russian_pattern = re.compile(r'[а-яА-Я]')
        if russian_pattern.search(table_display_name):
            if any(russian_term in lemmatized_query for russian_term in ['таблица', 'база', 'структура']):
                relevance += russian_context_weight

        # Тип документа
        doc_type = metadata.get("type", "")
        if doc_type == "table_structure" and "структур" in lemmatized_query:
            relevance += doc_type_structure_weight
        elif doc_type == "table_relations" and "связ" in lemmatized_query:
            relevance += doc_type_relations_weight

        # Бонус за большое количество столбцов (если нужно оставить)
        column_count = metadata.get("column_count", 0)
        if column_count > 5:
            relevance += min(column_count * column_count_factor, 2.0)

        return relevance

    def _log_relevance_scores(self, results: List[Dict], query: str, limit: int = None):
        if limit is None:
            limit = self.answer_limit_tables
        logger.info("=" * 80)
        logger.info("РАСЧЕТ РЕЛЕВАНТНОСТИ")
        logger.info("=" * 80)
        logger.info(f"Запрос: {query}")
        logger.info("-" * 80)

        for i, result in enumerate(results[:limit], 1):
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            score = result.get("score", 0)
            table_name = metadata.get("full_name", "Unknown").split('.')[-1]
            column_count = metadata.get("column_count", "N/A")
            logger.info(f"{i}. {table_name}")
            logger.info(f"   Сходство: {score:.3f} | Столбцов: {column_count}")

        logger.info("=" * 80)

    def _populate_context_with_tables(self, results: List[Dict]):
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
                    "schema": metadata.get("schema", ""),
                    "category": metadata.get("category", ""),
                    "column_count": metadata.get("column_count", 0),
                    "row_count": metadata.get("row_count", 0),
                    "purpose": metadata.get("purpose", ""),
                    "content_snippets": [],
                    "relevance_score": 0,
                    "columns": []  # новое поле для столбцов
                }

            doc_relevance = self._calculate_structure_relevance(
                self.lemmatized_query.lower(),
                self.lemmatized_query.lower(),
                content, metadata
            )
            if doc_relevance > tables_info[table_name]["relevance_score"]:
                tables_info[table_name]["relevance_score"] = doc_relevance

            if content:
                snippet = content[:200] + "..." if len(content) > 200 else content
                tables_info[table_name]["content_snippets"].append(snippet)

                # Извлекаем столбцы из содержимого и добавляем в общий список таблицы
                columns = self._extract_columns_from_content(content)
                for col in columns:
                    if col not in tables_info[table_name]["columns"]:
                        tables_info[table_name]["columns"].append(col)

        # Дедупликация столбцов по имени
        for table_name in tables_info:
            unique = {}
            for col in tables_info[table_name]["columns"]:
                if col['name'] not in unique:
                    unique[col['name']] = col
            tables_info[table_name]["columns"] = list(unique.values())

        sorted_tables = sorted(tables_info.items(),
                               key=lambda x: x[1]["relevance_score"],
                               reverse=True)
        self.rag_context["found_tables"] = [table[0] for table in sorted_tables[:self.answer_limit_tables]]
        self.rag_context["table_details"] = {table[0]: table[1] for table in sorted_tables[:self.answer_limit_tables]}

    def _extract_columns_from_content(self, content: str) -> List[Dict]:
        columns = []
        lines = content.split('\n')
        in_columns_section = False

        for line in lines:
            line = line.strip()
            if "СТОЛБЦЫ" in line or "COLUMNS" in line:
                in_columns_section = True
                continue
            if in_columns_section and line and line.isupper() and len(line.split()) < 3:
                in_columns_section = False
                continue
            if in_columns_section and line:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    clean_line = line[1:].strip()
                elif any(line.startswith(f"{i}.") for i in range(1, 50)):
                    clean_line = line.split('.', 1)[1].strip()
                else:
                    clean_line = line

                parts = clean_line.split()
                if len(parts) >= 2:
                    col_name = parts[0]
                    col_type = parts[1] if len(parts) > 1 else "unknown"
                    col_type = col_type.replace('(', '').replace(')', '').replace('_', ' ')
                    comment_start = clean_line.find('COMMENT_')
                    comment = clean_line[comment_start + 8:] if comment_start != -1 else ""
                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "description": clean_line,
                        "comment": comment
                    })
        return columns

    def _generate_structure_answer(self, question: str, results: List[Dict], limit: int = None) -> str:
        if limit is None:
            limit = self.answer_limit_tables

        # Собираем столбцы для каждой таблицы из результатов поиска
        columns_by_table = {}
        for result in results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            table_name = metadata.get("full_name", "")
            if not table_name or table_name == "database_overview":
                continue
            doc_type = metadata.get("type", "")
            if doc_type in ["table_info", "table_structure", "table_description"]:
                content = payload.get("content", "")
                cols = self._extract_columns_from_content(content)
                if table_name not in columns_by_table:
                    columns_by_table[table_name] = []
                columns_by_table[table_name].extend(cols)

        # Дедупликация столбцов по имени
        for table_name in columns_by_table:
            unique = {}
            for col in columns_by_table[table_name]:
                if col['name'] not in unique:
                    unique[col['name']] = col
            columns_by_table[table_name] = list(unique.values())

        answer_parts = []
        table_details = self.rag_context.get("table_details", {})
        found_tables = self.rag_context.get("found_tables", [])[:limit]

        if not found_tables:
            return "Информация по вашему запросу не найдена."

        answer_parts.append(f"**Запрос:** {question}")
        answer_parts.append(f"**Тип запроса:** {self.rag_context.get('question_type', 'general')}")
        answer_parts.append(f"**Найдено таблиц:** {len(found_tables)}")
        answer_parts.append("")
        answer_parts.append("**Наиболее релевантные таблицы:**")
        answer_parts.append("")

        for i, table_name in enumerate(found_tables, 1):
            table_info = table_details.get(table_name, {})
            if not table_info:
                continue
            answer_parts.append(f"{i}. **{table_info['display_name']}**")
            info_lines = []
            if table_info['schema'] and table_info['schema'] != 'public':
                info_lines.append(f"Схема: {table_info['schema']}")
            if table_info['full_name']:
                info_lines.append(f"Полное имя: {table_info['full_name']}")
            if table_info['category']:
                info_lines.append(f"Категория: {table_info['category']}")
            if table_info['column_count']:
                info_lines.append(f"Столбцов: {table_info['column_count']}")
            if table_info['row_count']:
                info_lines.append(f"Записей: {table_info['row_count']}")
            if table_info['purpose']:
                info_lines.append(f"Назначение: {table_info['purpose']}")
            if info_lines:
                answer_parts.append("   " + " | ".join(info_lines))

            # Используем столбцы, собранные из результатов
            columns = columns_by_table.get(table_name, [])
            if columns:
                relevant_columns = self._filter_relevant_columns(columns, question)
                if relevant_columns:
                    answer_parts.append("   **Релевантные столбцы:**")
                    unique_columns = {}
                    for col in relevant_columns:
                        if col['name'] not in unique_columns:
                            unique_columns[col['name']] = col
                    for j, (col_name, col_info) in enumerate(list(unique_columns.items())[:8], 1):
                        col_line = f"     {j}. {col_name}"
                        if col_info['type'] and col_info['type'] != 'unknown':
                            col_line += f" ({col_info['type']})"
                        if col_info.get('comment'):
                            comment = col_info['comment'][:40]
                            if len(col_info['comment']) > 40:
                                comment += "..."
                            col_line += f" — {comment}"
                        answer_parts.append(col_line)
                    if len(unique_columns) > 8:
                        answer_parts.append(f"     ... и ещё {len(unique_columns) - 8} столбцов")
                else:
                    answer_parts.append("   **Столбцы:** информация о структуре доступна")
            else:
                answer_parts.append("   **Столбцы:** информация отсутствует в кэше")
            answer_parts.append("")

        answer_parts.append("**💡 Рекомендации для уточнения запроса:**")
        answer_parts.append("• Укажите конкретную таблицу для получения детальной информации")
        answer_parts.append("• Запросите связи между таблицами")
        answer_parts.append("• Уточните, какие именно столбцы вас интересуют")
        answer_parts.append("• Используйте конкретные термины из базы данных")
        answer_parts.append("")
        total_columns = sum(table_details[t].get('column_count', 0) for t in found_tables)
        answer_parts.append(f"**Статистика:** Всего {len(found_tables)} таблиц, {total_columns} столбцов")

        return "\n".join(answer_parts)

    def _filter_relevant_columns(self, columns: List[Dict], question: str) -> List[Dict]:
        question_lower = question.lower()
        relevant_columns = []
        keyword_patterns = {
            "фио|фамилия|имя|отчество": ["last_name", "first_name", "middle_name", "fio", "фио"],
            "дата|время|период": ["date", "datetime", "timestamp", "in_date", "appointment_date"],
            "должность|позиция": ["position", "job", "role", "title", "должность"],
            "подразделение|отдел": ["department", "division", "unit", "branch", "подразделение"],
            "руководитель|начальник": ["chief", "manager", "director", "head", "руководитель"],
            "назначение|приказ": ["appointment", "order", "assignment", "назначение", "приказ"],
            "статус|состояние": ["status", "state", "active", "current", "статус"]
        }

        for column in columns:
            col_name = column['name'].lower()
            col_description = column.get('description', '').lower()
            col_comment = column.get('comment', '').lower()
            is_relevant = False
            for pattern, keywords in keyword_patterns.items():
                if re.search(pattern, question_lower):
                    if any(keyword.lower() in col_name for keyword in keywords) or \
                       any(keyword.lower() in col_description for keyword in keywords):
                        is_relevant = True
                        break
            query_words = set(question_lower.split())
            if any(word in col_name for word in query_words if len(word) > 3):
                is_relevant = True
            if is_relevant:
                relevant_columns.append(column)

        return relevant_columns

    def get_table_info_directly(self, table_name: str) -> str:
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