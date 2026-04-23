from pydantic import BaseModel

class Question(BaseModel):
    llm_prompt:str

class QuestionSQL(Question):
    llm_context:str

class QuestionSQL_TOOL(BaseModel):
    llm_prompt:str

class QuestionSQL_TOOL_CHAIN(QuestionSQL_TOOL):
    execute_sql:bool = False

class tool_safe_sql_execute(BaseModel):
    sql:str

class load_model_local(BaseModel):
    url:str

class load_model_hf(load_model_local):
    filename:str

class load_model_server(BaseModel):
    url:str
    api_key:str = None
    model:str = "No Name"