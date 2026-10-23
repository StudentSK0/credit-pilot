import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from applications import router
from auth import router as auth_router
from database import connection_parameters
from products import router as products_router
from workflow import router as workflow_router
from analytics import router as analytics_router
from demo import router as demo_router

app = FastAPI(
    title="Credit Pilot",
    version="0.2.0",
    description="Учебный кредитный кабинет. Только синтетические данные, локальные проверки и моделируемая выдача.",
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(workflow_router)
app.include_router(analytics_router)
app.include_router(demo_router)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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
