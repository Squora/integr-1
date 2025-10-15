from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PaginationParams(BaseModel):
    """Параметры пагинации"""
    page: int = Field(1, ge=1, description="Номер страницы")
    page_size: int = Field(10, ge=1, le=100, description="Размер страницы (макс 100)")

class PaginatedResponse(BaseModel):
    """Обертка для пагинированных ответов"""
    items: List[dict]
    total: int = Field(..., description="Общее количество элементов")
    page: int = Field(..., description="Текущая страница")
    page_size: int = Field(..., description="Размер страницы")
    total_pages: int = Field(..., description="Всего страниц")
    has_next: bool = Field(..., description="Есть ли следующая страница")
    has_prev: bool = Field(..., description="Есть ли предыдущая страница")

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class AuthorBase(BaseModel):
    name: str = Field(..., description="Имя автора")
    birth_year: Optional[int] = Field(None, description="Год рождения")
    country: Optional[str] = Field(None, description="Страна")

class AuthorCreate(AuthorBase):
    pass

class AuthorResponse(AuthorBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class AuthorMinimal(BaseModel):
    """Минимальная информация об авторе для опциональных полей"""
    id: int
    name: str

    class Config:
        from_attributes = True

class BookV1Base(BaseModel):
    title: str = Field(..., description="Название книги")
    author: str = Field(..., description="Автор книги")
    year: int = Field(..., description="Год издания")
    isbn: str = Field(..., description="ISBN книги")

class BookV1Create(BookV1Base):
    pass

class BookV1Response(BookV1Base):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class BookV1Minimal(BaseModel):
    """Минимальная информация о книге V1"""
    id: int
    title: str
    author: str

    class Config:
        from_attributes = True

class BookV2Base(BaseModel):
    title: str = Field(..., description="Название книги")
    author_id: int = Field(..., description="ID автора")
    year: int = Field(..., description="Год издания")
    isbn: str = Field(..., description="ISBN книги")
    pages: Optional[int] = Field(None, description="Количество страниц")
    genre: Optional[str] = Field(None, description="Жанр книги")

class BookV2Create(BookV2Base):
    pass

class BookV2Response(BookV2Base):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BookV2Extended(BookV2Response):
    """Расширенная информация о книге с данными об авторе"""
    author: Optional[AuthorMinimal] = None

    class Config:
        from_attributes = True

class BookV2Minimal(BaseModel):
    """Минимальная информация о книге V2"""
    id: int
    title: str
    year: int

    class Config:
        from_attributes = True

class BulkDeleteRequest(BaseModel):
    """Запрос на массовое удаление (внутренний API)"""
    ids: List[int] = Field(..., description="Список ID для удаления")

class BulkDeleteResponse(BaseModel):
    """Ответ на массовое удаление"""
    deleted_count: int = Field(..., description="Количество удаленных записей")
    failed_ids: List[int] = Field(default_factory=list, description="ID, которые не удалось удалить")

class StatisticsResponse(BaseModel):
    """Статистика (внутренний API)"""
    total_books_v1: int
    total_books_v2: int
    total_authors: int
    total_users: int
    genres: List[dict]
    books_by_year: List[dict]

class SystemHealthResponse(BaseModel):
    """Расширенная информация о здоровье системы (внутренний API)"""
    status: str
    timestamp: datetime
    database: str
    versions: List[str]
    uptime: str
    rate_limit_records: int
    idempotency_records: int
