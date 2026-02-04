from fastapi import APIRouter
from app.DAOs.tool_DAO import toolDAO

app = APIRouter(prefix = '/tool')

@app.post("/gettablesinfo")
async def get_tables_info_from_db(data:list[str]):
    return toolDAO.connect_and_get_table_info(data)

@app.get("/getalltablesinfo")
async def get_all_tables_info_from_db():
    return toolDAO.connect_and_get_all_tables_info()