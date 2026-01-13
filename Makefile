COMPOSE_DEV = docker-compose -f docker-compose.dev.yml

.PHONY: up down build restart logs ps shell-backend shell-frontend migrate test clean help run-backend

help:
	@echo "Доступные команды:"
	@echo "  make up             - Запустить все сервисы в фоновом режиме"
	@echo "  make down           - Остановить и удалить все контейнеры"
	@echo "  make build          - Собрать или пересобрать сервисы"
	@echo "  make restart        - Перезапустить все сервисы"
	@echo "  make logs           - Просмотр логов (всех или конкретного сервиса, например: make logs s=backend)"
	@echo "  make ps             - Статус запущенных контейнеров"
	@echo "  make shell-backend  - Зайти в терминал контейнера бэкенда"
	@echo "  make shell-frontend - Зайти в терминал контейнера фронтенда"
	@echo "  make migrate        - Применить миграции базы данных"
	@echo "  make test           - Запустить тесты бэкенда"
	@echo "  make run-backend    - Запустить бэкенд локально (без Docker)"
	@echo "  make clean          - Удалить неиспользуемые Docker ресурсы"

up:
	$(COMPOSE_DEV) up -d

down:
	$(COMPOSE_DEV) down

build:
	$(COMPOSE_DEV) build

restart:
	$(COMPOSE_DEV) restart

logs:
	$(COMPOSE_DEV) logs -f $(s)

ps:
	$(COMPOSE_DEV) ps

shell-backend:
	$(COMPOSE_DEV) exec backend sh

shell-frontend:
	$(COMPOSE_DEV) exec frontend sh

migrate:
	$(COMPOSE_DEV) exec backend alembic upgrade head

test:
	$(COMPOSE_DEV) exec backend pytest

run-backend:
	@powershell -Command " \
		if (Get-Command uv -ErrorAction SilentlyContinue) { \
			Write-Host 'Using uv to run backend...'; \
			cd services/backend; uv run --active uvicorn app.main:app --reload; \
		} elseif (Test-Path 'services/backend/.venv') { \
			Write-Host 'Using local venv in services/backend/.venv'; \
			cd services/backend; .\.venv\Scripts\uvicorn app.main:app --reload; \
		} elseif (Test-Path '.venv') { \
			Write-Host 'Using shared venv in .venv'; \
			cd services/backend; ..\..\.venv\Scripts\uvicorn app.main:app --reload; \
		} else { \
			Write-Host 'uv not found and no virtual environment found in services/backend/.venv or .venv.'; \
			Write-Host 'Please install uv or create a virtual environment.'; \
			exit 1; \
		}"

clean:
	docker system prune -f