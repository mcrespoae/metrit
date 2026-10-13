# Makefile

# Cross-platform recursive delete command used by the clean target
ifeq ($(OS),Windows_NT)
	RMDIR = rmdir /S /Q
else
	RMDIR = rm -rf
endif

.PHONY: install build example test lint typecheck check clean upload_pypi upload-testpypi

install:
	$(info Installing the repo)
	uv sync --dev

example:
	uv run python examples/examples.py

test:
	uv run python -m unittest discover -v -s ./tests -p "*test*.py"

lint:
	uv run flake8

typecheck:
	uv run basedpyright

check: lint typecheck

clean:
ifeq ($(OS),Windows_NT)
	@if exist build $(RMDIR) build
	@if exist dist $(RMDIR) dist
	@if exist .eggs $(RMDIR) .eggs
	@if exist metrit.egg-info $(RMDIR) metrit.egg-info

else
	$(RMDIR) build
	$(RMDIR) dist
	$(RMDIR) .eggs
	$(RMDIR) metrit.egg-info
endif

build:
# Use it only to check the version before uploading
	uv build


upload-pypi: clean install test build check
# DEPRECATED
# Instead use tags and the pypi_release.yml will upload the Github release and pypi
# Push your changes to main
# git tag 0.0.1 # or whatever version needed
# git push origin --tags

# Upload to PyPI. Make sure you have in your ~/.pypirc file in home directory
	uv run twine upload dist/*

upload-testpypi: clean install test build check
# DEPRECATED

# Upload to TestPyPI. Make sure you have in your ~/.pypirc file in home directory
# Use `uv run python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ metrit`
# for installing the testpypi version
	uv run twine upload --repository testpypi dist/*
