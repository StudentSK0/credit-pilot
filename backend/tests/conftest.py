from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql

from database import connection_parameters
from main import app
from seed import seed_demo


@pytest.fixture(scope="session")
def database():
    """Migrate a fresh database; never clear the application's existing database."""
    name = f"credit_pilot_test_{uuid4().hex}"
    with psycopg.connect(**connection_parameters(), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with pytest.MonkeyPatch.context() as patch:
                patch.setenv("POSTGRES_DB", name)
                patch.setenv("DEMO_CLIENT_PASSWORD", "demo-client-a-local")
                patch.setenv("DEMO_CLIENT_B_PASSWORD", "demo-client-b-local")
                patch.setenv("DEMO_BANK_PASSWORD", "demo-bank-local")
                patch.setenv("COOKIE_SECURE", "false")
                patch.setenv("ALLOWED_ORIGINS", "http://testserver,http://localhost:5173,http://localhost:8000")
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                command.upgrade(config, "head")
                with psycopg.connect(**connection_parameters()) as connection:
                    seed_demo(connection)
                yield
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def client(database):
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"login": "client-a", "password": "demo-client-a-local"})
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client
