"""Import book metadata from the local CSV into PostgreSQL."""

import csv
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


csv_path = Path(__file__).with_name("Data2_merged_clean.csv")
load_dotenv(csv_path.with_name(".env"), override=True)
with csv_path.open(encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file, delimiter=";")
    columns = reader.fieldnames
    if not columns or len(columns) != 9:
        raise ValueError("CSV must contain the expected 9 columns")
    rows = [tuple(row[column].strip() for column in columns) for row in reader]

if any(not row[0].isdigit() or not row[1] for row in rows):
    raise ValueError("Every CSV row needs a numeric id and book name")

with psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "booksdb"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.environ["DB_PASS"],
) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books_metadata (
                source_id INTEGER PRIMARY KEY,
                book_name TEXT NOT NULL,
                author TEXT,
                country TEXT,
                year TEXT,
                genre TEXT,
                title_y TEXT,
                wiki_link TEXT,
                image_link TEXT
            )
        """)
        execute_values(cur, """
            INSERT INTO books_metadata
                (source_id, book_name, author, country, year, genre,
                 title_y, wiki_link, image_link)
            VALUES %s
            ON CONFLICT (source_id) DO UPDATE SET
                book_name = EXCLUDED.book_name,
                author = EXCLUDED.author,
                country = EXCLUDED.country,
                year = EXCLUDED.year,
                genre = EXCLUDED.genre,
                title_y = EXCLUDED.title_y,
                wiki_link = EXCLUDED.wiki_link,
                image_link = EXCLUDED.image_link
        """, [(int(row[0]), *row[1:]) for row in rows])
        cur.execute("SELECT count(*) FROM books_metadata")
        print(f"Imported {len(rows)} CSV rows; books_metadata now has {cur.fetchone()[0]} rows.")
