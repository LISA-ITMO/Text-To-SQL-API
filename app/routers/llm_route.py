from fastapi import APIRouter
from app.schemas import QuestionSQL, Question, QuestionSQL_TOOL, QuestionSQL_TOOL_CHAIN
from app.DAOs.llm_DAO import llmDAO, validate_sql

app = APIRouter(prefix="/LLM")

@app.post('/getllmsqlanswer')
def get_llm_sql_answer(data:QuestionSQL):
    return(llmDAO.get_llm_sql_answer(data))

@app.post('/getllmanswer')
def get_llm_answer(data:Question):
    return(llmDAO.get_llm_answer(data))

@app.post("/getllmanswerwithtoolandchain")
def get_llm_answer_with_tool_and_chain(data:QuestionSQL_TOOL_CHAIN):
    return(llmDAO.get_llm_sql_answer_with_tool_and_chain(data))

@app.post("/getllmsqlanswerwithtoolchainrag")
def get_llm_answer_with_to0l_chain_rag(data: QuestionSQL_TOOL_CHAIN):
    return llmDAO.get_llm_sql_answer_with_tool_and_chain_and_RAG(data)

@app.post("/getragcontext")
def get_rag_context(data: QuestionSQL_TOOL):
    from app.services.rag_service import get_context_from_rag
    context = get_context_from_rag(data.llm_prompt)
    return {
        "question": data.llm_prompt,
        "rag_context": context,
        "context_length": len(context)
    }