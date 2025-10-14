# Library Management REST API

Полнофункциональный REST API для управления библиотекой с поддержкой версионирования, аутентификации, идемпотентности и rate limiting.

## Описание предметной области

Система управления библиотекой позволяет:
- Управлять книгами (CRUD операции)
- Управлять авторами (V2)
- Аутентифицировать пользователей
- Контролировать частоту запросов

### Сущности

**Книга (V1):**
- `id`: Уникальный идентификатор
- `title`: Название
- `author`: Автор (строка)
- `year`: Год издания
- `isbn`: ISBN код
- `created_at`: Дата создания

**Книга (V2 - расширенная):**
- Все поля из V1
- `author_id`: ID автора (связь с таблицей авторов)
- `pages`: Количество страниц (опционально)
- `genre`: Жанр (опционально)
- `updated_at`: Дата последнего обновления

**Автор (только V2):**
- `id`: Уникальный идентификатор
- `name`: Имя автора
- `birth_year`: Год рождения (опционально)
- `country`: Страна (опционально)
- `created_at`: Дата создания

## Установка и запуск

### Требования

- Docker >= 20.10
- Docker Compose >= 2.0
- Git

### Быстрый старт (Docker)

#### 1. Клонирование репозитория

```bash
git clone <your-repository-url>
cd library-api
```

#### 2. Создание .env файла

```bash
cp .env.example .env
```

При необходимости отредактируйте `.env` файл:

```bash
nano .env
```

#### 3. Запуск проекта одной командой

```bash
make quickstart
```

Эта команда выполнит:
- Сборку Docker образов
- Запуск контейнеров (API + PostgreSQL)
- Инициализацию базы данных
- Создание тестовых данных

#### 4. Проверка работы

Откройте в браузере:
- **API**: http://localhost:8000
- **Swagger документация**: http://localhost:8000/docs
- **V1 документация**: http://localhost:8000/api/v1/docs
- **V2 документация**: http://localhost:8000/api/v2/docs

##  Детальная инструкция

### Структура проекта

```
library-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # Основной файл приложения
│   ├── database.py      # Конфигурация БД
│   └── models.py        # Модели SQLAlchemy
├── alembic/
│   ├── versions/        # Файлы миграций
│   └── env.py          # Конфигурация Alembic
├── scripts/
│   └── init_db.py      # Скрипт инициализации БД
├── docker-compose.yml   # Конфигурация Docker
├── Dockerfile          # Образ приложения
├── requirements.txt    # Python зависимости
├── alembic.ini        # Конфигурация Alembic
├── Makefile           # Команды для управления
├── .env.example       # Пример переменных окружения
└── README.md          # Документация
```

### Управление с помощью Makefile

```bash
# Просмотр всех доступных команд
make help

# Сборка образов
make build

# Запуск сервисов
make up

# Остановка сервисов
make down

# Перезапуск
make restart

# Просмотр логов
make logs

# Инициализация БД
make init-db

# Применение миграций
make migrate-up

# Создание новой миграции
make migrate message="название миграции"

# Запуск тестов
make test
```

## Документация API

После запуска сервера документация доступна по адресам:
- **Swagger UI (основная):** http://localhost:8000/docs
- **V1 документация:** http://localhost:8000/api/v1/docs
- **V2 документация:** http://localhost:8000/api/v2/docs
- **ReDoc:** http://localhost:8000/redoc

## Аутентификация

### Выбор метода: JWT (JSON Web Tokens)

**Обоснование выбора JWT:**

1. **Stateless архитектура** - токены не требуют хранения сессий на сервере
2. **Масштабируемость** - легко работает в распределенных системах
3. **Безопасность** - цифровая подпись предотвращает подделку токенов
4. **Стандартизация** - широкая поддержка в различных платформах
5. **Самодостаточность** - токен содержит всю необходимую информацию

**Альтернативные методы и почему они не выбраны:**

- **API Keys**: Проще, но менее безопасны и сложнее отозвать
- **OAuth 2.0**: Избыточен для внутреннего API, требует дополнительной инфраструктуры
- **Basic Auth**: Небезопасен без HTTPS, передает credentials с каждым запросом

### Получение токена

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Ответ:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Использование токена

Добавьте токен в заголовок `Authorization`:
```bash
curl -X GET "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Примеры запросов

### API Version 1

#### Создание книги
```bash
curl -X POST "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "title": "1984",
    "author": "George Orwell",
    "year": 1949,
    "isbn": "978-0-452-28423-4"
  }'
```

#### Получение всех книг
```bash
curl -X GET "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Получение книги по ID
```bash
curl -X GET "http://localhost:8000/api/v1/books/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Обновление книги
```bash
curl -X PUT "http://localhost:8000/api/v1/books/1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "1984 (Updated)",
    "author": "George Orwell",
    "year": 1949,
    "isbn": "978-0-452-28423-4"
  }'
