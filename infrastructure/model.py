from infrastructure.openai_client import generate_text, embed_texts, EMBEDDING_MODEL, VECTOR_SIZE
import seaborn as sns
import matplotlib.pyplot as plt
from langgraph.graph import StateGraph, END
from typing import TypedDict
import regex as re
import json, requests  # ⚠️ bỏ chữ "re" ở đây

# =========================
# agent 1
# =========================

# gọi model để quyết định route — riêng cho routing (không trộn với agent4/5)
def ask_router(prompt: str) -> str:
    guard_prefix = """
⚠️ QUY TẮC BẮT BUỘC:
Chỉ trả về một trong các giá trị chính xác (không thêm gì khác):
- agent4
- agent4,agent5
- context4
- context45
- none
---
"""
    try:
        full = guard_prefix.strip() + "\n\n" + prompt.strip()
        resp = generate_text(full)
        text = resp.strip().lower()
        # làm sạch: chỉ giữ chữ thường, số, dấu phẩy
        text = re.sub(r"[^a-z0-9,]", "", text)
        if text in ("agent4", "agent4,agent5", "agent4agent5", "context4", "context45"):
            return "agent4,agent5" if text == "agent4agent5" else text
        return "none"
    except Exception as e:
        print("❌ ask_router error:", e)
        return "none"

prompt1 = """
Bạn điều phối câu hỏi cho hệ thống sách.
Sách đang xem trong cuộc trò chuyện: {current_book}
Câu hỏi mới: {user_input}

Xác định ý định theo ngữ nghĩa, không dựa vào từ khóa cố định:
- Nếu câu hỏi tiếp nối về sách đang xem và cần nội dung, diễn biến, nhân vật, lý do hay giải thích: context45.
- Nếu câu hỏi tiếp nối về sách đang xem và chỉ cần thông tin như tác giả, năm, thể loại: context4.
- Nếu hỏi sách khác, tìm sách hoặc gợi ý sách và cần nội dung: agent4,agent5.
- Nếu hỏi sách khác, tìm sách hoặc gợi ý sách và chỉ cần thông tin sách: agent4.
- Nếu không liên quan đến sách: none.
Không suy diễn câu hỏi mới thành câu hỏi tiếp nối khi nó đổi chủ đề. Chỉ trả về đúng một nhãn.
"""
# =========================
# agent4
# =========================
BOOK_EXTRACTION_PROMPT = """
Bạn là một trợ lý đọc hiểu sách thông minh.
Người dùng hỏi: "{user_question}"

Trong danh sách sách dưới đây:
{books_json}

Nhiệm vụ:
1. Phân tích xem người dùng đang muốn:
   - Một **quyển sách cụ thể** (ví dụ: "Số đỏ", "cuốn Kiêu hãnh và định kiến") 
     → chỉ trả về 1 sách gần đúng nhất.
   - Hay muốn **nhiều sách cùng chủ đề** (ví dụ: "5 quyển", "một số sách về lịch sử/lãng mạn") 
     → trả về tối đa 5 sách phù hợp nhất.

2. Trả về **duy nhất một JSON hợp lệ**:
   - Nếu 1 quyển → một object.
   - Nếu nhiều quyển → một mảng JSON gồm tối đa 5 object.

Mỗi đối tượng sách có cấu trúc sau:
{{
  "book_name": "<tên sách>",
  "author": "<tác giả nếu có>",
  "genre": "<thể loại nếu có>",
  "year": "<năm nếu có>",
  "country": "<quốc gia nếu có>",
  "title_y": "<tên phụ nếu có>",
  "wiki_link": "<link Wikipedia nếu có>",
  "image_link": "<link hình ảnh nếu có>"
}}

⚠️ Chỉ xuất ra JSON, không thêm giải thích hoặc markdown.
Nếu không có sách phù hợp, trả về [].
"""



def ask_agent4(user_question: str, books_list: list) -> str:
    """
    Sinh JSON danh sách sách phù hợp nhất từ câu hỏi và danh sách sách.
    ⚠️ KHÔNG thay đổi format đầu ra. Trả về chuỗi text raw của Gemini.
    """
    prompt = BOOK_EXTRACTION_PROMPT.format(
        user_question=user_question,
        books_json=json.dumps(books_list, ensure_ascii=False)
    )

    try:
        response = generate_text(prompt)
        return response
    except Exception as e:
        return f"❌ Lỗi khi gọi model: {e}"

# =========================
# agent5
# =========================

embedding_model_name = EMBEDDING_MODEL
fixed_vector_size = VECTOR_SIZE

# Model suy luận

AGENT5_PROMPT_TEMPLATE = """
Bạn là một trợ lý đọc hiểu sách. Dựa trên các đoạn sau:

{context}

Hãy trả lời câu hỏi của người dùng một cách **rõ ràng, ngắn gọn, diễn giải bằng lời của bạn**, không copy nguyên văn:
Câu hỏi: {query}
"""

# ===========================================
# 🔹 HÀM GỌI GEMINI (giữ nguyên output)
# ===========================================
def ask_agent5(prompt: str):
    """Gọi model Gemini 2.5 Flash để sinh nội dung (trả raw text)."""
    try:
        response = generate_text(prompt)
        return response
    except Exception as e:
        return f"❌ Lỗi khi gọi model: {e}"

# ===========================================
# 🔹 HÀM TẠO EMBEDDING (giữ nguyên logic pad/cut + norm)
# ===========================================
def get_gemini_embedding(texts):
    return embed_texts(texts)
