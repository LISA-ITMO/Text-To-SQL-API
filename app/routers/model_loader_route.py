from fastapi import APIRouter
from app.services.llm_service import load_model_from_hf, load_model_from_server
from app.schemas import load_model_local, load_model_hf, load_model_server

app = APIRouter(prefix='/loadmodel')

@app.post("/setlocalmodel")
def set_local_model(data:load_model_local):
    try:
        load_model_from_hf(local_model_path = data.url, filename = None, repo_id = None)
        return("Модель успешно загружена")
    except Exception as e:
        return(f"Проблемы при загрузке: {e}") 

@app.post("/setlocalmodelhf")
def set_local_model_hf(data:load_model_hf):
    try:
        load_model_from_hf(repo_id = data.url, filename = data.filename, local_model_path = None)
        return("Модель успешно загружена")
    except Exception as e:
        return(f"Проблемы при загрузке: {e}") 

@app.post("/setservermodel")
def set_server_model(data:load_model_server):
    return load_model_from_server(url = data.url, api_key = data.api_key, model = data.model)