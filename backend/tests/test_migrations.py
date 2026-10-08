from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from outthere.db import make_engine


def test_schema_migrates_up_down_and_up(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setenv("OUTTHERE_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = make_engine(url)
    assert {"user", "plan", "message", "change", "job"} <= set(inspect(engine).get_table_names())
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    engine.dispose()


def test_v2_migration_preserves_legacy_accounts_and_sessions(tmp_path, monkeypatch):
    from sqlalchemy import text

    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setenv("OUTTHERE_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "f6b4936e2c81")
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO user(id,display_name,created_at,feed_seq) VALUES (:id,'Legacy',1,0)"),
            {"id": "a" * 32},
        )
        connection.execute(
            text(
                "INSERT INTO authsession(id,user_id,access_hash,refresh_hash,"
                "access_expires_at,refresh_expires_at) "
                "VALUES (:id,:user,'hash-a','hash-r',1,2)"
            ),
            {"id": "b" * 32, "user": "a" * 32},
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT display_name,phone,version FROM user")).one() == (
            "Legacy",
            None,
            1,
        )
        assert connection.execute(text("SELECT device_id FROM authsession")).scalar() is None
    command.downgrade(config, "f6b4936e2c81")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT display_name FROM user")).scalar() == "Legacy"
        assert connection.execute(text("SELECT access_hash FROM authsession")).scalar() == "hash-a"
    command.upgrade(config, "head")
    engine.dispose()


def test_product_migration_preserves_populated_planning_and_devices(tmp_path, monkeypatch):
    from sqlalchemy import text

    url = f"sqlite:///{tmp_path / 'populated.db'}"
    monkeypatch.setenv("OUTTHERE_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "09528ba7ace9")
    engine = make_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO user(id,display_name,created_at,feed_seq,version) "
                "VALUES (:id,'Legacy',1,0,1)"
            ),
            {"id": "a" * 32},
        )
        db.execute(
            text(
                "INSERT INTO circle(id,owner_id,name,kind,created_at) "
                "VALUES (:id,:user,'Friends','social',1)"
            ),
            {"id": "b" * 32, "user": "a" * 32},
        )
        db.execute(
            text(
                "INSERT INTO plan(id,host_id,title,starts_at,ends_at,venue_timezone,"
                "place_label,version,message_seq,archived) "
                "VALUES (:id,:user,'Walk',2,3,'UTC','Park',1,0,0)"
            ),
            {"id": "c" * 32, "user": "a" * 32},
        )
        db.execute(
            text(
                "INSERT INTO device(id,user_id,installation_id,platform,created_at,last_seen_at) "
                "VALUES (:id,:user,:installation,'web',1,1)"
            ),
            {"id": "d" * 32, "user": "a" * 32, "installation": "e" * 32},
        )
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(
            text("SELECT title,visibility,currency,capacity,tags FROM plan")
        ).one() == ("Walk", "private", "INR", 15, "[]")
        assert db.execute(text("SELECT name,version,sleeping FROM circle")).one() == (
            "Friends",
            1,
            0,
        )
        assert db.execute(text("SELECT acknowledged_cursor,sync_epoch FROM device")).one() == (0, 0)
    command.check(config)
    command.downgrade(config, "09528ba7ace9")
    command.upgrade(config, "head")
    engine.dispose()
