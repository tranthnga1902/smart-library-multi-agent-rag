import json, re
from infrastructure.model import ask_agent4
from infrastructure.books import fetch_all_books


# =========================
# Lấy danh sách tất cả sách
# =========================
# =========================
# Trích xuất thông tin sách gần đúng nhất
# =========================
def find_closest_book_name(user_question: str, books_list: list):
    result_text = ask_agent4(user_question, books_list)

    # Làm sạch kết quả JSON mà agent trả về
    cleaned = re.sub(r"```(?:json)?", "", result_text, flags=re.IGNORECASE).strip().strip("`")

    try:
        parsed = json.loads(cleaned)

        # Nếu chỉ là 1 object → chuyển thành list
        if isinstance(parsed, dict):
            parsed = [parsed]

        normalized = []
        for p in parsed:
            item = {k: p.get(k, "") for k in [
                "book_name", "author", "genre", "year", "country", "title_y", "wiki_link", "image_link"
            ]}
            normalized.append(item)

        return normalized

    except Exception as e:
        print("⚠️ Lỗi parse JSON:", e)
        print("📄 Raw output:", result_text)
        return []


# =========================
# Hàm chính — KHÔNG GỌI API filter_books
# =========================
def ask_question4(user_question: str):
    """
    Trả về list thông tin sách đầy đủ (metadata) để agent4_node hiển thị.
    """
    try:
        books = fetch_all_books()
    except Exception as e:
        print(f"❌ Lỗi khi fetch sách: {e}")
        return {"error": "❌ Không lấy được danh sách sách từ database."}
    if not books:
        return {"error": "❌ Không lấy được danh sách sách từ API."}

    exact = [book for book in books if (book.get("book_name") or "").strip().casefold() == user_question.strip().casefold()]
    if exact:
        return exact

    mentioned = [book for book in books if (book.get("book_name") or "").strip().casefold() in user_question.casefold()]
    if mentioned:
        return mentioned[:5]

    extracted_books = find_closest_book_name(user_question, books)
    if not extracted_books:
        return {"error": "⚠️ Không tìm thấy sách phù hợp."}

    results = []

    # ✅ Lọc trực tiếp trong dữ liệu `books`
    for b in extracted_books:
        filter_conditions = {k: v for k, v in b.items() if v}
        matched_books = [
            book for book in books
            if all(
                str(book.get(k, "")).strip().lower() == str(v).strip().lower()
                for k, v in filter_conditions.items()
                if v
            )
        ]

        # Nếu có kết quả khớp thì thêm vào danh sách trả về
        if matched_books:
            results.append(matched_books[0])

    # Nếu không tìm thấy gì
    return results if results else {"error": "⚠️ Không tìm thấy dữ liệu phù hợp."}


# =========================
# Chạy thử CLI
# =========================
if __name__ == "__main__":
    print("===== TEST AGENT4 =====")
    print("Nhập 'exit' để thoát.\n")

    while True:
        user_question = input("❓ Nhập câu hỏi: ").strip()
        if user_question.lower() in ["exit", "quit"]:
            break

        answer = ask_question4(user_question)
        print(json.dumps(answer, indent=2, ensure_ascii=False))
        print("=" * 60)