```

#### Удаление книги
```bash
curl -X DELETE "http://localhost:8000/api/v1/books/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### API Version 2

#### Создание автора
```bash
curl -X POST "http://localhost:8000/api/v2/authors" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: author-key-456" \
  -d '{
    "name": "George Orwell",
    "birth_year": 1903,
    "country": "United Kingdom"
  }'
```

#### Создание книги с новыми полями
```bash
curl -X POST "http://localhost:8000/api/v2/books" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: book-v2-key-789" \
  -d '{
    "title": "1984",
    "author_id": 1,
    "year": 1949,
    "isbn": "978-0-452-28423-4",
    "pages": 328,
    "genre": "Dystopian Fiction"
  }'
```

#### Получение книг с фильтрацией
```bash
curl -X GET "http://localhost:8000/api/v2/books?genre=Dystopian%20Fiction" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Версионность API

### V1 → V2: Аддитивные изменения

**Добавленные возможности в V2:**
1. Новая сущность "Автор" с CRUD операциями
2. Поле `pages` (количество страниц) - опциональное
3. Поле `genre` (жанр) - опциональное
4. Поле `updated_at` для отслеживания изменений
5. Связь книга-автор через `author_id` вместо строки
6. Фильтрация книг по жанру

**Принципы версионирования:**
- **Обратная совместимость**: V1 продолжает работать без изменений
- **URL-based versioning**: `/api/v1/` и `/api/v2/`
- **Независимые схемы данных**: каждая версия имеет свои модели
- **Раздельная документация**: каждая версия документирована отдельно

### Что считается "ломающим" изменением (Breaking Changes)

**Следует избегать:**
- Удаление существующих полей
- Изменение типов данных полей
- Изменение формата ответов
- Удаление эндпоинтов
- Изменение семантики существующих операций
- Обязательные новые поля в запросах

**Безопасные изменения:**
- Добавление новых эндпоинтов
- Добавление опциональных полей
- Добавление новых query параметров
- Улучшение производительности
- Исправление багов

## Идемпотентность

### Поддержка идемпотентности для POST запросов

API поддерживает заголовок `Idempotency-Key` для операций создания ресурсов.

**Принцип работы:**
1. Клиент отправляет POST запрос с уникальным `Idempotency-Key`
2. Сервер создает ресурс и сохраняет ответ вместе с ключом
3. При повторном запросе с тем же ключом (в течение 24 часов) возвращается сохраненный ответ
4. Новый ресурс НЕ создается

**Пример:**
```bash
# Первый запрос - создает книгу
curl -X POST "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Idempotency-Key: my-unique-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Book", "author": "Test Author", "year": 2024, "isbn": "123"}'

# Повторный запрос с тем же ключом - возвращает ТУ ЖЕ книгу
curl -X POST "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Idempotency-Key: my-unique-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"title": "Different Book", "author": "Different", "year": 2024, "isbn": "456"}'
```

**Идемпотентность по умолчанию:**
- **GET** - безопасный, идемпотентный
- **PUT** - идемпотентный (многократное обновление дает тот же результат)
- **DELETE** - идемпотентный (повторное удаление не меняет состояние)
- **POST** - требует явного ключа идемпотентности

## Ограничение частоты запросов (Rate Limiting)

### Настройки
- **Лимит:** 10 запросов на IP-адрес
- **Окно:** 60 секунд
- **Алгоритм:** Sliding window

### Заголовки ответа

Каждый ответ содержит заголовок:
```
X-Limit-Remaining: 7
```

При превышении лимита (429 Too Many Requests):
```
X-Limit-Remaining: 0
Retry-After: 45
```

### Пример превышения лимита

```bash
# После 10 запросов за минуту
HTTP/1.1 429 Too Many Requests
X-Limit-Remaining: 0
Retry-After: 45

{
  "detail": "Rate limit exceeded"
}
```

### Рекомендации
- Отслеживайте заголовок `X-Limit-Remaining`
- Реализуйте exponential backoff при получении 429
- Распределяйте запросы во времени
- Кэшируйте часто запрашиваемые данные

## Архитектура и дизайн

### REST принципы
**Ресурсо-ориентированный дизайн:**
- `/books` - коллекция книг
- `/books/{id}` - конкретная книга
- `/authors` - коллекция авторов

**HTTP методы:**
- `GET` - получение данных
- `POST` - создание ресурса
- `PUT` - полное обновление
- `DELETE` - удаление

**HTTP статус коды:**
- `200` - успешный запрос
- `201` - ресурс создан
- `204` - успешно, нет содержимого
- `400` - некорректный запрос
- `401` - не авторизован
- `404` - ресурс не найден
- `429` - превышен лимит запросов

### Именование эндпоинтов

**Правила:**
1. Использовать существительные во множественном числе
2. Избегать глаголов в URL
3. Использовать kebab-case для составных слов
4. Логичная вложенность ресурсов

**Примеры:**
- `GET /api/v1/books`
- `POST /api/v2/authors`
- `GET /api/v1/getBooks`
- `POST /api/v1/createBook`

## Структура проекта

```
library-api/
├── main.py              # Основной файл приложения
├── requirements.txt     # Зависимости Python
├── README.md           # Документация
├── .gitignore          # Игнорируемые файлы
└── tests/              # Тесты (опционально)
    └── test_api.py
