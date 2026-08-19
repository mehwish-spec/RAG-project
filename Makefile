.PHONY: start start-ollama stop restart logs status reset clean

# One-command setup: build, start postgres+backend+frontend, run migrations.
start:
	./setup.sh

# Same, but also starts and provisions a local Ollama LLM.
start-ollama:
	./setup.sh --with-ollama

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f backend

status:
	docker compose ps

# Removes containers AND named volumes (database + uploaded files + ollama models).
reset:
	docker compose down -v

clean: reset
	docker compose rm -f
