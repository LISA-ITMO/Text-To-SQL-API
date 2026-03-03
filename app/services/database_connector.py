# database_connector.py
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class DatabaseConnector:
    """Класс для подключения к PostgreSQL базе данных upgo"""

    def __init__(self, host='10.94.21.18', port=5432, database='upgo_test_02',
                 user='upgo_kgs', password='Luu0QZbME93EOzZ'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def connect(self) -> bool:
        """Устанавливает соединение с базой данных"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            logger.info(f"Успешное подключение к базе данных {self.database}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            return False

    def get_database_schema(self) -> Dict[str, Any]:
        """Получает полную схему базы данных upgo"""
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()
            db_info = self._get_database_info(cursor)
            tables = self._get_tables(cursor)
            db_info['tables'] = {}

            for table in tqdm(tables, desc="Обработка таблиц"):
                table_name = table['table_name']
                schema_name = table.get('table_schema', 'public')

                table_info = {
                    'schema': schema_name,
                    'name': table_name,
                    'type': table.get('table_type', 'BASE TABLE'),
                    'size': table.get('table_size', 'unknown'),
                    'comment': table.get('table_comment'),
                    'row_count': 0,
                    'columns': [],
                    'foreign_keys': [],
                    'indexes': []
                }

                columns = self._get_table_columns(cursor, schema_name, table_name)
                table_info['columns'] = columns

                foreign_keys = self._get_foreign_keys(cursor, schema_name, table_name)
                table_info['foreign_keys'] = foreign_keys

                indexes = self._get_indexes(cursor, schema_name, table_name)
                table_info['indexes'] = indexes

                try:
                    stats = self._get_table_statistics(cursor, schema_name, table_name)
                    table_info['row_count'] = stats['row_count']
                    table_info['last_update'] = stats['last_update']
                except:
                    table_info['row_count'] = 0
                    table_info['last_update'] = None

                try:
                    if stats['row_count'] > 0 and table_name not in ['alembic_version']:
                        sample_data = self._get_sample_data(cursor, schema_name, table_name)
                        table_info['sample_data'] = sample_data
                except:
                    table_info['sample_data'] = []

                db_info['tables'][f"{schema_name}.{table_name}"] = table_info

            cursor.close()
            logger.info(f"Извлечена схема базы данных с {len(db_info['tables'])} таблицами")
            return db_info

        except Exception as e:
            logger.error(f"Ошибка получения схемы БД: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # Вспомогательные методы (остаются такими же как в исходном коде)
    def _get_database_info(self, cursor) -> Dict[str, Any]:
        """Получает общую информацию о базе данных"""
        query = """
        SELECT current_database() as database_name,
               current_user as current_user,
               version() as postgres_version,
               pg_size_pretty(pg_database_size(current_database())) as database_size;
        """
        cursor.execute(query)
        result = cursor.fetchone()

        return {
            'database_name': result['database_name'],
            'current_user': result['current_user'],
            'postgres_version': result['postgres_version'].split(',')[0],
            'database_size': result['database_size'],
            'extraction_time': datetime.now().isoformat()
        }

    def _get_tables(self, cursor) -> List[Dict[str, Any]]:
        """Получает список таблиц в базе данных"""
        query = """
        SELECT 
            table_schema,
            table_name,
            table_type,
            pg_size_pretty(pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name))) as table_size,
            obj_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass) as table_comment
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name;
        """
        cursor.execute(query)
        return cursor.fetchall()

    def _get_table_columns(self, cursor, schema: str, table_name: str) -> List[Dict[str, Any]]:
        """Получает информацию о колонках таблицы"""
        query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            col_description((%s || '.' || %s)::regclass, ordinal_position) as column_comment
        FROM information_schema.columns 
        WHERE table_schema = %s 
          AND table_name = %s
        ORDER BY ordinal_position;
        """
        cursor.execute(query, (schema, table_name, schema, table_name))
        columns = cursor.fetchall()

        columns_info = []
        for col in columns:
            columns_info.append({
                'name': col['column_name'],
                'type': col['data_type'],
                'nullable': col['is_nullable'] == 'YES',
                'default': col['column_default'],
                'max_length': col['character_maximum_length'],
                'precision': col['numeric_precision'],
                'scale': col['numeric_scale'],
                'comment': col['column_comment']
            })

        return columns_info

    def _get_foreign_keys(self, cursor, schema: str, table_name: str) -> List[Dict[str, Any]]:
        """Получает информацию о внешних ключах"""
        query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
          AND tc.table_schema = %s
          AND tc.table_name = %s;
        """
        cursor.execute(query, (schema, table_name))
        fks = cursor.fetchall()

        foreign_keys = []
        for fk in fks:
            foreign_keys.append({
                'constraint_name': fk['constraint_name'],
                'column': fk['column_name'],
                'references_table': f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}",
                'references_column': fk['foreign_column_name']
            })

        return foreign_keys

    def _get_indexes(self, cursor, schema: str, table_name: str) -> List[Dict[str, Any]]:
        """Получает информацию об индексах"""
        query = """
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = %s
          AND tablename = %s;
        """
        cursor.execute(query, (schema, table_name))
        indexes = cursor.fetchall()

        index_info = []
        for idx in indexes:
            index_info.append({
                'name': idx['indexname'],
                'definition': idx['indexdef']
            })

        return index_info

    def _get_table_statistics(self, cursor, schema: str, table_name: str) -> Dict[str, Any]:
        """Получает статистику по таблице"""
        try:
            count_query = f'SELECT COUNT(*) as row_count FROM "{schema}"."{table_name}"'
            cursor.execute(count_query)
            count_result = cursor.fetchone()

            date_columns = self._get_date_columns(cursor, schema, table_name)
            last_update = None

            if date_columns:
                for date_col in date_columns:
                    try:
                        date_query = f'SELECT MAX("{date_col}") as last_date FROM "{schema}"."{table_name}"'
                        cursor.execute(date_query)
                        date_result = cursor.fetchone()
                        if date_result and date_result['last_date']:
                            if last_update is None or date_result['last_date'] > last_update:
                                last_update = date_result['last_date']
                    except:
                        continue

                if last_update:
                    last_update = last_update.isoformat()

            return {
                'row_count': count_result['row_count'] if count_result else 0,
                'last_update': last_update
            }
        except Exception as e:
            logger.warning(f"Ошибка получения статистики для {schema}.{table_name}: {e}")
            return {'row_count': 0, 'last_update': None}

    def _get_date_columns(self, cursor, schema: str, table_name: str) -> List[str]:
        """Получает список колонок с типом даты"""
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND data_type IN ('date', 'timestamp without time zone', 
                          'timestamp with time zone', 'time');
        """
        cursor.execute(query, (schema, table_name))
        columns = cursor.fetchall()

        return [col['column_name'] for col in columns]

    def _get_sample_data(self, cursor, schema: str, table_name: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Получает примеры данных из таблицы"""
        try:
            query = f'SELECT * FROM "{schema}"."{table_name}" LIMIT %s'
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            sample_data = []
            for row in rows:
                row_dict = dict(row)
                for key, value in row_dict.items():
                    if isinstance(value, (datetime, date)):
                        row_dict[key] = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        row_dict[key] = str(value)
                sample_data.append(row_dict)

            return sample_data
        except Exception as e:
            logger.warning(f"Ошибка получения примеров данных для {schema}.{table_name}: {e}")
            return []

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Выполняет произвольный SQL запрос"""
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(query, params or ())

            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
            else:
                self.connection.commit()
                result = []

            cursor.close()
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            return []

    def get_table_data(self, schema: str, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает данные из таблицы"""
        query = f'SELECT * FROM "{schema}"."{table_name}" LIMIT %s'
        return self.execute_query(query, (limit,))

    def get_table_info(self, full_table_name: str) -> Dict[str, Any]:
        """Получает полную информацию о таблице"""
        if '.' in full_table_name:
            schema, table_name = full_table_name.split('.')
        else:
            schema, table_name = 'public', full_table_name

        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT 
                pg_size_pretty(pg_total_relation_size(quote_ident(%s) || '.' || quote_ident(%s))) as table_size,
                obj_description((quote_ident(%s) || '.' || quote_ident(%s))::regclass) as table_comment
            """
            cursor.execute(query, (schema, table_name, schema, table_name))
            table_info = cursor.fetchone()

            columns = self._get_table_columns(cursor, schema, table_name)
            stats = self._get_table_statistics(cursor, schema, table_name)
            foreign_keys = self._get_foreign_keys(cursor, schema, table_name)

            cursor.close()

            return {
                'schema': schema,
                'name': table_name,
                'full_name': f"{schema}.{table_name}",
                'size': table_info['table_size'],
                'comment': table_info['table_comment'],
                'row_count': stats['row_count'],
                'last_update': stats['last_update'],
                'columns': columns,
                'foreign_keys': foreign_keys,
                'column_count': len(columns)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о таблице {schema}.{table_name}: {e}")
            return {}

    def close(self):
        """Закрывает соединение с базой данных"""
        if self.connection:
            self.connection.close()
            logger.info("Соединение с базой данных закрыто")