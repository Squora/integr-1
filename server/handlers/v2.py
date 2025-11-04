from models import BookV2, Author
from utils.idempotency import check_idempotency, store_idempotency

def handle_create_book_v2(db, data, idempotency_key):
    cached = check_idempotency(db, idempotency_key, "book_v2")
    if cached:
        return cached

    if not db.query(Author).filter(Author.id == data["author_id"]).first():
        return {"error": "Author not found"}

    if db.query(BookV2).filter(BookV2.isbn == data["isbn"]).first():
        return {"error": "Book with this ISBN already exists"}

    book = BookV2(**data)
    db.add(book)
    db.commit()
    db.refresh(book)
    response = {
        "id": book.id,
        "title": book.title,
        "author_id": book.author_id,
        "year": book.year,
        "isbn": book.isbn,
        "pages": book.pages,
        "genre": book.genre,
        "created_at": book.created_at.isoformat(),
        "updated_at": book.updated_at.isoformat() if book.updated_at else None
    }
    store_idempotency(db, idempotency_key, "book_v2", response)
    return response

def handle_get_books_v2(db, genre=None):
    q = db.query(BookV2)
    if genre:
        q = q.filter(BookV2.genre == genre)
    books = q.all()
    return [{
        "id": b.id,
        "title": b.title,
        "author_id": b.author_id,
        "year": b.year,
        "isbn": b.isbn,
        "pages": b.pages,
        "genre": b.genre,
        "created_at": b.created_at.isoformat(),
        "updated_at": b.updated_at.isoformat() if b.updated_at else None
    } for b in books]