# Kết quả thực nghiệm bản hiện tại

Đã chạy12 màn ×6 cấu hình ×3 lượt = **216 lượt**, Python3.12.14 trên Windows. Có180 FOUND và36 NO_SOLUTION đúng dự kiến;180 lời giải đều được phát lại kiểm tra. Cả72 cấu hình đủ ba lượt và COMPLETE. Môi trường đầy đủ/timestamp ở [metadata.json](raw/metadata.json); xem [runs.csv](raw/runs.csv) và [run_details.json](raw/run_details.json) để kiểm tra từng lượt.

## Tệp dùng trong báo cáo

| Nội dung | Tệp |
|---|---|
| Tổng hợp tất cả | [all_summary.csv](tables/all_summary.csv) |
| Bốn thuật toán UNIT | [unit_summary.csv](tables/unit_summary.csv) |
| UCS/A* weighted | [weighted_summary.csv](tables/weighted_summary.csv) |
| Cách đọc statuses/median | [tables/README.md](tables/README.md) |
| Total time | [unit_total_time.png](plots/unit_total_time.png) |
| Peak Python memory | [unit_peak_memory.png](plots/unit_peak_memory.png) |
| Expanded nodes | [unit_expanded_nodes.png](plots/unit_expanded_nodes.png) |
| Độ dài lời giải | [unit_solution_length.png](plots/unit_solution_length.png) |
| Weighted cost | [weighted_solution_cost.png](plots/weighted_solution_cost.png) |

## Một vài kết quả để cả nhóm hiểu

Giá trị time dưới đây là median ba lượt và đã làm tròn; dùng CSV gốc khi làm bảng đầy đủ.

| Màn / policy | Thuật toán | Actions | Cost | Expanded | Total time (s) |
|---|---|---:|---:|---:|---:|
| basic_01 / UNIT | UCS | 2 | 2 | 2 |0.000504|
| basic_01 / UNIT | A* | 2 | 2 | 2 |0.000687|
| fragile_02 / UNIT | BFS | 6 | 6 | 30 |0.006537|
| fragile_02 / UNIT | A* | 6 | 6 | 6 |0.001899|
| fragile_02 / FRAGILE_PENALTY | UCS | 11 | 11 | 40 |0.010230|
| fragile_02 / FRAGILE_PENALTY | A* | 11 | 11 | 29 |0.007839|
| split_02 / UNIT | BFS | 14 | 14 | 139 |0.036861|
| split_02 / UNIT | DFS | 129 | 129 | 197 |0.051083|
| split_02 / UNIT | A* | 14 | 14 | 91 |0.024605|
| combined_02 / UNIT | BFS | 16 | 16 | 173 |0.044000|
| combined_02 / UNIT | DFS | 47 | 47 | 90 |0.020534|

Ở basic_01, A* có cùng expanded với UCS nhưng thêm tiền xử lý nên total time lớn hơn trong lượt đo này. Ở fragile_02/split_02, heuristic giúp giảm expanded. DFS ở combined_02 tìm nhanh hơn BFS nhưng lời giải dài hơn; ở split_02, DFS vừa dài vừa mở rộng nhiều hơn. Các ví dụ này giải thích vì sao cần báo cả tài nguyên và chất lượng lời giải, không chỉ một cột thời gian.

Đường6 RIGHT của fragile_02 có weightedcost12 dù UNITcost6. UCS/A* weighted chọn đường11action/cost11. Đây là khác biệt mục tiêu tối ưu; không so cost ở hai policy như cùng một đại lượng.

Các màn nhỏ nên time dưới0.001s dễ chịu nhiễu. Không kết luận A* luôn nhanh hơn hoặc DFS luôn tệ hơn. Hai màn vô nghiệm có time/memory/expanded thật; length/cost để trống và biểu đồ ghi NO SOL. Peak memory là tracemalloc Python allocations, không phải toàn bộ RAM tiến trình. Muốn thêm màn khó, đo vào thư mục mới để giữ bằng chứng của bản hiện tại.
