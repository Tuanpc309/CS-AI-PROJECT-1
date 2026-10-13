# Quyết định triển khai

Các quyết định dưới đây là mặc định đã được người dùng duyệt để cả nhóm làm thống nhất. Phân biệt với yêu cầu/thang điểm trong `../AI - Project 1.pdf` được tổng hợp ở README chính. Ngày ghi nhận bản triển khai: 14/10/2026 theo ngày của workspace.

| Phạm vi | Quyết định | File áp dụng |
|---|---|---|
| Kiến trúc | Engine là nguồn luật duy nhất; controller điều phối; GUI chỉ hiển thị/gửi action | engine.py, controller.py, gui.py |
| State | Frozen dataclasses/tuples; full-state key gồm bridge flags, tư thế/cubes và active | models.py |
| Nước đi | UP, DOWN, LEFT, RIGHT; thêm SWITCH khi split; auto-merge khi kề cạnh | geometry.py, engine.py |
| Thứ tự luật | Support cầu cũ → switch mới đủ điều kiện → parity/SET → split → support cầu mới → goal | engine.py, advanced.py |
| Permanent | SET_OPEN/SET_CLOSED mỗi lần kích hoạt; không thêm latch flag | advanced.py, loader.py |
| JSON | Ký tự . F G O B S X T; loader strict, sắp xếp IDs; cấm SET đối nghịch cùng bridge trong một màn | loader.py, levels/ |
| Solver | Tự cài BFS queue, DFS stack, UCS và A* best_g/heap; cùng successor/cost/metrics | solvers/ |
| Chi phí | UNIT và FRAGILE_PENALTY theo newly occupied cells; SWITCH cost1 | solvers/common.py |
| Heuristic | Reverse BFS relaxed cell graph gồm teleport trong cùng một action; max distance footprint | solvers/heuristics.py |
| GUI | Tkinter/ttk + Canvas 2D, sidebar cuộn, ký hiệu cùng màu, phím mũi tên/Space | gui.py |
| Chạy nền | Spawn process riêng, queue trả dữ liệu thuần, polling50ms; chỉ main thread thao tác Tk | worker.py, controller.py |
| Replay | Snapshot hiện tại khi Solve, bước250ms qua engine; phục hồi cả counter snapshot khi phát lại | controller.py |
| Đo | Perf_counter + tracemalloc; time gồm preprocess/search; không gồm spawn/load/replay | solvers/common.py, experiments/ |
| Thực nghiệm | 12 màn, 3 lượt/cấu hình, 216 lượt; 30s và256MiB; status riêng cho failure | experiments/run_all.py |
| Tổng hợp | Chỉ median cấu hình đủ lượt hoàn tất; NO_SOLUTION hợp lệ không có length/cost | experiments/plot_results.py |
| Môi trường | Mục tiêu3.13.x; xác minh hiện tại3.12.14 Windows; khóa package phiên bản thực tế | Source/requirements-lock.txt |

Điều chỉnh khi tích hợp: thêm `validate_state` để input sai trả lỗi rõ; cleanup worker idempotent; lưu counter snapshot cho replay; sidebar cuộn để metrics không tràn; worker hỏng trước phép đo được đánh dấu metrics unavailable. Các điều chỉnh giữ API và mục tiêu đã duyệt.

Khi đổi quy ước, thêm một dòng ghi **ngày, người phụ trách, lý do, phần thay đổi, module/test/README chịu ảnh hưởng và kết quả kiểm tra**. Không chỉ sửa một module khiến GUI và solver hiểu khác nhau. Dữ liệu benchmark cũ phải được giữ riêng nếu thay engine, cost, heuristic hoặc màn chơi.
