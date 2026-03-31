from fastapi import APIRouter
from app.schemas import QuestionSQL, Question, QuestionSQL_TOOL, QuestionSQL_TOOL_CHAIN
from app.DAOs.llm_DAO import llmDAO, validate_sql

app = APIRouter(prefix="/LLM")

@app.post('/getllmsqlanswer')
def get_llm_sql_answer(data:QuestionSQL):
    return(llmDAO.get_llm_sql_answer(data))

@app.post('/getllmsqlanswer_streaming')
def get_llm_sql_answer(data:QuestionSQL):
    return(llmDAO.get_llm_sql_answer_str_on(data))

@app.post('/getllmsqlanswer_no_streaming')
def get_llm_sql_answer(data:QuestionSQL):
    return(llmDAO.get_llm_sql_answer_str_off(data))

@app.post('/getllmanswer')
def get_llm_answer(data:Question):
    return(llmDAO.get_llm_answer(data))

@app.post("/getllmanswerwithtool")
def get_llm_answer_with_tool(data:QuestionSQL_TOOL):
    return(llmDAO.get_llm_sql_answer_with_tool(data))

@app.post("/getllmanswerwithtoolandchain")
def get_llm_answer_with_tool_and_chain(data:QuestionSQL_TOOL_CHAIN):
    return(llmDAO.get_llm_sql_answer_with_tool_and_chain(data))

@app.post("/tooltest")
def get_tool_test():
    return(llmDAO.tool_test())

@app.post('/sqlvalidatortest')
def sql_validate(sql:str):
    return(validate_sql(sql_query=sql))

@app.post("/getllmsqlanswerwithrag")
def get_llm_sql_answer_with_rag(data: QuestionSQL_TOOL_CHAIN):
    """
    Генерация SQL запроса с использованием RAG системы.
    Получает контекст из RAG на основе вопроса пользователя и использует его для генерации SQL.
    """
    return llmDAO.get_llm_sql_answer_with_rag_only(data)

@app.post("/getllmsqlanswerwithtoolchainrag")
def get_llm_answer_with_to0l_chain_rag(data: QuestionSQL_TOOL_CHAIN):
    return llmDAO.get_llm_sql_answer_with_tool_and_chain_and_RAG(data)

@app.post("/getragcontext")
def get_rag_context(data: QuestionSQL_TOOL):
    """
    Получает только контекст из RAG системы без генерации SQL.
    Полезно для отладки и проверки работы RAG.
    """
    from app.services.rag_service import get_context_from_rag
    context = get_context_from_rag(data.llm_prompt)
    return {
        "question": data.llm_prompt,
        "rag_context": context,
        "context_length": len(context)
    }