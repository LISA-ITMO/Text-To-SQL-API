from fastapi import FastAPI
import os
from dotenv import load_dotenv
from app.routers import llm_route, tool_route
from fastapi.staticfiles import StaticFiles
from app.pages import router
from app.services.llm_service import load_model_from_hf, load_model, load_model_from_server

load_dotenv()



app = FastAPI()

app.mount('/static', StaticFiles(directory='app/static'), 'static')

#load_model_from_hf(repo_id="Tvisterious/Llama3-2-3B-Instruct-text-to-sql-20K_GGUF_Q4_K_M",filename="Llama3-2-3B-Instruct-text-to-sql-20K_Q4_K_M.gguf") #Поле для ввода пути к LLM-модели / загрузки модели из сети
#load_model('./gguf_model/XiYanSQL-QwenCoder-14B-2504.Q5_K_M.gguf') #только локальные модели

load_model_from_server(os.getenv("LLM_SERVER"), os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL_NAME")) #подключение к локальному или облачному серверу. Для докального исправить только первый аргумент

app.include_router(llm_route.app, tags=["LLM"])
app.include_router(tool_route.app, tags=["TOOLS"])
app.include_router(router.app, tags=["UI"])
