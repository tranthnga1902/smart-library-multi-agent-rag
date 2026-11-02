"""Build or resume the local vector index for every CSV book."""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)

from infrastructure.books import fetch_all_books
from infrastructure.vector_store import index_book


def main():
    books = fetch_all_books()
    indexed = 0
    failed = []
    for number, book in enumerate(books, 1):
        try:
            chunks = index_book(book)
            indexed += bool(chunks)
            print(f"{number}/{len(books)}: {book['book_name']} - {chunks} new chunks", flush=True)
        except Exception as error:
            failed.append(book['book_name'])
            print(f"{number}/{len(books)}: {book['book_name']} - {type(error).__name__}: {error}", flush=True)
    print(f"Finished: {indexed} newly indexed, {len(failed)} failed", flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
