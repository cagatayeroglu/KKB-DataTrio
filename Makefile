.PHONY: install-dev quick pr full

install-dev:
	python -m pip install -e '.[dev]'

# Inner loop: coding agents should default to this.
quick:
	ruff check src tests scripts
	pytest -q tests/unit --disable-warnings --maxfail=1

# Feature -> dev gate. Intentionally still fast.
pr:
	ruff format --check src tests scripts
	ruff check src tests scripts
	pytest -q tests/unit --disable-warnings --maxfail=1
	bandit -q -r src
	python scripts/check_secrets.py

# dev -> main / explicit release gate.
full:
	ruff format --check src tests scripts
	ruff check src tests scripts
	mypy src
	pytest -q --disable-warnings
	bandit -q -r src
	python scripts/check_secrets.py
	pip-audit
