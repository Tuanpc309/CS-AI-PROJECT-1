# Triển khai web

Website: [Bloxorz · Quiet Worlds — Kazu](https://huyokazu.github.io/bloxorz-kazu/).

Source được phát triển ở nhánh `kazu-bloxorz-web`, dựa trên `tuanpc` của
`Tuanpc309/CS-AI-PROJECT-1`. Website công khai được triển khai qua GitHub Pages
ở repo riêng [huyokazu/bloxorz-kazu](https://github.com/huyokazu/bloxorz-kazu).
Tài khoản Kazu có quyền quản trị repo deploy này nên không cần thay đổi quyền
quản trị repo đồ án.

## Bản web không cần server Python

`build_pages.py` đóng gói giao diện và engine Python gốc vào website tĩnh.
Pyodide 314.0.7 chạy trong một module Web Worker, dùng lại `Catalog`,
`WebSession`, controller, loader và engine; không viết lại luật chơi bằng JS.
Các giá trị optimum được tính/kiểm tra khi build để điện thoại không chạy BFS
trong lúc chơi. Tkinter, solver và API HTTP local tiếp tục hoạt động như cũ.

Runtime WASM khoảng 13,5 MB chưa nén được tải cùng origin với website, có cache
trình duyệt. Lần đầu mở có thể mất vài giây; UI hiển thị tiến độ và cho thử lại
nếu tải lỗi. Không cần CDN lúc chơi. Hồ sơ vẫn lưu local theo origin, nên
website công khai không tự nhận các hồ sơ đã tạo ở localhost.

## Build và kiểm tra

Từ thư mục repo, Python 3.12+ và Node 24:

```powershell
python -m pytest Source/tests -q
node --test (Get-ChildItem Source/tests/*.test.mjs).FullName
python Source/tools/build_pages.py
node Source/tools/smoke_pages.mjs dist
python -m http.server 8080 --directory dist
```

Mở `http://127.0.0.1:8080/`. Trên Linux/macOS, lệnh JS tương đương là
`node --test Source/tests/*.test.mjs`. Chỉ cần pytest để chạy bộ test Python;
matplotlib thuộc phần đồ án thực nghiệm, không cần cho build web.

Builder yêu cầu thư mục output trống, không tự xóa thư mục có dữ liệu. Có thể
chọn output mới bằng `--output .cache/pages-next`. Runtime tải về lúc build
phải khớp sáu SHA-256 trong `Source/tools/pyodide-lock.json`; cache nằm trong
`.cache/pyodide`, không commit binary WASM hay môi trường `.venv` vào Git.

Smoke test chạy WebAssembly thật: replay 30 màn tới chiến thắng đúng optimum
và 3 sao; kiểm tra tách/ghép, switch, fragile, cầu, pause, Undo, restart,
phiên độc lập và request không hợp lệ. Bộ hiện tại còn có 225 test Python và
74 test JS. Chưa benchmark cold start/FPS trên điện thoại vật lý.

## Cập nhật website chính

Sau khi push source vào `kazu-bloxorz-web`, mở repo
`huyokazu/bloxorz-kazu` → **Actions → Publish Bloxorz by Kazu → Run workflow**.
Workflow lấy source mới nhất từ nhánh đó, chạy toàn bộ test, build, replay 30
màn bằng WASM rồi deploy bằng token tạm thời do GitHub cấp. Không cần lưu PAT
hoặc khóa deploy trong repo. `deployment.json` trên website ghi lại source
commit đã được triển khai.

Hồ sơ lưu theo origin của trình duyệt. Địa chỉ GitHub Pages mới có vùng lưu
riêng; các hồ sơ trên website trước đó không tự chuyển sang địa chỉ mới.

## GitHub Pages trực tiếp ở repo đồ án (tùy chọn)

Workflow `.github/workflows/deploy-pages.yml` tự kiểm tra source, build và chạy
smoke test khi push vào `kazu-bloxorz-web` hoặc `main`. Nhánh mới không được
tự merge vào `main`.

Tài khoản push `huyokazu` có quyền write, chưa có quyền quản trị Pages ở repo
này. Để dùng GitHub Pages, chủ repo chọn **Settings → Pages → GitHub Actions**,
cho phép nhánh này deploy vào environment `github-pages`, rồi tạo repository
variable `ENABLE_GITHUB_PAGES=true` và chạy lại workflow. Nếu chưa bật variable,
CI vẫn kiểm tra đầy đủ và bỏ qua riêng bước deploy Pages.

Bản tĩnh sử dụng đường dẫn tương đối, chạy được cả ở `/` và đường dẫn project
`/CS-AI-PROJECT-1/` hoặc `/bloxorz-kazu/`. Website chính ở trên được quản lý
bằng workflow riêng trong repo deploy.

Tham khảo: [Pyodide deployment](https://pyodide.org/en/stable/usage/downloading-and-deploying.html),
[Web Worker](https://pyodide.org/en/stable/usage/webworker.html),
[GitHub Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
