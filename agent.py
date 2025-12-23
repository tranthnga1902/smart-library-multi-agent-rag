
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any
from logic.agent1 import Agent1Logic,ask_router

from logic.agent4 import ask_question4
from logic.agent5 import ask_question5



def ask_agent(prompt: str):
    """
    Gọi model.generate_content() và in ra lỗi thật nếu có.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("❌ [ask_agent] Lỗi khi gọi model:", repr(e))
        import traceback
        traceback.print_exc()
        return f"❌ Lỗi khi gọi model: {e}"



# ======================
# 🔹 STATE TYPE
# ======================
from typing import TypedDict, List, Dict, Any

class State(TypedDict, total=False):
    user_input: str
    route: str
    output: str
    data_price: list
    x: list
    y: list

    sub_tasks: List[str]
    results: Dict[str, Any]

    chart_json: Dict[str, Any]
    product_details_json: Dict[str, Any]
    book_name: str
    top_k: int

    terminated: bool  # ✅ thêm cờ báo kết thúc


# ======================================================
# 🔹 AGENT 1 — LẬP KẾ HOẠCH VÀ ĐIỀU PHỐI
# ======================================================
from langgraph.graph import END

def agent1_node(state: dict, logic: 'Agent1Logic') -> dict:
    try:
        user_input = state.get("user_input", "")
        results = state.get("results", {}) or {}
        sub_tasks = state.get("sub_tasks", [])

        print(f"\n🚦 [Agent1] Bắt đầu với input: {user_input}")
        print(f"🔍 sub_tasks hiện tại: {sub_tasks}")

        # 🧱 Chặn vòng lặp nếu agent đã terminate
        if state.get("terminated"):
            print("🛑 [Agent1] Đã terminated → END.")
            state["route"] = "end"
            return state

        # =====================================================
        # 1️⃣ Lần đầu lập kế hoạch
        # =====================================================
        if not sub_tasks:
            print("🧠 [Agent1] Gọi plan_agents()...")
            sub_tasks = logic.plan_agents(user_input)
            print(f"📋 [Agent1] plan_agents() trả về: {sub_tasks}")

            # ❌ Không có subtask hợp lệ
            if not sub_tasks or not isinstance(sub_tasks, list):
                msg = "❌ Tôi không có thông tin phù hợp hoặc không hiểu yêu cầu."
                state.update({
                    "terminated": True,
                    "output": msg,
                    "route": "end"
                })
                results["agent1"] = msg
                state["results"] = results
                print("⚠️ [Agent1] Không có sub_tasks hợp lệ → DỪNG.")
                return state

            # ✅ Kiểm tra có topic hoặc book name
            has_books = bool(getattr(logic, "last_book_names", []))
            has_topic = bool(getattr(logic, "last_topic", None))
            if not has_books and not has_topic:
                msg = "❌ Tôi không tìm được sách hoặc chủ đề nào phù hợp với yêu cầu."
                state.update({
                    "terminated": True,
                    "output": msg,
                    "route": "end"
                })
                results["agent1"] = msg
                state["results"] = results
                print("⚠️ [Agent1] Không có last_book_names hoặc last_topic → DỪNG.")
                return state

            # ✅ Lưu sub_tasks, bắt đầu task đầu tiên
            state["sub_tasks"] = sub_tasks
            state["results"] = results
            state["route"] = sub_tasks[0]
            print(f"➡️ [Agent1] Chuyển route tới {state['route']}")
            return state

        # =====================================================
        # 2️⃣ Kiểm tra tiến trình sub_tasks
        # =====================================================
        completed = set(results.keys())
        remaining = [task for task in sub_tasks if task not in completed]
        print(f"📊 [Agent1] completed={completed}, remaining={remaining}")

        # 🧩 Nếu còn task nào chưa hoàn tất
        if remaining:
            next_task = remaining[0]
            print(f"➡️ [Agent1] Tiếp tục chạy {next_task}")
            state["route"] = next_task
            return state

        # =====================================================
        # 3️⃣ Khi tất cả đã xong → aggregate
        # =====================================================
        print("✅ [Agent1] Hoàn tất tất cả sub_tasks → aggregate.")
        state["route"] = "aggregate"
        return state

    except Exception as e:
        print("💥 [Agent1] Exception:", repr(e))
        import traceback
        traceback.print_exc()
        state.update({
            "terminated": True,
            "output": f"❌ Lỗi hệ thống: {e}",
            "route": "end"
        })
        return state


# ======================================================
# 🔹 AGENT 4 — TÌM THÔNG TIN SÁCH
# ======================================================
def agent4_node(state: dict) -> dict:
    """
    Gọi ask_question4(user_input) và xử lý kết quả:
    - Nếu ask_question4 trả về list -> lưu list + phần tử đầu vào state
    - Nếu trả về dict -> lưu trực tiếp
    - Chuẩn hóa keys: name, author, genre, year, nationality, image_url, wiki_link, description
    """
    user_input = state.get("user_input", "")
    results = state.get("results", {})

    try:
        answer = ask_question4(user_input)
    except Exception as e:
        print("⚠️ Lỗi gọi ask_question4:", e)
        answer = {"error": str(e)}

    # Reset key
    state.pop("product_details_json", None)
    state.pop("product_details_json_list", None)
    state.pop("book_name", None)

    def normalize_item(item):
        # item có thể chứa book_name / name, image_link / image_url, country / nationality
        name = item.get("book_name") or item.get("name") or item.get("title_y") or ""
        image_url = item.get("image_url") or item.get("image_link") or item.get("image") or ""
        nationality = item.get("country") or item.get("nationality") or ""
        return {
            "name": name,
            "book_name": item.get("book_name", name),
            "author": item.get("author", ""),
            "genre": item.get("genre", ""),
            "year": item.get("year") or item.get("năm", ""),
            "nationality": nationality,
            "wiki_link": item.get("wiki_link", ""),
            "image_url": image_url,
            "description": item.get("description", "")
        }

    # Case: list
    if isinstance(answer, list) and len(answer) > 0:
        normalized_list = [normalize_item(it) for it in answer]
        primary = normalized_list[0]
        state["book_name"] = primary.get("name") or primary.get("book_name") or None
        state["product_details_json"] = primary
        state["product_details_json_list"] = normalized_list
        formatted = f"📚 {primary.get('name')} của {primary.get('author','')}"
        print(f"✅ Agent4 (list): book_name = {state['book_name']}, total = {len(normalized_list)}")

    # Case: dict (single)
    elif isinstance(answer, dict) and not answer.get("error"):
        primary = normalize_item(answer)
        state["book_name"] = primary.get("name") or primary.get("book_name") or None
        state["product_details_json"] = primary
        # also provide a list with single element for uniformity
        state["product_details_json_list"] = [primary]
        formatted = f"📚 {primary.get('name')} của {primary.get('author','')}"
        print(f"✅ Agent4 (dict): book_name = {state['book_name']}")

    else:
        formatted = "⚠️ Không tìm thấy thông tin sách."
        state["book_name"] = None
        print("⚠️ Agent4: Không tìm thấy sách hoặc dữ liệu không hợp lệ.", answer)

    state["product_details_json_list"] = normalized_list
    results["agent4"] = normalized_list  # ✅ dữ liệu thật
    results["agent4_preview"] = formatted  # chỉ để debug/log
    state["results"] = results
    state["output"] = formatted
    return state


# ======================================================
# 🔹 AGENT 5 — TRUY XUẤT NỘI DUNG
# ======================================================
def agent5_node(state: dict) -> dict:
    query = state.get("user_input", "")
    book_name = state.get("book_name", None)
    results = state.get("results", {})
    k = state.get("top_k", 5)

    print(f"🧩 Agent5: Nhận book_name = {book_name}")

    if not book_name:
        msg = "❌ Không có tên sách để tìm nội dung."
        results["agent5"] = msg
        state["output"] = msg
        state["results"] = results
        return state

    answer = ask_question5(query, book_name=book_name, k=k)
    results["agent5"] = answer
    state["output"] = answer
    state["results"] = results

    print(f"✅ Agent5 trả về: {str(answer)[:120]}...")
    return state


# ======================================================
# 🔹 BUILD GRAPH
# ======================================================
logic = Agent1Logic(ask_router)
graph = StateGraph(State)

graph.add_node("agent1", lambda s: agent1_node(s, logic))
graph.add_node("aggregate", lambda s: logic.aggregate_results(s))

graph.add_node("agent4", agent4_node)
graph.add_node("agent5", agent5_node)

graph.set_entry_point("agent1")

# 🧩 Điều kiện rẽ nhánh
graph.add_conditional_edges(
    "agent1",
    lambda s: s.get("route", ""),
    {
        "agent4": "agent4",
        "agent5": "agent5",
        # nếu bạn muốn chạy node aggregate, trỏ tới "aggregate" (tên node)
        "aggregate": "aggregate",
        "self_answer": END,
        "end": END,
    },
)


# 🔧 Thêm các cạnh kết thúc hợp lệ
graph.add_edge("agent1", END)
graph.add_edge("agent4", END)
graph.add_edge("agent5", END)

# 🔁 Cho phép quay lại agent1 khi còn nhiệm vụ
graph.add_edge("agent4", "agent1")
graph.add_edge("agent5", "agent1")
graph.add_edge("aggregate", END)

# ✅ Biên dịch graph
app = graph.compile()

# ======================================================
# 🔹 TEST
# ======================================================
if __name__ == "__main__":
    query = "Cho tôi nội dung Số đỏ"
    result = app.invoke({"user_input": query})
    print("\n=== KẾT QUẢ CUỐI ===")
    print(result.get("output", "❌ Không có output"))

