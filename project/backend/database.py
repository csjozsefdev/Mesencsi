import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")
# Opcionális második fájl (pl. ha a JWT ide került): ugyanaz a KEY=value szintaxis, mint .env-ben — nem Python modul.
_env_py = _BACKEND_DIR / ".env.py"
if _env_py.is_file():
    load_dotenv(_env_py, override=True)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(
            f"Missing {name} in {_BACKEND_DIR / '.env'} — "
            "copy .env.example to .env and set PostgreSQL variables (never commit .env)."
        )
    return value


def _database_url() -> str:
    """Build DSN from .env — vagy teszthez ``MESENCSI_TEST_DATABASE_URL`` (pl. SQLite memória)."""
    test_url = (os.getenv("MESENCSI_TEST_DATABASE_URL") or "").strip()
    if test_url:
        return test_url
    user = _require_env("POSTGRES_USER").strip()
    if not user:
        raise ValueError("POSTGRES_USER in .env must be non-empty.")

    password = _require_env("POSTGRES_PASSWORD")
    host = (os.getenv("POSTGRES_HOST") or "localhost").strip()
    port = (os.getenv("POSTGRES_PORT") or "5432").strip()
    db = (os.getenv("POSTGRES_DB") or "mesencsi").strip()

    user_q = quote(user, safe="")
    if password:
        auth = f"{user_q}:{quote(password, safe='')}"
    else:
        auth = user_q
    return f"postgresql+psycopg://{auth}@{host}:{port}/{db}"


DATABASE_URL = _database_url()


class Base(DeclarativeBase):
    pass


_engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **_engine_kwargs)

if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_relation_missing_error(exc: BaseException) -> bool:
    """True when the driver reports a missing table/relation (often: Alembic not applied)."""
    if isinstance(exc, ProgrammingError):
        orig = getattr(exc, "orig", None)
        if orig is not None and type(orig).__name__ == "UndefinedTable":
            return True
        s = str(exc).lower()
        if "does not exist" in s and "relation" in s:
            return True
    return False


def is_undefined_column_error(exc: BaseException) -> bool:
    """True when a queried column is missing (ORM ahead of DB — run alembic upgrade head)."""
    if isinstance(exc, ProgrammingError):
        orig = getattr(exc, "orig", None)
        if orig is not None and type(orig).__name__ == "UndefinedColumn":
            return True
        s = str(exc).lower()
        if "undefinedcolumn" in s.replace(" ", "") or ("column" in s and "does not exist" in s):
            return True
    return False


def storybook_tables_exist(db: Session) -> bool:
    """Cheap check used before optional counts (e.g. admin /system)."""
    try:
        db.execute(text("SELECT 1 FROM digital_storybooks LIMIT 1"))
        return True
    except ProgrammingError:
        db.rollback()
        return False
