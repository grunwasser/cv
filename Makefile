VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)
PDF ?= $(shell $(PYTHON) scripts/build_cv.py --print-pdf-filename)
PDF_EN ?= $(if $(wildcard cv.en.yml),en/$(shell $(PYTHON) scripts/build_cv.py --print-pdf-filename --language en),)
.DEFAULT_GOAL := update

.PHONY: init init-en install install-browser optimize-photo build check update sync serve pdf

init:
	@if test -e cv.yml; then \
		echo "cv.yml existe déjà : aucun fichier remplacé"; \
	else \
		cp cv.exemple.yml cv.yml; \
		echo "cv.yml créé depuis cv.exemple.yml"; \
	fi

init-en:
	@if test -e cv.en.yml; then \
		echo "cv.en.yml existe déjà : aucun fichier remplacé"; \
	else \
		cp cv.en.exemple.yml cv.en.yml; \
		echo "cv.en.yml créé depuis cv.en.exemple.yml"; \
	fi

$(VENV_PYTHON):
	python3 -m venv $(VENV)

$(VENV)/.requirements: requirements.txt $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@touch $@

install: $(VENV)/.requirements

install-browser: install
	$(VENV_PYTHON) -m playwright install --with-deps chromium

optimize-photo: install
	$(VENV_PYTHON) scripts/optimize_photo.py

build: optimize-photo
	$(PYTHON) scripts/build_cv.py

check: build
	PYTHON_BIN="$(PYTHON)" PDF_OUTPUT="$(PDF)" PDF_OUTPUT_EN="$(PDF_EN)" REQUIRE_BROWSER_CHECKS=1 ./scripts/check_cv.sh

update: check

sync:
	./scripts/sync_cv.sh

serve:
	$(PYTHON) -m http.server 8000

pdf: build
	$(PYTHON) scripts/browser_checks.py --pdf-output "$(PDF)"
