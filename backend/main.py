import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from applications import router
from auth import router as auth_router
from database import connection_parameters
from products import router as products_router

app = FastAPI(title="Credit Pilot")
app.include_router(router)
app.include_router(auth_router)
app.include_router(products_router)


@app.get("/api/health", responses={503: {"description": "Database unavailable"}})
def health():
    try:
        with psycopg.connect(**connection_parameters()) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )

    return {"status": "ok", "database": "ok"}
