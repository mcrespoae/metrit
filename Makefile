# Makefile
# Check if the OS is Windows
ifeq ($(OS),Windows_NT)
	VENV_ACTIVATE = .venv\Scripts\activate &&
	PYTHON = python
	RM = del /Q
	RMDIR = rmdir /S /Q

else
	VENV_ACTIVATE = . .venv/bin/activate &
	PYTHON = python3
	RM = rm -f
	RMDIR = rm -rf

endif

.PHONY: install example

install:
	$(info Installing the repo)
ifeq ($(OS),Windows_NT)
	@if not exist .venv mkdir .venv
else
	@mkdir -p .venv
endif
	pipenv install -e . --dev

example:
	$(VENV_ACTIVATE) $(PYTHON) examples/examples.py


clean:
ifeq ($(OS),Windows_NT)
	@if exist build $(RMDIR) build
	@if exist dist $(RMDIR) dist
	@if exist .eggs $(RMDIR) .eggs
	@if exist tempit.egg-info $(RMDIR) tempit.egg-info

else
	$(RMDIR) build
	$(RMDIR) dist
	$(RMDIR) .eggs
	$(RMDIR) tempit.egg-info
endif





