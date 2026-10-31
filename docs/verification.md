# Xác minh bản triển khai

Ghi nhận tại workspace CS-AI ngày 14/10/2026. Đây là bằng chứng kiểm tra bản mã hiện tại, không phải bảo đảm mã sau này hoặc máy khác cho cùng thời gian. Mục tiêu Python 3.13.x chưa được chạy tại môi trường hiện tại.

## Môi trường và kiểm tra tự động

Python 3.12.14 trên Windows; môi trường riêng `.venv` ở gốc dự án. pytest 9.1.1, matplotlib 3.11.2 và các thư viện phụ thuộc được ghi ở Source/requirements-lock.txt. Tkinter có Tcl/Tk trong runtime.

Lệnh kiểm tra từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest Source\tests --basetemp tmp\pytest-full-03 -q
```

**Kết quả: 129 passed, không có skip.** Basetemp dùng một thư mục mới trong workspace vì temp mặc định của sandbox không cho pytest tạo file. Chỉ dùng đường dẫn riêng cho test; pytest có thể xóa thư mục đó khi chạy lại.

| Nhóm test | Số ca | Bằng chứng chính |
|---|---:|---|
| engine + loader | 59 | 12 phép lăn, support/goal/fragile, switch/bridge/split/merge, input và JSON lỗi |
| solvers | 32 | Mọi màn replay đúng, UNIT optimality, weighted cost, heuristic consistency, budget/errors, UCS stale/A* reopen, tổng hợp statuses |
| levels | 22 | Cơ chế dùng thật trong lời giải, hai màn vô nghiệm, split_02 cần≥2 SWITCH |
| controller | 10 | Loss/invalid, reset toàn state, snapshot/counter replay, busy guard, tải lỗi không mất phiên |
| worker | 4 | Mỗi solver chạy Windows spawn thật, queue trả result, cleanup idempotent |
| GUI | 2 | Tk root thật ẩn; vẽ12 màn, input/win/restart, async solver và replay/control states |

GUI tests dùng một Tk root cho vòng đời module và reset phiên trước mỗi test, giống một ứng dụng thật. Không gọi native automation của các ứng dụng khác. Kiểm tra này xác nhận widgets và luồng tương tác; nhóm vẫn nên dùng trực tiếp để đánh giá độ dễ đọc trên màn hình/máy nộp.

## Thực nghiệm chính thức của bản hiện tại

Chạy `experiments.run_all` mặc định rồi `experiments.plot_results`, output ở results/raw, tables, plots. Mỗi lượt là process spawn mới, ngân sách 30 s/256 MiB, có tracemalloc; replay sau phép đo. Môi trường và timestamp cụ thể nằm ở results/raw/metadata.json.

- 216 rows: 180 FOUND và 36 NO_SOLUTION; tất cả status đúng expected_status.
- 180 lời giải FOUND đều được replay xác nhận qua engine, kiểm tra cả action length/count/cost.
- 72 cấu hình, mỗi cấu hình 3 lượt; tất cả COMPLETE, metrics xác định không mâu thuẫn; không có TIMEOUT/MEMORY_LIMIT/ERROR.
- Có ba CSV summary và năm PNG. Đã xem trực quan các biểu đồ để kiểm tra tiêu đề, đơn vị, legend, labels và đánh dấu NO SOL thay cho length/cost bằng 0.
- Hai màn vô nghiệm được duyệt hết, không suy ra vô nghiệm từ timeout. Các test đồ thị độc lập xác nhận 3 và 89 state đạt tới tương ứng.

## Giới hạn của bằng chứng

Bộ12 màn nhỏ, chủ yếu kiểm chứng cơ chế; không đủ để kết luận ưu thế chung của một thuật toán ở quy mô lớn. Time có overhead tracemalloc và nhiễu máy; peak chỉ là Python allocations. Memory limit là ngưỡng mềm kiểm tra định kỳ. Chưa kiểm tra Python3.13 thực tế, chưa làm Report.pdf/video hoặc chạy trên máy giảng viên. Khi thay source/màn/cấu hình, cập nhật ghi chép và tách dữ liệu cũ trước đo lại.
