#!/usr/bin/env bash
set -Eeuo pipefail

python -m compileall -q app tests scripts alembic
ruff format --check app tests scripts alembic
ruff check app tests scripts alembic
mypy app
pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=90
bandit -c pyproject.toml -r app
pip-audit -r requirements.txt
python scripts/check_templates.py
node --check app/static/js/app.js
python scripts/check_release_integrity.py
