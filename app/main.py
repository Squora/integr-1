from fastapi import FastAPI, Depends, HTTPException, Header, Request, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, List
import jwt
import json
import time
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

from app.database import get_db
from app import models, schemas

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "internal-secret-key-12345")

START_TIME = datetime.utcnow()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)

app = FastAPI(
    title="Library Management API",
    description="REST API для управления библиотекой с поддержкой версионирования, пагинации и опциональных полей",
    version="2.1.0"
)

app_v1 = FastAPI(
    title="Library API V1",
    description="Версия 1 API библиотеки",
    version="1.0.0"
)

app_v2 = FastAPI(
    title="Library API V2",
    description="Версия 2 API библиотеки (расширенная)",
    version="2.0.0"
)

app_internal = FastAPI(
    title="Library Internal API",
    description="Внутренний API для служебных операций",
    version="1.0.0"
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/internal"):
        return await call_next(request)
    
    client_ip = request.client.host
    current_time = datetime.utcnow()
    
    db = next(get_db())
    
    try:
        old_time = current_time - timedelta(seconds=RATE_LIMIT_WINDOW)
        db.query(models.RateLimit).filter(
            models.RateLimit.client_ip == client_ip,
            models.RateLimit.request_time < old_time
        ).delete()
        
        request_count = db.query(models.RateLimit).filter(
            models.RateLimit.client_ip == client_ip
        ).count()
        
        if request_count >= RATE_LIMIT_REQUESTS:
            oldest_request = db.query(models.RateLimit).filter(
                models.RateLimit.client_ip == client_ip
            ).order_by(models.RateLimit.request_time).first()
            
            retry_after = int(RATE_LIMIT_WINDOW - (current_time - oldest_request.request_time).total_seconds())
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-Limit-Remaining": "0",
                    "Retry-After": str(retry_after)
                }
            )
        
        rate_limit = models.RateLimit(
            client_ip=client_ip,
            request_time=current_time,
            endpoint=str(request.url.path)
        )
        db.add(rate_limit)
        db.commit()
        
        response = await call_next(request)
        
        remaining = RATE_LIMIT_REQUESTS - request_count - 1
        response.headers["X-Limit-Remaining"] = str(remaining)
        
        return response
        
    finally:
        db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_internal_api_key(api_key: str = Depends(api_key_header)):
    """Проверка ключа для внутреннего API"""
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing internal API key"
        )
    return True

def check_idempotency(
    idempotency_key: Optional[str],
    resource_type: str,
    db: Session
) -> Optional[dict]:
    if not idempotency_key:
        return None
    
    stored = db.query(models.IdempotencyKey).filter(
        models.IdempotencyKey.key == idempotency_key,
        models.IdempotencyKey.resource_type == resource_type
    ).first()
    
    if stored:
        if (datetime.utcnow() - stored.created_at).total_seconds() < 86400:
            return json.loads(stored.response_data)
        else:
            db.delete(stored)
            db.commit()
    
    return None

def store_idempotency(
    idempotency_key: str,
    resource_type: str,
    response: dict,
    db: Session
):
    if idempotency_key:
        response_copy = response.copy()
        for key, value in response_copy.items():
            if isinstance(value, datetime):
                response_copy[key] = value.isoformat()
        
        idempotency = models.IdempotencyKey(
            key=idempotency_key,
            resource_type=resource_type,
            response_data=json.dumps(response_copy)
        )
        db.add(idempotency)
        db.commit()

def create_paginated_response(
    items: List,
    total: int,
    page: int,
    page_size: int
) -> schemas.PaginatedResponse:
    """Создание пагинированного ответа"""
    total_pages = (total + page_size - 1) // page_size
    
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )

def filter_fields(obj, fields: Optional[str]):
    """Фильтрация полей объекта"""
    if not fields:
        return obj
    
    if isinstance(obj, dict):
        data = obj
    else:
        data = obj.dict() if hasattr(obj, 'dict') else obj.__dict__
    
    requested_fields = [f.strip() for f in fields.split(',')]
    return {k: v for k, v in data.items() if k in requested_fields}

