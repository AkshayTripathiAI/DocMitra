"""SQLAlchemy engine, session and table creation."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BACKEND_DIR, settings


class Base(DeclarativeBase):
    pass


def _resolve_url(url: str) -> str:
    """Make relative SQLite paths relative to backend/, not the cwd."""
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith(prefix + "/") and ":memory:" not in url:
        path = BACKEND_DIR / url[len(prefix):]
        path.parent.mkdir(parents=True, exist_ok=True)
        return prefix + path.as_posix()
    return url


engine = create_engine(
    _resolve_url(settings.database_url),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
