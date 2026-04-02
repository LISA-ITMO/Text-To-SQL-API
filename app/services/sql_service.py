import re
from typing import Dict, Optional
from sqlglot import parse_one, exp, ParseError

def extract_sql_from_text(text: str) -> str:
    """
    Извлекает SQL запрос из текста, удаляя комментарии, пояснения и другой "шум".
    """
    if not text:
        return ""
    
    text = re.sub(r'```sql\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\n?', '', text)
    
    prefixes = [
        r'^SQL:\s*', r'^Query:\s*', r'^Запрос:\s*',
        r'^Here is the SQL query:\s*', r'^Here\'s the SQL query:\s*',
        r'^Вот SQL запрос:\s*', r'^Результат:\s*', r'^Answer:\s*'
    ]
    
    for prefix in prefixes:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    parts = text.split(';', 1)
    sql_candidate = parts[0].strip()
    
    if len(parts) > 1 and sql_candidate:
        if re.search(r'\bSELECT\b', sql_candidate, re.IGNORECASE):
            text = sql_candidate + ';'
    
    in_single_quote = False
    in_double_quote = False
    semicolon_pos = -1
    
    for i, char in enumerate(text):
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == ';' and not in_single_quote and not in_double_quote:
            semicolon_pos = i
            break
    
    if semicolon_pos != -1:
        text = text[:semicolon_pos + 1]
    
    lines = text.split('\n')
    sql_lines = []
    in_multiline_comment = False
    
    for line in lines:
        if '/*' in line and '*/' in line:
            line = re.sub(r'/\*.*?\*/', '', line)
        elif '/*' in line:
            in_multiline_comment = True
            line = re.sub(r'/\*.*', '', line)
        elif '*/' in line:
            in_multiline_comment = False
            line = re.sub(r'.*\*/', '', line)
        
        if in_multiline_comment:
            continue
        
        if '--' in line:
            line = line[:line.index('--')]
        
        if '#' in line:
            line = line[:line.index('#')]
        
        line = line.strip()
        if line:
            sql_lines.append(line)
    
    sql = ' '.join(sql_lines).strip()
    
    sql = re.sub(r'\s+', ' ', sql)
    
    if sql and not sql.endswith(';'):
        sql += ';'
    
    return sql


def validate_sql(sql_query: str, dialect: str = "postgres") -> Dict:
    """
    Валидация SQL запроса с предварительным извлечением из текста.
    """
    forbidden_expressions = [
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
        exp.Create, exp.TruncateTable, exp.Merge, exp.Grant, exp.Revoke
    ]
    
    cleaned_query = extract_sql_from_text(sql_query)
    
    if not cleaned_query:
        select_match = re.search(r'(SELECT\s+.*?;)', sql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            cleaned_query = select_match.group(1)
        else:
            cleaned_query = sql_query.strip()
    
    if not cleaned_query:
        return {
            'Status': False,
            'Error': "No SQL query found in the response",
            'SQL': None
        }
    
    cleaned_query = cleaned_query.split(';')[0] + ';'
    
    try:
        tree = parse_one(cleaned_query, read=dialect)
        clean_sql = tree.sql(dialect=dialect)
        
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
        try:
            aggressive_match = re.search(
                r'(SELECT\s+.+?\s+FROM\s+.+?)(?:\s+WHERE\s+.+?)?(?:\s+GROUP\s+BY\s+.+?)?(?:\s+ORDER\s+BY\s+.+?)?;',
                cleaned_query,
                re.IGNORECASE | re.DOTALL
            )
            if aggressive_match:
                aggressive_sql = aggressive_match.group(1) + ';'
                tree = parse_one(aggressive_sql, read=dialect)
                clean_sql = tree.sql(dialect=dialect)
                
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
        except:
            pass
        
        return {
            'Status': False,
            'Error': f"Syntax error: {e}",
            'SQL': None
        }