import csv, requests, re, time, os, psycopg2
import numpy as np
from bs4 import BeautifulSoup
import google.generativeai as genai

# Cấu hình Gemini API
API_KEY = os.getenv("GOOGLE_API_KEY")


# --- 2. CẤU HÌNH GEMINI ---
if not API_KEY:
    raise ValueError("❌ LỖI: GOOGLE_API_KEY không được tìm thấy trong biến môi trường!")

genai.configure(api_key=API_KEY)
embedding_model_name = "models/text-embedding-004"
fixed_vector_size = 1024

# Kết nối Postgres trong Docker container
# Kết nối Postgres (Sửa lại đoạn này)
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"), # Lấy từ Docker (db), nếu chạy máy ngoài thì dùng localhost
    port=os.getenv("DB_PORT", 5433),         # Lấy 5432 từ Docker hoặc 5433 từ máy ngoài
    dbname=os.getenv("DB_NAME", "booksdb"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASS", "123456")
)
cur = conn.cursor()

# Tạo extension vector nếu chưa có
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
conn.commit()

# Tạo bảng
cur.execute("""
CREATE TABLE IF NOT EXISTS books_vector (
    id SERIAL PRIMARY KEY,
    book_name TEXT,
    author TEXT,
    country TEXT,
    year TEXT,
    genre TEXT,
    title_y TEXT,
    wiki_link TEXT,
    image_link TEXT,
    paragraph_index INT,
    content TEXT,
    embedding VECTOR(1024)
);
""")
conn.commit()

# Hàm chia đoạn text thành chunks
def semantic_chunk(text, max_len=200):
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks, current_chunk = [], ""
    for s in sentences:
        if len((current_chunk + " " + s).split()) > max_len:
            chunks.append(current_chunk.strip())
            current_chunk = s
        else:
            current_chunk += " " + s if current_chunk else s
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# Hàm tạo embedding với Gemini
def get_gemini_embedding(texts):
    if isinstance(texts, str): texts = [texts]
    all_embeddings = []
    for i in range(0, len(texts), 50):
        batch = texts[i:i+50]
        try:
            result = genai.embed_content(model=embedding_model_name, content=batch)
            for emb in result["embedding"]:
                if len(emb) < fixed_vector_size:
                    emb += [0.0]*(fixed_vector_size - len(emb))
                elif len(emb) > fixed_vector_size:
                    emb = emb[:fixed_vector_size]
                all_embeddings.append(emb)
        except Exception:
            all_embeddings.extend([[0.0]*fixed_vector_size]*len(batch))
        time.sleep(1)
    return all_embeddings

# Đọc CSV và xử lý từng sách
with open("Data2_merged_clean.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        book_name = row["tên sách_x"]
        author = row["tác giả"]
        country = row["quốc gia"]
        year = row["năm sáng tác"]
        genre = row["thể loại"]
        title_y = row["tên sách_y"]
        wiki_link = row["link Wikipedia"]
        image_link = row["link hình ảnh"]

        # tải nội dung Wikipedia
        try:
            r = requests.get(wiki_link, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip())>50]
        except:
            paragraphs = []

        # chia chunk và tạo embedding
        all_chunks = []
        for idx, p in enumerate(paragraphs):
            chunks = semantic_chunk(p)
            all_chunks.extend([(idx, c) for c in chunks])

        if not all_chunks: continue
        embeddings = get_gemini_embedding([c[1] for c in all_chunks])

        # lưu vào Postgres
        for (para_idx, chunk_text), emb in zip(all_chunks, embeddings):
            cur.execute("""
                INSERT INTO books_vector
                (book_name, author, country, year, genre, title_y, wiki_link, image_link, paragraph_index, content, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                book_name, author, country, year, genre, title_y, wiki_link, image_link, para_idx, chunk_text, emb
            ))

conn.commit()
cur.close()
conn.close()


