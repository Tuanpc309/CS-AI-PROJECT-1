# Cách đọc kết quả thực nghiệm

Số lượt dự kiến mỗi cấu hình: 3. Có 72 cấu hình, 0 cấu hình chưa COMPLETE.

COMPLETE: đủ lượt, mọi status đúng expected_status, metrics xác định ổn định. Chỉ nhóm này có median.
INCOMPLETE: thiếu lượt, có TIMEOUT/MEMORY_LIMIT/ERROR hoặc status trái dự kiến; xem status_counts.
INCONSISTENT: các lượt hoàn tất nhưng length/cost/expanded không ổn định; điều tra trước khi dùng báo cáo.

NO_SOLUTION đúng dự kiến là một lượt hoàn tất hợp lệ, có time/memory/expanded; length/cost để trống.
Ký hiệu x trên biểu đồ không phải kết quả bằng 0. NO SOL là không tồn tại length/cost; các nhãn khác là kết quả thiếu/thất bại.
Thời gian chính = preprocessing + search. Peak memory chỉ là Python allocations theo tracemalloc; không phải tổng RAM tiến trình.
Các giá trị UNIT và FRAGILE_PENALTY tối ưu mục tiêu khác nhau. So UCS/A* theo cùng policy.

Dữ liệu gốc và environment nằm trong results/raw/runs.csv, run_details.json và metadata.json.
