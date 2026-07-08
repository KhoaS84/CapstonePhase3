# ADR 0001: Tích hợp mô hình GPT-4o-mini làm mô hình LLM chính

* **Trạng thái:** Đề xuất (Draft)
* **Tác giả:** Khoa (Leader AIE1)
* **Ngày tạo:** 2026-07-08

---

## 1. Bối cảnh (Context)
Dịch vụ tóm tắt đánh giá sản phẩm (`product-reviews`) hiện đang sử dụng một dịch vụ Mock LLM (`llm`). Dịch vụ mock này chỉ trả về các phản hồi giả lập được định cấu hình sẵn, không có khả năng hiểu và trả lời ngôn ngữ tự nhiên thực tế của khách hàng. Để đưa sản phẩm vào vận hành thực tế và phát triển Trợ lý mua sắm thông minh (Shopping Copilot), hệ thống cần được tích hợp với một mô hình ngôn ngữ lớn (LLM) thực sự.

Tuy nhiên, việc tích hợp LLM thật phải đối mặt với các ràng buộc về **ngân sách chi phí token** và **chỉ số cam kết chất lượng dịch vụ (SLA Latency)**.

---

## 2. Các phương án xem xét (Alternatives)

### Phương án A: Sử dụng GPT-4o
* **Ưu điểm**: Khả năng suy luận vượt trội, gọi tool cực kỳ chính xác, hiểu ngữ cảnh phức tạp tốt nhất.
* **Nhược điểm**: Chi phí rất đắt ($2.50 / 1M input tokens, $10.00 / 1M output tokens), tốc độ phản hồi trung bình chậm hơn.

### Phương án B: Sử dụng GPT-4o-mini
* **Ưu điểm**: Tốc độ phản hồi rất nhanh, chi phí siêu rẻ ($0.150 / 1M input tokens, $0.600 / 1M output tokens - rẻ hơn 15 lần so với GPT-4o), hỗ trợ Tool Calling tốt.
* **Nhược điểm**: Khả năng suy luận phức tạp kém hơn một chút so với bản lớn gpt-4o.

---

## 3. Quyết định (Decision)
Chúng tôi quyết định chọn **GPT-4o-mini** làm mô hình LLM chính cho dịch vụ `product-reviews` trong tuần 1.

**Lý do chọn lựa:**
1. **Tối ưu chi phí:** Phù hợp với hạn mức ngân sách của Task Force và dễ trình CFO phê duyệt chi tiêu.
2. **Hiệu năng (Latency):** Thời gian phản hồi nhanh giúp hệ thống duy trì chỉ số SLA của storefront tốt hơn.
3. **Đầy đủ tính năng:** Hỗ trợ tốt cơ chế gọi công cụ (tool calling) cần thiết cho Shopping Copilot.

---

## 4. Hệ quả (Consequences)
* **Về mặt kỹ thuật**: Cần cập nhật tệp `deploy/values-aio-llm.yaml` để cấu hình model sang `gpt-4o-mini` và thiết lập các biến môi trường OpenAI API Key qua Kubernetes Secret.
* **Về mặt giám sát**: Cần theo dõi chặt chẽ độ trễ (latency) của API OpenAI trên Jaeger vì các cuộc gọi API mạng ngoài sẽ chậm hơn nhiều so với Mock local.
* **Kế hoạch tiếp theo**: Đo đạc độ chính xác (Fidelity) của model này thông qua script đánh giá tự động ở Ticket 2 để quyết định xem có cần nâng cấp lên model lớn hơn hoặc sử dụng cơ chế Model Routing (định tuyến linh hoạt) hay không.
