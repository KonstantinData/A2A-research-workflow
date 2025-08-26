.PHONY: lint test build run

lint:
@echo "Lint placeholder"

test:
pytest

build:
docker build -t a2a-workflow -f ops/Dockerfile .

run:
python core/orchestrator.py
