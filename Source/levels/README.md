# Bộ 12 màn Bloxorz

Nhóm tự thiết kế các màn này cho bản đầu của đồ án; không sao chép màn của game gốc. Mỗi JSON được dùng chung cho chơi tay, replay và cả bốn solver. Cùng một file tạo cùng `Level` và `initial_state`, không có bàn riêng cho từng thuật toán.

Bộ màn ưu tiên giúp thành viên hiểu và kiểm chứng cơ chế. Bàn nhỏ nên thời gian giữa các solver có thể chỉ chênh lệch rất ít; kết luận hiệu năng phải dựa trên số liệu đo, không dựa vào độ dài witness dưới đây. Nếu bổ sung màn khó sau này, giữ bộ hiện tại để kiểm tra hồi quy và ghi phiên bản bộ benchmark trong báo cáo.

## Cách đọc và điều khiển

Tọa độ `(r,c)` bắt đầu từ 0; hàng tăng xuống dưới và cột tăng sang phải. `UP/DOWN/LEFT/RIGHT` là phím mũi tên. `SWITCH` là Space, chọn cube A/B khi đã tách; nó cũng được tính là một action. Khối tách mặc định chọn A, là destination đầu tiên trong JSON.

| Ký hiệu | Ý nghĩa |
|---|---|
| `.` | Void, không nâng đỡ khối |
| `F` | Sàn thường; start và destination của split nằm trên loại này |
| `G` | Goal; chỉ khối nguyên vẹn đứng U ở đây mới thắng |
| `O` | Fragile; khối nguyên vẹn đứng U sẽ rơi, nằm H/V thì được |
| `B` | Cầu; nâng đỡ chỉ khi bridge group tương ứng enabled |
| `S` | Soft switch; một phần khối/cube mới đè lên là kích hoạt |
| `X` | Heavy switch; chỉ khối nguyên vẹn mới đứng U lên để kích hoạt |
| `T` | Split switch; đứng U lên để teleport và tách |

New Game/Restart đưa mọi cầu và khối về trạng thái ban đầu. Khi thử witness, phải Restart trước; Solve trong GUI từ current state còn benchmark luôn bắt đầu từ initial state.

Cube riêng được đứng trên O hoặc G nhưng không phá O và không thắng G. Công tắc kích hoạt khi **mới đủ điều kiện** so với state trước; nhấn Space, vẽ lại bàn hoặc để một cube đứng yên trên S không kích hoạt lại. Việc đổi cầu được áp dụng sau khi kiểm tra nâng đỡ bằng cấu hình cầu cũ, nên một nước đã rơi không thể được công tắc trong cùng bước cứu.

## Nội dung và mức độ

| File | Mức độ học luật | Cơ chế được dùng trong lời giải | Kết quả dự kiến | Shortest UNIT actions |
|---|---|---|---|---:|
| [basic_01.json](basic_01.json) | Bắt đầu | U → H → U tại goal | FOUND | 2 |
| [basic_02.json](basic_02.json) | Cơ bản | Đường hẹp có khối nằm H và V | FOUND | 7 |
| [fragile_01.json](fragile_01.json) | Cơ bản | Bước đầu buộc nằm qua O; có nhánh đứng O gây rơi | FOUND | 4 |
| [fragile_02.json](fragile_02.json) | Trung bình | Đường ngắn vào O và đường dài tránh O | FOUND | 6 |
| [switch_01.json](switch_01.json) | Trung bình | Soft + TOGGLE; trở về start sau khi mở cầu | FOUND | 8 |
| [switch_02.json](switch_02.json) | Trung bình | Heavy + SET_OPEN; nằm trên X không đủ | FOUND | 4 |
| [split_01.json](split_01.json) | Trung bình | Hai cube phải được điều khiển, rồi ghép lại | FOUND | 11 |
| [split_02.json](split_02.json) | Nâng cao | Hai cube mở cầu cho nhau, cần ít nhất 2 SWITCH | FOUND | 14 |
| [combined_01.json](combined_01.json) | Nâng cao | Soft, fragile, heavy và hai cầu | FOUND | 10 |
| [combined_02.json](combined_02.json) | Nâng cao | Split + cầu; SET_CLOSED đóng đường đã đi qua | FOUND | 16 |
| [no_solution_01.json](no_solution_01.json) | Kiểm tra thất bại | Goal tách khỏi phần bàn khối tới được | NO_SOLUTION | — |
| [no_solution_02.json](no_solution_02.json) | Kiểm tra thất bại | Có chu trình và switch đổi cầu, goal vẫn không tới được | NO_SOLUTION | — |

