import os

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Credit Pilot")


@app.get("/api/health", responses={503: {"description": "Database unavailable"}})
def health():
    try:
        with psycopg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=3,
            options="-c statement_timeout=3000",
        ) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )

    return {"status": "ok", "database": "ok"}
