from acceptance_runbook import format_pipeline_acceptance_runbook, get_pipeline_acceptance_runbook


def test_pipeline_acceptance_runbook_orders_local_validation_steps():
    runbook = get_pipeline_acceptance_runbook(
        {
            "VIRTUAL_ENV": r"J:\tax\data-pipeline\.venv",
            "PYTHONUTF8": "1",
            "DATABASE_URL": "postgresql+asyncpg://local",
            "PIPELINE_SHARED_SECRET": "secret",
        }
    )

    assert [step.command for step in runbook.steps] == [
        r".\.venv\Scripts\python -m pip install -r requirements.txt",
        r".\.venv\Scripts\python -m pytest",
        r".\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8000",
        "GET http://127.0.0.1:8000/health",
    ]
    assert runbook.steps[1].validates == "Pipeline behavior tests under locked Python dependencies"


def test_pipeline_acceptance_runbook_formats_environment_misuse_warnings():
    text = format_pipeline_acceptance_runbook(get_pipeline_acceptance_runbook({}))

    assert "Data Pipeline final local acceptance runbook" in text
    assert "Missing env: PYTHONUTF8" in text
    assert "Missing env: DATABASE_URL" in text
    assert "Use .\\.venv\\Scripts\\python, not global Anaconda/python/pytest" in text
    assert "Pipeline does not own migrations; do not run Alembic or SQLAlchemy create_all" in text
