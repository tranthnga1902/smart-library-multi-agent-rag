import os
import re
from urllib.parse import urlparse

import numpy as np
import psycopg2
import requests
from bs4 import BeautifulSoup

from infrastructure.openai_client import embed_texts, VECTOR_SIZE


def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "booksdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.environ["DB_PASS"],
    )


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books_vector (
                id BIGSERIAL PRIMARY KEY,
                book_name TEXT NOT NULL,
                paragraph_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding DOUBLE PRECISION[] NOT NULL,
                UNIQUE (book_name, paragraph_index)
            )
        """)
    conn.commit()


def chunks_from_wikipedia(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("vi.wikipedia.org", "en.wikipedia.org"):
        raise ValueError("Book needs a valid Wikipedia URL")
    response = requests.get(url, headers={"User-Agent": "BookRAGAgent/1.0"}, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("#mw-content-text p")]
    chunks = []
    for paragraph in paragraphs:
        if len(paragraph) < 50:
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if current and len((current + " " + sentence).split()) > 180:
                chunks.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
    return chunks


def index_book(book):
    name = book["book_name"]
    with connect() as conn:
        ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM books_vector WHERE book_name = %s", (name,))
            if cur.fetchone()[0]:
                return 0
    chunks = chunks_from_wikipedia(book["wiki_link"])
    if not chunks:
        raise ValueError(f"No Wikipedia content for {name}")
    vectors = embed_texts(chunks)
    if len(vectors) != len(chunks):
        raise ValueError("Embedding count does not match chunk count")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO books_vector (book_name, paragraph_index, content, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (book_name, paragraph_index) DO NOTHING
            """, [(name, i, chunk, vector) for i, (chunk, vector) in enumerate(zip(chunks, vectors))])
    return len(chunks)


def search(query, book_name, k=5):
    with connect() as conn:
        ensure_table(conn)
        with conn.cursor() as cur:
            if book_name:
                cur.execute("SELECT content, embedding FROM books_vector WHERE book_name = %s", (book_name,))
            else:
                cur.execute("SELECT content, embedding FROM books_vector")
            rows = cur.fetchall()
    if not rows:
        return []
    query_vector = np.asarray(embed_texts(query)[0], dtype=np.float32)
    vectors = np.asarray([row[1] for row in rows], dtype=np.float32)
    if vectors.shape[1] != VECTOR_SIZE:
        raise ValueError("Stored embeddings have the wrong dimensions; rebuild books_vector")
    scores = vectors @ query_vector / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vector) + 1e-12)
    return [rows[i][0] for i in np.argsort(scores)[::-1][:k]]
