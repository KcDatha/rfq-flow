"""Cold-start guard: importing the API app must not import langgraph.

The serverless entry point serves page loads and plain GETs through the
same function as submissions. Importing langgraph (and compiling the
graph) at module load added seconds to every cold start; only a
submission should pay that cost.
"""
import os
import subprocess
import sys

BACKEND = os.path.join(os.path.dirname(__file__), "..")


def test_importing_main_does_not_load_langgraph():
    code = (
        "import sys;"
        f"sys.path.insert(0, {BACKEND!r});"
        "import app.main;"
        "assert 'langgraph' not in sys.modules, 'langgraph imported eagerly';"
        "assert 'langchain_google_genai' not in sys.modules;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_graph_pipeline_is_lazy_singleton():
    sys.path.insert(0, BACKEND)
    from app import graph

    assert graph._pipeline is None  # not compiled at import time
    first = graph.get_pipeline()
    assert first is graph.get_pipeline()
