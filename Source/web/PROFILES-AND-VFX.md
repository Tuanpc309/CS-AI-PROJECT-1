# Hồ sơ local và game feel

## Hồ sơ nhiều slot

Giải pháp dùng LocalStorage, phù hợp nhiều người cùng thiết bị/trình duyệt.
Đây là chọn hồ sơ local, không có mật khẩu, email hay tự đồng bộ cloud. Dữ liệu
theo origin: `localhost`, `127.0.0.1`, cổng khác hoặc thiết bị khác có vùng lưu
khác nhau. Xóa dữ liệu trang sẽ xóa hồ sơ tại origin đó.

`ProfileStore` trong `profiles.js` là state container của JavaScript thuần:
`currentUser`, `list`, `create`, `select`, `recordWin`, `subscribe`. `ProfileUI`
quản lý selector và form; renderer/engine không chứa dữ liệu hồ sơ. Mỗi hồ sơ
lưu riêng ở `bloxorz.profiles.v1.slot.<id>`, tránh ghi đè slot khác. Khi có Web
Locks, thao tác cùng slot được tuần tự hóa giữa các tab. Fallback tuần tự hóa
trong tab; cập nhật luôn đọc bản mới nhất trước khi merge. `storage` event cập
nhật selector và tiến trình của tài khoản đang chọn ở tab khác.

```json
{
 "id":"player-7b8ef3120a4c4ac7a0c98e3d5b1f0269","username":"An","avatar":"fox",
 "unlockedLevel":2,
 "levelStats":{
  "campaign_01":{
   "stars":3,"bestMoves":5,"bestTimeMs":10543,
   "lastMoves":5,"lastTimeMs":10543,"plays":1,
   "completedAt":"2026-10-16T12:00:00.000Z",
   "lastCompletedAt":"2026-10-16T12:00:00.000Z"
  }
 },
 "createdAt":"2026-10-16T11:59:00.000Z","lastPlayed":"2026-10-16T12:00:00.000Z"
}
```

Xem `profile-types.d.ts` và `profile.schema.json`. Tên 1–20 ký tự, 6 avatar
pixel dựng bằng SVG rect; ID ngẫu nhiên 128-bit qua getRandomValues (dùng được
cả HTTP trong LAN). Không có giới hạn cố định 30 trong model.

- Lần đầu, stats cũ ở `bloxorz.worlds.best.v1` được nhập **một lần** vào hồ sơ
  `Hành trình cũ`; giữ nguyên key nguồn. Thời gian cũ không có thì là null,
  hiển thị “—”, không bịa một kỷ lục 0 giây.
- Hồ sơ mới bắt đầu màn 1. Thắng màn N mở N+1, giới hạn theo catalog hiện tại.
  Nếu thêm màn 31, profile đã hoàn thành 30 tự nhận quyền mở 31 lần chọn sau.
- Menu, passcode và lệnh load đều kiểm tra quyền mở màn. Nhóm benchmark/demo
  vẫn dùng tự do. Đây là quy tắc client cho game local, không phải cloud auth
  hoặc cơ chế chống gian lận.
- Khi thắng, sao lấy max, bestMoves lấy min, bestTimeMs lấy min **độc lập**.
  Một lần replay kém hơn không xóa kỷ lục cũ. Snapshot lưu đúng ID sở hữu ván,
  không lấy hồ sơ mới để ghi kết quả của người chơi trước.
- RunClock chỉ cộng thời gian đang chơi; trừ pause, profile selector, menu,
  tab ẩn và VFX thắng. Restart/load đổi màn bắt đầu đồng hồ mới; Undo tiếp tục
  đồng hồ của ván đó. Mở lại modal thắng không ghi thêm một lượt hoàn thành.
- Chọn lại hồ sơ hiện tại/Trở lại tiếp tục ván đang pause. Chọn hồ sơ khác
  tạo phiên engine mới ở màn cao nhất đã mở, với Undo và counter riêng. Ván
  chưa hoàn thành không được lưu qua reload/đổi sang hồ sơ khác.
- Lỗi quota/quyền lưu hiện thông báo. Kết quả thắng chưa lưu được giữ chờ trong
  tab và được thử lưu trước khi rời ván; không báo thành công khi setItem thất bại.

