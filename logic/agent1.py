
from infrastructure.model  import ask_router,prompt1
from infrastructure.books import fetch_all_books
# helper: lấy tên sách từ API (lowercase list)


def fetch_book_names():
    try:
        data = fetch_all_books()
        names = [ (b.get("book_name") or b.get("tên sách_x") or "").strip().lower() for b in data if (b.get("book_name") or b.get("tên sách_x")) ]
        return list(dict.fromkeys(names))  # bỏ trùng
    except Exception as e:
        print("❌ fetch_book_names error:", e)
        return []

class Agent1Logic:
    def __init__(self, ask_router_fn):
        self.ask_router = ask_router_fn
        self.available_agents = ["agent4", "agent5"]
        self.book_names = fetch_book_names()
        # thống nhất tên thuộc tính dùng bởi agent1_node
        self.last_book_names = []   # danh sách tên sách detect được (lowercase)
        self.last_topic = None      # chủ đề detect được (string)

    def plan_agents(self, user_input: str, context_book_name=None):
        question = (user_input or "").strip()
        if not question:
            return [], None

        lowered = question.casefold()
        matched = [name for name in self.book_names if name and name in lowered]
        self.last_book_names = matched
        self.last_topic = None
        if lowered in self.book_names:
            return ["agent4"], None

        current_book = context_book_name if context_book_name and context_book_name.casefold() in self.book_names else None
        route = self.ask_router(prompt1.format(
            user_input=question,
            current_book=current_book or "none",
        ))
        use_context = bool(current_book and not matched and route.startswith("context"))
        if route == "none":
            return [], None
        if route in ("context45", "agent4,agent5"):
            tasks = ["agent4", "agent5"]
        elif route in ("context4", "agent4"):
            tasks = ["agent4"]
        else:
            return [], None
        if not matched and not use_context:
            self.last_topic = question
        return tasks, current_book if use_context else None

    # Aggregate the results from selected agents.
    def aggregate_results(self, state: dict):
        results = state.get("results", {})

        # 🔹 Lấy danh sách sách từ các nguồn khác nhau
        book_list = (
                state.get("product_details_json_list")
                or results.get("agent4")  # ✅ Nếu agent4 chứa danh sách sách
                or []
        )

        if not book_list:
            single = state.get("product_details_json", {}) or {}
            if single:
                book_list = [single]

        if not book_list:
            topic = getattr(self, "last_topic", None)
            if topic:
                state["output"] = f"⚠️ Không tìm thấy sách nào phù hợp với chủ đề **{topic}**."
            else:
                state["output"] = "⚠️ Hệ thống không có dữ liệu sách để tổng hợp."
            return state

        # 🔹 Nếu agent5 có nội dung tổng hợp
        content_text = results.get("agent5", "")

        # 🧩 Tạo danh sách văn bản hiển thị
        book_texts = []
        for idx, book in enumerate(book_list, 1):
            name = book.get("book_name") or book.get("name") or f"Sách {idx}"
            author = book.get("author") or "Không rõ"
            genre = book.get("genre") or "Không rõ"
            year = book.get("year") or "Không rõ"
            country = book.get("nationality") or "Không rõ"
            image_url = book.get("image_link") or book.get("image_url") or ""
            wiki_link = book.get("wiki_link") or "Không có link"

            text_block = (
                f"📘 **{idx}. {name}**\n"
                f"👤 Tác giả: {author}\n"
                f"📖 Thể loại: {genre}\n"
                f"🌍 Quốc gia: {country}\n"
                f"📅 Năm: {year}\n"
                f"🔗 Wiki: {wiki_link}\n"
                f"🖼 Ảnh: {image_url or 'Không có ảnh'}\n"
            )
            book_texts.append(text_block)

        # 🔹 Ghép văn bản tổng hợp
        final_text = "📚 **Danh sách sách tìm được:**\n\n" + "\n\n".join(book_texts)

        # ✅ Chỉ thêm phần nội dung tóm tắt nếu KHÔNG trùng với phần mô tả trong danh sách sách
        if content_text:
            descs = [b.get("description", "").strip() for b in book_list if b.get("description")]
            if not any(content_text.strip() == d for d in descs):
                final_text += f"\n\n📝 **Nội dung chi tiết / tóm tắt:**\n{content_text}"
            else:
                print("⚠️ [Aggregate] Nội dung agent5 trùng với mô tả trong agent4 → bỏ qua để tránh lặp.")

        # 🔹 Lưu vào state
        state["output"] = final_text
        state["aggregate_data"] = {
            "book_list": book_list,
            "content_summary": content_text or "Không có nội dung chi tiết."
        }

        return state
