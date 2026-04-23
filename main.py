from fastapi import FastAPI
import os
from dotenv import load_dotenv
from app.routers import llm_route, tool_route, model_loader_route
from fastapi.staticfiles import StaticFiles
from app.pages import router

load_dotenv()

app = FastAPI(title="Text-To-SQL DB Master: Documentation")

app.mount('/static', StaticFiles(directory='app/static'), 'static')

app.include_router(llm_route.app, tags=["LLM"])
app.include_router(tool_route.app, tags=["TOOLS"])
app.include_router(router.app, tags=["UI"])
app.include_router(model_loader_route.app, tags=["SET LLM MODEL"])
