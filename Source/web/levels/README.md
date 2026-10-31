# Campaign — 30 màn / 5 biome

`campaign.json` định nghĩa thứ tự hiển thị và metadata. `campaign_01.json` đến
`campaign_30.json` chứa bàn chơi thực; `solutions.json` chứa lời giải BFS, số bước
và số state đã duyệt để kiểm tra tác giả. Server không gửi lời giải cho browser.
`quiet_01.json` và 12 màn trong `Source/levels` thuộc nhóm bổ sung.

| Chương | Màn | Cơ chế tăng tiến | Số bước BFS của 6 màn |
|---|---|---|---|
| Forest | 1–6 | Sàn rộng, căn tư thế, góc nhìn | 5, 7, 8, 9, 11, 14 |
| Dusk | 7–12 | Dải cam bắt buộc nằm, cầu hẹp đã mở | 13, 15, 16, 17, 19, 25 |
| Neon | 13–18 | 3 màn công tắc đơn → 3 màn công tắc kép | 15, 16, 17, 23, 24, 29 |
| Cavern | 19–24 | Tách/di chuyển hai cube, mở lối, hợp nhất | 11, 13, 15, 15, 16, 19 |
| Celestial | 25–30 | Tách + nhiều công tắc + cầu + dải cam | 30, 32, 33, 34, 36, 42 |

Độ khó gồm cả số cơ chế và nhánh quyết định, không chỉ số bước: đầu chương tách
khối ngắn hơn cuối chương công tắc để người chơi học quy tắc mới. Trong chương,
chọn candidate theo optimum BFS tăng dần. Score để hỗ trợ tác giả là
`optimal + 5 * số_công_tắc + 8 * chỉ_số_chương` (chỉ số từ 0); không dùng score
này để tính sao. Layout khác nhau về grid/start/goal, không chỉ đổi tên/biome.

## JSON và TypeScript

`level.schema.json` là JSON Schema Draft 2020-12. Loader kiểm tra thêm quan hệ
giữa ô/cầu/công tắc, hình chữ nhật và duy nhất một G. `biomeId` tùy chọn cho
level cũ (mặc định forest), bắt buộc theo quy ước cho campaign mới.

```ts
type BiomeId = 'forest' | 'dusk' | 'neon' | 'cavern' | 'celestial';
type Coord = [row: number, column: number];
type Effect = {bridge_id: string; operation: 'TOGGLE' | 'SET_OPEN' | 'SET_CLOSED'};
type Switch = {id: string; cell: Coord; effects: Effect[]} & (
  {type: 'SOFT' | 'HEAVY'} | {type: 'SPLIT'; destinations: [Coord, Coord]}
);
interface Level {
  id: string; biomeId?: BiomeId; grid: string[]; start: Coord; goal: Coord;
  bridges: {id: string; cells: Coord[]; initial_enabled: boolean}[];
  switches: Switch[];
}
```

```json
{
  "id": "my_level", "biomeId": "forest",
  "grid": [".......", ".FFFFG.", ".FFFFF.", "......."],
  "start": [1, 1], "goal": [1, 5], "bridges": [], "switches": []
}
```

Ví dụ trên minh họa schema, không cam kết số bước. Tọa độ từ 0; hàng tăng xuống,
cột tăng sang phải. Start nằm trên F; thắng khi khối nguyên đứng trên G.

| Ô | Luật |
|---|---|
| `.` | Vực; chạm vào sẽ rơi |
| `F` | Sàn thường |
| `G` | Lỗ đích, khối nằm có thể đi qua |
| `O` | Gạch cam: chỉ đỡ khối nằm; đứng gây FRAGILE_UPRIGHT |
| `B` | Cầu: chỉ đỡ khối khi cờ cầu bật |
| `S` | SOFT: khối đứng/nằm hoặc cube đơn đều nhấn được |
| `X` | HEAVY: chỉ khối nguyên đứng mới nhấn |
| `T` | SPLIT: khối nguyên đứng bị tách và chuyển tới 2 destinations |

Mỗi B thuộc đúng một bridge; mỗi S/X/T có một switch đúng loại. Effects tham
chiếu bridge ID tồn tại. TOGGLE đảo trạng thái, SET_OPEN/SET_CLOSED đặt trạng
thái; chỉ kích hoạt khi vừa đủ điều kiện, không toggle liên tục khi còn đè nút.
SPLIT destinations là hai F không trùng, không kề cạnh. Hai cube kề nhau sẽ hợp
nhất; Space chọn cube và tính một bước. Bộ 30 dùng SPLIT để chuyển vị trí hai
cube, chưa thêm loại ô teleport độc lập.

Metadata manifest: `id`, `file`, `title`, `subtitle`, `biomeId`, `chapter`,
`chapterLevel`, `difficulty` (1–5), `difficultyLabel`, `mechanics`. Không nhét
metadata vào file bàn ngoài biomeId; loader từ chối trường lạ.

## Mở rộng thành 30+ màn

1. Tạo JSON ID mới, ví dụ `campaign_31.json`, dùng biome hiện có.
2. Chạy loader, BFS, replay qua engine; thêm proof/test tương ứng.
3. Thêm manifest theo thứ tự mong muốn, cập nhật chapterLevel. Catalog không
   giới hạn 30; menu và tổng số màn theo biome được tính từ manifest.
4. Thêm biome hoàn toàn mới thì cập nhật BIOMES, enum loader/schema và renderer.

`Source/tools/build_campaign.py` là công cụ tác giả tái lập theo seed. Nó tạo
candidate bằng terrace/carving, chọn start/goal, mở rộng các motif fragile,
switch/split, rồi BFS bằng engine thật. Candidate vô nghiệm bị loại; candidate
chương 2/5 phải đi qua cam, chương 4/5 phải tách khối. Chọn 6 candidate theo
độ dài lời giải trong từng nhóm, viết JSON và proof. Không sinh map ngẫu nhiên
trong lúc chơi. Chạy công cụ sẽ **tạo lại cả bộ campaign**; để thêm một màn riêng,
làm theo bốn bước trên thay vì chạy lại công cụ.

```powershell
python Source/tools/build_campaign.py
python -m pytest Source/tests/test_campaign.py -q
```

Test replay mọi màn và so optimum bằng solver BFS trong ngân sách 2 giây/màn.
Test đồ thị ở các màn đại diện chứng minh không bypass được cam và không bỏ
qua bất kỳ công tắc nào. Bản đồ JSON đã lưu là dữ liệu được game tải trực tiếp.
