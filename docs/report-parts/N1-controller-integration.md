# N1 — controller, tích hợp, báo cáo và video

## Hiểu và kiểm tra mã

- `main.py` tạo Tk và app trong main guard để Windows spawn không mở thêm cửa sổ trong worker.
- `GameController` giữ Level, initial/current State, phase, số action và kết quả. GUI gọi controller, controller gọi engine; không tự tính hướng lăn ở controller.
- `begin_solve` chụp current state cùng counter, tạo request ID và worker. Trong khi SOLVING, GUI khóa thao tác đổi phiên. `poll_solver` chỉ nhận kết quả đúng request.
- `SearchJob` lấy queue không chặn, dọn handle sau khi child kết thúc. Đóng app terminate worker đang chạy. Watchdog xử lý worker treo nhưng không bịa metrics.
- Replay khôi phục snapshot và counter, qua engine từng action; không gán thẳng state goal. Restart khôi phục toàn bộ initial state, xóa lời giải.

Chạy `tests/test_controller.py`, `test_worker.py`, `test_gui.py`. Demo load → RIGHT → Solve → Replay → Restart; demo rơi → Restart; demo split/cầu rồi Restart. Kiểm tra closing trong lúc solver chạy khi nhóm sửa phần worker.

## Phần viết báo cáo

Giải thích sơ đồ hệ thống, luồng Load/Move/Solve/Replay/Restart và nguyên tắc một engine chung. Ghi cách cài/chạy ở Source/README, môi trường thật ở results/raw/metadata.json. Nhận phần thuật toán/engine/thực nghiệm từ người phụ trách, rà khớp các định nghĩa state/cost/expanded.

Khung PDF: thông tin nhóm → mục tiêu/luật → mô hình state/action/goal → kiến trúc/engine → bốn thuật toán và cost/heuristic → thiết lập/kết quả/nhận xét thực nghiệm → giới hạn → phân công/tỷ lệ thực tế → tài liệu tham khảo → phụ lục dùng AI và link video. Đối chiếu yêu cầu PDF của thầy trước xuất bản.

## Việc còn lại thuộc bản nộp

Thu tên/MSSV, deadline/nơi nộp thật; viết PDF hoàn chỉnh; quay video GUI với lời/subtitle và upload YouTube công khai; kiểm tra link trong phiên chưa đăng nhập. Các witness demo đã có ở levels/README. Nén Source cùng Report.pdf theo tên MSSV; bỏ .venv/cache/tmp, kiểm tra quy định20MB và chạy lại từ bản sạch.
