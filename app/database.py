import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import settings


def _ensure_sqlite_dir(database_url: str) -> None:
    """Garante que o diretório do arquivo SQLite exista antes de abrir conexão."""
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        db_path = database_url.replace("sqlite:///", "", 1)
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)


_ensure_sqlite_dir(settings.DATABASE_URL)

connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy 2.0."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Provedor de sessão do banco para injeção de dependência no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Cria as tabelas caso ainda não existam."""
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
