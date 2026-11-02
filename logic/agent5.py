from infrastructure.books import fetch_all_books
from infrastructure.model import AGENT5_PROMPT_TEMPLATE, ask_agent5
from infrastructure.vector_store import index_book, search


def ask_question5(query, book_name=None, k=5):
    if book_name:
        book = next((item for item in fetch_all_books()
                     if item["book_name"].casefold() == book_name.casefold()), None)
        if not book:
            return "Không tìm thấy sách trong database."
        try:
            index_book(book)
        except Exception as error:
            return f"Không tạo được vector cho sách: {error}"

    try:
        passages = search(query, book_name, k)
    except Exception as error:
        return f"Không tìm kiếm được vector: {error}"
    if not passages:
        return "Chưa có nội dung được lập chỉ mục cho sách này."
    context = "\n".join(passages)
    return ask_agent5(AGENT5_PROMPT_TEMPLATE.format(context=context, query=query))


if __name__ == "__main__":
    while True:
        query = input("Câu hỏi (exit để thoát): ").strip()
        if query.lower() == "exit":
            break
        book_name = input("Tên sách: ").strip() or None
        print(ask_question5(query, book_name))
