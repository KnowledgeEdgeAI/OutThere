from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    sqlite = parsed.get_backend_name() == "sqlite"
    if sqlite and parsed.database not in (None, "", ":memory:"):
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 10} if sqlite else {},
        pool_pre_ping=True,
        hide_parameters=True,
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def sqlite_options(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


@contextmanager
def transaction(engine: Engine, *, write: bool = False):
    with Session(engine, expire_on_commit=False) as session:
        if engine.dialect.name == "sqlite":
            # Real read snapshots; serialize local writes before reading version/receipt state.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
