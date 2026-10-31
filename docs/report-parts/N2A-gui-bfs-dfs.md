# N2A — GUI, BFS và DFS stack

## GUI

`BloxorzApp` vẽ board từ Level/current State. U là một ô, H/V là hai ô; cube A/B có màu riêng và active có viền đậm. Ô đặc biệt có ký hiệu cùng màu; cầu tắt dùng nét đứt. Cột phải cuộn được khi kết quả dài.

Nút/phím chỉ chuyển yêu cầu sang controller. Tick50ms polling kết quả worker và tiến replay; worker không vẽ Canvas. Solve từ current state, benchmark từ initial state. Khi SOLVING/REPLAYING, khóa thao tác thay đổi phiên. Kiểm tra focus: khi dropdown nhận phím, mũi tên chọn mục; bấm bàn để chơi.

## BFS và DFS

Đọc `solvers/common.py` trước để hiểu successor và parent chung. BFS dùng deque FIFO, ghi nhận state khi thêm frontier; mọi state key chứa đủ bridge/split nên không bỏ đường cần quay lại vị trí cũ. UNIT có cost1 nên tầng BFS đầu tiên tới goal có ít action nhất.

DFS dùng list stack, không recursion. Push successors theo thứ tự đảo của UP/DOWN/LEFT/RIGHT/SWITCH để pop theo quy ước. Giữ visited và parent để tránh chu trình. DFS có thể tìm nhanh một đường dài; không hứa tối ưu. Khi policy weighted, BFS/DFS báo cost của đường tìm được nhưng không đổi mục tiêu duyệt thành tối ưu cost.

## Bàn giao và báo cáo

Chạy tests solver/GUI, demo cả bốn nút, trạng thái thua/thắng và Replay. Viết pseudocode BFS/DFS từ mã thật, giải thích frontier/visited/parent và điều kiện dừng. Dùng `split_02` hoặc `combined_02` để đối chiếu độ dài DFS với BFS trong bảng kết quả thật; không suy luận DFS luôn nhanh/chậm từ một màn.

Nếu sửa màu/bố cục, giữ ký hiệu và hiển thị đủ status/metrics. Nếu sửa BFS/DFS, replay mọi lời giải và đối chiếu các kiểm tra tối ưu UNIT trước bàn giao N1.
