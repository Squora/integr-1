import sys
import os
import hashlib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal, Base
from app.models import User, Author, BookV1, BookV2
from datetime import datetime

def hash_password_simple(password: str) -> str:
    """Простое хеширование через SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_tables():
    """Создание всех таблиц"""
    print("Создание таблиц...")
    Base.metadata.create_all(bind=engine)
    print("✓ Таблицы созданы")

def create_admin_user(db):
    """Создание администратора"""
    print("Создание пользователя admin...")
    
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        print("! Пользователь admin уже существует")
        # Обновляем пароль на случай, если был старый
        admin.hashed_password = hash_password_simple("admin123")
        db.commit()
        print("✓ Пароль обновлен")
        return
    
    admin = User(
        username="admin",
        hashed_password=hash_password_simple("admin123"),
        role="admin"
    )
    db.add(admin)
    db.commit()
    print("✓ Пользователь admin создан (пароль: admin123)")

def seed_authors(db):
    """Наполнение таблицы авторов"""
    print("Добавление авторов...")
    
    authors_data = [
        {"name": "Лев Николаевич Толстой", "birth_year": 1828, "country": "Россия"},
        {"name": "Федор Михайлович Достоевский", "birth_year": 1821, "country": "Россия"},
        {"name": "Михаил Афанасьевич Булгаков", "birth_year": 1891, "country": "Россия"},
        {"name": "Антон Павлович Чехов", "birth_year": 1860, "country": "Россия"},
        {"name": "Александр Сергеевич Пушкин", "birth_year": 1799, "country": "Россия"},
        {"name": "George Orwell", "birth_year": 1903, "country": "United Kingdom"},
        {"name": "J.K. Rowling", "birth_year": 1965, "country": "United Kingdom"},
        {"name": "Ernest Hemingway", "birth_year": 1899, "country": "USA"},
    ]
    
    added = 0
    for author_data in authors_data:
        existing = db.query(Author).filter(Author.name == author_data["name"]).first()
        if not existing:
            author = Author(**author_data)
            db.add(author)
            added += 1
    
    db.commit()
    print(f"✓ Добавлено {added} новых авторов (всего: {len(authors_data)})")

def seed_books_v1(db):
    """Наполнение таблицы книг V1"""
    print("Добавление книг V1...")
    
    books_data = [
        {"title": "Война и мир", "author": "Лев Толстой", "year": 1869, "isbn": "978-5-17-098229-4"},
        {"title": "Анна Каренина", "author": "Лев Толстой", "year": 1877, "isbn": "978-5-17-982341-6"},
        {"title": "Преступление и наказание", "author": "Федор Достоевский", "year": 1866, "isbn": "978-5-389-01087-8"},
        {"title": "Братья Карамазовы", "author": "Федор Достоевский", "year": 1880, "isbn": "978-5-17-982342-3"},
        {"title": "Мастер и Маргарита", "author": "Михаил Булгаков", "year": 1967, "isbn": "978-5-17-982344-7"},
    ]
    
    added = 0
    for book_data in books_data:
        existing = db.query(BookV1).filter(BookV1.isbn == book_data["isbn"]).first()
        if not existing:
            book = BookV1(**book_data)
            db.add(book)
            added += 1
    
    db.commit()
    print(f"✓ Добавлено {added} новых книг V1 (всего: {len(books_data)})")

def seed_books_v2(db):
    """Наполнение таблицы книг V2"""
    print("Добавление книг V2...")
    
    authors = {
        "Толстой": db.query(Author).filter(Author.name.contains("Толстой")).first(),
        "Достоевский": db.query(Author).filter(Author.name.contains("Достоевский")).first(),
        "Булгаков": db.query(Author).filter(Author.name.contains("Булгаков")).first(),
        "Чехов": db.query(Author).filter(Author.name.contains("Чехов")).first(),
        "Пушкин": db.query(Author).filter(Author.name.contains("Пушкин")).first(),
        "Orwell": db.query(Author).filter(Author.name == "George Orwell").first(),
        "Rowling": db.query(Author).filter(Author.name == "J.K. Rowling").first(),
        "Hemingway": db.query(Author).filter(Author.name == "Ernest Hemingway").first(),
    }
    
    books_data = [
        {"title": "Война и мир", "author": "Толстой", "year": 1869, "isbn": "978-5-17-098230-0", "pages": 1274, "genre": "Исторический роман"},
        {"title": "Анна Каренина", "author": "Толстой", "year": 1877, "isbn": "978-5-17-098231-7", "pages": 864, "genre": "Роман"},
        {"title": "Преступление и наказание", "author": "Достоевский", "year": 1866, "isbn": "978-5-389-01088-5", "pages": 671, "genre": "Психологический роман"},
        {"title": "Идиот", "author": "Достоевский", "year": 1869, "isbn": "978-5-17-982345-4", "pages": 640, "genre": "Роман"},
        {"title": "Мастер и Маргарита", "author": "Булгаков", "year": 1967, "isbn": "978-5-17-982346-1", "pages": 480, "genre": "Фантастика"},
        {"title": "Собачье сердце", "author": "Булгаков", "year": 1925, "isbn": "978-5-17-982347-8", "pages": 352, "genre": "Сатира"},
        {"title": "Вишневый сад", "author": "Чехов", "year": 1904, "isbn": "978-5-17-982348-5", "pages": 128, "genre": "Пьеса"},
        {"title": "Евгений Онегин", "author": "Пушкин", "year": 1833, "isbn": "978-5-17-982349-2", "pages": 224, "genre": "Роман в стихах"},
        {"title": "1984", "author": "Orwell", "year": 1949, "isbn": "978-0-452-28423-4", "pages": 328, "genre": "Антиутопия"},
        {"title": "Animal Farm", "author": "Orwell", "year": 1945, "isbn": "978-0-452-28424-1", "pages": 144, "genre": "Сатира"},
        {"title": "Harry Potter and the Philosopher's Stone", "author": "Rowling", "year": 1997, "isbn": "978-0-439-70818-8", "pages": 223, "genre": "Фэнтези"},
        {"title": "The Old Man and the Sea", "author": "Hemingway", "year": 1952, "isbn": "978-0-684-80122-3", "pages": 127, "genre": "Повесть"},
    ]
    
    added = 0
    for book_data in books_data:
        author_key = book_data.pop("author")
        author = authors.get(author_key)
        
        if author:
            existing = db.query(BookV2).filter(BookV2.isbn == book_data["isbn"]).first()
            if not existing:
                book = BookV2(author_id=author.id, **book_data)
                db.add(book)
                added += 1
    
    db.commit()
    print(f"✓ Добавлено {added} новых книг V2 (всего: {len(books_data)})")

def main():
    """Основная функция"""
    print("\n" + "="*50)
    print("Инициализация базы данных Library API")
    print("="*50 + "\n")
    
    try:
        create_tables()
        
        db = SessionLocal()
        
        try:
            create_admin_user(db)
            
            seed_authors(db)
            seed_books_v1(db)
            seed_books_v2(db)
            
            print("\n" + "="*50)
            print("✓ Инициализация завершена успешно!")
            print("="*50)
            print("\nДанные для входа:")
            print("  Username: admin")
            print("  Password: admin123")
            print("\nAPI доступен по адресу: http://localhost:8000")
            print("Документация: http://localhost:8000/docs")
            print()
            
        except Exception as e:
            print(f"\n✗ Ошибка: {e}")
            db.rollback()
            raise
        finally:
            db.close()
            
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()