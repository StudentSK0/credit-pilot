"""Explicit, idempotent local demo accounts; never claims existing applications."""

import os

import psycopg

from auth import password_hash
from database import connection_parameters

DEMO_ACCOUNTS = (
    ("client-a", "CLIENT", "1234567890", "DEMO_CLIENT_PASSWORD", "demo-client-a-local"),
    ("client-b", "CLIENT", "123456789012", "DEMO_CLIENT_B_PASSWORD", "demo-client-b-local"),
    ("bank", "BANK_EMPLOYEE", None, "DEMO_BANK_PASSWORD", "demo-bank-local"),
)


def seed_demo(connection):
    with connection.transaction():
        for login, role, inn, password_variable, default_password in DEMO_ACCOUNTS:
            company_id = None
            if inn:
                company_id = connection.execute(
                    "INSERT INTO companies (name, inn) VALUES (%s, %s) "
                    "ON CONFLICT (inn) DO UPDATE SET inn = EXCLUDED.inn RETURNING id",
                    (f"Demo {login}", inn),
                ).fetchone()[0]
            if connection.execute("SELECT id FROM users WHERE login = %s", (login,)).fetchone():
                continue
            connection.execute(
                "INSERT INTO users (login, password_hash, role, company_id) VALUES (%s, %s, %s, %s)",
                (login, password_hash(os.getenv(password_variable, default_password)), role, company_id),
            )


if __name__ == "__main__":
    with psycopg.connect(**connection_parameters()) as connection:
        seed_demo(connection)
    print("Demo accounts ready: client-a, client-b, bank. Existing accounts and applications preserved.")
