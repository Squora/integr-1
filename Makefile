.PHONY: help build up down restart logs clean init-db migrate test

help:
	@echo "Доступные команды:"
	@echo "  make build      - Сборка Docker образов"
	@echo "  make up         - Запуск всех сервисов"
	@echo "  make down       - Остановка всех сервисов"
	@echo "  make restart    - Перезапуск сервисов"
	@echo "  make logs       - Просмотр логов"
	@echo "  make clean      - Очистка Docker volumes"
	@echo "  make init-db    - Инициализация БД с тестовыми данными"
	@echo "  make migrate    - Создание новой миграции"
	@echo "  make migrate-up - Применение миграций"
	@echo "  make test       - Запуск тестов"
	@echo "  make shell      - Зайти в контейнер API"
	@echo "  make db-shell   - Зайти в PostgreSQL"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Сервисы запущены!"
	@echo "API: http://localhost:8000"
	@echo "Документация: http://localhost:8000/docs"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	@echo "Volumes удалены"

init-db:
	docker-compose exec api python scripts/init_db.py

migrate:
	docker-compose exec api alembic revision --autogenerate -m "$(message)"

migrate-up:
	docker-compose exec api alembic upgrade head

migrate-down:
	docker-compose exec api alembic downgrade -1

test:
	docker-compose exec api pytest tests/ -v

shell:
	docker-compose exec api /bin/bash

db-shell:
	docker-compose exec db psql -U library_user -d library_db

# Быстрый старт
quickstart: build up
	@echo "Ожидание запуска БД..."
	@sleep 5
	@echo "Инициализация БД..."
	@make init-db
	@echo ""
	@echo "✓ Проект запущен!"
	@echo "API доступен по адресу: http://localhost:8000"
	@echo "Документация: http://localhost:8000/docs"
	@echo ""
	@echo "Данные для входа:"
	@echo "  Username: admin"
	@echo "  Password: admin123"
