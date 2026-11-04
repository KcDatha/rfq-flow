from sqlmodel import SQLModel, create_engine

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)


def init_db() -> None:
    # Imported here so the models are registered before create_all runs.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