## Lăn, tiếp đất, bụi và hook

`motion.js`: lăn rigid body 220 ms → commit state/cầu → **settle 50 ms** →
tách khối nếu có. Khi rơi vào vực hoặc lỗ đích: lăn → rơi, không sinh thud/bụi
giả trên khoảng trống. Space đổi cube không sinh impact. Input khóa qua cả settle.

`impact.js` tính footprint, loại mặt đỡ, tư thế và pose settle thuần túy. Nén
chiều cao 2,5% khi nằm, 4% khi đứng, giãn ngang bù thể tích. Khi đứng, cả tile
và đáy khối lún theo `-0.05 * sin(pi*t)`, trở lại chính xác ở t=1. Chỉ là pose
đồ họa, không đổi tọa độ collision hoặc trạng thái engine.

`LandingDust` dùng pool 32 instance box, phát 8 hạt từ cạnh footprint, tuổi thọ
280 ms. Ma trận được tái sử dụng, hạt nhỏ dần rồi ẩn; không tạo mesh mới theo
từng cú lăn. Đổi màn/restart xóa effect cũ. Reduced motion bỏ settle/dust/wind
nhưng vẫn phát callback âm thanh để người dùng có phản hồi.

Trong `app.js`, `board` có thể gắn hook:

```js
board.setEffectHooks({
  onRollStart({action, orientation, mode}) {
    // Phát tiếng ma sát khi bắt đầu lăn.
  },
  onImpact(surfaceType, impact) {
    // surfaceType: grass | stone | fragile | bridge | switch | split
    // impact: cells, position:{x,y,z}, upright, width, depth, action
    // Gắn thud hoặc haptic tại đây, theo tùy chọn người chơi.
  }
});
```

Hook được gọi đúng một lần mỗi nước hợp lệ; hook lỗi không làm kẹt input.
Canvas cũng phát CustomEvent có bubbles: `bloxorz-roll-start` và
`bloxorz-impact`; `event.detail` chứa metadata tương ứng. App đã nối thud Web
Audio theo surface, dùng nút âm thanh hiện có (mặc định tắt). Không tự bật rung.

## Gió instanced

`wind.js` thêm vertex shader qua MeshLambertMaterial.onBeforeCompile. Mỗi instance
có `windData = [rootY, height, phase, strength]`. Shader tính vị trí world trước,
trọng số `clamp((worldY-rootY)/height,0,1)^2`; đáy bằng 0, ngọn nhận lực lớn nhất.
Sóng `sin(time*0.8 + worldX*0.5 + worldZ*0.5 + phase)` tạo độ liên tục không gian,
thêm một sóng nhỏ theo Z. Offset chuyển lại local bằng kích thước instance,
nên thân và tán dùng cùng lực gió dù scale khác nhau.

Forest có thân/tán cây và **432 lá cỏ** (6 đảo × 24 bụi × 3 lá); Dusk có cỏ
theo palette hoàng hôn. Cả lớp vegetation dùng **một InstancedMesh / một draw**,
chỉ cập nhật uniform thời gian; không cập nhật hàng trăm matrix mỗi frame.
Gốc cỏ nằm đúng trên mặt đảo, gốc cây giữ cố định. Bốn sprite lá bổ sung thỉnh
thoảng bay qua bàn. Không tác động vào tile/collision.

Renderer cho gió/camera/impact chạy theo requestAnimationFrame, nền khác khoảng
30 fps; dừng cảnh khi tab ẩn hoặc đang chọn hồ sơ. Reduced motion đặt lực gió
bằng 0. Không có shadow map/postprocessing. Mục tiêu là 60 fps với chi phí gió
thấp; chưa benchmark trên điện thoại vật lý, nên không cam kết 60 fps mọi máy.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest Source/tests -q
node --test (Get-ChildItem Source/tests/*.test.mjs).FullName
```

Bộ hiện tại: 225 test Python, 74 test JS. Các test mới kiểm tra tách hồ sơ,
merge stats, migrate, storage failure, gating, đồng hồ, footprint/settle, bụi,
gốc gió và uniform instancing. Xem `docs/ui-verification.md` cho kiểm tra UI.
