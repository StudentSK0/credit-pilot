import os

import psycopg


def connection_parameters():
    return {
        "host": os.environ["POSTGRES_HOST"],
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "connect_timeout": 3,
        "options": "-c statement_timeout=3000",
    }


def get_connection():
    with psycopg.connect(**connection_parameters()) as connection:
        yield connection
