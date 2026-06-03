IMAGE_NAME   ?= flight-tracker
CONFIG_FILE  ?= config.json
PORT         ?= 8080
VENV         ?= .venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip

.PHONY: help install test test-docker run run-docker stop logs build build-test clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install       Create venv and install dependencies"
	@echo "  test          Run tests locally (auto-creates venv if needed)"
	@echo "  test-docker   Run tests inside Docker"
	@echo "  build         Build the production Docker image"
	@echo "  build-test    Build the test Docker image"
	@echo "  run           Run locally (requires AMADEUS_API_KEY, AMADEUS_API_SECRET, WEBHOOK_URL)"
	@echo "  run-docker    Run in Docker using $(CONFIG_FILE)"
	@echo "  stop          Stop and remove the running container"
	@echo "  logs          Tail logs from the running container"
	@echo "  clean         Remove venv and cached files"

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip

install: $(VENV)/bin/activate
	$(PIP) install --quiet -r requirements.txt pytest

test: install
	$(PYTHON) -m pytest test_flight_tracker.py -v

test-docker: build-test
	docker run --rm flight-tracker-test

build:
	docker build -t $(IMAGE_NAME) .

build-test:
	docker build -f Dockerfile.test -t flight-tracker-test .

run: install
	$(PYTHON) flight_tracker.py

run-docker: build
	docker run -d \
		-p $(PORT):8080 \
		-v $(PWD)/$(CONFIG_FILE):/app/config.json \
		--name $(IMAGE_NAME) \
		$(IMAGE_NAME)
	@echo "Flight Tracker running → http://localhost:$(PORT)/status"

stop:
	docker stop $(IMAGE_NAME) && docker rm $(IMAGE_NAME)

logs:
	docker logs -f $(IMAGE_NAME)

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache
