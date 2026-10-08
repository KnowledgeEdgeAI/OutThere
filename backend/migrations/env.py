from alembic import context
from sqlmodel import SQLModel

from outthere import (  # noqa: F401
    coordination,
    delivery,
    matching,
    media,
    models,
    money,
    product_models,
    ripples,
    safety,
    sharing,
)
from outthere.db import make_engine
from outthere.settings import Settings

target_metadata = SQLModel.metadata


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=Settings().database_url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(Settings().database_url)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run_migrations()
