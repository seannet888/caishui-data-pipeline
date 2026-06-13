from pathlib import Path

from acceptance_runbook import get_pipeline_acceptance_runbook


def test_readme_final_acceptance_stays_in_sync_with_runbook():
    readme = Path("README.md").read_text(encoding="utf-8")
    runbook = get_pipeline_acceptance_runbook({})

    for step in runbook.steps:
        assert step.command in readme

    for warning in runbook.warnings:
        assert warning in readme


def test_environment_contract_keeps_test_imports_and_dependency_pins_explicit():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert 'asyncio_mode = "auto"' in pyproject
    assert 'pythonpath = ["."]' in pyproject
    assert "openai==1.35.13" in requirements
    assert "httpx==0.27.2" in requirements