@app.post("/auth/login", response_model=schemas.Token, tags=["Authentication"])
async def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Аутентификация пользователя с использованием JWT токенов.
    
    **Обоснование выбора JWT:**
    - Stateless архитектура
    - Масштабируемость
    - Безопасность (цифровая подпись)
    - Стандартизация
    """
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app_v1.post("/books", response_model=schemas.BookV1Response, status_code=201, tags=["Books V1"])
async def create_book_v1(
    book: schemas.BookV1Create,
    user: models.User = Depends(verify_token),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """Создание новой книги (версия 1) с поддержкой идемпотентности."""
    cached_response = check_idempotency(idempotency_key, "book_v1", db)
    if cached_response:
        return cached_response
    
    existing = db.query(models.BookV1).filter(models.BookV1.isbn == book.isbn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    db_book = models.BookV1(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    
    response = schemas.BookV1Response.from_orm(db_book).dict()
    store_idempotency(idempotency_key, "book_v1", response, db)
    
    return db_book

@app_v1.get("/books", tags=["Books V1"])
async def get_books_v1(
    user: models.User = Depends(verify_token),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(10, ge=1, le=100, description="Размер страницы"),
    fields: Optional[str] = Query(None, description="Список полей через запятую (id,title,author)"),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех книг (версия 1) с пагинацией и опциональными полями.
    
    **Пагинация**: Используется offset-based (page/page_size)
    **Обоснование**: Простота реализации, предсказуемость, подходит для небольших и средних наборов данных
    
    **Опциональные поля**: Параметр fields позволяет выбрать нужные поля
    **Пример**: ?fields=id,title,author
    """
    query = db.query(models.BookV1)
    total = query.count()
    
    offset = (page - 1) * page_size
    books = query.offset(offset).limit(page_size).all()
    
    if fields:
        items = [filter_fields(schemas.BookV1Response.from_orm(book), fields) for book in books]
    else:
        items = [schemas.BookV1Response.from_orm(book).dict() for book in books]
    
    return create_paginated_response(items, total, page, page_size)

