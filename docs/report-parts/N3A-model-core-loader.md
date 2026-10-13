# N3A — model, loader và core engine

## State và hình học

`Level` cố định, `State` frozen và tuple; không sửa bridge flags chung giữa các nhánh. MERGED chứa anchor+U/H/V; SPLIT chứa A/B theo identity và active0/1. Cả hai chứa tuple flags theo bridge IDs sorted. State làm key trực tiếp. Ví dụ switch_01 quay về cùng `(r,c,U)` với bridge mới cho thấy key vị trí đơn thuần sai.

U anchor là ô đứng; H anchor là ô trái; V anchor là ô trên. Đọc bảng12 phép lăn trong `geometry.py` và tests tương ứng. Các phép lăn chỉ tính hình học; engine quyết định nâng đỡ/effects/thắng. Hai cube đi vào kề cạnh auto-merge trước kiểm tra tư thế/fragile; diagonal vẫn split.

## Loader và transition

Loader đọc UTF-8 JSON, validate grid/coords/IDs/tile metadata, startF, đúng mộtG, bridge/switch phủ đủ ký hiệu, split destinations là F khác nhau không kề cạnh. Cấm SET đối nghịch cùngbridge trong một màn và sắp xếp IDs. `level_from_dict` hỗ trợ kiểm tra không cần file tạm; `load_level` trả Level và initial State.

Engine validate input; terminalgoal không chuyển tiếp; SWITCH chỉ đổi active; bước hướng gọi geometry rồi advanced. Chỉ VALID/WIN trả state mới; LOSS/INVALID giữ input bất biến. Goal được nâng đỡ nhưng chỉ mergedU mới thắng.

## Bàn giao và báo cáo

Chạy test_engine/test_loader; minh họa U→H→U basic_01, đườngH/V basic_02, ngoài bàn/void và goal. Vẽ một ví dụ footprint và anchor để người đọc hiểu tọa độ. Giải thích vì sao immutable state/full key bảo vệ search. Khi đổi schema/model, trao đổi cả N3B và nhóm2, cập nhật docs/tests trước tích hợp.
