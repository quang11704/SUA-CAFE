# SỨA cà phê

Web app tiếng Việt tông hồng: bán hàng, phiếu PDF, kho thủ công, sổ bánh, báo cáo và quản lý nhân viên. Dữ liệu lưu SQLite; frontend HTML/CSS/JavaScript, backend Python và ReportLab.

**Branch công khai chỉ chứa dữ liệu mẫu giả lập** (3 món, 2 nguyên liệu), không chứa giá vốn/tồn kho/doanh thu thật từ Excel. App hiển thị nhãn BẢN DÙNG THỬ khi chạy dữ liệu mẫu. Xem [IMPORT_EXCEL.md](IMPORT_EXCEL.md) để nhập dữ liệu của quán trong workspace riêng.

## Đã chạy demo? Cập nhật và nhập dữ liệu thật

Trong Terminal của Codespaces đang dùng đúng branch `feat/sua-cafe-management`:

```bash
git pull --ff-only
bash install.sh
bash .devcontainer/restart.sh
```

Tải lại trang app, đăng nhập bằng tài khoản chủ quán đã tạo → **Dữ liệu quán → Chọn hai file Excel → Đọc file & xem trước**. Kiểm tra menu/giá, sửa số tồn theo kiểm kê, chọn ngày tương ứng và đánh dấu đã đối soát → **Áp dụng dữ liệu thật cho quán**. Không cần upload file qua Git hoặc gõ lệnh import.

App tạo database thật riêng, cất bản dùng thử, giữ tài khoản/phiên và thông tin quán. Đơn/chi phí/sổ bánh thử không được cộng vào dữ liệu thật. Chuyển lại lần nữa cùng bản xem trước trả cùng kết quả; khởi động lại vẫn mở đúng database. Tab/giỏ/PDF cũ bị chặn khi thuộc dữ liệu khác. Sau chuyển, tải **bản sao dữ liệu hiện tại** về máy và lưu ở nơi an toàn.

Tồn/công thức vẫn cần bạn xác nhận; nhập Excel chưa bật tự trừ nguyên liệu. Đây là môi trường dùng thử nghiệp vụ bằng số liệu thật, chưa thay thế hosting production và backup theo lịch.

## Mở ngay trên trình duyệt — không cần cài trên Windows