@app_v1.get("/books/{book_id}", response_model=schemas.BookV1Response, tags=["Books V1"])
async def get_book_v1(
    book_id: int,
    user: models.User = Depends(verify_token),
    fields: Optional[str] = Query(None, description="Список полей через запятую"),
    db: Session = Depends(get_db)
):
    """Получение книги по ID (версия 1) с опциональными полями."""
    book = db.query(models.BookV1).filter(models.BookV1.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if fields:
        return filter_fields(schemas.BookV1Response.from_orm(book), fields)
    return book

@app_v1.put("/books/{book_id}", response_model=schemas.BookV1Response, tags=["Books V1"])
async def update_book_v1(
    book_id: int,
    book: schemas.BookV1Create,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Обновление книги (версия 1). Идемпотентная операция."""
    db_book = db.query(models.BookV1).filter(models.BookV1.id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    for key, value in book.dict().items():
        setattr(db_book, key, value)
    
    db.commit()
    db.refresh(db_book)
    return db_book

@app_v1.delete("/books/{book_id}", status_code=204, tags=["Books V1"])
async def delete_book_v1(
    book_id: int,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Удаление книги (версия 1). Идемпотентная операция."""
    db_book = db.query(models.BookV1).filter(models.BookV1.id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    db.delete(db_book)
    db.commit()
    return None

@app_v2.post("/authors", response_model=schemas.AuthorResponse, status_code=201, tags=["Authors V2"])
async def create_author(
    author: schemas.AuthorCreate,
    user: models.User = Depends(verify_token),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """Создание нового автора (только в версии 2)."""
    cached_response = check_idempotency(idempotency_key, "author", db)
    if cached_response:
        return cached_response
    
    db_author = models.Author(**author.dict())
    db.add(db_author)
    db.commit()
    db.refresh(db_author)
    
    response = schemas.AuthorResponse.from_orm(db_author).dict()
    store_idempotency(idempotency_key, "author", response, db)
    
    return db_author

@app_v2.get("/authors", tags=["Authors V2"])
async def get_authors(
    user: models.User = Depends(verify_token),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    fields: Optional[str] = Query(None, description="Опциональные поля"),
    db: Session = Depends(get_db)
):
    """Получение списка всех авторов с пагинацией."""
    query = db.query(models.Author)
    total = query.count()
    
    offset = (page - 1) * page_size
    authors = query.offset(offset).limit(page_size).all()
    
    if fields:
        items = [filter_fields(schemas.AuthorResponse.from_orm(author), fields) for author in authors]
    else:
        items = [schemas.AuthorResponse.from_orm(author).dict() for author in authors]
    
    return create_paginated_response(items, total, page, page_size)

@app_v2.get("/authors/{author_id}", response_model=schemas.AuthorResponse, tags=["Authors V2"])
async def get_author(
    author_id: int,
    user: models.User = Depends(verify_token),
    fields: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Получение автора по ID."""
    author = db.query(models.Author).filter(models.Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    if fields:
        return filter_fields(schemas.AuthorResponse.from_orm(author), fields)
    return author

@app_v2.post("/books", response_model=schemas.BookV2Response, status_code=201, tags=["Books V2"])
async def create_book_v2(
    book: schemas.BookV2Create,
    user: models.User = Depends(verify_token),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """Создание новой книги (версия 2) с расширенными полями."""
    cached_response = check_idempotency(idempotency_key, "book_v2", db)
    if cached_response:
        return cached_response
    
    author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
    if not author:
        raise HTTPException(status_code=400, detail="Author not found")
    
    existing = db.query(models.BookV2).filter(models.BookV2.isbn == book.isbn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    db_book = models.BookV2(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    
    response = schemas.BookV2Response.from_orm(db_book).dict()
    store_idempotency(idempotency_key, "book_v2", response, db)
    
    return db_book

@app_v2.get("/books", tags=["Books V2"])
async def get_books_v2(
    user: models.User = Depends(verify_token),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    genre: Optional[str] = Query(None),
    fields: Optional[str] = Query(None, description="Опциональные поля"),
    include_author: bool = Query(False, description="Включить информацию об авторе"),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех книг (версия 2) с пагинацией, фильтрацией и опциональными полями.
    
    **Опциональные поля:**
    - fields: выбор конкретных полей (id,title,year)
    - include_author: включение данных об авторе в ответ
    
    **Обоснование**: Позволяет клиентам получать только нужные данные, снижая объем трафика
    """
    query = db.query(models.BookV2)
    if genre:
        query = query.filter(models.BookV2.genre == genre)
    
    total = query.count()
    offset = (page - 1) * page_size
    books = query.offset(offset).limit(page_size).all()
    
    items = []
    for book in books:
        if include_author:
            book_dict = schemas.BookV2Extended.from_orm(book).dict()
            author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
            if author:
                book_dict['author'] = schemas.AuthorMinimal.from_orm(author).dict()
        else:
            book_dict = schemas.BookV2Response.from_orm(book).dict()
        
        if fields:
            book_dict = filter_fields(book_dict, fields)
        
        items.append(book_dict)
    
    return create_paginated_response(items, total, page, page_size)

@app_v2.get("/books/{book_id}", tags=["Books V2"])
async def get_book_v2(
    book_id: int,
    user: models.User = Depends(verify_token),
    fields: Optional[str] = Query(None),
    include_author: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Получение книги по ID (версия 2) с опциональными полями."""
    book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if include_author:
        book_dict = schemas.BookV2Extended.from_orm(book).dict()
        author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
        if author:
            book_dict['author'] = schemas.AuthorMinimal.from_orm(author).dict()
    else:
        book_dict = schemas.BookV2Response.from_orm(book).dict()
    
    if fields:
        return filter_fields(book_dict, fields)
    return book_dict

@app_v2.put("/books/{book_id}", response_model=schemas.BookV2Response, tags=["Books V2"])
async def update_book_v2(
    book_id: int,
    book: schemas.BookV2Create,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Обновление книги (версия 2). Идемпотентная операция."""
    db_book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
    if not author:
        raise HTTPException(status_code=400, detail="Author not found")
    
    for key, value in book.dict().items():
        setattr(db_book, key, value)
    
    db_book.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_book)
    return db_book

@app_v2.delete("/books/{book_id}", status_code=204, tags=["Books V2"])
async def delete_book_v2(
    book_id: int,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Удаление книги (версия 2). Идемпотентная операция."""
    db_book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    db.delete(db_book)
    db.commit()
    return None


@app_internal.post("/books/v2/bulk-delete", response_model=schemas.BulkDeleteResponse, tags=["Internal"])
async def bulk_delete_books(
    request: schemas.BulkDeleteRequest,
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    """
    Массовое удаление книг (внутренний API).
    
    **Почему внутренний:**
    - Потенциально опасная операция (массовое удаление)
    - Не требует детальной валидации и проверок
    - Используется внутренними сервисами для очистки данных
    - Упрощенная авторизация (API ключ вместо JWT)
    
    **Упрощения:**
    - Нет проверки прав конкретного пользователя
    - Нет подробного логирования каждого удаления
    - Не создает резервные копии
    """
    deleted_count = 0
    failed_ids = []
    
    for book_id in request.ids:
        book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
        if book:
            db.delete(book)
            deleted_count += 1
        else:
            failed_ids.append(book_id)
    
    db.commit()
    
    return schemas.BulkDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )

@app_internal.get("/statistics", response_model=schemas.StatisticsResponse, tags=["Internal"])
async def get_statistics(
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    """
    Получение статистики системы (внутренний API).
    
    **Почему внутренний:**
    - Содержит агрегированные данные для мониторинга
    - Может быть ресурсоемким при больших объемах данных
    - Используется для дашбордов и аналитики
    - Не требует пользовательской аутентификации
    """
    total_books_v1 = db.query(models.BookV1).count()
    total_books_v2 = db.query(models.BookV2).count()
    total_authors = db.query(models.Author).count()
    total_users = db.query(models.User).count()
    
    genres = db.query(
        models.BookV2.genre,
        func.count(models.BookV2.id).label('count')
    ).group_by(models.BookV2.genre).all()
    
    genres_list = [{"genre": g[0] or "Unknown", "count": g[1]} for g in genres]
    
    books_by_year = db.query(
        models.BookV2.year,
        func.count(models.BookV2.id).label('count')
    ).group_by(models.BookV2.year).order_by(models.BookV2.year.desc()).limit(10).all()
    
    books_by_year_list = [{"year": y[0], "count": y[1]} for y in books_by_year]
    
    return schemas.StatisticsResponse(
        total_books_v1=total_books_v1,
        total_books_v2=total_books_v2,
        total_authors=total_authors,
        total_users=total_users,
        genres=genres_list,
        books_by_year=books_by_year_list
    )

@app_internal.get("/health/detailed", response_model=schemas.SystemHealthResponse, tags=["Internal"])
async def detailed_health_check(
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    """
    Расширенная проверка здоровья системы (внутренний API).
    
    **Почему внутренний:**
    - Содержит детальную информацию о системе
    - Может раскрывать внутреннюю архитектуру
    - Используется для мониторинга и алертинга
    """
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    uptime = datetime.utcnow() - START_TIME
    uptime_str = str(uptime).split('.')[0]
    
    rate_limit_count = db.query(models.RateLimit).count()
    idempotency_count = db.query(models.IdempotencyKey).count()
    
    return schemas.SystemHealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        database=db_status,
        versions=["v1", "v2"],
        uptime=uptime_str,
        rate_limit_records=rate_limit_count,
        idempotency_records=idempotency_count
    )

@app_internal.delete("/cleanup/old-records", tags=["Internal"])
async def cleanup_old_records(
    _: bool = Depends(verify_internal_api_key),
    days: int = Query(7, ge=1, description="Удалить записи старше N дней"),
    db: Session = Depends(get_db)
):
    """
    Очистка старых служебных записей (внутренний API).
    
    **Почему внутренний:**
    - Техническая операция обслуживания
    - Не связана с бизнес-логикой
    - Может влиять на производительность
    """
    old_date = datetime.utcnow() - timedelta(days=days)
    
    rate_limit_deleted = db.query(models.RateLimit).filter(
        models.RateLimit.request_time < old_date
    ).delete()
    
    idempotency_deleted = db.query(models.IdempotencyKey).filter(
        models.IdempotencyKey.created_at < old_date
    ).delete()
    
    db.commit()
    
    return {
        "message": "Cleanup completed",
        "rate_limit_deleted": rate_limit_deleted,
        "idempotency_deleted": idempotency_deleted,
        "older_than_days": days
    }

app.mount("/api/v1", app_v1)
app.mount("/api/v2", app_v2)
app.mount("/internal", app_internal)

@app.get("/", tags=["Root"])
async def root():
    """Корневой эндпоинт с информацией о доступных версиях API."""
    return {
        "message": "Library Management API v2.1.0",
        "versions": {
            "v1": "/api/v1/docs",
            "v2": "/api/v2/docs"
        },
        "authentication": "/auth/login",
        "documentation": "/docs",
        "internal_api": "/internal/docs (requires X-Internal-API-Key header)",
        "features": [
            "JWT Authentication",
            "Rate Limiting",
            "Idempotency",
            "Pagination",
            "Optional Fields",
            "Internal API"
        ]
    }

@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Базовая проверка здоровья API (публичный эндпоинт)."""
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "versions": ["v1", "v2"]
    }
