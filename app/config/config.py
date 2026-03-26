import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv


env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


def str_to_bool(s):
    return s.lower() in ('true', '1', 't', 'yes', 'y')

def str_to_list(s, sep=','):
    if not s:
        return []
    return [item.strip() for item in s.split(sep)]


# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'host.docker.internal'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'upgo_test_02'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '12345')
}

# Qdrant vector database
QDRANT_CONFIG = {
    'url': os.getenv('QDRANT_URL', 'http://qdrant:6333'),
    'collection_name': os.getenv('QDRANT_COLLECTION_NAME', 'upgo_database_schema'),
    'backup_dir': os.getenv('QDRANT_BACKUP_DIR', 'vector_db_backups'),
    'batch_size': int(os.getenv('QDRANT_BATCH_SIZE', 50)),
    'score_threshold': float(os.getenv('QDRANT_SCORE_THRESHOLD', 0.10)),
    'search_limit': int(os.getenv('QDRANT_SEARCH_LIMIT', 30))
}

# Embeddings model
MODEL_CONFIG = {
    'model_name': os.getenv('EMBEDDINGS_MODEL_NAME', 'intfloat/multilingual-e5-large-instruct'),
    'dimension': int(os.getenv('EMBEDDINGS_DIMENSION', 1024))
}

