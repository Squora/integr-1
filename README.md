# **Library Management API через RabbitMQ (Асинхронный обмен сообщениями)**

Полнофункциональная **асинхронная интеграционная система** для управления библиотекой с использованием **RabbitMQ** как шины сообщений.  
Поддерживает **версионирование**, **идемпотентность**, **аутентификацию**, **обработку ошибок**, **DLQ** и **масштабируемость**.

---

## Цель работы

- Изучить подход к проектированию **асинхронного API** через обмен сообщениями.
- Научиться использовать **RabbitMQ** как шину взаимодействия между клиентом и сервером.
- Реализовать **надёжность**, **масштабируемость** и **устойчивость к сбоям**.

> **Важно:**  
> Данная лабораторная повторяет логику **лабораторной №1 (REST API)** — те же сущности, операции и структура.  
> **Разница:** вместо HTTP используется **RabbitMQ + `aio-pika`**.

---

## Архитектура

```
[Клиент] 
   │
   ├──→ [api.requests] → [Сервер] → [PostgreSQL]
   │                         │
   │                         └──→ [Idempotency Keys]
   │
   └──← [amq.gen-...] ← [reply_to] ← [Сервер]
```

- **Очереди:**
  - `api.requests` — входящие запросы
  - `amq.gen-*` — временные `reply_to` очереди клиента (exclusive)
  - `api.dlq` — Dead Letter Queue для необработанных сообщений

---

## Установка и запуск

### Требования

- Docker >= 20.10
- Docker Compose >= 2.0

### Быстрый старт

```bash
git clone <your-repo>
cd lab4
docker compose up -d --build
```

Сервисы:
- `rabbitmq` — брокер сообщений
- `postgres` — БД
- `server` — обработчик сообщений
- `client` — демонстрация вызовов

---

## Структура проекта

```
lab4/
├── server/
│   ├── main.py              # Асинхронный обработчик RabbitMQ
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py          # Base = declarative_base()
│   │   └── entities.py      # BookV1, BookV2, Author, User, IdempotencyKey
│   ├── handlers/
│   │   ├── v1.py            # CRUD для BookV1
│   │   ├── v2.py            # CRUD для BookV2 + Author
│   │   └── auth.py          # login
│   └── utils/
│       ├── db.py            # get_db(), Base.metadata.create_all
│       ├── auth.py          # verify_api_key
│       └── idempotency.py   # check/store idempotency
├── client/
│   ├── client.py            # AsyncAPIClient (reply_to + correlation_id)
│   └── examples.py          # Демо: создание, фильтрация, идемпотентность
├── docker-compose.yml
├── .env
└── README.md
```

---

## Формат сообщений

### Запрос

```json
{
  "id": "uuid",
  "version": "v1",
  "action": "create_book",
  "data": { ... },
  "auth": "supersecretapikey",
  "idempotency_key": "create-1984-v1"
}
```

### Ответ (в `reply_to` очередь)

```json
{
  "correlation_id": "uuid",
  "status": "ok",
  "data": { ... },
  "error": null
}
```

---

## Аутентификация

### Метод: **API Key**

```json
"auth": "supersecretapikey"
```

**Обоснование:**
- Простота реализации
- Подходит для внутренних систем
- Легко отзывать (смена ключа)
- Не требует хранения сессий

> В production: использовать **JWT в `data.auth_token`**

---

## Идемпотентность

- Реализовано через таблицу `idempotency_keys`
- Ключ: `idempotency_key` + `resource_type` (`book_v1`, `book_v2`)
- При повторном запросе — **возвращается кэшированный ответ**
- Хранение: **PostgreSQL**

```python
check_idempotency(db, key, "book_v1") → cached_response or None
store_idempotency(db, key, "book_v1", response)
```

---

## Обработка ошибок и надёжность

| Механизм | Реализация |
|--------|-----------|
| **DLQ** | `api.dlq` с `x-dead-letter-routing-key: api.requests` |
| **Retry** | RabbitMQ автоматически переотправит из DLQ |
| **Requeue** | `message.process(requeue=True)` |
| **Логирование** | `logging.INFO` / `ERROR` |
| **Graceful shutdown** | `async with connection:` |

---

## Примеры запросов (через клиент)

```bash
docker compose run --rm client
```

### 1. Создание книги (v1)

```json
{
  "action": "create_book",
  "version": "v1",
  "data": {
    "title": "1984",
    "author": "George Orwell",
    "year": 1949,
    "isbn": "978-0451524935"
  },
  "idempotency_key": "create-1984-v1"
}
```

**Ответ:**
```json
{
  "status": "ok",
  "data": {
    "id": 1,
    "title": "1984",
    "created_at": "2025-11-04T18:34:37.371004"
  }
}
```

### 2. Идемпотентность

Повторный запрос с тем же `idempotency_key` → **тот же `id`**, **не создаётся дубликат**

### 3. Создание автора (v2)

```json
{
  "action": "create_author",
  "version": "v2",
  "data": {
    "name": "J.K. Rowling",
    "birth_year": 1965,
    "country": "UK"
  }
}
```

### 4. Фильтрация по жанру

```json
{
  "action": "get_books",
  "version": "v2",
  "data": { "genre": "Fantasy" }
}
```

---

## Схема обмена сообщениями

```
1. Клиент → publish(api.requests)
   ├─ correlation_id: uuid
   ├─ reply_to: amq.gen-...
   └─ body: { action, version, data, auth, idempotency_key }

2. Сервер → consume(api.requests)
   ├─ verify_api_key
   ├─ check_idempotency
   ├─ handle_* (db)
   ├─ store_idempotency
   └─ publish(reply_to)
       ├─ correlation_id
       └─ { status, data, error }

3. Клиент → consume(reply_to)
   └─ match by correlation_id
```

---

## Сравнение: RabbitMQ vs REST

| Критерий | REST (HTTP) | RabbitMQ (Async) |
|--------|------------|------------------|
| **Скорость** | Быстро (синхронно) | Медленнее (очереди) |
| **Надёжность** | Потеря при сбое | Гарантированная доставка |
| **Масштабируемость** | Вертикальная | Горизонтальная (очереди) |
| **Состояние** | Stateless | Stateful (очереди) |
| **Отказоустойчивость** | Зависит от клиента | DLQ, retry |
| **Сложность** | Низкая | Высокая |
| **Use Case** | Веб, мобильные | Интеграции, бэкенд |

---

## Запуск и проверка

```bash
# Запуск
docker compose up -d

# Логи сервера
docker compose logs -f server

# Запуск клиента (демо)
docker compose run --rm client
```

---

## Выводы

### Достижения

- Полностью **асинхронное API** через RabbitMQ
- **Идемпотентность** через БД
- **DLQ** + retry
- **reply_to** + **correlation_id**
- **Версионирование** (`v1`, `v2`)
- **Аутентификация** по API ключу
- **Фильтрация** по `genre`

### Изучено

1. `aio-pika` + `connect_robust`
2. `reply_to` + `correlation_id`
3. Dead Letter Queue
4. Идемпотентность в асинхронных системах
5. SQLAlchemy + async session
6. Docker Compose с несколькими сервисами

---
