.PHONY: dev prod down

dev:
	ENV=development docker compose up --build

prod:
	ENV=production docker compose up -d --build

down:
	docker compose down
