.PHONY: help install dev test cov lint format run run-dev analyze evaluate sanctions-update migrate docs-sync docker-build docker-up docker-down clean

help:
	@echo "install | dev | test | cov | lint | format | run | run-dev | analyze | evaluate | sanctions-update | migrate | docs-sync | docker-up | docker-down | clean"

install:            ## runtime install
	pip install .
dev:                ## editable install with test/lint tooling
	pip install -e ".[dev]"
test:
	pytest
cov:
	pytest --cov=sentinelai --cov-report=term-missing
lint:
	ruff check sentinelai tests migrations
format:
	ruff check --fix sentinelai tests migrations
run:
	sentinelai serve
run-dev:
	sentinelai serve --reload
analyze:            ## run the bundled demo scenarios through the deterministic engine
	sentinelai analyze --no-llm
evaluate:           ## regenerate documentation/BENCHMARK.md
	sentinelai evaluate --n 3000 --seed 7 --markdown documentation/BENCHMARK.md
sanctions-update:   ## download the official OFAC SDN list
	sentinelai sanctions update
migrate:
	alembic upgrade head
docs-sync:          ## rebuild the GitHub-Pages copy in docs/ from frontend/
	python scripts/sync_docs.py
docker-build:
	docker build -t sentinelai:latest .
docker-up:
	docker compose up -d
docker-down:
	docker compose down
clean:
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
