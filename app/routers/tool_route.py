from fastapi import APIRouter
from app.DAOs.tool_DAO import toolDAO
from app.schemas import tool_safe_sql_execute

app = APIRouter(prefix = '/tool')

@app.post("/gettablesinfo")
async def get_tables_info_from_db(data:list[str]):
    return toolDAO.connect_and_get_table_info(data)

@app.get("/getalltablesinfo")
async def get_all_tables_info_from_db():
    return toolDAO.connect_and_get_all_tables_info()

@app.post("/safeexecutesql")
async def safe_execute_ql(data:tool_safe_sql_execute):
    return toolDAO.safe_connect_and_execute_sql(data.sql)