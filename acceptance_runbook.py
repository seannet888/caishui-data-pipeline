from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Iterable, Mapping


PipelineEnv = Mapping[str, str | None]


@dataclass(frozen=True)
class PipelineAcceptanceStep:
    command: str
    validates: str
    required_env: tuple[str, ...]
    missing_env: tuple[str, ...]


@dataclass(frozen=True)
class PipelineAcceptanceRunbook:
    title: str
    warnings: tuple[str, ...]
    steps: tuple[PipelineAcceptanceStep, ...]


def get_pipeline_acceptance_runbook(
    env: PipelineEnv = environ,
) -> PipelineAcceptanceRunbook:
    steps = (
        _create_step(
            command=r".\.venv\Scripts\python -m pip install -r requirements.txt",
            validates="Locked Python dependencies install into the project virtualenv",
            required_env=("PYTHONUTF8",),
            env=env,
        ),
        _create_step(
            command=r".\.venv\Scripts\python -m pytest",
            validates="Pipeline behavior tests under locked Python dependencies",
            required_env=("PYTHONUTF8",),
            env=env,
        ),
        _create_step(
            command=r".\.venv\Scripts\python -m uvicorn api.main:app --host 127.0.0.1 --port 8000",
            validates="FastAPI service starts with schema check and task recovery",
            required_env=("PYTHONUTF8", "DATABASE_URL", "PIPELINE_SHARED_SECRET"),
            env=env,
        ),
        _create_step(
            command="GET http://127.0.0.1:8000/health",
            validates="Pipeline health endpoint is reachable for WebApp live handshakes",
            required_env=(),
            env=env,
        ),
    )

    return PipelineAcceptanceRunbook(
        title="Data Pipeline final local acceptance runbook",
        warnings=(
            r"Use .\.venv\Scripts\python, not global Anaconda/python/pytest",
            "Pipeline does not own migrations; do not run Alembic or SQLAlchemy create_all",
            "PYTHONUTF8=1 is required on Windows to avoid GBK/UTF-8 drift",
        ),
        steps=steps,
    )


def format_pipeline_acceptance_runbook(runbook: PipelineAcceptanceRunbook) -> str:
    missing_env = _unique(
        env_name for step in runbook.steps for env_name in step.missing_env
    )

    lines = [
        runbook.title,
        *runbook.warnings,
        *(f"Missing env: {env_name}" for env_name in missing_env),
    ]

    for index, step in enumerate(runbook.steps, start=1):
        lines.extend(
            [
                f"{index}. {step.command}",
                f"   Validates: {step.validates}",
                f"   Required env: {_format_list(step.required_env)}",
                f"   Missing env: {_format_list(step.missing_env)}",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    print(format_pipeline_acceptance_runbook(get_pipeline_acceptance_runbook()))
    return 0


def _create_step(
    *,
    command: str,
    validates: str,
    required_env: tuple[str, ...],
    env: PipelineEnv,
) -> PipelineAcceptanceStep:
    return PipelineAcceptanceStep(
        command=command,
        validates=validates,
        required_env=required_env,
        missing_env=tuple(key for key in required_env if not env.get(key)),
    )


def _format_list(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


if __name__ == "__main__":
    raise SystemExit(main())
