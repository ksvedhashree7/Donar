.PHONY: up seed test down

up:
	docker compose up --build -d

seed:
	@echo "Seed script not implemented in Phase 0 scaffold."

test:
	cd backend && python -m pytest

down:
	docker compose down -v
