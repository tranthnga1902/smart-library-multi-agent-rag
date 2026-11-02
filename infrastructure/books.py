import os

import psycopg2


def fetch_all_books():
    with psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "booksdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "123456"),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT book_name, author, country, year, genre,
                                title_y, wiki_link, image_link
                FROM books_metadata
            """)
            return [dict(zip(
                ("book_name", "author", "country", "year", "genre",
                 "title_y", "wiki_link", "image_link"), row
            )) for row in cur.fetchall()]
