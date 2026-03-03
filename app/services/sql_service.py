from typing import Dict
from sqlglot import parse_one, exp, ParseError

#Функция для валидации sql перед отправкой (проверка на выполняемость, синтаксис и отсутствие INSERT, DELETE и т.д.), а также парсер текста для поиска sql
def validate_sql(sql_query:str, dialect:str = "postgres") -> Dict:
    forbidden_expressions = [exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
                             exp.Create, exp.TruncateTable, exp.Merge, exp.Grant, exp.Revoke]
    cleaned_query = sql_query.strip()
    if cleaned_query.upper().startswith("SQL:"):
        cleaned_query = cleaned_query[4:].strip()

    tree = parse_one(cleaned_query, read=dialect)
    clean_sql = tree.sql(dialect=dialect)

    try:
        for expr_type in forbidden_expressions:
            if tree.find(expr_type):
                return {
                    'Status': False,
                    'Error': "Forbidden expression in SQL",
                    'SQL': None
                }
        
        if not tree.find(exp.Select):
                return {
                    'Status': False,
                    'Error': "No SELECT in expression",
                    'SQL': None
                }
        return {
            'Status': True,
            'Error': None,
            'SQL': clean_sql
            }
    except ParseError as e:
        return {
            'Status': False,
            'Error': f"Syntax error: {e}",
            'SQL': None
        }