# RAG general settings
RAG_CONFIG = {
    'answer_limit_tables': int(os.getenv('RAG_ANSWER_LIMIT_TABLES', 5)),
    'max_predicted_tables': int(os.getenv('RAG_MAX_PREDICTED_TABLES', 3)),
    'max_predicted_columns': int(os.getenv('RAG_MAX_PREDICTED_COLUMNS', 3)),
    'use_lemmatizer': str_to_bool(os.getenv('RAG_USE_LEMMATIZER', 'true')),
    'stop_words': str_to_list(os.getenv('RAG_STOP_WORDS', 
        'и,в,во,не,что,он,на,я,с,со,как,а,то,все,она,так,его,но,да,ты,к,у,же,вы,за,бы,по,только,ее,мне,было,вот,от,меня,еще,нет,о,из,ему,теперь,когда,даже,ну,вдруг,ли,если,уже,или,ни,быть,был,него,до,вас,нибудь,опять,уж,вам,ведь,там,потом,себя,ничего,ей,может,они,тут,где,есть,надо,ней,для,мы,тебя,их,чем,была,сам,чтобы,без,будто,чего,раз,тоже,себе,под,будет,ж,тогда,кто,этот,того,потому,этого,какой,совсем,ним,здесь,этом,один,почти,мой,тем,чтобы,нее,сейчас,были,куда,зачем,всех,никогда,можно,при,наконец,два,об,другой,хоть,после,над,больше,тот,через,эти,нас,про,всего,них,какая,много,разве,три,эту,моя,впрочем,хорошо,свою,этой,перед,иногда,лучше,чуть,том,нельзя,такой,им,более,всегда,конечно,всю,между')),
    'relevance_weights': {
        'table_match': float(os.getenv('RAG_RELEVANCE_WEIGHTS_TABLE_MATCH', 2.0)),
        'column_match': float(os.getenv('RAG_RELEVANCE_WEIGHTS_COLUMN_MATCH', 0.5)),
        'term_match': float(os.getenv('RAG_RELEVANCE_WEIGHTS_TERM_MATCH', 0.3)),
        'russian_context': float(os.getenv('RAG_RELEVANCE_WEIGHTS_RUSSIAN_CONTEXT', 0.5)),
        'doc_type_structure': float(os.getenv('RAG_RELEVANCE_WEIGHTS_DOC_TYPE_STRUCTURE', 1.0)),
        'doc_type_relations': float(os.getenv('RAG_RELEVANCE_WEIGHTS_DOC_TYPE_RELATIONS', 1.0)),
        'column_count_factor': float(os.getenv('RAG_RELEVANCE_WEIGHTS_COLUMN_COUNT_FACTOR', 0.1))
    },
    'keyword_patterns': {
        'structure': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_STRUCTURE', 'структура,столбец,колонка,поле,тип данных,описание таблиц')),
        'relations': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_RELATIONS', 'связь,отношение,ключ,foreign,ссылаться,внешний')),
        'columns': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_COLUMNS', 'столбец,колонка,поле,атрибут,показатель')),
        'data_query': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_DATA_QUERY', 'вывести,найти,получить,запрос,select,данные,информацию')),
        'fio': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_FIO', 'фио,фамилия,имя,отчество,ф.и.о.,full name')),
        'date': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_DATE', 'дата,период,время,год,месяц,число,срок')),
        'appointment': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_APPOINTMENT', 'назначен,назначение,утвержден,принят,вступил в должность')),
        'manager': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_MANAGER', 'руководитель,начальник,директор,заведующий,управляющий')),
        'organization': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_ORGANIZATION', 'организация,подразделение,отдел,департамент,служба')),
        'position': str_to_list(os.getenv('RAG_KEYWORD_PATTERNS_POSITION', 'должность,позиция,звание,ранг,категория'))
    },
    'table_patterns': {
        'сотрудник|employee|staff|worker': str_to_list(os.getenv('RAG_TABLE_PATTERNS_EMPLOYEE', 'staff_employee,employee,staff,personnel')),
        'руководитель|chief|manager|director|head': str_to_list(os.getenv('RAG_TABLE_PATTERNS_MANAGER', 'chief,manager,director,head')),
        'организация|organization|department|подразделение': str_to_list(os.getenv('RAG_TABLE_PATTERNS_ORGANIZATION', 'organizations_organization,department,division')),
        'должность|position|job|role': str_to_list(os.getenv('RAG_TABLE_PATTERNS_POSITION', 'organizations_position,position,job_title')),
        'штат|staffing|расписание|вакансия': str_to_list(os.getenv('RAG_TABLE_PATTERNS_STAFFING', 'staffing_department,staffing,staff_schedule')),
        'приказ|order|назначение|appointment': str_to_list(os.getenv('RAG_TABLE_PATTERNS_ORDER', 'orders_order,order,appointment_order')),
        'резерв|reserve|кадр|personnel': str_to_list(os.getenv('RAG_TABLE_PATTERNS_RESERVE', 'staff_reserveinfo,reserve,personnel_reserve')),
        'наград|award|reward|медаль|орден': str_to_list(os.getenv('RAG_TABLE_PATTERNS_AWARD', 'staff_employeeaward,employee_award,award,reward,honor,decoration,medal'))
    },
    'column_patterns': {
        'фио|фамилия|имя|отчество|fio|full.name': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_FIO', 'last_name,first_name,middle_name,full_name,surname,given_name,patronymic')),
        'дата|date|время|time|период|period': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_DATE', 'in_date,appointment_date,order_date,start_date,end_date,created_at,updated_at,effective_date')),
        'должность|position|job|role|title': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_POSITION', 'position_name,job_title,role_name,title')),
        'подразделение|department|отдел|division': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_DEPARTMENT', 'department_name,division_name,unit_name,branch_name,full_path,department_path,org_structure')),
        'статус|status|состояние|state': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_STATUS', 'status,state,is_active,is_current,appointment_status,employment_status')),
        'id|код|номер|number|code': str_to_list(os.getenv('RAG_COLUMN_PATTERNS_ID', 'id,employee_id,position_id,department_id,order_id'))
    }
}

# Lemmatizer settings
LEMMATIZER_CONFIG = {
    'enabled': str_to_bool(os.getenv('LEMMATIZER_ENABLED', 'true')),
    'additional_stop_words': str_to_list(os.getenv('LEMMATIZER_ADDITIONAL_STOP_WORDS', ''))
}

# Logging
LOGGING_CONFIG = {
    'level': os.getenv('LOGGING_LEVEL', 'INFO'),
    'file': os.getenv('LOGGING_FILE', 'upgo_rag_system.log'),
    'format': os.getenv('LOGGING_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
}

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format'],
        handlers=[
            logging.FileHandler(LOGGING_CONFIG['file'], encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()