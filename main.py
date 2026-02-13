from fastapi import FastAPI
from app.routers import llm_route, tool_route
from fastapi.staticfiles import StaticFiles
from app.pages import router
from app.services.llm_service import load_model

app = FastAPI()

app.mount('/static', StaticFiles(directory='app/static'), 'static')

load_model("./gguf_model/llama-3-sqlcoder-8b-q4_k_m.gguf") #Поле для ввода пути к LLM-модели

app.include_router(llm_route.app, tags=["LLM"])
app.include_router(tool_route.app, tags=["TOOLS"])
app.include_router(router.app, tags=["UI"])
