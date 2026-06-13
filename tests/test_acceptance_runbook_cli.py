import subprocess
import sys


def test_acceptance_runbook_cli_prints_final_local_acceptance_guidance():
    result = subprocess.run(
        [sys.executable, "-m", "acceptance_runbook"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Data Pipeline final local acceptance runbook" in result.stdout
    assert r".\.venv\Scripts\python -m pytest" in result.stdout
    assert "Use .\\.venv\\Scripts\\python, not global Anaconda/python/pytest" in result.stdout
