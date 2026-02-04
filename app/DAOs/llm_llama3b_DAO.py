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
from typing import TypedDict, List, Dict, Any
from app.services.llm_llama3b_service import get_llm
from app.DAOs.tool_DAO import toolDAO
import re
import json
import logging

from app.services.rag_service import get_context_from_rag


#Фунция для форматирования SQL-запроса, чтобы очистить его от лишнего
def format_llm_answer(answer:str) -> str:
    end_substring = re.search(';', answer)
    start_substring = re.search('SELECT', answer)
    formatted_str = re.sub(r'\s{2,}', ' ', answer[start_substring.start():end_substring.start()] + ';')
    return formatted_str

AVAILABLE_TOOLS = {
    "connect_and_get_all_tables_info": toolDAO.connect_and_get_all_tables_info,
}

#Класс с описанием состояния LLM-агента
class AgentState(TypedDict):
    question: str
    function_to_call: str
    context: str
    final_answer: str

#Нода агента с формированием промпта для вызова функции и возвращения JSON с состоянием агента
def agent_node(state: AgentState) -> AgentState:
    llm = get_llm()

    model_with_tools = llm.bind_tools([toolDAO.connect_and_get_all_tables_info])
    response = model_with_tools.invoke("Какие таблицы и их столбцы в скобках есть у меня в базе данных? Выведи их без перевода на русский язык.")
    
    response_text = response.content if hasattr(response, 'content') else str(response)
    print(response_text)
    try:
        # Ищем JSON в ответе (модель могла добавить пояснения)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response_text)
        
        return {
            "question": state["question"],
            "function_to_call": data.get('name'),
            "context": "",
            "final_answer": ""
        }
        
    except json.JSONDecodeError:
        # Если не получилось распарсить JSON, возвращаем как финальный ответ
        print("Ошибка обработки JSON в ноде агента!")
        return {
            "question": state["question"],
            "function_to_call": "",
            "context": "",
            "final_answer": ""
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
    alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

    ### Instruction:
    SQL Prompt: {}

    ### Input:
    Company database: {}

    ### Response:
    SQL: {}
    """
    response = llm.invoke(
        alpaca_prompt.format(
            state.get("question"),
            state.get("context"),
            "",
            ),
        max_tokens=64,
        temperature=0.2)
    result = format_llm_answer(response.content)
    return{
        **state,
        "final_answer": result
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
        alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

        ### Instruction:
        SQL Prompt: {}

        ### Input:
        Company database: {}

        ### Response:
        SQL: {}
        """

        try:
            response = llm.invoke(
                alpaca_prompt.format(
                    data.llm_prompt,
                    data.llm_context,
                    "",
                    ),
                max_tokens=64,
                temperature=0.2)
            return format_llm_answer(response.content) 
        
        except Exception as e:
            return (f"Ошибка работы LLM: {e}")

    #Простой метод для генерации обычного ответа (не SQL-запроса)
    @staticmethod
    def get_llm_answer(data:Question):
        llm = get_llm()
        try:
            response = llm.invoke(
                data.llm_prompt,
                max_tokens=128,
                temperature=0.6)
            return response.content
            
        except Exception as e:
            return (f"Ошибка работы LLM: {e}")
        
    #Метод для фреймворка llama_cpp_agent сначала выполняющий функцию, а потом использующий контекст из неё для генерации SQL
    @staticmethod
    def get_llm_sql_answer_with_tool(data:QuestionSQL):
        llm_model = get_llm()
        alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

        ### Instruction:
        SQL Prompt: {}

        ### Input:
        Company database: {}

        ### Response:
        SQL: {}
        """
        llm_provider = LlamaCppPythonProvider(llm_model)
        settings = llm_provider.get_provider_default_settings()
        settings.temperature = 0.2

        get_db_info_function_tool = LlamaCppFunctionTool(toolDAO.connect_and_get_all_tables_info)
        #get_users_table_info = LlamaCppFunctionTool(get_users_table_info_o)

        function_call_agent = FunctionCallingAgent(
            llm_provider,
            llama_cpp_function_tools=[get_db_info_function_tool],
            allow_parallel_function_calling=True,
            messages_formatter_type=MessagesFormatterType.CHATML)
        
        response_provider = function_call_agent.generate_response("Какие таблицы и их столбцы в скобках есть у меня в базе данных? Выведи их без перевода на русский язык.", llm_sampling_settings=settings)
        
        try:
            response = llm_model(
            alpaca_prompt.format(
                data.llm_prompt,
                response_provider[0]["arguments"]["content"],
                "",
                ),
            max_tokens=64,
            temperature=0.6)

            result = response['choices'][0]['text']
            formatted_result = format_llm_answer(result)
            final_answer = {}
            final_answer['user_request'] = data.llm_prompt
            final_answer['result'] = formatted_result
            final_answer['context'] = response_provider[0]["arguments"]["content"]
            return final_answer
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
        })
        return (result["final_answer"], result["context"], result["function_to_call"])

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
        return (result["final_answer"], result["context"], result["function_to_call"])

    # Добавим новый метод для прямого использования RAG без графа
    @staticmethod
    def get_llm_sql_answer_with_rag_only(data: QuestionSQL_TOOL_CHAIN):
        """
        Генерация SQL запроса используя ТОЛЬКО контекст из RAG системы.
        Не вызывает инструменты или графы, только RAG + LLM.
        """
        try:
            # Получаем контекст из RAG
            llm = get_llm()
            rag_context = get_context_from_rag(data.llm_prompt)

            # Проверяем, не вернулась ли ошибка
            if "Ошибка" in rag_context and "базы данных" in rag_context:
                # Если RAG вернул ошибку, пробуем получить общую информацию о таблицах
                #logger.warning("RAG вернул ошибку, используем общую информацию о таблицах")

                # Получаем общую информацию о всех таблицах как запасной вариант
                try:
                    general_info = toolDAO.connect_and_get_all_tables_info()
                    rag_context = f"Общая информация о таблицах в базе данных:\n{general_info}\n\nВопрос пользователя: {data.llm_prompt}"
                except Exception as e:
                    rag_context = f"Не удалось получить информацию о базе данных. Ошибка: {str(e)}"

            # Используем улучшенный промпт
            alpaca_prompt = """Ты - эксперт по SQL и базе данных UPGO. Сгенерируй SQL запрос на основе предоставленной схемы базы данных.

    СХЕМА БАЗЫ ДАННЫХ:
    {}

    ВОПРОС ПОЛЬЗОВАТЕЛЯ:
    {}

    ИНСТРУКЦИИ:
    1. Используй ТОЛЬКО таблицы и столбцы из предоставленной схемы
    2. Если информации недостаточно, верни SELECT NULL
    3. Будь точным и используй правильные имена таблиц и столбцов

    SQL ЗАПРОС:"""

            # Форматируем промпт
            formatted_prompt = alpaca_prompt.format(
                rag_context,
                data.llm_prompt
            )

            # Генерируем SQL
            response = llm.invoke(
                formatted_prompt,
                max_tokens=150,
                temperature=0.1,
                stop=[";"]
            )

            # Форматируем ответ
            sql_query = response.content if hasattr(response, 'content') else str(response)
            sql_query = sql_query.strip()

            # Добавляем точку с запятой, если ее нет
            if not sql_query.endswith(';'):
                sql_query += ';'

            # Очищаем SQL от лишнего текста
            sql_query = format_llm_answer(sql_query)

            # Если требуется выполнить SQL
            if data.execute_sql:
                try:
                    sql_result = toolDAO.connect_and_execute_sql(sql_query)
                    return {
                        "sql_query": sql_query,
                        "execution_result": sql_result,
                        "rag_context_preview": rag_context[:300] + "..." if len(rag_context) > 300 else rag_context,
                        "status": "success"
                    }
                except Exception as e:
                    return {
                        "sql_query": sql_query,
                        "error": f"Ошибка выполнения SQL: {str(e)}",
                        "rag_context_preview": rag_context[:300] + "..." if len(rag_context) > 300 else rag_context,
                        "status": "execution_error"
                    }
            else:
                return {
                    "sql_query": sql_query,
                    "rag_context_preview": rag_context[:300] + "..." if len(rag_context) > 300 else rag_context,
                    "rag_context_length": len(rag_context),
                    "status": "success"
                }

        except Exception as e:
            #logger.error(f"Ошибка генерации SQL с RAG: {e}")
            return {
                "error": f"Ошибка генерации SQL с RAG: {str(e)}",
                "status": "generation_error"
            }