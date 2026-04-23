from app.schemas import QuestionSQL, Question, QuestionSQL_TOOL, QuestionSQL_TOOL_CHAIN
from llama_cpp_agent import LlamaCppFunctionTool
from llama_cpp_agent import FunctionCallingAgent, LlamaCppAgent
from llama_cpp_agent import MessagesFormatterType
from llama_cpp_agent.providers import LlamaCppPythonProvider
from llama_cpp_agent import AgentChainElement, AgentChain
from langchain_community.chat_models import ChatLlamaCpp
from langgraph.graph import StateGraph, END
from langchain.agents import create_agent
from langchain.tools import tool
from typing import TypedDict
from app.services.llm_service import get_llm
from app.DAOs.tool_DAO import toolDAO
from app.services.sql_service import validate_sql
from app.services.rag_service import get_context_from_rag

AVAILABLE_TOOLS = {
    "connect_and_get_all_tables_info": toolDAO.connect_and_get_all_tables_info,
}

#Класс с описанием состояния LLM-агента
class AgentState(TypedDict):
    question: str
    function_to_call: str
    context: str
    final_answer: str
    sql: str

#Нода агента с формированием промпта для вызова функции и возвращения JSON с состоянием агента
def agent_node(state: AgentState) -> AgentState:
    llm = get_llm()
    if state["context"] == '':
        context = toolDAO.connect_and_get_all_tables_info()
    else:
        context = state["context"]


    '''model_with_tools = llm.bind_tools([toolDAO.connect_and_get_all_tables_info])
    response = model_with_tools.invoke("Какие таблицы и их столбцы в скобках есть у меня в базе данных? Выведи их без перевода на русский язык.")
    
    response_text = response.content if hasattr(response, 'content') else str(response)
    print(response_text)
    try:
        # Ищем JSON в ответе (модель могла добавить пояснения)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response_text)'''
        
    return {
            "question": state["question"],
            "function_to_call": '1',
            "context": context,
            "final_answer": "",
            "sql":""
        }
        
    '''except json.JSONDecodeError:
        # Если не получилось распарсить JSON, возвращаем как финальный ответ
        print("Ошибка обработки JSON в ноде агента!")
        return {
            "question": state["question"],
            "function_to_call": "",
            "context": "",
            "final_answer": ""
        }'''

#Нода для получения функции и вызова её из массива функций 
def tool_node(state: AgentState) -> AgentState:
    tool_name = state.get("function_to_call")

    if tool_name in AVAILABLE_TOOLS:
        tool_func = AVAILABLE_TOOLS[tool_name]
        try:
            result = tool_func()
        except Exception as e:
            result = f"Ошибка при выполнении инструмента {tool_name}: {e}"
        return {
            **state,
            "context": str(result)
        }
    else:
        result = "Неизвестная функция"
        return {
            **state,
            "context": result
        }

#Последняя нода получающая контекст и вызывающая генерацию SQL-запроса по alpaca prompt
def sql_generation_node(state: AgentState) -> AgentState:
    llm = get_llm()
    alpaca_prompt = f"""You are SQL specialist. Do NOT output reasoning or thinking. Do NOT include <think> blocks. Only output SQL. Generate an SQL query based on the Prompt and the context from Company database.
    Prompt: {state.get('question')}
    Company database: {state.get('context')}
    Output ONLY the SQL query. No explanations or text before/after. Do NOT explain anything. Do NOT add comments. Return ONLY SQL."""

    response = llm.invoke(
        alpaca_prompt,
        max_tokens=-1,
        temperature=0.1,
        top_p=0.8)

    response_text = response.content if hasattr(response, 'content') else ""

    if not response_text or not response_text.strip():
        if hasattr(response, 'additional_kwargs'):
            reasoning = response.additional_kwargs.get('reasoning_content', '')
            if reasoning:
                response_text = reasoning
    
    final_answer = validate_sql(response_text)
    
    if final_answer['Status']:
        return{
            **state,
            "final_answer": final_answer['SQL'],
            "sql": final_answer['SQL']
        }
    else:
        return{
            **state,
            "final_answer": final_answer['Error']
        }
    

def sql_exec_node(state: AgentState) -> AgentState:
    sql_exec_result = toolDAO.connect_and_execute_sql(state.get("final_answer"))
    return{
        **state,
        "final_answer": sql_exec_result
    }

def end_with_error_node(state: AgentState) -> AgentState:
    return{
        **state,
        "final_answer": "К сожалению, запрос не был сгенерирован из-за проблем с получением контекста."
    }

