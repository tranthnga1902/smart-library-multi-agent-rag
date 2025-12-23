from flask import Flask, render_template, request, jsonify
from flow.agent import app as agent_app
import traceback, json

flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return render_template("index.html")

@flask_app.route("/ask", methods=["POST"])
def ask():
    try:
        user_input = request.json.get("message")
        result = agent_app.invoke({"user_input": user_input})

        # 🔍 In ra dữ liệu thô mà agent trả về
        print("\n================= 🧠 RAW AGENT RESULT =================")
        try:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception:
            print(result)
        print("========================================================\n")

        # 🧹 Loại bỏ agent5 nếu tồn tại (tránh lặp nội dung)
        if isinstance(result, dict) and "agent5" in result:
            del result["agent5"]
        if "results" in result and isinstance(result["results"], dict):
            result["results"].pop("agent5", None)

        # 🔧 Chuẩn hóa dữ liệu để FE hiển thị được
        if "product_details_json_list" not in result:
            if "product_details_json" in result:
                result["product_details_json_list"] = [result["product_details_json"]]

        # 🔹 Ép kiểu an toàn cho product_details_json_list
        if "product_details_json_list" in result:
            data = result["product_details_json_list"]
            if isinstance(data, str):
                try:
                    result["product_details_json_list"] = json.loads(data)
                except json.JSONDecodeError:
                    print("⚠️ Không parse được JSON list:", data)
                    result["product_details_json_list"] = []

        if "output" not in result:
            result["output"] = "⚠️ Hệ thống không tạo ra output văn bản tổng hợp."

        return jsonify(result)

    except Exception as e:
        print("❌ Lỗi Flask khi gọi Agent:")
        traceback.print_exc()
        return jsonify({
            "output": f"❌ Lỗi hệ thống: {e or 'Không rõ lỗi (rỗng)'}",
            "error": traceback.format_exc()
        }), 500


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5001, debug=True)
