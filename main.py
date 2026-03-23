from fastapi import FastAPI
from app.routers import llm_route, tool_route
from fastapi.staticfiles import StaticFiles
from app.pages import router
from app.services.llm_service import load_model_from_hf, load_model


app = FastAPI()

app.mount('/static', StaticFiles(directory='app/static'), 'static')

load_model_from_hf(repo_id="mradermacher/XiYanSQL-QwenCoder-14B-2504-GGUF",filename="XiYanSQL-QwenCoder-14B-2504.Q5_K_M.gguf") #Поле для ввода пути к LLM-модели / загрузки модели из сети

#load_model('./gguf_model/XiYanSQL-QwenCoder-14B-2504.Q5_K_M.gguf') #только локальные модели

app.include_router(llm_route.app, tags=["LLM"])
app.include_router(tool_route.app, tags=["TOOLS"])
app.include_router(router.app, tags=["UI"])
