# Product Reviews Service

This service returns product reviews for a specific product, along with an
AI-generated summary of the product reviews.

## Local Build

To build the protos, run from the root directory:

```sh
make docker-generate-protobuf
```

## Docker Build

From the root directory, run:

```sh
docker compose build product-reviews
```

## LLM Configuration

By default, this service uses a mock LLM service, as configured in
the `.env` file:

``` yaml
LLM_BASE_URL=http://${LLM_HOST}:${LLM_PORT}/v1
LLM_MODEL=techx-llm
OPENAI_API_KEY=dummy
```

If desired, the configuration can be changed to point to a real, OpenAI API
compatible LLM in the file `.env.override`. For example, the following
configuration can be used to utilize OpenAI's gpt-4o-mini model:

``` yaml
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=<replace with API key>
```

---

## Sơ đồ luồng hoạt động (Code Flowchart)

Dưới đây là sơ đồ Mermaid thể hiện luồng xử lý của các dịch vụ trong [product_reviews_server.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase3/techx-corp-platform/src/product-reviews/product_reviews_server.py):

```mermaid
flowchart TD
    Request([Yêu cầu từ Client]) --> Endpoint{Endpoint gRPC?}
    
    %% GetProductReviews
    Endpoint -->|GetProductReviews| DB_Reviews[Lấy reviews từ DB]
    DB_Reviews --> Metric_Reviews[Ghi nhận OpenTelemetry Metrics] --> Ret_Reviews([Trả về danh sách reviews])
    
    %% GetAverageProductReviewScore
    Endpoint -->|GetAverageProductReviewScore| DB_Avg[Lấy điểm trung bình từ DB]
    DB_Avg --> Ret_Avg([Trả về điểm trung bình])
    
    %% AskProductAIAssistant
    Endpoint -->|AskProductAIAssistant| AI_Flow{Kiểm tra flag llmRateLimitError?}
    AI_Flow -->|Bật & 50% tỉ lệ| Mock_429[Gọi Mock LLM báo lỗi 429] --> Fallback[Trả về câu fallback lỗi hệ thống]
    AI_Flow -->|Tắt hoặc không bị| LLM_1[Gọi LLM lần 1 kèm danh sách tools]
    
    LLM_1 --> Tool_Req{LLM yêu cầu gọi Tool?}
    
    %% Nhánh có gọi Tool
    Tool_Req -->|Có| Exec_Tool[Chạy tool nội bộ: fetch_product_reviews / fetch_product_info]
    Exec_Tool --> Append_Tool[Thêm kết quả tool vào messages]
    
    Append_Tool --> Flag_Inaccurate{Flag llmInaccurateResponse bật<br>AND product_id == 'L9ECAV7KIM'?}
    Flag_Inaccurate -->|Đúng| Prompt_Inaccurate[Thêm hướng dẫn sinh câu trả lời SAI]
    Flag_Inaccurate -->|Sai| Prompt_Accurate[Thêm hướng dẫn sinh câu trả lời ĐÚNG]
    
    Prompt_Inaccurate --> LLM_2[Gọi LLM lần 2 để tổng hợp câu trả lời]
    Prompt_Accurate --> LLM_2
    LLM_2 --> AI_Ret
    
    %% Nhánh không gọi Tool
    Tool_Req -->|Không| AI_Ret[Đóng gói câu trả lời của LLM]
    
    AI_Ret --> Metric_AI[Ghi nhận OpenTelemetry Metrics AI] --> Ret_AI([Trả về câu trả lời cho client])
```

## Chi tiết các luồng xử lý chính

### 1. Luồng Lấy Đánh Giá & Điểm Số
* **`GetProductReviews`**: Truy vấn danh sách đánh giá từ cơ sở dữ liệu Postgres bằng hàm `fetch_product_reviews_from_db`, ghi nhận số lượng review nhận được vào OpenTelemetry metric `app_product_review_counter`, sau đó trả về danh sách dưới định dạng protobuf.
* **`GetAverageProductReviewScore`**: Truy vấn điểm đánh giá trung bình từ database và trả về.

### 2. Luồng Trợ lý AI (`AskProductAIAssistant`)
* **Bước 1: Chống chịu sự cố (Fault Tolerance)**
  * Kiểm tra Feature Flag `llmRateLimitError`. Nếu được bật bởi Ban Tổ Chức, hệ thống giả lập lỗi Rate Limit (429) với tỷ lệ 50% và trả về thông báo lỗi thân thiện để tránh làm sập client.
* **Bước 2: Gọi LLM Lần 1 (Giai đoạn Đề xuất Hành động)**
  * Tạo kết nối đến LLM (theo API OpenAI tương thích). Gửi kèm danh sách `tools` định nghĩa trong mã nguồn (gồm `fetch_product_reviews` và `fetch_product_info`).
* **Bước 3: Thực thi Tool (nếu LLM yêu cầu)**
  * Nếu LLM quyết định cần gọi tool, hệ thống sẽ thực thi các hàm truy vấn DB (`fetch_product_reviews` hoặc `fetch_product_info`) cục bộ.
  * Kết quả trả về từ tool được chuyển thành văn bản JSON và chèn vào lịch sử hội thoại (`messages`).
* **Bước 4: Gọi LLM Lần 2 (Giai đoạn Tổng hợp câu trả lời)**
  * Hệ thống kiểm tra Feature Flag `llmInaccurateResponse` trên sản phẩm test (`L9ECAV7KIM`) để điều hướng hành vi sinh phản hồi (sinh câu trả lời đúng hay cố tình sai lệch).
  * Gọi LLM lần 2 để đúc kết câu trả lời cuối cùng dựa trên các dữ liệu thực tế thu thập được từ tool.
* **Bước 5: Trả kết quả**
  * Tăng chỉ số metric `app_ai_assistant_counter` và trả câu trả lời cho Client.
