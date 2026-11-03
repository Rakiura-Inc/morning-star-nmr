# Local work, all through uv (https://docs.astral.sh/uv/).
#   make local      install everything (the package editable, the Rakiura helper, Jupyter Lab) and open
#                   Jupyter Lab on the notebooks
#   make test       run the tests (in parallel, in random order)
#   make lint       ruff on the code and the notebooks
#   make hooks      every git hook, as CI runs them (ruff, notebook output stripping, workflow checks...)
#   make run        execute every notebook headless (blank answers) into notebooks/executed/

.PHONY: local test lint hooks run manifests clean

local:
	uv sync --group notebooks
	uv run jupyter lab notebooks

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

hooks:
	uvx prek run --all-files

run:
	RAKIURA_LIVE=0 uv run scripts/run_notebooks.py

manifests:
	uv run scripts/build_manifest.py

clean:
	rm -rf notebooks/handin notebooks/nmr_data handin nmr_data .pytest_cache
