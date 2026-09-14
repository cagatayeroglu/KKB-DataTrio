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
	mypy src
	pytest -q tests/unit --disable-warnings --maxfail=1
	bandit -q -r src
	python scripts/check_secrets.py

# Reviewed audit exceptions, each with its reason in ROADMAP's M0-08 record.
# PYSEC-2026-113: Arrow C++ IPC pre-buffering, not reachable through pyarrow.
# PYSEC-2026-1845: pytest's shared /tmp directory; a development-only tool.
AUDIT_EXCEPTIONS = --ignore-vuln PYSEC-2026-113 --ignore-vuln PYSEC-2026-1845

# dev -> main / explicit release gate.
full:
	ruff format --check src tests scripts
	ruff check src tests scripts
	mypy src
	pytest -q --disable-warnings
	bandit -q -r src
	python scripts/check_secrets.py
	pip-audit $(AUDIT_EXCEPTIONS)
