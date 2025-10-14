from fastapi import FastAPI, Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
import jwt
import json
import time
from pydantic import BaseModel, Field
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

from app.database import get_db
from app import models

load_dotenv()

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# Pydantic модели для V1
class BookV1Create(BaseModel):
    title: str = Field(..., description="Название книги")
    author: str = Field(..., description="Автор книги")
    year: int = Field(..., description="Год издания")
    isbn: str = Field(..., description="ISBN книги")

class BookV1Response(BookV1Create):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Pydantic модели для V2
class BookV2Create(BaseModel):
    title: str = Field(..., description="Название книги")
    author_id: int = Field(..., description="ID автора")
    year: int = Field(..., description="Год издания")
    isbn: str = Field(..., description="ISBN книги")
    pages: Optional[int] = Field(None, description="Количество страниц")
    genre: Optional[str] = Field(None, description="Жанр книги")

class BookV2Response(BookV2Create):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AuthorCreate(BaseModel):
    name: str = Field(..., description="Имя автора")
    birth_year: Optional[int] = Field(None, description="Год рождения")
    country: Optional[str] = Field(None, description="Страна")

class AuthorResponse(AuthorCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Создание приложений
app = FastAPI(
    title="Library Management API",
    description="REST API для управления библиотекой с поддержкой версионирования",
    version="2.0.0"
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

# Middleware для rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = datetime.utcnow()
    
    # Получаем сессию БД
    db = next(get_db())
    
    try:
        # Очистка старых записей
        old_time = current_time - timedelta(seconds=RATE_LIMIT_WINDOW)
        db.query(models.RateLimit).filter(
            models.RateLimit.client_ip == client_ip,
            models.RateLimit.request_time < old_time
        ).delete()
        
        # Подсчет текущих запросов
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
        
        # Добавление текущего запроса
        rate_limit = models.RateLimit(
            client_ip=client_ip,
            request_time=current_time,
            endpoint=str(request.url)
        )
        db.add(rate_limit)
        db.commit()
        
        response = await call_next(request)
        
        # Добавление заголовков rate limit
        remaining = RATE_LIMIT_REQUESTS - request_count - 1
        response.headers["X-Limit-Remaining"] = str(remaining)
        
        return response
        
    finally:
        db.close()

# Функции аутентификации
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
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

# Функции идемпотентности
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
        # Проверка времени жизни (24 часа)
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
        # Преобразуем datetime объекты в строки
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

# Эндпоинт аутентификации
@app.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(user: UserLogin, db: Session = Depends(get_db)):
    """Аутентификация пользователя с использованием JWT токенов."""
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# =========================
# API Version 1
# =========================

@app_v1.post("/books", response_model=BookV1Response, status_code=201, tags=["Books V1"])
async def create_book_v1(
    book: BookV1Create,
    user: models.User = Depends(verify_token),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """Создание новой книги (версия 1) с поддержкой идемпотентности."""
    # Проверка идемпотентности
    cached_response = check_idempotency(idempotency_key, "book_v1", db)
    if cached_response:
        return cached_response
    
    # Проверка уникальности ISBN
    existing = db.query(models.BookV1).filter(models.BookV1.isbn == book.isbn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    db_book = models.BookV1(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    
    response = BookV1Response.from_orm(db_book).dict()
    store_idempotency(idempotency_key, "book_v1", response, db)
    
    return db_book

@app_v1.get("/books", response_model=List[BookV1Response], tags=["Books V1"])
async def get_books_v1(
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Получение списка всех книг (версия 1)."""
    books = db.query(models.BookV1).all()
    return books

@app_v1.get("/books/{book_id}", response_model=BookV1Response, tags=["Books V1"])
async def get_book_v1(
    book_id: int,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Получение книги по ID (версия 1)."""
    book = db.query(models.BookV1).filter(models.BookV1.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@app_v1.put("/books/{book_id}", response_model=BookV1Response, tags=["Books V1"])
async def update_book_v1(
    book_id: int,
    book: BookV1Create,
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

# =========================
# API Version 2
# =========================

@app_v2.post("/authors", response_model=AuthorResponse, status_code=201, tags=["Authors V2"])
async def create_author(
    author: AuthorCreate,
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
    
    response = AuthorResponse.from_orm(db_author).dict()
    store_idempotency(idempotency_key, "author", response, db)
    
    return db_author

@app_v2.get("/authors", response_model=List[AuthorResponse], tags=["Authors V2"])
async def get_authors(
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Получение списка всех авторов."""
    authors = db.query(models.Author).all()
    return authors

@app_v2.get("/authors/{author_id}", response_model=AuthorResponse, tags=["Authors V2"])
async def get_author(
    author_id: int,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Получение автора по ID."""
    author = db.query(models.Author).filter(models.Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author

@app_v2.post("/books", response_model=BookV2Response, status_code=201, tags=["Books V2"])
async def create_book_v2(
    book: BookV2Create,
    user: models.User = Depends(verify_token),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """Создание новой книги (версия 2) с расширенными полями."""
    cached_response = check_idempotency(idempotency_key, "book_v2", db)
    if cached_response:
        return cached_response
    
    # Проверка существования автора
    author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
    if not author:
        raise HTTPException(status_code=400, detail="Author not found")
    
    # Проверка уникальности ISBN
    existing = db.query(models.BookV2).filter(models.BookV2.isbn == book.isbn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    db_book = models.BookV2(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    
    response = BookV2Response.from_orm(db_book).dict()
    store_idempotency(idempotency_key, "book_v2", response, db)
    
    return db_book

@app_v2.get("/books", response_model=List[BookV2Response], tags=["Books V2"])
async def get_books_v2(
    user: models.User = Depends(verify_token),
    genre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получение списка всех книг (версия 2) с фильтрацией по жанру."""
    query = db.query(models.BookV2)
    if genre:
        query = query.filter(models.BookV2.genre == genre)
    books = query.all()
    return books

@app_v2.get("/books/{book_id}", response_model=BookV2Response, tags=["Books V2"])
async def get_book_v2(
    book_id: int,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Получение книги по ID (версия 2)."""
    book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@app_v2.put("/books/{book_id}", response_model=BookV2Response, tags=["Books V2"])
async def update_book_v2(
    book_id: int,
    book: BookV2Create,
    user: models.User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Обновление книги (версия 2). Идемпотентная операция."""
    db_book = db.query(models.BookV2).filter(models.BookV2.id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Проверка существования автора
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

# Монтирование версий API
app.mount("/api/v1", app_v1)
app.mount("/api/v2", app_v2)

@app.get("/", tags=["Root"])
async def root():
    """Корневой эндпоинт с информацией о доступных версиях API."""
    return {
        "message": "Library Management API",
        "versions": {
            "v1": "/api/v1/docs",
            "v2": "/api/v2/docs"
        },
        "authentication": "/auth/login",
        "documentation": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Проверка здоровья API и подключения к БД."""
    try:
        # Проверка подключения к БД
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
