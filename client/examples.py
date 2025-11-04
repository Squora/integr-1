# lab4/client/examples.py
import asyncio
from client import AsyncAPIClient

API_KEY = "supersecretapikey"


async def main():
    client = AsyncAPIClient()
    await client.connect()

    try:
        # === 1. Создание книги v1 ===
        print("\n" + "="*60)
        print("1. Создание книги (v1) — с идемпотентностью")
        print("="*60)

        resp = await client.call(
            action="create_book",
            version="v1",  # ← "v1", не "1"
            data={
                "title": "1984",
                "author": "George Orwell",
                "year": 1949,
                "isbn": "978-0451524935"
            },
            auth=API_KEY,
            idempotency_key="create-1984-v1"
        )
        print("Ответ:", resp["data"] if resp["status"] == "ok" else resp)

        # === 2. Повторный запрос ===
        print("\nПовторный запрос (идемпотентность)...")
        resp2 = await client.call(
            action="create_book",
            version="v1",
            data={
                "title": "1984",
                "author": "George Orwell",
                "year": 1949,
                "isbn": "978-0451524935"
            },
            auth=API_KEY,
            idempotency_key="create-1984-v1"
        )
        print("Идемпотентный ответ:", resp2["data"] if resp2["status"] == "ok" else resp2)

        # === 3. Получение всех книг v1 ===
        print("\n" + "="*60)
        print("2. Получение списка книг (v1)")
        print("="*60)

        books = await client.call("get_books", "v1", data={}, auth=API_KEY)
        print("Книги:", books["data"] if books["status"] == "ok" else books)

        # === 4. Создание автора (v2) ===
        print("\n" + "="*60)
        print("3. Создание автора (v2)")
        print("="*60)

        author = await client.call(
            action="create_author",
            version="v2",
            data={
                "name": "J.K. Rowling",
                "birth_year": 1965,
                "country": "UK"
            },
            auth=API_KEY,
            idempotency_key="author-rowling"
        )
        print("Автор:", author["data"] if author["status"] == "ok" else author)

        # === 5. Создание книги v2 ===
        print("\n" + "="*60)
        print("4. Создание книги (v2)")
        print("="*60)

        book_v2 = await client.call(
            action="create_book",
            version="v2",
            data={
                "title": "Harry Potter",
                "author_id": 1,
                "year": 1997,
                "isbn": "978-0439708180",
                "pages": 320,
                "genre": "Fantasy"
            },
            auth=API_KEY,
            idempotency_key="book-hp-v2"
        )
        print("Книга v2:", book_v2["data"] if book_v2["status"] == "ok" else book_v2)

        # === 6. Фильтрация по жанру ===
        print("\n" + "="*60)
        print("5. Фильтрация по жанру (v2)")
        print("="*60)

        filtered = await client.call(
            "get_books",
            "v2",
            data={"genre": "Fantasy"},
            auth=API_KEY
        )
        print("Фильтр по 'Fantasy':", filtered["data"] if filtered["status"] == "ok" else filtered)

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())