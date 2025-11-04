from models import BookV1
from utils.idempotency import check_idempotency, store_idempotency

def handle_create_book(db, data, idempotency_key):
    cached = check_idempotency(db, idempotency_key, "book_v1")
    if cached:
        return cached

    existing = db.query(BookV1).filter(BookV1.isbn == data["isbn"]).first()
    if existing:
        return {"error": "Book with this ISBN already exists"}

    book = BookV1(**data)
    db.add(book)
    db.commit()
    db.refresh(book)
    response = {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "created_at": book.created_at.isoformat()
    }
    store_idempotency(db, idempotency_key, "book_v1", response)
    return response

def handle_get_books(db):
    books = db.query(BookV1).all()
    return [{
        "id": b.id,
        "title": b.title,
        "author": b.author,
        "year": b.year,
        "isbn": b.isbn,
        "created_at": b.created_at.isoformat()
    } for b in books]

def handle_get_book(db, book_id):
    book = db.query(BookV1).filter(BookV1.id == book_id).first()
    if not book:
        return {"error": "Book not found"}
    return {
        "id": book.id, "title": book.title, "author": book.author,
        "year": book.year, "isbn": book.isbn, "created_at": book.created_at
    }

def handle_update_book(db, book_id, data):
    book = db.query(BookV1).filter(BookV1.id == book_id).first()
    if not book:
        return {"error": "Book not found"}
    for k, v in data.items():
        setattr(book, k, v)
    db.commit()
    db.refresh(book)
    return {
        "id": book.id, "title": book.title, "author": book.author,
        "year": book.year, "isbn": book.isbn, "created_at": book.created_at
    }

def handle_delete_book(db, book_id):
    book = db.query(BookV1).filter(BookV1.id == book_id).first()
    if not book:
        return {"error": "Book not found"}
    db.delete(book)
    db.commit()
    return {"status": "deleted"}