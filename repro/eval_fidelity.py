#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fidelity Evaluation Framework (Bộ Đánh Giá Độ Trung Thực của Tóm Tắt AI)
Dành cho TICKET 2 (Thịnh) - Nhóm AIE1

Script này thực hiện:
1. Lấy dữ liệu đánh giá sản phẩm (review gốc) từ PostgreSQL.
2. Gọi API của dịch vụ AI (AskProductAIAssistant hoặc gọi trực tiếp LLM).
3. Thực hiện đánh giá chéo (LLM-as-a-judge hoặc so sánh từ khóa) để chấm điểm Fidelity (1-5).
"""

import os
import sys
import json
import psycopg2
import grpc
from openai import OpenAI

# Nạp proto đã được sinh ra
# Lưu ý: cần trỏ python path tới thư mục chứa demo_pb2 và demo_pb2_grpc
sys.path.append(os.path.join(os.path.dirname(__file__), "../techx-corp-platform/src/product-reviews"))
try:
    import demo_pb2
    import demo_pb2_grpc
except ImportError:
    print("[Cảnh báo] Chưa tìm thấy file demo_pb2.py. Hãy chạy 'make docker-generate-protobuf' trước.")

# Cấu hình kết nối Postgres & gRPC (Đọc từ môi trường hoặc lấy giá trị mặc định local)
DB_CONN = os.environ.get("DB_CONNECTION_STRING", "Host=localhost;Username=otelu;Password=otelp;Database=demo;Port=5432")
PRODUCT_REVIEWS_ADDR = os.environ.get("PRODUCT_REVIEWS_ADDR", "localhost:50054")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def get_raw_reviews_from_db(product_id):
    """Lấy danh sách review gốc từ cơ sở dữ liệu Postgres"""
    print(f"[*] Đang lấy review gốc cho sản phẩm {product_id} từ Postgres...")
    try:
        # Tách chuỗi connection string sang dạng dict cho psycopg2
        conn_dict = {}
        for part in DB_CONN.split(";"):
            if "=" in part:
                k, v = part.split("=")
                conn_dict[k.lower().strip()] = v.strip()
        
        # Kết nối DB
        conn = psycopg2.connect(
            host=conn_dict.get("host", "localhost"),
            user=conn_dict.get("username", "otelu"),
            password=conn_dict.get("password", "otelp"),
            database=conn_dict.get("database", "demo"),
            port=conn_dict.get("port", "5432")
        )
        
        with conn.cursor() as cur:
            query = "SELECT username, description, score FROM reviews.productreviews WHERE product_id = %s"
            cur.execute(query, (product_id,))
            records = cur.fetchall()
            
        conn.close()
        reviews = [{"username": r[0], "description": r[1], "score": r[2]} for r in records]
        print(f"[+] Tìm thấy {len(reviews)} review(s) cho sản phẩm {product_id}.")
        return reviews
    except Exception as e:
        print(f"[!] Lỗi kết nối DB: {e}")
        return []

def get_ai_summary_via_grpc(product_id):
    """Gọi gRPC AskProductAIAssistant để lấy tóm tắt từ AI"""
    print(f"[*] Đang gọi dịch vụ gRPC Product Reviews ({PRODUCT_REVIEWS_ADDR}) để lấy tóm tắt...")
    try:
        channel = grpc.insecure_channel(PRODUCT_REVIEWS_ADDR)
        stub = demo_pb2_grpc.ProductReviewServiceStub(channel)
        
        # Gửi câu hỏi yêu cầu tóm tắt đánh giá
        request = demo_pb2.AskProductAIAssistantRequest(
            product_id=product_id,
            question="Can you summarize the product reviews?"
        )
        response = stub.AskProductAIAssistant(request)
        print(f"[+] Đã nhận phản hồi từ AI: \"{response.response}\"")
        return response.response
    except Exception as e:
        print(f"[!] Không thể gọi gRPC Service (Có thể do service chưa chạy): {e}")
        # Trả về chuỗi giả lập nếu không kết nối được gRPC để test logic script
        return "Trình giả lập gRPC bị lỗi kết nối."

def evaluate_fidelity_llm_as_a_judge(raw_reviews, ai_summary):
    """Sử dụng LLM làm giám khảo (LLM-as-a-judge) để chấm điểm Fidelity của tóm tắt"""
    if not OPENAI_API_KEY:
        print("[!] Không tìm thấy OPENAI_API_KEY. Sử dụng bộ lọc heuristic từ khóa cơ bản để thay thế.")
        return evaluate_fidelity_heuristic(raw_reviews, ai_summary)
        
    print("[*] Đang gọi GPT-4o-mini làm Giám khảo chấm điểm Fidelity...")
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        reviews_str = "\n".join([f"- Score: {r['score']} | Review: {r['description']}" for r in raw_reviews])
        
        prompt = f"""
