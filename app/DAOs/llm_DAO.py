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
from app.services.llm_service import get_llm, get_llm_backend
from app.DAOs.tool_DAO import toolDAO
from app.services.sql_service import validate_sql
from app.services.rag_service import get_context_from_rag

AVAILABLE_TOOLS = {
    "connect_and_get_all_tables_info": toolDAO.connect_and_get_all_tables_info,
}

#Универсальный извлекатель текста ответа.
def extract_response_text(response) -> str:
    if hasattr(response, 'content') and response.content:
        return response.content
    if hasattr(response, 'additional_kwargs'):
        reasoning = response.additional_kwargs.get('reasoning_content', '')
        if reasoning:
            return reasoning
    return str(response)

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
        
    return {
            "question": state["question"],
            "function_to_call": '1',
            "context": context,
            "final_answer": "",
            "sql":""
        }

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
    backend = get_llm_backend()

    alpaca_prompt = f"""You are SQL specialist. Do NOT output reasoning or thinking. Do NOT include <think> blocks. Only output SQL. Generate an SQL query based on the Prompt and the context from Company database.
    Prompt: {state.get('question')}
    Company database: {state.get('context')}
    Output ONLY the SQL query. No explanations or text before/after. Do NOT explain anything. Do NOT add comments. Return ONLY SQL."""

    invoke_kwargs = {
        "temperature": 0.1,
    }
    
    if backend == 'local':
        invoke_kwargs["max_tokens"] = -1
        invoke_kwargs["top_p"] = 0.8
    else:
        invoke_kwargs["max_tokens"] = 4096
    
    response = llm.invoke(alpaca_prompt, **invoke_kwargs)

    response_text = extract_response_text(response)
    
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
    def get_llm_sql_answer(data: QuestionSQL) -> str:
        llm = get_llm()
        backend = get_llm_backend()
        alpaca_prompt = f"""You are SQL specialist. Do NOT output reasoning or thinking. Do NOT include <think> blocks. Only output SQL. Generate an SQL query based on the Prompt and the context from Company database.
        Prompt: {data.llm_prompt}
        Company database: {data.llm_context}
        Output ONLY the SQL query. No explanations or text before/after. Do NOT explain anything. Do NOT add comments. Return ONLY SQL."""

        try:
            invoke_kwargs = {"temperature": 0.1}
            if backend == 'local':
                invoke_kwargs["max_tokens"] = -1
                invoke_kwargs["top_p"] = 0.8
            else:
                invoke_kwargs["max_tokens"] = 4096
                
            response = llm.invoke(alpaca_prompt, **invoke_kwargs)

            response_text = extract_response_text(response)

            final_answer = validate_sql(response_text)
            
            if final_answer['Status']:
                return final_answer['SQL']
            else:
                return final_answer['Error']
            
        except Exception as e:
            return f"Ошибка работы LLM: {e}"
        
    #Простой метод для генерации обычного ответа (не SQL-запроса)
    @staticmethod
    def get_llm_answer(data: Question):
        llm = get_llm()
        backend = get_llm_backend()
        invoke_kwargs = {"temperature": 0.1}
        if backend == 'local':
            invoke_kwargs["max_tokens"] = -1
            invoke_kwargs["top_p"] = 0.8
        else:
            invoke_kwargs["max_tokens"] = 4096
            
        try:
            response = llm.invoke(data.llm_prompt, **invoke_kwargs)
            return extract_response_text(response)
        except Exception as e:
            return f"Ошибка работы LLM: {e}"
        
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
