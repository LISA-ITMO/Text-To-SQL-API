# vectorizer.py
import logging
import re
from typing import List, Dict, Any
from tqdm import tqdm

logger = logging.getLogger(__name__)


class DatabaseVectorizer:
    """Класс для лаконичной векторизации структуры базы данных upgo"""

    def __init__(self):
        self.table_name_cache = {}
        self.column_type_mapping = {}

    def create_documents(self, db_schema: Dict[str, Any]) -> List[Dict]:
        """
        Создает документы для векторизации из схемы БД

        Args:
            db_schema: Словарь со схемой базы данных

        Returns:
            List[Dict]: Список документов для векторизации
        """
        if not db_schema:
            logger.error("Получена пустая схема БД")
            return []

        documents = []
        tables = db_schema.get('tables', {})

        if not tables:
            logger.warning("В схеме БД не найдено таблиц")
            return []

        logger.info(f"Начало векторизации {len(tables)} таблиц")

        # Сначала создаем кэш имен таблиц для лучшей обработки
        self._build_table_cache(tables)

        # Создаем документ с общей информацией о БД
        db_doc = self._create_database_document(db_schema)
        if db_doc:
            documents.append(db_doc)

        # Создаем документы для каждой таблицы
        for full_table_name, table_info in tqdm(tables.items(), desc="Векторизация таблиц"):
            table_doc = self._create_table_document(full_table_name, table_info)
            if table_doc:
                documents.append(table_doc)

                # Для таблиц с небольшим количеством записей добавляем отдельный документ с данными
                if table_info.get('row_count', 0) > 0 and table_info.get('row_count', 0) <= 100:
                    sample_doc = self._create_sample_data_document(full_table_name, table_info)
                    if sample_doc:
                        documents.append(sample_doc)

        logger.info(f"Создано {len(documents)} документов для векторизации")

        # Логируем статистику
        self._log_vectorization_stats(documents)

        return documents

    def _build_table_cache(self, tables: Dict[str, Any]):
        """Создает кэш имен таблиц для быстрого доступа"""
        self.table_name_cache = {}
        self.column_type_mapping = {}

        for full_name, table_info in tables.items():
            table_name = full_name.split('.')[-1].lower()
            self.table_name_cache[table_name] = full_name

            # Кэшируем типы столбцов для каждой таблицы
            columns = table_info.get('columns', [])
            column_types = {}
            for col in columns:
                column_types[col['name'].lower()] = col['type']
            self.column_type_mapping[full_name] = column_types

    def _create_database_document(self, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создает документ с общей информацией о базе данных

        Returns:
            Dict[str, Any]: Документ с информацией о БД
        """
        database_name = db_schema.get('database_name', 'upgo')
        postgres_version = db_schema.get('postgres_version', '')
        extraction_time = db_schema.get('extraction_time', '')
        tables = db_schema.get('tables', {})
        table_count = len(tables)

        if table_count == 0:
            return None

        # Подсчитываем статистику
        total_rows = 0
        total_columns = 0
        tables_by_schema = {}
        table_categories = {}

        for full_name, table_info in tables.items():
            schema = table_info.get('schema', 'public')
            if schema not in tables_by_schema:
                tables_by_schema[schema] = []
            tables_by_schema[schema].append(full_name)

            total_rows += table_info.get('row_count', 0)
            total_columns += len(table_info.get('columns', []))

            # Определяем категорию таблицы
            category = self._determine_table_category(full_name, table_info)
            if category not in table_categories:
                table_categories[category] = []
            table_categories[category].append(full_name)

        # Формируем содержимое
        content_parts = [
            f"БАЗА ДАННЫХ {database_name}",
            f"ВЕРСИЯ PostgreSQL {postgres_version}",
            f"ТАБЛИЦ {table_count}",
            f"ЗАПИСЕЙ {total_rows}",
            f"СТОЛБЦОВ {total_columns}",
            f"ВРЕМЯ СКАНИРОВАНИЯ {extraction_time}"
        ]

        # Добавляем таблицы по схемам
        for schema, schema_tables in tables_by_schema.items():
            content_parts.append(f"СХЕМА {schema} ТАБЛИЦ {len(schema_tables)}")

        # Добавляем категории таблиц
        content_parts.append("КАТЕГОРИИ ТАБЛИЦ")
        for category, category_tables in table_categories.items():
            content_parts.append(f"{category} {len(category_tables)}")

        # Добавляем ключевые таблицы системы
        key_tables = self._identify_key_tables(tables)
        if key_tables:
            content_parts.append("КЛЮЧЕВЫЕ ТАБЛИЦЫ")
            for table_name, row_count in key_tables[:10]:
                content_parts.append(f"{table_name} {row_count}")

        content = "\n".join(content_parts)

        metadata = {
            'type': 'database_overview',
            'database_name': database_name,
            'table_count': table_count,
            'total_rows': total_rows,
            'total_columns': total_columns,
            'postgres_version': postgres_version,
            'extraction_time': extraction_time,
            'schema_count': len(tables_by_schema),
            'category_count': len(table_categories)
        }

        return {'content': content, 'metadata': metadata}

    def _create_table_document(self, full_table_name: str, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создает документ с информацией о таблице

        Args:
            full_table_name: Полное имя таблицы (schema.table)
            table_info: Информация о таблице

        Returns:
            Dict[str, Any]: Документ с информацией о таблице
        """
        table_name = full_table_name.split('.')[-1]
        schema = table_info.get('schema', 'public')
        comment = table_info.get('comment', '')
        row_count = table_info.get('row_count', 0)
        columns = table_info.get('columns', [])
        foreign_keys = table_info.get('foreign_keys', [])
        indexes = table_info.get('indexes', [])

        # Определяем категорию таблицы
        category = self._determine_table_category(full_table_name, table_info)

        # Формируем структурированное содержимое
        content_parts = [f"ТАБЛИЦА {schema}.{table_name}"]

        if category:
            content_parts.append(f"КАТЕГОРИЯ {category}")

        if comment:
            # Очищаем комментарий от лишних пробелов и переносов строк
            clean_comment = re.sub(r'\s+', ' ', comment.strip())
            content_parts.append(f"КОММЕНТАРИЙ {clean_comment}")

        # Основная информация
        content_parts.append(f"ЗАПИСЕЙ {row_count}")
        content_parts.append(f"СТОЛБЦОВ {len(columns)}")

        if foreign_keys:
            content_parts.append(f"СВЯЗЕЙ {len(foreign_keys)}")

        if indexes:
            content_parts.append(f"ИНДЕКСОВ {len(indexes)}")

        # Столбцы
        if columns:
            content_parts.append("СТОЛБЦЫ")
            primary_keys = []

            for col in columns:
                col_info = self._format_column_info(col)
                content_parts.append(col_info)

                # Определяем потенциальные первичные ключи
                if self._is_primary_key_candidate(col):
                    primary_keys.append(col['name'])

            if primary_keys:
                content_parts.append(f"ВОЗМОЖНЫЕ КЛЮЧИ {' '.join(primary_keys)}")

        # Внешние ключи (связи)
        if foreign_keys:
            content_parts.append("СВЯЗИ")
            referenced_tables = set()

            for fk in foreign_keys:
                fk_info = f"{fk['column']} -> {fk['references_table']}.{fk['references_column']}"
                content_parts.append(fk_info)

                # Добавляем в список ссылающихся таблиц
                ref_table = fk['references_table']
                ref_table_short = ref_table.split('.')[-1]
                referenced_tables.add(ref_table_short)

            if referenced_tables:
                content_parts.append(f"ССЫЛАЕТСЯ_НА {' '.join(sorted(referenced_tables))}")

        # Индексы
        if indexes:
            content_parts.append("ИНДЕКСЫ")
            for idx in indexes[:5]:  # Ограничиваем количество индексов
                idx_name = idx['name']
                # Извлекаем столбцы из определения индекса
                idx_def = idx['definition']
                if 'ON ' in idx_def and '(' in idx_def and ')' in idx_def:
                    cols_part = idx_def.split('(')[1].split(')')[0]
                    content_parts.append(f"{idx_name} {cols_part}")

        # Определяем вероятное назначение таблицы
        purpose = self._determine_table_purpose(table_name, table_info)
        if purpose:
            content_parts.append(f"НАЗНАЧЕНИЕ {purpose}")

        content = "\n".join(content_parts)

        # Подготавливаем метаданные
        metadata = {
            'type': 'table_info',
            'schema': schema,
            'table_name': table_name,
            'full_name': full_table_name,
            'category': category,
            'row_count': row_count,
            'column_count': len(columns),
            'foreign_key_count': len(foreign_keys),
            'index_count': len(indexes),
            'has_comment': bool(comment),
            'has_foreign_keys': len(foreign_keys) > 0,
            'has_indexes': len(indexes) > 0
        }

        # Добавляем информацию о типах столбцов
        column_types = {}
        for col in columns:
            column_types[col['name']] = col['type']
        metadata['column_types'] = column_types

        # Добавляем информацию о ссылающихся таблицах
        if foreign_keys:
            referenced_tables = list(set([fk['references_table'] for fk in foreign_keys]))
            metadata['referenced_tables'] = referenced_tables

        return {'content': content, 'metadata': metadata}

    def _create_sample_data_document(self, full_table_name: str, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создает документ с примерами данных из таблицы

        Args:
            full_table_name: Полное имя таблицы
            table_info: Информация о таблице

        Returns:
            Dict[str, Any]: Документ с примерами данных
        """
        sample_data = table_info.get('sample_data', [])
        if not sample_data:
            return None

        table_name = full_table_name.split('.')[-1]
        schema = table_info.get('schema', 'public')
        columns = table_info.get('columns', [])

        # Получаем имена столбцов
        column_names = [col['name'] for col in columns]

        # Формируем содержимое
        content_parts = [f"ДАННЫЕ ТАБЛИЦЫ {schema}.{table_name}"]

        # Добавляем структуру столбцов
        content_parts.append("СТРУКТУРА")
        for i, col_name in enumerate(column_names[:10]):  # Ограничиваем количество столбцов
            if i < len(columns):
                col = columns[i]
                col_info = f"{col_name} {col['type']}"
                if not col['nullable']:
                    col_info += " NOT_NULL"
                content_parts.append(col_info)

        # Добавляем примеры данных
        content_parts.append("ПРИМЕРЫ")
        for i, row in enumerate(sample_data[:3]):  # Ограничиваем количество строк
            row_parts = []
            for col_name in column_names[:5]:  # Ограничиваем количество столбцов в примере
                if col_name in row:
                    value = str(row[col_name])
                    # Обрезаем длинные значения
                    if len(value) > 30:
                        value = value[:27] + "..."
                    row_parts.append(f"{col_name}={value}")

            if row_parts:
                content_parts.append(f"ЗАПИСЬ_{i + 1} {' '.join(row_parts)}")

        content = "\n".join(content_parts)

        metadata = {
            'type': 'sample_data',
            'schema': schema,
            'table_name': table_name,
            'full_name': full_table_name,
            'sample_count': len(sample_data),
            'column_count': len(columns),
            'data_available': True
        }

        return {'content': content, 'metadata': metadata}

    def _format_column_info(self, column: Dict[str, Any]) -> str:
        """
        Форматирует информацию о столбце в компактный вид

        Args:
            column: Информация о столбце

        Returns:
            str: Отформатированная строка с информацией о столбце
        """
        name = column['name']
        col_type = column['type'].replace(' ', '_')

        # Собираем части информации о столбце
        parts = [name, col_type]

        if not column['nullable']:
            parts.append("NOT_NULL")

        if column['default']:
            default_str = str(column['default'])
            # Очищаем значение по умолчанию
            default_clean = re.sub(r'\s+', '_', default_str[:30].strip())
            parts.append(f"DEFAULT_{default_clean}")

        if column['comment']:
            comment_str = column['comment']
            comment_clean = re.sub(r'\s+', '_', comment_str[:30].strip())
            parts.append(f"COMMENT_{comment_clean}")

        return ' '.join(parts)

    def _determine_table_category(self, full_table_name: str, table_info: Dict[str, Any]) -> str:
        """
        Определяет категорию таблицы по её имени и структуре

        Args:
            full_table_name: Полное имя таблицы
            table_info: Информация о таблице

        Returns:
            str: Категория таблицы
        """
        table_name = full_table_name.split('.')[-1].lower()
        columns = [col['name'].lower() for col in table_info.get('columns', [])]

        # Проверяем по ключевым словам в имени таблицы
        category_keywords = {
            'user': ['user', 'account', 'auth', 'login', 'register'],
            'employee': ['employee', 'staff', 'worker', 'personnel'],
            'organization': ['department', 'organization', 'division', 'unit', 'branch'],
            'position': ['position', 'job', 'role', 'title'],
            'education': ['education', 'training', 'course', 'learning', 'certificate'],
            'finance': ['income', 'salary', 'finance', 'payment', 'wage', 'tax'],
            'document': ['document', 'file', 'report', 'attachment'],
            'address': ['address', 'location', 'contact'],
            'system': ['log', 'history', 'audit', 'session', 'config', 'setting'],
            'hr': ['hr', 'human_resource', 'personnel', 'штат', 'кадр'],  # Добавляем HR-категорию
            'staffing': ['staffing', 'штатное', 'расписание', 'вакансия', 'vacancy']
            # Добавляем категорию штатного расписания
        }

        for category, keywords in category_keywords.items():
            if any(keyword in table_name for keyword in keywords):
                return category

            # Также проверяем по столбцам
            for col in columns:
                if any(keyword in col for keyword in keywords):
                    return category

        # Проверяем по более сложным паттернам
        if 'id' in table_name and ('employee' in table_name or 'user' in table_name):
            return 'relation'

        if any(x in table_name for x in ['_has_', '_rel_', '_link_', '_mapping_']):
            return 'relation'

        if table_name.endswith('_log') or table_name.endswith('_history'):
            return 'system'

        return 'other'

    def _determine_table_purpose(self, table_name: str, table_info: Dict[str, Any]) -> str:
        """
        Определяет вероятное назначение таблицы

        Args:
            table_name: Имя таблицы
            table_info: Информация о таблице

        Returns:
            str: Краткое описание назначения
        """
        table_lower = table_name.lower()
        columns = table_info.get('columns', [])
        column_names = [col['name'].lower() for col in columns]

        # Маппинг таблиц и их назначений
        purpose_mapping = {
            'user': 'хранение_пользователей_системы',
            'account': 'учетные_записи_пользователей',
            'employee': 'данные_сотрудников_организации',
            'staff': 'кадровый_состав_персонал',
            'department': 'организационные_подразделения',
            'position': 'должности_в_организации',
            'education': 'образование_обучение_сотрудников',
            'income': 'доходы_зарплата_финансы',
            'salary': 'оплата_труда_оклады',
            'address': 'адреса_контакты',
            'document': 'документы_файлы_отчеты',
            'log': 'журналы_событий_история',
            'session': 'сессии_пользователей',
            'permission': 'права_доступа_роли',
            'group': 'группы_пользователей',
            'role': 'роли_пользователей',
            'vacancy': 'вакансии_открытые_позиции',
            'staffing': 'штатное_расписание_кадровое_планирование'
        }

        # Ищем совпадение в имени таблицы
        for key, purpose in purpose_mapping.items():
            if key in table_lower:
                return purpose

        # Если не нашли по имени, анализируем структуру
        if any(col in ['salary', 'wage', 'income_amount'] for col in column_names):
            return 'финансовые_данные_оплата'

        if any(col in ['start_date', 'end_date', 'hire_date', 'termination_date'] for col in column_names):
            return 'временные_данные_периоды'

        if any(col.endswith('_id') for col in column_names) and len(column_names) <= 3:
            return 'связующая_таблица_отношения'

        return 'общие_данные_справочник'

    def _is_primary_key_candidate(self, column: Dict[str, Any]) -> bool:
        """
        Определяет, является ли столбец кандидатом в первичные ключи

        Args:
            column: Информация о столбце

        Returns:
            bool: True если столбец похож на первичный ключ
        """
        name = column['name'].lower()
        col_type = column['type']

        # Проверяем по имени
        if name == 'id' or name.endswith('_id'):
            return True

        # Проверяем по типу и свойствам
        if col_type in ['integer', 'bigint', 'serial', 'bigserial']:
            if column.get('default') and 'nextval' in str(column['default']):
                return True

        return False

    def _identify_key_tables(self, tables: Dict[str, Any]) -> List[tuple]:
        """
        Идентифицирует ключевые таблицы системы

        Args:
            tables: Словарь с таблицами

        Returns:
            List[tuple]: Список кортежей (имя_таблицы, количество_записей)
        """
        key_tables = []
        key_patterns = [
            'user', 'account', 'employee', 'person', 'staff',
            'department', 'organization', 'position', 'role',
            'permission', 'group', 'salary', 'income', 'payment'
        ]

        for full_name, table_info in tables.items():
            table_name = full_name.split('.')[-1].lower()

            # Проверяем совпадение с ключевыми паттернами
            for pattern in key_patterns:
                if pattern in table_name:
                    key_tables.append((
                        full_name.split('.')[-1],
                        table_info.get('row_count', 0)
                    ))
                    break

        # Сортируем по количеству записей (по убыванию)
        key_tables.sort(key=lambda x: x[1], reverse=True)

        return key_tables

    def _log_vectorization_stats(self, documents: List[Dict]):
        """
        Логирует статистику по векторизации

        Args:
            documents: Список документов
        """
        if not documents:
            logger.warning("Нет документов для логирования статистики")
            return

        # Подсчитываем статистику по типам документов
        doc_types = {}
        total_tables = 0
        total_columns = 0
        total_rows = 0

        for doc in documents:
            doc_type = doc['metadata'].get('type', 'unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

            if doc_type == 'table_info':
                total_tables += 1
                total_columns += doc['metadata'].get('column_count', 0)
                total_rows += doc['metadata'].get('row_count', 0)

        # Логируем статистику
        logger.info("=" * 60)
        logger.info("СТАТИСТИКА ВЕКТОРИЗАЦИИ")
        logger.info("=" * 60)
        logger.info(f"Всего документов: {len(documents)}")

        for doc_type, count in doc_types.items():
            logger.info(f"  {doc_type}: {count}")

        logger.info(f"Таблиц обработано: {total_tables}")
        logger.info(f"Всего столбцов: {total_columns}")
        logger.info(f"Всего записей: {total_rows}")

        # Средние значения
        if total_tables > 0:
            avg_columns = total_columns / total_tables
            avg_rows = total_rows / total_tables
            logger.info(f"Среднее столбцов на таблицу: {avg_columns:.1f}")
            logger.info(f"Среднее записей на таблицу: {avg_rows:.1f}")

        logger.info("=" * 60)


# Пример использования
if __name__ == "__main__":
    # Настройка логирования для теста
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Пример схемы БД для тестирования
    test_schema = {
        'database_name': 'test_db',
        'postgres_version': 'PostgreSQL 14.0',
        'extraction_time': '2024-01-15T10:30:00',
        'tables': {
            'public.users': {
                'schema': 'public',
                'name': 'users',
                'row_count': 1000,
                'comment': 'Таблица пользователей системы',
                'columns': [
                    {
                        'name': 'id',
                        'type': 'integer',
                        'nullable': False,
                        'default': "nextval('users_id_seq'::regclass)",
                        'comment': 'Первичный ключ'
                    },
                    {
                        'name': 'username',
                        'type': 'character varying',
                        'nullable': False,
                        'default': None,
                        'comment': 'Имя пользователя'
                    },
                    {
                        'name': 'email',
                        'type': 'character varying',
                        'nullable': False,
                        'default': None,
                        'comment': 'Email адрес'
                    }
                ],
                'foreign_keys': [],
                'indexes': [
                    {
                        'name': 'users_pkey',
                        'definition': 'CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)'
                    }
                ],
                'sample_data': [
                    {'id': 1, 'username': 'admin', 'email': 'admin@example.com'},
                    {'id': 2, 'username': 'user1', 'email': 'user1@example.com'}
                ]
            },
            'public.employees': {
                'schema': 'public',
                'name': 'employees',
                'row_count': 500,
                'comment': 'Сотрудники компании',
                'columns': [
                    {
                        'name': 'id',
                        'type': 'integer',
                        'nullable': False,
                        'default': "nextval('employees_id_seq'::regclass)",
                        'comment': 'ID сотрудника'
                    },
                    {
                        'name': 'first_name',
                        'type': 'character varying',
                        'nullable': False,
                        'default': None,
                        'comment': 'Имя'
                    },
                    {
                        'name': 'last_name',
                        'type': 'character varying',
                        'nullable': False,
                        'default': None,
                        'comment': 'Фамилия'
                    },
                    {
                        'name': 'department_id',
                        'type': 'integer',
                        'nullable': True,
                        'default': None,
                        'comment': 'ID отдела'
                    }
                ],
                'foreign_keys': [
                    {
                        'constraint_name': 'employees_department_id_fkey',
                        'column': 'department_id',
                        'references_table': 'public.departments',
                        'references_column': 'id'
                    }
                ],
                'indexes': [],
                'sample_data': [
                    {'id': 1, 'first_name': 'Иван', 'last_name': 'Иванов', 'department_id': 1}
                ]
            }
        }
    }

    # Создаем экземпляр векторизатора
    vectorizer = DatabaseVectorizer()

    # Тестируем создание документов
    documents = vectorizer.create_documents(test_schema)

    # Показываем примеры документов
    print("\n" + "=" * 80)
    print("ПРИМЕРЫ ДОКУМЕНТОВ ДЛЯ ВЕКТОРИЗАЦИИ")
    print("=" * 80)

    for i, doc in enumerate(documents[:2]):  # Показываем первые 2 документа
        print(f"\nДокумент {i + 1} (тип: {doc['metadata']['type']}):")
        print("-" * 40)
        print(doc['content'])
        print("-" * 40)
        print(f"Метаданные: {doc['metadata']}")
        print("=" * 80)