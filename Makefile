.PHONY: up down logs test test-known lint

up:
	docker compose up --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f

test:
	pytest -m "not acceptance and not integration" -q

test-known:
	pytest -m "acceptance or integration" -q -rxX

lint:
	python -m compileall -q tickets-api event-service slow-classification-service tests

