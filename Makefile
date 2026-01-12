COMPOSE_DEV = docker-compose -f docker-compose.dev.yml

.PHONY: up down build restart logs ps shell-backend shell-frontend migrate test clean help

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

clean:
	docker system prune -f