Các độ dài ở bảng đã được BFS kiểm tra độc lập qua engine và replay; không phải kết quả thực nghiệm thời gian/bộ nhớ. `tests/test_levels.py` tự xác nhận lại khi chạy test. Hai màn vô nghiệm chỉ nhận nhãn này sau khi tìm kiếm duyệt hết tập trạng thái đạt tới, lần lượt 3 và 89 state; không dùng timeout để kết luận.

## Witness để chơi tay, demo và kiểm tra tích hợp

Mỗi dòng là một lời giải ngắn nhất theo UNIT của file tương ứng. Các thuật toán khác có thể trả lời giải khác; điều đó bình thường nếu lời giải vẫn hợp lệ và đúng mục tiêu tối ưu của thuật toán.

```text
basic_01:
RIGHT RIGHT

basic_02:
RIGHT RIGHT DOWN RIGHT DOWN RIGHT RIGHT

fragile_01:
RIGHT RIGHT RIGHT RIGHT

fragile_02 (đường ngắn nhất theo số action):
RIGHT RIGHT RIGHT RIGHT RIGHT RIGHT

switch_01:
UP UP DOWN DOWN RIGHT RIGHT RIGHT RIGHT

switch_02:
RIGHT RIGHT RIGHT RIGHT

split_01:
RIGHT RIGHT RIGHT RIGHT RIGHT UP SWITCH LEFT DOWN RIGHT RIGHT

split_02:
RIGHT RIGHT RIGHT RIGHT SWITCH LEFT LEFT LEFT SWITCH RIGHT UP DOWN RIGHT RIGHT

combined_01:
UP UP DOWN DOWN RIGHT RIGHT RIGHT RIGHT RIGHT RIGHT

combined_02:
RIGHT RIGHT RIGHT SWITCH LEFT LEFT LEFT LEFT LEFT DOWN DOWN RIGHT SWITCH RIGHT RIGHT RIGHT
```

### Vì sao các màn đặc biệt đáng dùng trong video/báo cáo?

**fragile_01:** ở start chỉ RIGHT tạo nước đi hợp lệ. Khối nằm H trên hai ô O, nên người xem thấy rõ fragile vẫn đỡ khối nằm. Các ô phía dưới tạo nhánh có thể đưa khối đứng lên O và rơi; test tìm được nhánh này từ các state đạt tới. Không phải đặt một ô O ở vị trí không bao giờ được sử dụng.

**fragile_02:** đường 6 RIGHT có UNIT cost 6 nhưng FRAGILE_PENALTY cost 12, vì ba lần vào O bị tính 3 thay vì 1. Một đường sạch là DOWN, 9 RIGHT, UP: dài 11 action nhưng weighted cost 11. Do đó đường tối ưu theo số action không tối ưu theo weighted cost. UCS/A* weighted phải ưu tiên chi phí; BFS vẫn tối ưu số action, kể cả khi được yêu cầu báo weighted cost. Không ghi đường 11 action là “BFS kém hơn”; đó là một mục tiêu khác.

**switch_01:** đi UP hai lần để nhấn soft rồi DOWN hai lần trở về đúng start `(4,1)` ở tư thế U, nhưng bridge đã bật. Sau đó RIGHT bốn lần tới goal. Đây là ví dụ trực tiếp cho việc state key phải có bridge flags; visited chỉ dùng `(r,c,o)` sẽ bỏ trạng thái cần thiết khi quay về.

**switch_02:** heavy ở `(1,4)` chỉ mở cầu khi khối đứng U. Vùng bên dưới cho phép đạt một state nằm H/V đè lên heavy khi cầu vẫn tắt. Test xác nhận cả tình huống nằm không kích hoạt và đứng kích hoạt; short witness cho thấy việc đứng lên heavy trước khi đi cầu.

