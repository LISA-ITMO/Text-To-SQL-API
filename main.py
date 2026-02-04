from fastapi import FastAPI
from app.routers import llm_llama3b_route, tool_route
from app.services.llm_llama3b_service import load_model

app = FastAPI()

load_model("./gguf_model/Llama3-2-3B-Instruct-text-to-sql-20K_Q4_K_M.gguf") #Поле для ввода пути к LLM-модели

app.include_router(llm_llama3b_route.app, tags=["/llm_llama3b"])
app.include_router(tool_route.app, tags=["/tools"])

