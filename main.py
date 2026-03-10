from fastapi import FastAPI
from app.routers import llm_route, tool_route
from fastapi.staticfiles import StaticFiles
from app.pages import router
from app.services.llm_service import load_model_from_hf


app = FastAPI()

app.mount('/static', StaticFiles(directory='app/static'), 'static')

load_model_from_hf(repo_id="vindows/qwen2.5-0.5b-text-to-sql-gguf",filename="qwen2.5-0.5b-text-to-sql-f16.gguf") #Поле для ввода пути к LLM-модели / загрузки модели из сети

app.include_router(llm_route.app, tags=["LLM"])
app.include_router(tool_route.app, tags=["TOOLS"])
app.include_router(router.app, tags=["UI"])
