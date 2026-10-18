# Local testing before anything is published.
#   make local      create .venv, install this package (editable) and the Rakiura helper if it is
#                   next door, then open Jupyter Lab on the notebooks
#   make test       run the tests
#   make run        execute every notebook headless (blank answers) into notebooks/executed/

PYTHON ?= python3
VENV ?= .venv
# The notebook helper is not on PyPI yet. Point this at its folder (it is optional).
RAKIURA_PY ?= ../rakiura-labs-platform/tools/rakiura-py
BIN := $(VENV)/bin

.PHONY: local venv install test run manifests clean

local: install
	$(BIN)/jupyter lab notebooks

venv:
	test -x $(BIN)/python || $(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -q --upgrade pip

install: venv
	$(BIN)/pip install -q -e ".[dev,notebooks,explore]"
	@if [ -d "$(RAKIURA_PY)" ]; then \
		$(BIN)/pip install -q -e "$(RAKIURA_PY)" && echo "Installed the Rakiura helper from $(RAKIURA_PY)"; \
	else \
		echo "Rakiura helper not found at $(RAKIURA_PY): notebooks run in offline mode (set RAKIURA_PY=...)"; \
	fi

test: install
	$(BIN)/python -m pytest -q

run: install
	RAKIURA_LIVE=0 $(BIN)/python scripts/run_notebooks.py

manifests: install
	$(BIN)/python scripts/build_manifest.py

clean:
	rm -rf notebooks/handin notebooks/nmr_data handin nmr_data .pytest_cache
