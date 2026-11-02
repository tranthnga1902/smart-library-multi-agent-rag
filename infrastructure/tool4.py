from flask import Flask, request, jsonify
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
from infrastructure.openai_client import embed_texts
from infrastructure.vector_store import index_book
from infrastructure.books import fetch_all_books
import os, re, time, requests
from bs4 import BeautifulSoup
from flasgger import Swagger
import socket

app = Flask(__name__)
swagger = Swagger(app)

# =========================
# HÀM LẤY IP MẠNG NỘI BỘ
# =========================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# =========================
# CẤU HÌNH POSTGRES & GEMINI
# =========================
# =========================
import os

# Lấy cấu hình từ biến môi trường (Docker truyền vào)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "booksdb"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "123456")
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# =========================
# HÀM CHUNK & EMBEDDING
# =========================
def semantic_chunk(text, max_len=200):
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if len((current + " " + s).split()) > max_len:
            chunks.append(current.strip())
            current = s
        else:
            current += " " + s if current else s
    if current:
        chunks.append(current.strip())
    return chunks

def get_gemini_embedding(texts):
    return embed_texts(texts)

@app.route("/add_vector", methods=["POST"])
def add_vector():
    """
    Thêm sách mới và vector nội dung từ Wikipedia
    ---
    tags:
      - Vector Operations
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - book_name
            - wiki_link
          properties:
            book_name:
              type: string
            wiki_link:
              type: string
    responses:
      200:
        description: Thêm thành công
    """
    data = request.json
    book_name = data.get("book_name")
    wiki_link = data.get("wiki_link")

    if not book_name or not wiki_link:
        return jsonify({"error": "Thiếu book_name hoặc wiki_link"}), 400

    try:
        chunks = index_book({"book_name": book_name, "wiki_link": wiki_link})
        return jsonify({"success": f"Đã lập chỉ mục {book_name} với {chunks} đoạn mới."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# 🔹 API: XÓA VECTOR
# =========================
@app.route("/delete_vector", methods=["DELETE"])
def delete_vector():
    """
    Xóa toàn bộ vector của một sách
    ---
    tags:
      - Vector Operations
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - book_name
          properties:
            book_name:
              type: string
    responses:
      200:
        description: Số bản ghi bị xóa
    """
    data = request.json
    book_name = data.get("book_name")
    if not book_name:
        return jsonify({"error": "Thiếu book_name"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM books_vector WHERE book_name = %s", (book_name,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"deleted": deleted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# 🔹 API: CẬP NHẬT VECTOR
# =========================
@app.route("/update_vector", methods=["PUT"])
def update_vector():
    """
    Cập nhật lại nội dung của một đoạn văn (theo ID)
    ---
    tags:
      - Vector Operations
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - id
            - new_content
          properties:
            id:
              type: integer
            new_content:
              type: string
    responses:
      200:
        description: Cập nhật thành công
    """
    data = request.json
    id_ = data.get("id")
    new_content = data.get("new_content")
    if not id_ or not new_content:
        return jsonify({"error": "Thiếu id hoặc new_content"}), 400

    try:
        embedding = get_gemini_embedding(new_content)[0]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE books_vector
            SET content = %s, embedding = %s
            WHERE id = %s
        """, (new_content, embedding, id_))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"updated": id_})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# 🔹 API: LẤY TOÀN BỘ SÁCH
# =========================
@app.route("/all_books", methods=["GET"])
def all_books():
    """
    Lấy toàn bộ metadata sách
    ---
    tags:
      - Books
    responses:
      200:
        description: Danh sách tất cả sách
    """
    try:
        return jsonify(fetch_all_books())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# 🔹 CHẠY ỨNG DỤNG
# =========================
if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000
    print(f"Flask app đang chạy. Truy cập Swagger UI tại: http://127.0.0.1:{port}/apidocs/")
    print(f"Hoặc trong mạng nội bộ: http://{get_local_ip()}:{port}/apidocs/")
    app.run(host=host, port=port)
