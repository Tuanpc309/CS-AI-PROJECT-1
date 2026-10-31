# Kiểm tra độ khó bộ map — 31/10/2026

Đây là lượt khảo sát mới trên **43 map**, dùng chính engine và các solver của
dự án. Không thay đổi map hoặc kết quả thực nghiệm cũ.

- 30 campaign, 12 benchmark và `quiet_01`.
- Mỗi map chạy BFS, DFS, UCS, A* từ initial state với UNIT: **172 lượt**.
- Mỗi cấu hình chạy trong process mới, 5 giây, 256 MiB tracked Python memory;
  thời gian solver không gồm khởi động process. Bật tracemalloc.
- 164 lượt của 41 map có nghiệm đều FOUND và được replay xác minh; 8 lượt của
  hai map vô nghiệm đều NO_SOLUTION. Không có timeout, lỗi hay vượt bộ nhớ.
- Đây là **một lượt/cấu hình** để khảo sát. Không dùng chênh lệch thời gian nhỏ
  này để kết luận thuật toán nào luôn nhanh hơn.

## Campaign đang phân hóa thế nào?

| Nhóm map | Ô có sàn/cơ chế | Lời giải ngắn nhất UNIT | Node BFS mở rộng trước đích | Node A* mở rộng trước đích |
|---|---:|---:|---:|---:|
| 01–06 · Làm quen | 13–48 | 5–14 | 10–112 | 8–109 |
| 07–12 · Căn tư thế | 58–62 | 13–25 | 105–125 | 62–96 |
| 13–18 · Kết nối | 56–57 | 15–29 | 193–220 | 96–181 |
| 19–24 · Phân mảnh | 17–38 | 11–19 | 133–943 | 56–207 |
| 25–30 · Tổng hợp | 44–59 | 30–42 | 1.738–1.812 | 1.421–1.746 |

**24/30 map campaign cần dưới 1.000 node BFS mở rộng.** Lượt UNIT chậm nhất
đo được là UCS ở campaign_26, khoảng 0,802 giây; bộ nhớ đỉnh lớn nhất là BFS
ở campaign_30, 706.776 byte (khoảng 0,674 MiB).

Đây là số node đã mở rộng khi tìm thấy đích, **không phải tổng số trạng thái
reachable**. Thời gian và memory nêu trên có overhead đo tracemalloc và phụ
thuộc môi trường; thông tin môi trường nằm trong `audit.json`.

Những ví dụ cho thấy cần đánh giá nhiều chiều:

- `campaign_24`: tối ưu 19 bước; DFS đi 172 bước. BFS mở rộng 943 node,
  A* 207 node, tức BFS/A* khoảng 4,56. Đây là map hiện tại phân biệt tốt DFS
  với lời giải tối ưu và cho thấy lợi ích heuristic.
- `campaign_21`: tối ưu 15 bước nhưng DFS đi 165 bước, gấp 11 lần.
- `campaign_30`: tối ưu 42 bước; BFS mở rộng 1.812 node, A* 1.739, giảm
  khoảng 4%. `campaign_29` chỉ giảm khoảng 1%. Map có chuỗi lời giải dài
  chưa chắc phân biệt rõ BFS với A*.
- Chương 5 đều có BFS khoảng 1.700–1.800 node: chưa tạo dải quy mô rộng để
  khảo sát khả năng mở rộng hay áp lực bộ nhớ.

## BFS và UCS giống nhau là hợp lý với UNIT

Ở cả 30 campaign, BFS và UCS trả **cùng chuỗi thao tác và số node mở rộng**.
Khi mỗi cạnh đều cost 1, ưu tiên tổng cost của UCS tương đương ưu tiên lớp
độ sâu của BFS; cài đặt hiện tại còn giữ thứ tự FIFO khi hòa cost. Tăng độ khó
map mà vẫn giữ UNIT sẽ không tự tạo khác biệt về nghiệm tối ưu giữa chúng.

Lượt probe mới với cùng FRAGILE_PENALTY cho cả bốn thuật toán:

