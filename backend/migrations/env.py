from alembic import context
from sqlalchemy import URL, create_engine, pool

from database import connection_parameters

parameters = connection_parameters()
url = URL.create(
    "postgresql+psycopg",
    username=parameters["user"],
    password=parameters["password"],
    host=parameters["host"],
    port=int(parameters["port"]),
    database=parameters["dbname"],
)

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