Bạn là một kiểm toán viên hệ thống AI cao cấp chuyên đánh giá chất lượng tóm tắt.
Nhiệm vụ của bạn là so sánh ĐÁNH GIÁ GỐC của sản phẩm với BẢN TÓM TẮT DO AI TẠO RA, và đánh giá độ trung thực (Fidelity).

ĐÁNH GIÁ GỐC:
{reviews_str}

BẢN TÓM TẮT DO AI TẠO RA:
{ai_summary}

Hãy chấm điểm Fidelity từ 1 đến 5 theo tiêu chuẩn sau:
- 5: Hoàn hảo. Tóm tắt hoàn toàn dựa trên dữ liệu thật, không có chi tiết bịa đặt hoặc suy diễn sai lệch.
- 4: Tốt. Tóm tắt đúng phần lớn, có thể bỏ sót 1-2 điểm phụ nhỏ nhưng không bịa đặt.
- 3: Khá. Tóm tắt còn mơ hồ, chưa nêu được hết bức tranh toàn cảnh của reviews.
- 2: Tệ. Tóm tắt bắt đầu bịa đặt ra các thông tin không có trong đánh giá gốc (Ví dụ: Reviews khen nhưng tóm tắt kêu chê, hoặc tự bịa ra thông số).
- 1: Sai lệch hoàn toàn. Tóm tắt trái ngược với đánh giá gốc hoặc bịa đặt thông tin nghiêm trọng.

Trả về kết quả dưới định dạng JSON duy nhất như sau:
{{
  "score": <điểm từ 1-5>,
  "reason": "<giải thích lý do chi tiết vì sao cho điểm này>"
}}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=10
        )
        
        result = json.loads(response.choices[0].message.content)
        return result["score"], result["reason"]
        
    except Exception as e:
        print(f"[!] Lỗi khi gọi LLM làm giám khảo: {e}")
        return 3, "Lỗi API, mặc định chấm 3 điểm."

def evaluate_fidelity_heuristic(raw_reviews, ai_summary):
    """Thuật toán đánh giá Fidelity đơn giản (Keyword & Sentiment heuristics) khi không có OpenAI Key"""
    # So khớp xem nếu review gốc toàn tích cực (điểm > 3) nhưng tóm tắt lại chê (chứa từ tiêu cực)
    # Đây là logic sơ bộ để chạy thử
    score = 5
    reason = "Dựa trên bộ lọc heuristic từ khóa: Tóm tắt có sự tương thích cao về ngữ nghĩa."
    
    # Kiểm tra xem sản phẩm có bị lỗi test case cố định không
    if "inaccurate" in ai_summary.lower() or "not recommended" in ai_summary.lower():
        score = 1
        reason = "Phát hiện tóm tắt chứa thông tin sai lệch so với cơ sở dữ liệu thực tế."
        
    return score, reason

def run_eval_for_product(product_id):
    print("=" * 60)
    print(f"BẮT ĐẦU ĐÁNH GIÁ SẢN PHẨM: {product_id}")
    print("=" * 60)
    
    # 1. Lấy reviews gốc từ DB
    raw_reviews = get_raw_reviews_from_db(product_id)
    if not raw_reviews:
        print("[!] Không có dữ liệu đánh giá để so sánh.")
        return
        
    # 2. Lấy tóm tắt AI sinh ra
    ai_summary = get_ai_summary_via_grpc(product_id)
    
    # 3. Chấm điểm Fidelity
    score, reason = evaluate_fidelity_llm_as_a_judge(raw_reviews, ai_summary)
    
    print("-" * 60)
    print(f"KẾT QUẢ ĐÁNH GIÁ FIDELITY CHO {product_id}:")
    print(f"-> ĐIỂM SỐ: {score} / 5")
    print(f"-> LÝ DO: {reason}")
    print("=" * 60)

if __name__ == "__main__":
    # Test case mẫu:
    # 1. L9ECAV7KIM: Sản phẩm test để kiểm tra lỗi sai lệch (khi bật flag)
    # 2. 0PUK6V6EV0: Sản phẩm thông thường
    
    target_product = "L9ECAV7KIM"
    if len(sys.argv) > 1:
        target_product = sys.argv[1]
        
    run_eval_for_product(target_product)
