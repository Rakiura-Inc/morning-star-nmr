# Local testing.
#   make local      create .venv, install this package (editable) and the Rakiura helper, then open
#                   Jupyter Lab on the notebooks
#   make test       run the tests
#   make run        execute every notebook headless (blank answers) into notebooks/executed/

PYTHON ?= python3
VENV ?= .venv
# The Rakiura notebook helper (optional). Set RAKIURA_HELPER to a local checkout to use that instead.
RAKIURA_HELPER ?= rakiura @ git+https://github.com/Rakiura-Inc/rakiura-py@main
BIN := $(VENV)/bin

.PHONY: local venv install test run manifests clean

local: install
	$(BIN)/jupyter lab notebooks

venv:
	test -x $(BIN)/python || $(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -q --upgrade pip

install: venv
	$(BIN)/pip install -q -e ".[dev,notebooks,explore]"
	@$(BIN)/pip install -q "$(RAKIURA_HELPER)" && echo "Installed the Rakiura helper." \
		|| echo "Could not install the Rakiura helper, so the notebooks run in offline mode."

test: install
	$(BIN)/python -m pytest -q

run: install
	RAKIURA_LIVE=0 $(BIN)/python scripts/run_notebooks.py

manifests: install
	$(BIN)/python scripts/build_manifest.py

clean:
	rm -rf notebooks/handin notebooks/nmr_data handin nmr_data .pytest_cache
