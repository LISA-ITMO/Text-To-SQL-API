from pydantic import BaseModel

class Question(BaseModel):
    llm_prompt:str

class QuestionSQL(Question):
    llm_context:str

class QuestionSQL_TOOL(BaseModel):
    llm_prompt:str

class QuestionSQL_TOOL_CHAIN(QuestionSQL_TOOL):
    execute_sql:bool = False