1. Mở [branch app trên GitHub](https://github.com/quang11704/SUA-CAFE/tree/feat/sua-cafe-management), đăng nhập GitHub.
2. Bấm **Code → Codespaces → Create codespace on feat/sua-cafe-management**. Nếu đã có Codespace cũ, tạo mới từ đúng branch hoặc rebuild container sau khi chuyển branch.
3. Đợi môi trường cài xong. Cấu hình `.devcontainer` tự cài thư viện và khởi động SỨA.
4. Mở tab **Ports**, dòng **8000**, bấm biểu tượng **Open in Browser**. Giữ **Port Visibility = Private**.
5. Tự đặt tài khoản chủ quán và mật khẩu trên màn hình đầu tiên, rồi vào app.

Nếu app chưa tự mở, dùng Terminal trong Codespaces:

```bash
bash .devcontainer/start.sh
```

Codespaces chạy trên máy chủ GitHub, không chạy trên máy Windows của bạn. Dịch vụ có hạn mức/chi phí tùy tài khoản; GitHub hiển thị điều kiện trước khi tạo. Đây là môi trường dùng thử/phát triển, không phải hosting vận hành lâu dài. Tài khoản GitHub khác không tự có quyền vào cổng Private.

Dữ liệu SQLite thuộc Codespace đó. Stop/start giữ lại workspace; **xóa Codespace có thể mất dữ liệu chưa sao lưu**. Tải backup trước khi xóa hoặc tạo máy mới.

## Chạy trên Windows

Xem [WINDOWS.md](WINDOWS.md). Khi đã có Python 3.12, giải nén mã nguồn và nhấp đúp **START_WINDOWS.bat** để cài thư viện, mở trình duyệt và chạy app. Không cần Git/Node/Docker để chạy local.

## Chạy trên Linux/macOS/cloud hiện tại

```bash
cd SUA-CAFE  # thư mục chứa mã nguồn sau khi tải/clone
bash install.sh
.venv/bin/python server.py
```

Mặc định 127.0.0.1:8000. Có thể đổi `HOST`, `PORT`, `SUA_DB`. Font PDF đi kèm tại `assets/fonts/DejaVuSans.ttf`, có giấy phép phân phối trong cùng thư mục; không cần cài font hệ thống.

**Lần đầu:** mở giao diện trên máy chủ, tự tạo tài khoản chủ quán với tên đăng nhập không dấu và mật khẩu ít nhất 10 ký tự. Không có mật khẩu mặc định. Khởi tạo chỉ nhận yêu cầu từ loopback; hãy hoàn tất trước khi cho phép truy cập từ xa. Không gửi mật khẩu trong chat hoặc lưu vào mã nguồn.

Sau đó vào **Cài đặt & nhân viên** để sửa thông tin quán, tạo tài khoản thu ngân/kho và đổi mật khẩu. Cookie phiên HttpOnly/SameSite Strict, hết hạn sau 12 giờ; POST cần CSRF token. Đổi mật khẩu, khóa tài khoản hoặc đổi quyền sẽ thu hồi các phiên tương ứng. Chặn đăng nhập sau 10 lần thử trong 15 phút theo địa chỉ kết nối. Sau reverse proxy, cần cấu hình giới hạn truy cập phù hợp trước production.

## Những phần đã chạy

- Menu: hỗ trợ món/size từ Excel; chủ quán thêm món, chỉnh giá bán/giá vốn ước tính, ngừng bán. Đơn cũ giữ snapshot giá/cost và thông tin quán trên PDF.
- POS: tìm/lọc nhóm, giỏ hàng, ghi chú, giảm giá theo số tiền (chỉ chủ quán), tiền mặt/chuyển khoản.
- Chống đơn trùng: `request_key` theo người dùng, cùng mã/nội dung trả cùng đơn; khác nội dung trả 409. Browser giữ lần thanh toán chưa xác nhận và cho thử lại kể cả sau reload. Lần thử được lưu riêng theo ID tài khoản trên thiết bị.
- Đơn hàng: tìm mã/tên món, lọc ngày/trạng thái, xem chi tiết, tải PDF. Thu ngân chỉ xem đơn của mình.
- Hoàn tiền: chủ quán hoàn toàn bộ đơn một lần, có lý do; giữ đơn gốc, tạo chứng từ tại thời điểm hoàn. Không tự hoàn nguyên liệu/giá vốn đã tiêu hao; PDF giữ nội dung giao dịch gốc, chứng từ hoàn hiển thị ở chi tiết đơn.
- Kho: điều chỉnh nhập/xuất có lý do, chặn âm trong transaction, xem lịch sử, cảnh báo ngưỡng. Thu ngân không có quyền kho. Nhân viên kho không được nhận giá nhập/cost/lợi nhuận từ API.
- Bánh: ghi nhập/bán/hủy theo đợt/ngày, chặn bán + hủy vượt nhập. Bản ghi nhập nhầm có thể hủy kèm lý do, không bị xóa khỏi lịch sử.
- Chi phí: nhóm thuê mặt bằng/lương/điện nước/khác, hủy bản ghi nhập nhầm có lý do.
- Báo cáo ngày/tháng: API tính doanh thu thuần, hoàn tiền, giá vốn, hủy bánh, chi phí, lợi nhuận ước tính. Xuất CSV UTF-8 có BOM, mở bằng Excel.
- Dữ liệu quán: chủ quán tải hai file XLSX (tối đa 8 MB/file), xem trước có hạn 30 phút, đối soát tồn/ngày kiểm kê và áp dụng riêng khỏi demo. Giữ bản demo nhất quán để tải, tài khoản/cấu hình/phiên được duy trì.
- Cài đặt: tên quán/địa chỉ/điện thoại/lời nhắn PDF; tài khoản và vai trò; tải backup SQLite; xem 250 thao tác gần nhất.
- Nhật ký server lưu người/thời điểm/nội dung trước–sau cho giá bán, cấu hình, kho, hoàn tiền, hủy bản ghi. Không ghi mật khẩu vào audit.

## Dữ liệu và giới hạn nghiệp vụ

`data/demo.json` là dữ liệu mẫu đi kèm repo. Nếu có `data/seed.json` riêng, app dùng dữ liệu đó thay mẫu. File seed thật, Excel và database bị bỏ qua bởi Git; không thêm chúng bằng `git add -f`. `import_excel.py` nhận đường dẫn Excel do bạn cung cấp, chỉ chạy khi chủ động nhập dữ liệu, không chạy mỗi lần khởi động. Database lưu dấu nguồn seed và sẽ từ chối khởi tạo nếu nguồn đã đổi, tránh trộn mẫu/thật. Khi đổi từ demo sang dữ liệu thật, dùng database mới riêng như hướng dẫn IMPORT_EXCEL.md; không trộn tồn/giá demo với dữ liệu thật.

- File COST: hỗ trợ menu theo size, định lượng và công thức bán thành phẩm. Giá vốn là kết quả Excel đã lưu, ghi sai số 5–10%. Chưa có tính cost động theo giá nguyên liệu/công thức.
- File quản lý quán: nhập dòng tồn có tên/đơn vị/giá/số tồn hợp lệ. Tồn theo đơn vị đóng gói gốc. Chưa ghép toàn bộ danh mục nguyên liệu của COST vào tồn vì khác tên/quy cách.
- Doanh thu lịch sử có ngày Excel hợp lệ được xem riêng; các khối ngày dạng chuỗi thiếu năm và chi phí lịch sử chưa nhập tự động. Không tính lợi nhuận lịch sử khi thiếu vốn/chi phí đã đối soát. Một ô ngày lỗi P161 không được sử dụng.
- **Chưa tự trừ nguyên liệu:** cần chủ quán xác nhận ghép mã, g/ml/hộp, sản lượng mẻ, bao bì và hao hụt. Hiện kho nhập/xuất độc lập, chưa có phiếu nhập kèm đơn giá, lô/hạn dùng hay sản xuất BTP.
- **Bánh là nguồn doanh thu riêng:** không ghi lại cùng lượt bán trên POS. Chưa có danh mục bánh/lô/hạn dùng/chuyển dư sang ngày sau.
- Lợi nhuận ước tính = doanh thu thuần − cost đơn đã bán − cost bánh đã bán − cost bánh hủy − chi phí vận hành chưa hủy. Hoàn tiền trừ doanh thu ở ngày hoàn; không hoàn vốn đã tiêu hao. Không ghi mua nguyên liệu thành chi phí vận hành nếu đã tính trong giá vốn.
- Đơn mới lưu giá/cost đơn vị làm tròn half-up tới VNĐ, không thay cost đơn cũ khi migration. Chưa là sổ kế toán chuẩn hoặc công cụ quyết toán thuế.
- Phiếu PDF không phải hóa đơn điện tử thuế. Chuyển khoản do nhân viên xác nhận thủ công, chưa kết nối ngân hàng.
- Chưa có quản lý ca, hoàn một phần, chỉnh công thức, backup theo lịch hoặc đồng bộ offline. Nhập Excel qua UI chỉ dùng cho chuyển đầu kỳ từ demo; không ghi đè dữ liệu thật đã vận hành.

## Lưu trữ, nâng cấp và sao lưu

Ban đầu dữ liệu ở `data/sua.sqlite3`. Sau nhập thật qua UI, database mới `data/sua-live-<mã>.sqlite3` được chọn bởi `data/sua.active.json` (hoặc marker tương ứng nếu dùng `SUA_DB` khác). Bản demo gốc và bản sao `data/sua-demo-backup-<mã>.sqlite3` được giữ. Tất cả đều bỏ qua bởi Git; cần sao lưu cả database thật đang hoạt động, không chỉ file demo ban đầu. `server.init()` áp dụng schema v1 theo cách bổ sung, không xóa bảng cũ/đơn/tồn hoặc ghi đè menu đã chỉnh. Kiểm thử đã chạy migration từ schema cũ và chạy init lặp lại. Nên sao lưu trước nâng cấp.

Chủ quán tải bản sao qua **Cài đặt → Tải bản sao SQLite**. Bản sao nhất quán, được chuyển về một file độc lập không cần WAL/SHM. File chứa tài khoản/phiên và dữ liệu quán, cần bảo quản riêng. Không đưa lên Git hay thư mục web.

Sao lưu bằng CLI, dùng đường dẫn đích mới:

```bash
.venv/bin/python -c "import sqlite3; import server; a=server.connect(); b=sqlite3.connect('/tmp/sua-backup.sqlite3'); a.backup(b); b.execute('PRAGMA journal_mode=DELETE'); b.close(); a.close()"
```

`/tmp` không phải lưu trữ lâu dài: chuyển bản sao sang nơi an toàn ngoài máy chủ. Trước khôi phục, dừng server, giữ bản sao của database hiện tại và mọi sidecar WAL/SHM. Kiểm tra file backup bằng `PRAGMA integrity_check`; dùng SQLite backup API từ file nguồn read-only sang file DB đích mới, kiểm tra tổng đơn/tồn và thay DB khi server đã dừng. Sau khôi phục nên thu hồi các phiên cũ. Chưa có nút khôi phục trên UI và chưa có backup tự động.

## Kiểm thử

```bash
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
# Môi trường đã có Playwright + Chromium:
node tests/browser_smoke.cjs
node tests/browser_import.cjs
```

29 integration tests dùng database tạm: auth/CSRF/rate limit, Origin qua cổng HTTPS của Codespaces, quyền và dữ liệu cost ẩn, thu hồi phiên, snapshot giá/PDF, idempotency với yêu cầu đồng thời, tồn cuối đồng thời, hoàn ngày khác, báo cáo/CSV, hủy sổ/chi phí, migration bảo toàn dữ liệu, backup phục hồi, PDF nhiều trang và chuyển dữ liệu Excel: upload/kiểm quyền/giới hạn, xem trước, ngày trùng, file không có dimension, áp dụng/replay, tab cũ, giữ tài khoản, backup demo và chọn lại database sau restart.

Luồng nhập đã kiểm tra end-to-end bằng XLSX giả lập và parser đã đọc được hai workbook thật trong workspace riêng; không commit dữ liệu nguồn. Cấu hình Codespaces chưa được tạo/thử trên một Codespace GitHub thật trong phiên này; đã kiểm thử đường dẫn cài/start và mô phỏng Origin của cổng chuyển tiếp. Launcher Windows chưa chạy thử trên Windows.

Browser test tự chạy server riêng bằng SQLite tạm và Chromium (`CHROMIUM_PATH` để đổi binary). Kiểm tra khởi tạo, các màn hình chính, thêm món, mất phản hồi sau khi đơn đã lưu rồi retry qua reload, PDF, kho/bánh, CSV, hoàn tiền, cấu hình/nhân viên, tải backup, mobile 390px và tài khoản thu ngân. Script browser_import kiểm tra import thật qua API, retry khi mất phản hồi, stale tab, backup demo và restart. Không tạo giao dịch thử trong DB thật. Ảnh kiểm thử lưu ở `/tmp/sua-v2-desktop.png` và `/tmp/sua-v2-mobile.png`.

## Trước khi đưa lên Internet

Mặc dù đã có đăng nhập, đây vẫn là server phát triển. Cần app server production, HTTPS/reverse proxy đúng cấu hình, `SUA_SECURE_COOKIE=1` khi phục vụ qua HTTPS, quản lý secret/config, backup tự động ngoài máy chủ, đo tải và kiểm thử khôi phục trên hạ tầng đích. API state hiện trả toàn bộ dữ liệu của vai trò, chưa phân trang đầy đủ. Xem [PLAN.md](PLAN.md) cho yêu cầu còn lại; chưa được xem là đã hoàn tất mọi P0 hoặc đã triển khai production.
