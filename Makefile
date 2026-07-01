.PHONY: help api frontend dev test fmt lint clean

help:
	@echo "make api       - run FastAPI dev server"
	@echo "make frontend  - run Next.js dev server"
	@echo "make dev       - api + frontend in parallel"
	@echo "make test      - run pytest"
	@echo "make fmt       - ruff format"
	@echo "make lint      - ruff check"
	@echo "make clean     - clear caches"

api:
	uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) api & $(MAKE) frontend & wait

test:
	uv run pytest -v

fmt:
	uv run ruff format src tests scripts

lint:
	uv run ruff check src tests scripts

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf frontend/.next
