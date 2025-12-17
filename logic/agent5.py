# logic/agent5_logic.py
import re
import psycopg2
import requests
from bs4 import BeautifulSoup

# import hạ tầng
from infrastructure.model import ask_agent5, get_gemini_embedding, AGENT5_PROMPT_TEMPLATE

# ===========================================
# 🔹 KẾT NỐI POSTGRES (giữ nguyên config bạn có)
# ===========================================
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    dbname="booksdb",
    user="postgres",
    password="123456"
)
cur = conn.cursor()

# ===========================================
# 🔹 HÀM CHUNKING (giữ nguyên)
# ===========================================
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

    overlapped = []
    for i in range(len(chunks)):
        start = max(0, i-1)
        end = min(len(chunks), i+2)
        overlapped.append(" ".join(chunks[start:end]))
    return overlapped

# ===========================================
# 🔹 HÀM XỬ LÝ URL VÀ LƯU VÀO DB (giữ nguyên)
# ===========================================
def add_book_to_db(book_name, wiki_url):
    try:
        r = requests.get(wiki_url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip())>50]
    except Exception as e:
        print(f"⚠️ Lỗi tải URL {wiki_url}: {e}")
        return

    for idx, p in enumerate(paragraphs):
        chunks = semantic_chunk(p)
        embeddings = get_gemini_embedding(chunks)
        for chunk_text, emb in zip(chunks, embeddings):
            cur.execute("""
                INSERT INTO books_vector
                (book_name, paragraph_index, content, embedding)
                VALUES (%s,%s,%s,%s)
            """, (book_name, idx, chunk_text, emb))
    conn.commit()
    print(f"✅ Đã thêm sách '{book_name}' vào DB ({len(paragraphs)} đoạn).")

# ===========================================
# 🔹 HÀM VECTOR SEARCH (giữ nguyên)
# ===========================================
def search_vector_db(query, book_name=None, k=5):
    query_vec = get_gemini_embedding(query)[0]
    if book_name:
        cur.execute("""
            SELECT content, paragraph_index
            FROM books_vector
            WHERE book_name = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (book_name, query_vec, k))
    else:
        cur.execute("""
            SELECT content, book_name, paragraph_index
            FROM books_vector
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_vec, k))
    return cur.fetchall()

# ===========================================
# 🔹 HÀM HỎI ĐÁP KẾT HỢP LLM (GIỮ NGUYÊN PROMPT)
# ===========================================
def ask_question5(query, book_name=None, k=5):
    results = search_vector_db(query, book_name, k)
    if not results:
        return "Không tìm thấy thông tin phù hợp trong DB."

    context = "\n".join([r[0] for r in results])

    # SỬ DỤNG PROMPT TỪ INFRASTRUCTURE (KHÔNG PHÁ ĐỊNH DẠNG)
    prompt = AGENT5_PROMPT_TEMPLATE.format(context=context, query=query)

    return ask_agent5(prompt)

# ===========================================
# 🔹 MAIN (giữ nguyên)
# ===========================================
def main():
    print("📌 Agent truy xuất + tóm tắt với chunk + embedding + LLM")
    while True:
        query = input("🔹 Nhập câu hỏi (exit để thoát): ").strip()
        if query.lower() == "exit":
            break
        book_name = input("🔹 Nhập tên sách (Enter bỏ qua): ").strip() or None
        answer = ask_question5(query, book_name)
        print(f"\n💡 Kết quả:\n{answer}\n")

if __name__ == "__main__":
    main()
