# Bloxorz Solver — hướng dẫn chạy và đọc mã

## Giao diện in-game mới — Isometric Web UI

Đã bổ sung giao diện trình duyệt responsive: Three.js voxel 3D, nền biome/kính mờ,
HUD số bước và sao, passcode, Pause/Restart, Undo 5 lần, D-pad xoay 45°,
vuốt theo góc nhìn, modal thắng/thua và chọn màn. Luật chơi vẫn chạy bằng
engine Python hiện tại; Three.js được lưu cùng source, không cần Node.js/npm để chơi.

Bản hiện tại lấy giao diện nhánh `kazu-bloxorz-web` làm nền, thu gọn HUD và
khoảng cách. Nút **Lời giải** mở bảng BFS/DFS/UCS/A*, chuỗi bước có thứ tự,
giải thích cách tìm đường, số liệu đo và phát lại. Có thể chạy cả bốn từ cùng
snapshot, đổi UNIT/FRAGILE_PENALTY và xem lại từng kết quả. Chi tiết ở
[hướng dẫn lời giải](web/README.md#lời-giải-bfs-dfs-ucs-a).

Từ thư mục chứa `Source`:

```powershell
.\.venv\Scripts\python.exe Source\main.py --web
```

Hoặc dùng Python đã cài: `python Source/main.py --web`. Trình duyệt tự mở
`http://127.0.0.1:8000`. Giữ terminal chạy trong lúc chơi. Đọc
[hướng dẫn UI và cấu trúc mã](web/README.md) để chạy trên điện thoại cùng Wi-Fi,
đổi cổng, chọn màn và chỉnh theme/animation. Giao diện Tkinter và solver cũ vẫn
mở bằng lệnh không có `--web` như bên dưới.

Game mặc định mở [campaign 30 màn / 5 biome](web/levels/README.md), có rừng voxel,
mây hoàng hôn, phố neon, hang pha lê và miền sao. Three.js dựng cảnh 3D với
camera orbit 360°, chuột phải/hai ngón để xoay; phím hướng theo camera.
Khối lăn quanh cạnh đáy đúng 90° trong 220 ms, sau đó nén nhẹ 50 ms, phát bụi
pixel và làm ô đỡ lún nhẹ khi đứng. Cỏ/cây dùng vertex shader gió neo gốc với
InstancedMesh; có hook âm thanh/haptic và hỗ trợ reduced motion.

Màn hình đầu cho chọn/tạo hồ sơ với 6 avatar pixel. LocalStorage giữ riêng màn
đã mở, sao, số bước và thời gian tốt nhất cho từng người; đổi người chơi ở
header hoặc Pause. Tiến trình cũ được nhập một lần vào `Hành trình cũ`. Đây là
hồ sơ local theo trình duyệt, chưa đồng bộ cloud. Đọc
[cấu trúc hồ sơ và hook VFX](web/PROFILES-AND-VFX.md) để tích hợp thêm.

`Khoảng lặng` và 12 màn benchmark nằm trong mục bổ sung. Bộ Python đã qua
**249 test trên Windows**, không có skip; **84 test Node** kiểm tra hình học,
vòng đời animation, camera, gesture, hồ sơ, đồng hồ và gió. Kiểm tra giao diện thực tế được
ghi ở [UI verification](../docs/ui-verification.md).

Đây là bản triển khai theo kiến trúc nhóm đã chốt: Loader → Controller → Engine, bốn solver cùng gọi Engine, GUI Tkinter hiển thị state và replay. Có luật cơ bản, fragile, cầu, soft/heavy switch, toggle/SET, tách/đổi/ghép cube và bộ 12 màn. Xem `../README.md` để đọc yêu cầu của thầy, thang điểm và phân công đầy đủ; xem `levels/README.md` để lấy chuỗi chơi thử từng màn.

## 1. Môi trường

- Mục tiêu của nhóm: Python 3.13.x trên Windows.
- Bản hiện tại đã kiểm tra bằng **Python 3.12.14, Windows**, Tkinter/Tcl/Tk đi kèm runtime, pytest 9.1.1 và matplotlib 3.11.2. Chưa xác nhận chạy trên Python 3.13 bằng thực nghiệm; nhóm kiểm tra lại trên môi trường nộp và cập nhật ghi chú này.
- Game và solver dùng thư viện chuẩn Python. `pytest` dùng kiểm thử; `matplotlib` dùng vẽ biểu đồ. `requirements-lock.txt` ghi các phiên bản thư viện thực tế của môi trường đã kiểm tra; `requirements.txt` ghi phạm vi tương thích dự kiến.
- Tkinter đi kèm bản Python có hỗ trợ Tcl/Tk; không cài bằng pip. Khi cài Python trên Windows, giữ tùy chọn Tcl/Tk.

## 2. Cài và chạy từ thư mục gốc CS-AI

Mở terminal tại thư mục chứa `Source` và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Source\requirements-lock.txt
.\.venv\Scripts\python.exe Source\main.py
```

Không cần activate môi trường. Trên máy đang có `.venv` đã cài thư viện, chỉ cần lệnh cuối. Game tự tìm `levels` theo vị trí file mã nguồn, không phụ thuộc thư mục mở terminal. Chọn màn lúc khởi động bằng:

```powershell
.\.venv\Scripts\python.exe Source\main.py --level Source\levels\split_02.json
```

Nếu gói nộp chỉ có `Source/` và `Report.pdf`, tạo `.venv` ở thư mục chứa hai mục đó và dùng các lệnh tương tự. Không mang `.venv` của một máy sang máy khác.

## 3. Chơi và giải

1. Chọn màn ở cột bên phải. Đổi màn hoặc **New Game** tải màn đó về trạng thái ban đầu.
2. Bấm vào bàn để nhận phím. **Mũi tên** di chuyển; **Space** đổi cube A/B sau khi tách. Viền đậm chỉ cube đang điều khiển.
3. **Restart** khôi phục vị trí, tư thế, hai cube, cube đang chọn và toàn bộ cầu. Khi thua, cần Restart/chọn màn để tiếp tục.
4. Chọn chi phí **UNIT** hoặc **FRAGILE_PENALTY**, rồi bấm BFS/DFS/UCS/A*. Solver giải từ **trạng thái hiện tại**, giữ nguyên bàn thật trong lúc tìm kiếm.
5. Kết quả hiện status, chuỗi action, độ dài, chi phí, số lần di chuyển/đổi cube, thời gian, peak memory Python và expanded nodes. Cột phải có thanh cuộn để đọc đủ kết quả khi cửa sổ thấp.
6. **Replay** trở về đúng snapshot đã giải và thực hiện mỗi action qua engine, khoảng 250 ms/bước. Chơi thêm một bước hợp lệ, Restart hoặc đổi màn sẽ xóa lời giải cũ.

Trong khi Solve/Replay, các thao tác thay đổi phiên bị khóa; cửa sổ vẫn phản hồi và có thể đóng. Đóng cửa sổ sẽ dọn worker. Không có nút Cancel trong bản đầu.

| Ô | Luật |
|---|---|
| F | Sàn thường |
| G | Khối nguyên vẹn đứng U trên G mới thắng; cube đứng G chưa thắng |
| O | Khối nguyên vẹn đứng U sẽ rơi; nằm H/V và cube được nâng đỡ |
| B | Chỉ nâng đỡ khi nhóm cầu tương ứng bật |
| S | Soft: một phần khối/cube mới đè lên sẽ kích hoạt |
| X | Heavy: chỉ khối nguyên vẹn đứng U mới kích hoạt |
| ( ) | Split: đứng U để tách tới hai vị trí F đã cấu hình |
| Khoảng trống | Khối chạm vào sẽ rơi |

Thử `basic_01`: RIGHT, RIGHT để thắng. Thử `switch_01`: UP, UP, DOWN, DOWN rồi RIGHT bốn lần. Thử các màn split theo witness trong `levels/README.md`.

## 4. Hai cách tính chi phí

- **UNIT:** mọi action, kể cả SWITCH, có cost 1. BFS tối ưu số action; UCS/A* cũng tối ưu cost này. DFS không bảo đảm lời giải ngắn nhất.
- **FRAGILE_PENALTY:** action hướng có cost 3 nếu footprint mới chiếm thêm ô O, còn lại cost 1; SWITCH luôn 1. Không phạt lại cube đứng yên trên O. UCS/A* tối ưu tổng cost; BFS/DFS vẫn duyệt theo quy tắc của mình và chỉ báo thêm cost.

`fragile_02` cho thấy khác biệt: 6 RIGHT có weighted cost 12; DOWN + 9 RIGHT + UP dài 11 nhưng cost 11. Benchmark weighted chỉ so UCS/A*; không diễn giải độ dài nhỏ hơn thành cost tốt hơn.

## 5. Chạy kiểm tra

Từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest Source\tests -q
```

Bộ kiểm tra gồm engine/loader, bốn solver và cost/heuristic, đặc tính của 12 màn, vòng đời controller, worker spawn thật và GUI thật. Kiểm tra GUI tạo cửa sổ ẩn; máy không có Tcl/Tk hoặc display sẽ báo skip cho phần đó. Bản Windows hiện tại chạy toàn bộ **249 test, không có skip**. Ghi chép xác minh nằm ở `../docs/verification.md`.

Nếu môi trường hạn chế không cho ghi thư mục temp mặc định, thêm `--basetemp` trỏ vào một **thư mục mới, riêng cho test trong workspace**. Pytest sẽ quản lý và có thể xóa nội dung thư mục đó khi chạy lại, nên không chọn thư mục chứa tài liệu/mã của nhóm.

## 6. Chạy thực nghiệm và biểu đồ

Từ thư mục gốc chuyển vào Source:

```powershell
cd Source
..\.venv\Scripts\python.exe -m experiments.run_all --output ../results/raw
..\.venv\Scripts\python.exe -m experiments.plot_results --input ../results/raw/runs.csv --output ../results
```

Mặc định: 12 màn × (4 thuật toán UNIT + UCS/A* weighted) × 3 lượt = **216 lượt**. Mỗi lượt dùng process mới, 30 giây và peak Python memory tối đa 256 MiB theo kiểm tra định kỳ. Tạo:

| File/thư mục | Nội dung |
|---|---|
| results/raw/runs.csv | Các metrics riêng của từng lượt |
| results/raw/run_details.json | Chuỗi action, thông báo, cấu hình và kết quả kiểm tra replay |
| results/raw/metadata.json | Python, hệ điều hành, packages, ngân sách và cách đo |
| results/tables/*_summary.csv | Median ba lượt của mỗi cấu hình hoàn tất đúng dự kiến |
| results/plots/*.png | Bốn biểu đồ UNIT và một biểu đồ weighted cost |

Runner ghi đè dữ liệu cùng thư mục output. Khi sửa màn/thuật toán hoặc muốn giữ lần đo cũ, chọn output khác. Ví dụ chạy thử ít lượt:

```powershell
..\.venv\Scripts\python.exe -m experiments.run_all --levels basic_01 split_01 --algorithms BFS ASTAR --policies UNIT --runs 1 --output ../results/quick/raw
..\.venv\Scripts\python.exe -m experiments.plot_results --input ../results/quick/raw/runs.csv --output ../results/quick
```

NO_SOLUTION sau khi duyệt hết là kết quả hợp lệ của hai màn vô nghiệm, có time/memory/expanded nhưng không có length/cost. TIMEOUT và MEMORY_LIMIT chưa kết luận vô nghiệm. ERROR cần xem metadata. Failure/thiếu lượt giữ nguyên status, không được tổng hợp thành số 0. Guard lỗi trước khi thu metrics thì CSV để trống các metrics đó.

Time chính = preprocessing + search, bao gồm truy vết, không gồm load JSON, khởi động process, render và kiểm tra replay. Memory đo bằng tracemalloc là peak **Python allocations**, gồm bảng heuristic, không phải tổng RAM tiến trình. Expanded là lần lấy node hợp lệ, chưa là goal, để sinh successors; heap entry cũ bị bỏ không tính. So sánh trên cùng bộ màn/cấu hình và máy.

## 7. Đọc mã theo vai trò

| Thành viên | File chính | Điểm cần hiểu khi bàn giao |
|---|---|---|
| N1 | main.py, controller.py, worker.py | Snapshot, phase phiên, worker queue, replay, reset đầy đủ, kết quả cũ |
| N2A | gui.py, solvers/bfs.py, solvers/dfs.py | Canvas phản ánh state; BFS queue; DFS stack và thứ tự push đảo |
| N2B | solvers/common.py, ucs.py, astar.py, heuristics.py, experiments/ | Cost, best_g, parent, heap, heuristic, budget và metrics |
| N3A | models.py, loader.py, geometry.py, engine.py | State/key bất biến, schema, 12 phép lăn và public transition |
| N3B | advanced.py, levels/ | Switch mới nhấn, parity/SET, support toàn bộ cube, split/merge |

`models.py` là hợp đồng chung. `State` chứa cả bridge flags và active cube, được dùng trực tiếp làm key. `Level` là cấu hình cố định. Không đặt luật di chuyển trong GUI/solver. Hướng dẫn kỹ thuật và phần báo cáo cho từng người nằm ở `../docs/report-parts/`.

Các API để dùng trong script/chương trình khác (mở Python tại Source):

```python
from loader import load_level
from models import Action, Algorithm, CostPolicy, SearchConfig
from engine import transition
from solvers import solve

level, start = load_level("levels/basic_01.json")
step = transition(level, start, Action.RIGHT)
result = solve(level, start, Algorithm.ASTAR,
               SearchConfig(cost_policy=CostPolicy.UNIT))
print(result.status.value, result.actions, result.solution_cost)
```

`transition` chỉ trả `next_state` với VALID/WIN; LOSS/INVALID_ACTION trả None và không sửa input. Loader có `level_from_dict` cho kiểm tra trong bộ nhớ. `validate_state` kiểm tra một snapshot mà không chạy lại effects. Solver không dùng expected_status để tìm kiếm; manifest dự kiến chỉ giúp runner nhận ra kết quả bất thường.

## 8. Giới hạn và việc hoàn thiện bản nộp

- GUI Tkinter là góc nhìn 2D và replay từng bước. Giao diện web Kazu có bàn 3D,
  animation lăn/rơi, Undo và bảng BFS/DFS/UCS/A* cùng metrics/phát lại;
  chưa có editor hoặc lưu/khôi phục phiên đang chơi sau khi tải lại trang.
- Bộ 12 màn nhỏ để kiểm chứng cơ chế. Chênh lệch thời gian rất nhỏ không đủ để kết luận một thuật toán luôn nhanh hơn; muốn phân tích quy mô lớn cần thêm bộ màn và ghi riêng phiên bản thực nghiệm.
- Ngưỡng memory kiểm tra định kỳ là ngưỡng mềm, có thể bị vượt giữa hai lần kiểm tra. Watchdog ngoài worker dùng để tránh treo, không thay số liệu tìm kiếm.
- Source và dữ liệu đo không thay cho báo cáo/video. Nhóm vẫn phải hiểu mã, kiểm tra trên Python/máy nộp, điền tên/MSSV/phân công thực tế, viết Report.pdf, nguồn tham khảo/phụ lục dùng AI và quay video theo đề.

## 9. Xử lý lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `python` mở Store hoặc không nhận lệnh | Cài Python có Tcl/Tk và PATH; hoặc dùng `py -3.13` thay `python` ở bước tạo venv |
| Thiếu pytest/matplotlib | Cài bằng đúng Python trong `.venv`, theo requirements-lock.txt |
| Thiếu `_tkinter`/Tcl/Tk | Sửa/cài lại Python có Tcl/Tk; game cần GUI thật |
| Phím mũi tên chỉ chọn dropdown | Bấm bàn chơi để lấy focus |
| Không thấy hết metrics | Cuộn cột bên phải hoặc tăng chiều cao cửa sổ |
| LevelFormatError | Kiểm tra JSON/schema; lỗi tải không làm mất phiên đang chơi |
| Không Replay sau khi chơi thêm | Solve lại từ current state hoặc Restart rồi Solve |
| Chữ tiếng Việt sai trong terminal cũ | Dùng `python -X utf8 ...`; CSV/JSON/Markdown đã ghi UTF-8 |

Khi báo lỗi cho đồng đội, gửi file màn, phiên bản source, state/chuỗi action, kết quả mong đợi và thông báo thực tế.
