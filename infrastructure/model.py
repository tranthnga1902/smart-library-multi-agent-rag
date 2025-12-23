import google.generativeai as genai
import seaborn as sns
import matplotlib.pyplot as plt
from langgraph.graph import StateGraph, END
from typing import TypedDict
# ======================
# Gemini API config
# ======================

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("❌ Lỗi: Chưa cấu hình GOOGLE_API_KEY trong biến môi trường!")
else:
    genai.configure(api_key=API_KEY)model = genai.GenerativeModel("gemini-3-flash-preview")
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
- none
---
"""
    try:
        full = guard_prefix.strip() + "\n\n" + prompt.strip()
        resp = model.generate_content(full)
        text = resp.text.strip().lower()
        # làm sạch: chỉ giữ chữ thường, số, dấu phẩy
        text = re.sub(r"[^a-z0-9,]", "", text)
        if text in ("agent4","agent4agent5","agent4,agent5"):
            # chuẩn hóa "agent4agent5" -> "agent4,agent5"
            return "agent4,agent5" if "agent5" in text and "agent4" in text else text
        return "none"
    except Exception as e:
        print("❌ ask_router error:", e)
        return "none"

prompt1 = """
Bạn là Trưởng nhóm điều phối. Người dùng hỏi: "{user_input}"
Nếu họ muốn nội dung/tóm tắt -> trả về "agent4,agent5".
Nếu họ chỉ muốn metadata (tác giả, năm, thể loại, ảnh, wiki) -> trả về "agent4".
Nếu ngoài phạm vi sách -> trả về "none".
Chỉ trả một trong 3 giá trị, không giải thích thêm.
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
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Lỗi khi gọi model: {e}"

# =========================
# agent5
# =========================

embedding_model_name = "models/text-embedding-004"
fixed_vector_size = 1024

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
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Lỗi khi gọi model: {e}"

# ===========================================
# 🔹 HÀM TẠO EMBEDDING (giữ nguyên logic pad/cut + norm)
# ===========================================
def get_gemini_embedding(texts):
    """Sinh embedding từ Gemini, cắt/pad về fixed_vector_size = 1024, chuẩn hóa."""
    if isinstance(texts, str):
        texts = [texts]
    embeddings = []
    for i in range(0, len(texts), 50):
        batch = texts[i:i+50]
        try:
            res = genai.embed_content(model=embedding_model_name, content=batch)
            for emb in res["embedding"]:
                if len(emb) > fixed_vector_size:
                    emb = emb[:fixed_vector_size]
                elif len(emb) < fixed_vector_size:
                    emb += [0.0] * (fixed_vector_size - len(emb))
                emb = np.array(emb, dtype=np.float32)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb /= norm
                embeddings.append(emb.tolist())
        except Exception:
            embeddings.extend([[0.0] * fixed_vector_size] * len(batch))
    return embeddings
