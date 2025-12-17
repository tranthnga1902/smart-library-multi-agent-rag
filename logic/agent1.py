
import regex as re
import json, requests  # ⚠️ bỏ chữ "re" ở đây
from infrastructure.model  import ask_router,prompt1
# helper: lấy tên sách từ API (lowercase list)


def fetch_book_names(api_url="http://127.0.0.1:5000/all_books"):
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
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

    def plan_agents(self, user_input: str):
        ui = (user_input or "").strip()
        if not ui:
            return []

        ui_low = ui.lower()

        # 1) tìm tên sách chính xác/partial có trong thư viện
        matched = [n for n in self.book_names if n and n in ui_low]
        self.last_book_names = matched

        # 2) nếu không tìm thấy tên sách -> thử detect topic / yêu cầu số lượng
        if not matched:
            ui_low = ui_low.strip()

            # 🟢 Detect dạng "của tác giả ..." hoặc "của [tên người]"
            author_match = re.search(r"của ([\w\s\p{L}]+)", ui_low)
            if author_match:
                author = author_match.group(1).strip()
                self.last_topic = f"tác giả {author}"
                return ["agent4"]

            # 🟢 Detect dạng "sách của [quốc gia]" hoặc "sách từ [nước]"
            country_match = re.search(r"(?:của|từ) ([\w\s\p{L}]+)", ui_low)
            if country_match and any(
                    word in ui_low for word in
                    ["quốc gia", "nước", "brazil", "mỹ", "pháp", "anh", "nhật", "trung", "nga"]
            ):
                country = country_match.group(1).strip()
                self.last_topic = f"sách từ {country}"
                return ["agent4"]

            # 🟡 Các từ khóa theo chủ đề / thể loại (giữ nguyên code cũ)
            topic_keywords = [
                "về", "về chủ đề", "về đề tài", "về thể loại", "sách về",
                "5 cuốn", "5 quyển", "một số", "mấy", "gợi ý", "đề xuất", "liệt kê"
            ]
            if any(kw in ui_low for kw in topic_keywords):
                m = re.search(r"về (.+)", ui_low)
                topic = None
                if m:
                    topic = m.group(1).strip().rstrip(".?!")
                self.last_topic = topic or ui_low
                return ["agent4"]

            # không phải sách, không phải yêu cầu chủ đề -> nằm ngoài scope
            return []

        # 3) nếu có ít nhất 1 tên sách khớp -> gọi router (model) để quyết định có cần agent5
        from infrastructure.model import ask_router

        route_str = self.ask_router(prompt1.format(user_input=user_input)).strip().lower()
        if route_str == "none":
            return []

        required = [r.strip() for r in route_str.split(",") if r.strip() in self.available_agents]
        if "agent5" in required and "agent4" not in required:
            required.insert(0, "agent4")
        # lưu last_topic = None vì user đã hỏi cuốn cụ thể
        self.last_topic = None
        return required

    # --------------------------------------------------
    # 🔹 TỔNG HỢP KẾT QUẢ
    # --------------------------------------------------
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
