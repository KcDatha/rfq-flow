import os
import sys
import tempfile

# Evals run against a throwaway DB so they never touch dev data.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.seed import seed_catalog  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def catalog():
    init_db()
    with Session(engine) as session:
        seed_catalog(session)
