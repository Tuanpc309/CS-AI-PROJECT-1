# N3B — fragile, switch, bridge, split và merge

## Thứ tự luật cần giữ

1. Sau geometry/auto-merge, kiểm tra support toàn bộ footprint theo cầu cũ. Khối đã rơi không được switch trong cùng bước cứu.
2. Xác định switch **mới đủ điều kiện**: eligible(candidate) trừ eligible(old). Soft nhận mọi phần khối/cube; heavy/split chỉ mergedU. Đứng yên/đổi cube không nhấn lại switch.
3. TOGGLE cùng bridge gộp theo parity; SET_OPEN/CLOSED áp sau và ghi đè toggle. Permanent trong bản này là SET mỗi lần nhấn, không có latch.
4. Split teleport tới hai F đã cấu hình, active=A; không chạy effects nối tiếp ở destination.
5. Kiểm tra support lại với bridge mới, gồm cả cube inactive; tắt cầu dưới cube inactive làm LOSS. Cuối cùng kiểm tra goal.

Fragile đỡ H/V và cube, nhưng mergedU rơi. Cube vào ô của cube kia là INVALID; hai cube kề cạnh tự ghép H/V. Giữ identity A/B tới lúc ghép; SWITCH có cost1 nên active phải nằm trong state key.

## Kiểm tra và demo

Tests engine có parity, SET precedence, heavy lying, no-repeat switch, support trước/sau effects, inactive cube loss, split vàmerge. Tests levels xác nhận cơ chế thực sự dùng trong lời giải; split_02 không có lời giải nếu giới hạn≤1SWITCH.

Video nên dùng fragile_01, switch_02, split_02 vàcombined_02 theo witness ở levels/README. combined_02 có SET_CLOSED đóng đường phía sau mà không rơi: bridge đóng chỉ gây thua nếu mất support. Restart mọi màn nâng cao phải khôi phục đầy đủ bridge/cube/active.

## Phần viết báo cáo

Giải thích một chuyển trạng thái có events SWITCH_PRESSED/BRIDGE_CHANGED/SPLIT/MERGE, kèm hình trước/sau. Đặt ví dụ thứ tự luật và case cube inactive để người đọc hiểu vì sao advanced làm không gian state rộng hơn. Viết rõ các quy ước nhóm tự chọn trong cases đề chưa chi tiết, đối chiếu với mục4/6 README chính, không trình bày quy ước nội bộ thành lời thầy.
