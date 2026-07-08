# ADR 0002: Thiết kế cơ chế Fallback xử lý sự cố kết nối LLM

* **Trạng thái:** Đề xuất (Draft)
* **Tác giả:** Kiên (AIE1) & Khoa (Leader AIE1)
* **Ngày tạo:** 2026-07-08

---

## 1. Bối cảnh (Context)
Khi tích hợp LLM thật (OpenAI/Bedrock) vào dịch vụ `product-reviews`, toàn bộ hệ thống storefront sẽ phụ thuộc vào tính sẵn sàng của API ngoài này. Tuy nhiên, các API này có nguy cơ gặp sự cố bất cứ lúc nào (lỗi kết nối mạng, vượt quá giới hạn cuộc gọi - Rate Limit 429, hoặc API sập 500/503). 

Nếu không có cơ chế dự phòng (Fallback), bất kỳ lỗi nào từ LLM cũng sẽ khiến cuộc gọi gRPC `AskProductAIAssistant` bị lỗi, dẫn đến việc giao diện web của storefront bị đơ hoặc báo lỗi hệ thống với người dùng, trực tiếp làm hỏng trải nghiệm khách hàng (UX) và vi phạm SLO.

---

## 2. Giải pháp Đề xuất (Proposed Solution)
Chúng tôi triển khai cơ chế **Fallback & Chống chịu lỗi (Fault Tolerance)** ngay trong dịch vụ `product-reviews` tại hàm `get_ai_assistant_response`:

1. **Thiết lập Timeout nghiêm ngặt**: Cấu hình thời gian chờ tối đa khi gọi OpenAI API là **8 giây** (bảo vệ SLA tổng thể của storefront).
2. **Khối bắt lỗi ngoại lệ (Try-Except Block)**: Bọc toàn bộ các bước gọi API của OpenAI để bắt tất cả các lỗi kết nối, quá thời gian chờ, lỗi xác thực hoặc lỗi Rate Limit.
3. **Cơ chế Phản hồi Dự phòng (Fallback response)**:
   * Nếu cuộc gọi LLM thất bại ở bất kỳ bước nào, hệ thống sẽ tự động chuyển sang trả về một câu thông báo thân thiện được định nghĩa trước: *"Hệ thống trợ lý AI đang bận xử lý thông tin. Quý khách vui lòng thử lại sau ít phút."* hoặc lấy nội dung tóm tắt tĩnh đã được cache trước trong database.

---

## 3. Lợi ích & Đánh giá (Benefits & Evaluation)
* **Độ tin cậy (Reliability)**: Giữ cho storefront luôn hoạt động bình thường kể cả khi LLM bên thứ ba bị sập hoàn toàn.
* **Thời gian phản hồi (Latency)**: Khống chế thời gian chờ tối đa nhờ cài đặt timeout, không để request bị treo vô hạn.
* **Hệ quả**: Khách hàng sẽ nhận được thông báo lỗi thân thiện thay vì thấy một trang web bị đơ hay lỗi server trắng xóa.
