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


@pytest.fixture(scope="session")
def database():
    """Migrate a fresh database; never clear the application's existing database."""
    name = f"credit_pilot_test_{uuid4().hex}"
    with psycopg.connect(**connection_parameters(), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with pytest.MonkeyPatch.context() as patch:
                patch.setenv("POSTGRES_DB", name)
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                command.upgrade(config, "head")
                yield
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def client(database):
    with TestClient(app) as client:
        yield client