class llmDAO():
    #Метод для генерации SQL-запроса по предоставленным в полях промпта и контекста базы данных
    @staticmethod
    def get_llm_sql_answer(data:QuestionSQL) -> str:
        llm = get_llm()
        alpaca_prompt = f"""You are SQL specialist. Do NOT output reasoning or thinking. Do NOT include <think> blocks. Only output SQL. Generate an SQL query based on the Prompt and the context from Company database.
        Prompt: {data.llm_prompt}
        Company database: {data.llm_context}
        Output ONLY the SQL query. No explanations or text before/after. Do NOT explain anything. Do NOT add comments. Return ONLY SQL."""

        try:
            response = llm.invoke(
                alpaca_prompt,
                max_tokens=-1,
                temperature=0.1,
                top_p=0.8)

            response_text = response.content if hasattr(response, 'content') else ""

            if not response_text or not response_text.strip():
                if hasattr(response, 'additional_kwargs'):
                    reasoning = response.additional_kwargs.get('reasoning_content', '')
                    if reasoning:
                        response_text = reasoning
                        print("INFO: Использован reasoning_content (content был пуст)")

            final_answer = validate_sql(response_text)
            
            if final_answer['Status']:
                return final_answer['SQL']
            else:
                return final_answer['Error']
            
        except Exception as e:
            return f"Ошибка работы LLM: {e}"
        
    #Простой метод для генерации обычного ответа (не SQL-запроса)
    @staticmethod
    def get_llm_answer(data:Question):
        llm = get_llm()
        try:
            response = llm.invoke(
                data.llm_prompt,
                max_tokens=-1,
                temperature=0.1,
                top_p=0.8)
            return response.content
            
        except Exception as e:
            return (f"Ошибка работы LLM: {e}")
        
    @staticmethod
    def get_llm_sql_answer_with_tool_and_chain(data:QuestionSQL_TOOL_CHAIN):

        def decide_next_node(state:AgentState) -> str:
            tool = state.get("function_to_call")
            context = state.get("context")
            if context != "":
                return "sql_generation"
            elif tool != "":
                return "tool"
            else:
                return "error"
                
        graph_builder = StateGraph(AgentState)

        graph_builder.add_node("agent", agent_node)
        graph_builder.add_node("tool", tool_node)
        graph_builder.add_node("sql_generation", sql_generation_node)
        graph_builder.add_node("error", end_with_error_node)

        graph_builder.set_entry_point("agent")

        graph_builder.add_conditional_edges(
            "agent",
            decide_next_node,
            {
                "tool": "tool",
                "sql_generation": "sql_generation",
                "error": "error"
            }
        )

        if(data.execute_sql):
            graph_builder.add_node("sql_exec", sql_exec_node)

            graph_builder.add_edge("tool", "sql_generation")
            graph_builder.add_edge("sql_generation", "sql_exec")
            graph_builder.add_edge("sql_exec", END)
        else:
            graph_builder.add_edge("tool", "sql_generation")
            graph_builder.add_edge("sql_generation", END)

        graph = graph_builder.compile()

        result = graph.invoke({
            "question":data.llm_prompt,
            "function_to_call":"",
            "context":"",
            "final_answer":"",
            "sql":"",
        })
        return (result["final_answer"], result["context"], result["function_to_call"], result["sql"])

    @staticmethod
    def get_llm_sql_answer_with_tool_and_chain_and_RAG(data: QuestionSQL_TOOL_CHAIN):
        """Генерация SQL с использованием RAG системы для получения контекста"""

        # Получаем контекст из RAG системы
        rag_context = get_context_from_rag(data.llm_prompt)

        def decide_next_node(state: AgentState) -> str:
            tool = state.get("function_to_call")
            context = state.get("context")
            if context != "":
                return "sql_generation"
            elif tool != "":
                return "tool"
            else:
                return "error"

        graph_builder = StateGraph(AgentState)

        graph_builder.add_node("agent", agent_node)
        graph_builder.add_node("tool", tool_node)
        graph_builder.add_node("sql_generation", sql_generation_node)
        graph_builder.add_node("error", end_with_error_node)

        graph_builder.set_entry_point("agent")

        graph_builder.add_conditional_edges(
            "agent",
            decide_next_node,
            {
                "tool": "tool",
                "sql_generation": "sql_generation",
                "error": "error"
            }
        )

        if (data.execute_sql):
            graph_builder.add_node("sql_exec", sql_exec_node)

            graph_builder.add_edge("tool", "sql_generation")
            graph_builder.add_edge("sql_generation", "sql_exec")
            graph_builder.add_edge("sql_exec", END)
        else:
            graph_builder.add_edge("tool", "sql_generation")
            graph_builder.add_edge("sql_generation", END)

        graph = graph_builder.compile()

        result = graph.invoke({
            "question": data.llm_prompt,
            "function_to_call": "",
            "context": rag_context,  # Используем контекст из RAG
            "final_answer": "",
        })
        return (result["final_answer"], result["context"], result["function_to_call"], result["sql"])
