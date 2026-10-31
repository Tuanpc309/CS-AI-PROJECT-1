# Bloxorz · Kazu + lời giải thuật toán

Three.js 0.186.1 + HTML/CSS UI overlay; luật chơi và solver chạy bằng Python.
Thư viện Three.js (MIT) được lưu tại `vendor/`, không tải CDN khi chơi.

Bản công khai dùng Pyodide trong Web Worker để chạy cùng engine mà không cần
server Python. Xem [build và triển khai](../../docs/deployment.md). Bản local
bên dưới tiếp tục dùng API HTTP của Python.

## Chạy

Từ thư mục dự án, Python 3.12+:

```powershell
python Source/main.py --web
# Hoặc môi trường có sẵn:
.\.venv\Scripts\python.exe Source/main.py --web --no-browser
```

Mở `http://127.0.0.1:8000`. Cần WebGL2 và server đang chạy, không mở trực tiếp
`index.html`. Không cần Node/npm để chơi. Dùng `--host 0.0.0.0` để thiết bị cùng
LAN truy cập qua IPv4 của máy; mỗi tab có phiên riêng. `--port 8080` đổi cổng,
`--level Source/levels/split_02.json` chọn màn mặc định. Không có `--web` mở GUI
Tkinter và bảng solver cũ.

## Điều khiển

| Thao tác | Kết quả |
|---|---|
| WASD / mũi tên / D-pad | Lăn theo hướng nhìn hiện tại |
| Kéo một ngón trên bàn | Lăn theo trục màn hình gần nhất |
| Giữ chuột phải rồi kéo | Orbit ngang/dọc quanh tâm bàn |
| Kéo hai ngón | Orbit bằng chuyển động tâm của hai tiếp điểm |
| ↶ / ↷ | Xoay camera 90°; hỗ trợ người không dùng chuột phải |
| ◇ | Về góc nhìn ban đầu theo cung ngắn nhất |
| Z / R / Esc | Undo / Restart / Pause |
| Space / Đổi khối | Chọn cube A hoặc B sau khi tách |
| H / ? | Hướng dẫn |

Camera dùng orthographic để giữ chất voxel và kích thước khối ổn định. Azimuth
không giới hạn; polar bị chặn từ 30° tới 71,1° tính từ trục thẳng đứng, camera
luôn trên mặt bàn. Damping độc lập frame rate: `1 - exp(-14 * dt)`. Camera được
lượng tử hóa theo bốn hướng mặt đất để mỗi phím luôn tương ứng một hướng duy
nhất; hướng được chốt khi bắt đầu gửi nước đi. Không đổi hướng giữa một lần lăn.
Mọi thao tác orbit kết thúc mà không sinh thêm nước đi; pointer cancel/lost
capture cũng xóa swipe đang chờ.

Khối lăn cứng quanh cạnh đáy 90° trong 220 ms, `easeInOutQuad`, rồi settle 50 ms
với bụi pixel và tile lún nhẹ khi đứng. State/cầu cũ
được vẽ đến khi chạm đất, sau đó mới rơi hoặc tách khối. Input khóa đến khi toàn
bộ chuyển động kết thúc. Reduced motion bỏ lăn, quán tính và chuyển động nền;
camera vẫn cập nhật góc khi người dùng điều khiển.

## Lời giải BFS, DFS, UCS, A*

Bấm **Lời giải** phía trên thanh Hoàn tác. Bàn chơi tạm dừng để các thuật toán
cùng giải từ một snapshot: vị trí khối, cầu, cube đang chọn và số bước hiện tại.

1. Chọn BFS, DFS, UCS hoặc A*, hoặc **Chạy cả 4** để so sánh lần lượt.
2. Bảng hiển thị trạng thái, số thao tác, cost, tổng thời gian, peak Python memory
   và số node mở rộng. Chọn tên thuật toán trong bảng để xem lại kết quả đã chạy.
3. Phần dưới hiển thị các bước đánh số, gồm cả thao tác đổi cube. Mở **Cách …
   tìm đường** để đọc giải thích của thuật toán đang chọn.
4. **Phát lại** đưa bàn về đúng snapshot đã giải rồi đi từng bước qua engine.
   Có nút dừng; sau khi dừng có thể tiếp tục chơi hoặc phát lại thuật toán khác.

UNIT tính mỗi thao tác là 1. FRAGILE_PENALTY tính thao tác đi vào ô fragile là 3,
còn lại là 1. BFS tối ưu số thao tác; DFS không bảo đảm ngắn nhất. UCS/A* tối ưu
cost đã chọn. Chuỗi hiển thị là đường lời giải, không phải thứ tự duyệt toàn bộ
không gian trạng thái. Hướng trong danh sách theo bàn ở góc nhìn ban đầu;
phát lại tự đặt camera về góc này. Khi tự đi thêm, undo, restart hoặc đổi màn,
kết quả cũ được xóa để tránh phát lại từ sai vị trí.

Mỗi lượt có ngân sách 30 giây, 256 MiB Python tracked memory khi runtime hỗ trợ
đo. TIMEOUT/MEMORY_LIMIT không được kết luận là vô nghiệm. Dấu `—` là chưa có
số liệu; không thay bằng số 0 giả. Bản HTTP chạy solver trong process riêng và
có **Dừng tìm kiếm**. Bản Pages giải trong Web Worker với cùng ngân sách; nút
hủy không hiện vì không thể ngắt Python đồng bộ đang chạy trong worker.

