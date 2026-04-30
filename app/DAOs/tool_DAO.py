from app.services.db_service import get_connection

class toolDAO():

    @staticmethod
    def connect_and_get_table_info(table_names: list[str]):
        """
        Получает информацию о столбцах для списка таблиц
        """
        response = []
        query = """SELECT 
                column_name,
                data_type
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position"""

        connection = get_connection()
        
        try:
            cursor = connection.cursor()
            
            for table in table_names:
                cursor.execute(query, (table,))
                rows = cursor.fetchall()
                
                # Преобразуем результат в список словарей
                table_columns = []
                for row in rows:
                    # row[0] - column_name, row[1] - data_type
                    table_columns.append(f"{row[0]} {row[1]}")
                
                response.append({
                    "table_name": table,
                    "table_columns": ", ".join(table_columns)
                })
            
            cursor.close()
            return response
            
        except Exception as e:
            print(f"Error getting table info: {e}")
            raise
        finally:
            if connection:
                connection.close()

    @staticmethod
    def connect_and_get_all_tables_info() -> str:
        """
        Получить названия таблиц и названия их полей из базы данных.
        """
        connection = get_connection()
        
        try:
            cursor = connection.cursor()
            
            # Получаем все имена таблиц
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_rows = cursor.fetchall()
            
            # Извлекаем имена таблиц из результата
            tables_names = [row[0] for row in table_rows]
            cursor.close()
            
            # Получаем информацию о таблицах
            tables_info = toolDAO.connect_and_get_table_info(tables_names)
            
            # Формируем строку ответа
            table_strings = []
            for table_info in tables_info:
                table_strings.append(f"{table_info['table_name']}({table_info['table_columns']})")

            tables_and_cols = ", ".join(table_strings)

            return "Все таблицы из моей базы данных с столбцами в скобках: " + tables_and_cols
            
        except Exception as e:
            print(f"Error getting all tables info: {e}")
            raise
        finally:
            if connection:
                connection.close()

    @staticmethod
    def connect_and_execute_sql(sql:str):
        connection = get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(sql)
            response = cursor.fetchall()
            cursor.close()
            return response
        
        except Exception as e:
            print(f"Error executing SQL: {e}")
            raise
        finally:
            if connection:
                connection.close()
