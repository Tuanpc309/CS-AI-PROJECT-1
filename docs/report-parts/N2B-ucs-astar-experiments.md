# N2B — UCS, A*, cost, heuristic và thực nghiệm

## Thuật toán và cost

UCS chọn g nhỏ nhất; A* chọn g+h. Heap có counter để tie-break ổn định mà không so State. `best_g` chỉ cập nhật khi tìm đường rẻ hơn, parent được thay theo đường mới; heap entry cũ bị bỏ trước kiểm tra goal. A* cho phép reopen. Positive cost giúp parent không tạo chu trình.

UNIT cost1. FRAGILE_PENALTY xét `occupied(next)-occupied(old)` có O thì cost3 cho action hướng; SWITCH1. Ví dụ `fragile_02`: shortest6 weightedcost12, đường11 weightedcost11. Cần trình bày đồng thời length và cost.

## Lập luận heuristic

Đọc `heuristics.py` cùng mục10 README chính. Tạo graph mỗi ô non-void, cạnh1/2 ô theo trục giá1, cho cầu/fragile như sàn và bỏ điều kiện ô giữa. Với split, thêm cạnh từ mọi ô có thể thuộc footprint trước lượt đứng T đến mỗi destination với giá1; lăn+teleport xảy ra cùng action. Reverse BFS từ goal cho khoảng cách d; h(state)=max d của footprint.

Mỗi ô cũ p ánh xạ được tới ô mới q mà p=q hoặc có cạnh relaxed p→q trong một bước. Vì vậy d(p)≤1+d(q), h(s)≤1+h(s′)≤cost+h(s′). Goal có h0. h nhất quán nên cũng chấp nhận được. Unreachable lấy N số ô: không có cạnh tới vùng có đường goal; khoảng cách hữu hạn tối đaN−1. Phải giữ cạnh teleport khi sửa graph. Test đối chiếu UCS/A* và h consistency hỗ trợ lập luận; test không thay cho chứng minh.

## Đo và viết nhận xét

Runner216 lượt, process riêng, kiểm tra replay sau phép đo. Đọc definitions time/memory/expanded ở Source/README. Dùng CSV raw cùng metadata và median tables; xem status_counts trước nhận xét. NO_SOLUTION có tài nguyên nhưng không có length/cost; TIMEOUT chưa là vô nghiệm.

Bộ hiện tại nhỏ: A* có thể ít expanded hơn nhưng preprocessing làm total time lớn hơn ở màn rất dễ. So cả time/peak/expanded/length, giải thích theo cấu trúc màn và frontier thay vì kết luận chung. Nếu thêm màn lớn, giữ bộ kiểm chứng và tách kết quả mới; ghi môi trường, phiên bản mã/màn và ngân sách. Gửi N1 bảng, năm PNG, đoạn nhận xét gắn với số liệu và các giới hạn.