Ván đã xem lời giải FOUND hoặc dùng phát lại là ván có hỗ trợ: không ghi kỷ lục
hay mở khóa trong hồ sơ. Chơi lại để bắt đầu ván tự giải mới. Giao diện giữ bàn
3D, năm biome và hồ sơ của Kazu; HUD/padding được thu gọn, thông tin giải thuật
nằm trong hộp riêng, không che bàn khi chơi.

## Biome và hiệu năng

| Màn | Biome | Cảnh thủ tục |
|---|---|---|
| 1–6 | Floating Pixel Forest | Đảo đá, cỏ, cây voxel, lá pixel |
| 7–12 | Dusk Sanctuary | Gradient cam tím, mây khối, cột đền |
| 13–18 | Misty Neon | Thành phố nhỏ, vệt cyan/tím, mưa billboard |
| 19–24 | Crystal Cavern | Cụm pha lê, sương xanh, mặt nước ngầm phẳng |
| 25–30 | Starlit Void | Mảnh đảo thiên thể, sao pixel, sao băng xa |

`biomes.js` chứa bảng màu và `VoxelEnvironment`. Tất cả cây/đá/mây/cột được
gom vào một `InstancedMesh`; tọa độ lấy từ seed ID của level để tái lập được.
Particles dùng chung CanvasTexture 8×8 với NearestFilter và Sprite quay mặt về
camera. Không dùng texture ảnh ngoài. Đồ trang trí nằm ngoài hình chữ nhật bàn,
không tham gia collision, switch hoặc solver. Nền CSS gradient và Three.js Fog
cùng bảng màu, ánh sáng hemisphere + directional; giữ điểm tương tác sáng hơn
môi trường. Hồ dùng mặt phẳng trong suốt, không dùng planar reflection đắt tiền.

DPR giới hạn 1,5, không shadow map/postprocessing; nền khác khoảng 30 fps,
gió/camera/lăn theo requestAnimationFrame. Khi tab ẩn hoặc chọn hồ sơ không render. Reduced motion
vẽ lại theo sự kiện. Chuyển màn dispose geometry/material/texture của cảnh cũ;
tile chia sẻ geometry/material, không tạo tài nguyên GPU mới mỗi frame. Đây là
kiểm tra bằng viewport trình duyệt, chưa đo trên điện thoại vật lý.

## Cấu trúc

| File | Trách nhiệm |
|---|---|
| `board.js` | Scene WebGL, camera, tile/khối, vòng render, quản lý GPU |
| `motion.js` | Vòng đời lăn → commit → rơi/tách; khóa chuyển động |
| `rolling.js` | Hình học xoay cạnh đáy thuần túy |
| `camera.js` | Góc orbit, giới hạn, damping và hướng input |
| `gestures.js` | Trạng thái chuột/touch, phân biệt swipe và orbit |
| `biomes.js` | Palette, voxel procedural, billboard, particles |
| `profiles.js` / `profile-ui.js` | State hồ sơ local, chọn/tạo/đổi người chơi |
| `run-clock.js` | Thời gian chơi thực, bỏ thời gian menu/pause |
| `impact.js` / `landing-dust.js` | Settle 50 ms, footprint, pool bụi pixel |
| `wind.js` | Shader gió neo gốc trên InstancedMesh |
| `app.js` | HTTP, HUD, menu, solver polling, replay, bàn phím, audio và kỷ lục |
| `solutions.js` | Bảng so sánh, chuỗi bước, giải thích thuật toán và định dạng metrics |
| `styles.css` | Glass overlay, responsive, reduced motion |
| `levels/` | 30 JSON, schema, manifest, lời giải và hướng dẫn thêm màn |
| `../webapp.py` | HTTP local, catalog, session, solver worker, kiểm tra và phát lại lời giải |

Game mở màn chọn hồ sơ local, mỗi người có tên/avatar, stats và tiến trình riêng.
Menu nhóm 5 chương, mỗi chương 6 màn; hồ sơ mới mở màn 1, thắng để mở màn kế tiếp.
13 màn benchmark/demo cũ nằm trong nhóm bổ sung. Stats cũ được migrate vào một
hồ sơ riêng. Xem [model hồ sơ, persistence, hook VFX và shader gió](PROFILES-AND-VFX.md).
Tối ưu tính bằng BFS UNIT với ngân sách 2 giây và cache; cả 30 màn được
test trong cùng ngân sách. 3 sao = optimum, 2 sao = optimum + max(2, ceil(optimum/3)),
1 sao = hoàn thành. Nước rơi không tăng counter theo controller; chọn cube có
tính một bước. Undo tối đa 5 lần, phục hồi cả cầu/tư thế/cube và counter.

`POST /api/session` trả token, catalog và snapshot; `POST /api/command` với
header `X-Session` nhận `move/load/undo/restart/pause/resume/state`. Payload level
có `width`, `height`, `biomeId`, `chapter`, `chapterLevel`, `chapterTotal`.
JSON API chặn cross-origin; static dùng allowlist. Không có lưu tài khoản/phiên
qua lần khởi động server. Xem [dữ liệu và 30 màn](levels/README.md).

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest Source/tests -q
node --test (Get-ChildItem Source/tests/*.test.mjs).FullName
```

Python kiểm tra engine/loader/solver, replay 30 lời giải BFS, tính cần thiết của
cơ chế, catalog và HTTP. Node chỉ cần khi chạy test JS: 12 chuyển tư thế, pivot,
timing/commit, camera mapping/damping/polar, right drag/two-finger/cancel.

Tài liệu Three.js: [OrthographicCamera](https://threejs.org/docs/#OrthographicCamera),
[InstancedMesh](https://threejs.org/docs/#InstancedMesh), [Fog](https://threejs.org/docs/#Fog).