```

## 🧪 Тестирование API

### Использование curl

```bash
# Получить токен
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# Использовать токен
curl -X GET "http://localhost:8000/api/v1/books" \
  -H "Authorization: Bearer $TOKEN"
```

### Использование Python requests

```python
import requests

# Аутентификация
response = requests.post(
    "http://localhost:8000/auth/login",
    json={"username": "admin", "password": "admin123"}
)
token = response.json()["access_token"]

# Запрос с токеном
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/v1/books",
    headers=headers
)
print(response.json())
```

### Тестирование идемпотентности

```python
import requests
import uuid

token = "YOUR_TOKEN"
headers = {
    "Authorization": f"Bearer {token}",
    "Idempotency-Key": str(uuid.uuid4())
}

# Первый запрос
response1 = requests.post(
    "http://localhost:8000/api/v1/books",
    headers=headers,
    json={
        "title": "Test Book",
        "author": "Test Author",
        "year": 2024,
        "isbn": "123456"
    }
)

# Второй запрос с тем же ключом
response2 = requests.post(
    "http://localhost:8000/api/v1/books",
    headers=headers,
    json={
        "title": "Different Title",
        "author": "Different Author",
        "year": 2024,
        "isbn": "789012"
    }
)

# Должны вернуть одинаковые данные
assert response1.json() == response2.json()
```

## Безопасность

### Реализованные меры

1. **JWT аутентификация** - защита всех эндпоинтов
2. **Password hashing** - SHA-256 хеширование паролей
3. **Token expiration** - токены истекают через 30 минут
4. **Rate limiting** - защита от DDoS атак
5. **Input validation** - Pydantic модели валидируют входные данные

### Рекомендации для production

1. Использовать HTTPS
2. Изменить `SECRET_KEY` на безопасный случайный ключ
3. Использовать более стойкий алгоритм хеширования (bcrypt, argon2)
4. Настроить CORS для конкретных доменов
5. Использовать базу данных вместо in-memory хранилища
6. Добавить логирование и мониторинг
7. Настроить refresh tokens для длительных сессий

## Масштабирование

### Текущие ограничения
- In-memory хранилище (данные теряются при перезапуске)
- Single-threaded rate limiting
- Нет персистентного хранения токенов

### Рекомендации для production

1. **База данных:**
   - PostgreSQL для реляционных данных
   - Redis для кеширования и rate limiting

2. **Архитектура:**
   - Разделение API на микросервисы
   - Load balancer для распределения нагрузки
   - Горизонтальное масштабирование

3. **Мониторинг:**
   - Prometheus для метрик
   - Grafana для визуализации
   - ELK stack для логов

## Выводы

### Достижения проекта
**Хороший API:**
- Простая и предсказуемая структура
- Осмысленные имена эндпоинтов
- Полная документация (OpenAPI/Swagger)
- Валидация данных через Pydantic

**Стабильность:**
- Версионирование API (v1, v2)
- Обратная совместимость
- Аддитивные изменения без breaking changes

**Безопасность:**
- JWT аутентификация
- Rate limiting
- Input validation

**Надежность:**
- Идемпотентность POST операций
- Правильные HTTP статус коды
- Обработка ошибок

### Изученные концепции

1. **REST принципы** - ресурсо-ориентированный дизайн
2. **API Versioning** - поддержка множественных версий
3. **Authentication** - JWT токены
4. **Idempotency** - защита от дублирования операций
5. **Rate Limiting** - контроль нагрузки
6. **Documentation** - автоматическая генерация через OpenAPI

### Возможные улучшения

1. Добавить пагинацию для списков
2. Реализовать поиск и фильтрацию
3. Добавить PATCH для частичного обновления
4. Реализовать HATEOAS
5. Добавить GraphQL эндпоинт
6. Улучшить обработку ошибок (кастомные коды)
7. Добавить WebSocket для real-time уведомлений
8. Реализовать кеширование (ETags, Cache-Control)

## Полезные ссылки

- **Документация:** http://localhost:8000/docs
- **Swagger UI:** http://localhost:8000/api/v1/docs и /api/v2/docs
- **Health Check:** http://localhost:8000/health
