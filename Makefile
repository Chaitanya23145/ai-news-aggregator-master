.PHONY: help install run api test docker-build docker-up clean

help:
	@echo "Available Make targets:"
	@echo "  make install       Install python requirements"
	@echo "  make run           Run daily news aggregation pipeline via CLI"
	@echo "  make api           Run FastAPI REST server and web dashboard"
	@echo "  make test          Run unit test suite"
	@echo "  make docker-build  Build production Docker image"
	@echo "  make docker-up     Start application & Postgres via Docker Compose"
	@echo "  make clean         Clean Python cache and temporary test files"

install:
	pip install -r requirements.txt

run:
	python main.py

api:
	uvicorn app.api:app --reload --port 8000

test:
	python -m unittest tests/test_pipeline.py

docker-build:
	docker build -t ai-news-aggregator:latest .

docker-up:
	docker compose up -d

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