**split_01:** đứng T `(1,4)` đưa A tới `(4,1)`, B tới `(2,5)`. A phải đi tới vùng ghép, rồi SWITCH để B di chuyển. Nếu bỏ mọi hành động SWITCH, duyệt hết đồ thị vẫn không có lời giải. Khi B sang trái tại witness, hai cube ghép thành V; khối lăn xuống rồi vào goal.

**split_02:** A nhấn `a_button` để mở đường B và đóng `return_gate` phía sau. B nhấn `b_button` để mở `a_access` cho A. Cần chọn lại A để vào vùng ghép; BFS với giới hạn tối đa 1 SWITCH đã duyệt hết và xác nhận không có lời giải. Test giữ bằng chứng này, nên sửa màn vô tình tạo lối tắt sẽ bị phát hiện.

**combined_01:** soft phía trên mở entry_gate, sau đó khối nằm qua fragile. Heavy ở `(4,6)` mở exit_gate. Short witness thực sự nhấn cả soft/heavy và dùng O; hai cầu đều cần để đến goal.

**combined_02:** B đi qua return_gate đang bật ở `(2,8)`, rồi nhấn b_button tại `(2,5)`. Công tắc vừa mở a_access vừa SET_CLOSED return_gate phía sau B. Cầu đóng không làm khối rơi vì cả hai cube đều đang ở vị trí còn được nâng đỡ. Witness sau đó ghép và thắng. Màn này minh họa rằng SET_CLOSED là thao tác hợp lệ, không tự đồng nghĩa với thua. Cần lưu cấu hình cầu đầy đủ khi Restart.

### Hai đoạn demo ngắn để phân biệt luật

Đây là các chuỗi kiểm tra luật, **không phải lời giải**. Restart trước mỗi chuỗi.

| Màn | Chuỗi hành động | Điều cần quan sát |
|---|---|---|
| fragile_01 | RIGHT RIGHT DOWN LEFT UP | Bốn bước đầu hợp lệ; UP cuối đưa khối đứng U vào O `(1,3)` và trả LOSS / FRAGILE_UPRIGHT |
| switch_02 | DOWN RIGHT UP RIGHT | Khối nằm H trên `(1,3)`–`(1,4)`, phủ heavy X; gate vẫn tắt |

Sau chuỗi heavy nằm, Restart rồi RIGHT RIGHT: khối đứng U trên X `(1,4)` và gate mới bật. Hai chuỗi này đã được áp qua engine từ initial state, nên nhóm có thể dùng trực tiếp để chuẩn bị video.

Trên fragile_02, UCS và A* với FRAGILE_PENALTY đều đã tìm đường sạch 11 action / cost 11. Khi trình bày thực nghiệm, lấy thời gian/bộ nhớ từ CSV của runner; các thông tin ở đây chỉ xác nhận hành vi và chi phí lời giải.

## Sửa hoặc thêm một màn

1. Giữ schema JSON ở README chính, mỗi G/B/S/X/T phải có cấu hình tương ứng đúng.
2. Start/destination là F thuần; hai destination khác nhau và không kề cạnh.
3. Các bridge IDs được loader sắp xếp tăng dần; không suy ra vị trí flag từ thứ tự object viết trong JSON.
4. Không định nghĩa SET_OPEN và SET_CLOSED cùng trỏ một bridge ở bất kỳ switch nào trong cùng màn. Bản schema này từ chối cấu hình đó; TOGGLE cùng bridge với một kiểu SET vẫn hợp lệ.
5. Kiểm tra loader, solver và replay. Nếu sửa bộ 12 màn, cập nhật witness/test và xóa hoặc tách số liệu thực nghiệm cũ để không trộn dữ liệu của hai phiên bản.
6. Nếu gọi màn là vô nghiệm, phải để một tìm kiếm hoàn tất xác nhận; không dựa vào cảm giác hoặc vượt giới hạn thời gian.

Chạy kiểm tra từ `Source` bằng `python -m pytest tests/test_levels.py`. Các test không hard-code lời giải để dẫn hướng solver: chúng tìm kiếm độc lập rồi kiểm tra độ dài và các sự kiện thực tế của engine.