| Map | Thuật toán | Bước | Cost |
|---|---|---:|---:|
| fragile_02 | BFS | 6 | 12 |
| fragile_02 | DFS | 30 | 42 |
| fragile_02 | UCS | 11 | 11 |
| fragile_02 | A* | 11 | 11 |
| campaign_30 | BFS | 42 | 58 |
| campaign_30 | UCS | 42 | 58 |

`fragile_02` chứng minh đúng khác biệt ít bước và ít cost, nhưng khoảng cách
cost hiện chỉ là 1. `campaign_30` có ô fragile mà vẫn không tạo lựa chọn tốt
hơn bằng cách đi xa hơn. Dữ liệu probe đầy đủ nằm trong `weighted-probes.json`.

## Đánh giá cho nhóm

Đã duyệt toàn bộ đồ thị trạng thái tới được của 43 map, dừng mở rộng tại goal;
không màn nào chạm giới hạn 100.000 state hoặc 5 giây của lượt duyệt cấu trúc.
Campaign có 11–2.540 state, benchmark có 3–446 state. Màn 24 có 2.540 state,
lớn hơn màn 30 có 1.848 state dù màn 30 cần nhiều bước hơn. Dữ liệu độc lập
với số expanded của lượt solver, tại `reachability.json`.

43 cấu hình puzzle khác nhau khi tính cả start/goal, loại ô và cơ chế. Tuy nhiên,
campaign 14/15 chỉ đổi start; 16/17 cũng chỉ đổi start; 26/29 chỉ đổi goal.
Khi chỉ xét hình dạng các ô không phải vực và cho phép xoay/phản chiếu/tịnh tiến,
có 39 silhouette trong 43 map. Xem `structural_diversity.json`.

Bộ hiện tại có ích để chơi, minh họa luật và kiểm tra đúng/sai. Sự lo ngại về
việc chưa đủ phân hóa cho **thực nghiệm hiệu năng** có cơ sở, đặc biệt với
benchmark cơ bản chỉ 2–173 node BFS và hai map vô nghiệm chỉ 3/89 node.

Có thể giữ bộ đang chơi và bổ sung một bộ benchmark riêng gồm nhiều mức quy
mô. Chọn candidate bằng số node mở rộng, số nhánh hợp lệ, chất lượng nghiệm
DFS, tương quan BFS/A* và lựa chọn cost, thay vì chỉ nhãn độ khó hoặc số bước.
Các map nhiều vòng, nhiều lựa chọn có vẻ tiến gần goal nhưng cần quay lại mở
cầu, và split ở vùng rộng có thể tạo tìm kiếm lớn hơn; cần đo để xác nhận.
Nên có map có/không có lợi cho heuristic, giữ các ca vô nghiệm và ghi seed,
phiên bản map cùng giới hạn chạy. Không chọn map chỉ để một solver luôn thắng.

## Dữ liệu và tái lập

- [Ảnh tổng quan 30 campaign](campaign-maps.png) và [13 map bổ sung](extra-maps.png).
- `atlas-data.json`: map và các số liệu gọn để xem trực quan.
- `reachability.json`: thống kê đồ thị tới được, goal là terminal.
- `structural_diversity.json`: đối chiếu hình dạng và cấu hình cơ chế.
- `audit.json`: map, tọa độ, catalog metadata, cấu hình/môi trường và toàn bộ
  SearchResult theo thuật toán, gồm các actions và xác minh replay.
- `runs.csv`: 172 lượt UNIT để mở trong bảng tính.
- `summary.json`: tóm tắt theo chương.
- `weighted-probes.json`: 8 lượt FRAGILE_PENALTY mới trên hai map.

Chạy từ thư mục gốc dự án:

```powershell
.\.venv\Scripts\python.exe results/map-audit-20261031/audit_maps.py
.\.venv\Scripts\python.exe results/map-audit-20261031/weighted_probe.py
```

Hai lệnh chỉ ghi lại các artifact của thư mục khảo sát này. Lưu bản hiện tại
trước nếu muốn so sánh nhiều lần chạy.
