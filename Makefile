IMAGE_NAME   ?= flight-tracker
CONFIG_FILE  ?= config.json
PORT         ?= 8080

.PHONY: help install test test-docker run run-docker stop logs build build-test

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install       Install Python dependencies locally"
	@echo "  test          Run tests locally"
	@echo "  test-docker   Run tests inside Docker"
	@echo "  build         Build the production Docker image"
	@echo "  build-test    Build the test Docker image"
	@echo "  run           Run locally (requires AMADEUS_API_KEY, AMADEUS_API_SECRET, WEBHOOK_URL)"
	@echo "  run-docker    Run in Docker using $(CONFIG_FILE)"
	@echo "  stop          Stop and remove the running container"
	@echo "  logs          Tail logs from the running container"

install:
	pip install -r requirements.txt pytest

test:
	python -m pytest test_flight_tracker.py -v

test-docker: build-test
	docker run --rm flight-tracker-test

build:
	docker build -t $(IMAGE_NAME) .

build-test:
	docker build -f Dockerfile.test -t flight-tracker-test .

run:
	python flight_tracker.py

run-docker: build
	docker run -d \
		-p $(PORT):8080 \
		-v $(PWD)/$(CONFIG_FILE):/app/config.json:ro \
		--name $(IMAGE_NAME) \
		$(IMAGE_NAME)
	@echo "Flight Tracker running → http://localhost:$(PORT)/status"

stop:
	docker stop $(IMAGE_NAME) && docker rm $(IMAGE_NAME)

logs:
	docker logs -f $(IMAGE_NAME)
