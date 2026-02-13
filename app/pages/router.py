from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

app  = APIRouter(prefix="/UI")
templates = Jinja2Templates(directory='app/templates')

@app.get('/main')
def open_main_ui(request: Request):
    return templates.TemplateResponse(name='main.html', context={'request': request})