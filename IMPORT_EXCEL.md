# Nhập Excel riêng tư vào SỨA cà phê

Mã nguồn công khai chỉ chứa **dữ liệu demo tổng hợp** tại `data/demo.json`. Menu, công thức, giá vốn, tồn và doanh thu thật từ Excel của quán không được đưa lên GitHub.

App tự dùng `data/seed.json` nếu file riêng tư này tồn tại; nếu không, dùng demo. Khi chuyển từ demo sang dữ liệu thật, khởi động với **một database mới**, không dùng lại database demo. Script nhập chỉ tạo JSON, không xóa, gộp hoặc sửa database đang có. App lưu dấu nguồn seed trong database và từ chối khởi động nếu nguồn đã đổi; cần chọn database mới để tránh trộn demo/thật.

## 1. Upload Excel riêng tư vào Codespaces

Giữ cổng app ở chế độ **Private**. Trong Explorer của Codespaces, tạo thư mục `attachments` và upload trực tiếp hai file vào đó. Không đưa Excel vào giao diện tạo commit, issue hoặc link tải công khai trên GitHub.

Ví dụ:

```text
attachments/SỨA CAFÉ.xlsx
attachments/QUẢN LÝ COST + CÔNG THỨC ĐỊNH LƯỢNG SỨA CAFE FINALz.xlsx
```

Repo bỏ qua `attachments/`, các file `*.xlsx`, `data/seed.json` và `data/*.sqlite3*` trong `.gitignore`. Nếu chọn đường dẫn khác, kiểm tra chúng vẫn được bỏ qua. Không dùng `git add -f`. Bạn cũng có thể để Excel hoàn toàn ngoài checkout và truyền đường dẫn tuyệt đối.

Chạy các lệnh dưới đây trong Terminal tại **thư mục gốc của repo**. Codespaces đã cài thư viện qua `install.sh`; không cần cài phần mềm trên máy cá nhân.

## 2. Sao lưu và dừng app trước khi đổi dữ liệu

Nếu có dữ liệu muốn giữ, vào **Cài đặt → Tải bản sao SQLite**, tải bản sao về nơi riêng tư và an toàn. Backup chứa dữ liệu quán và tài khoản; không commit file này lên GitHub.

Nếu app chạy trực tiếp trong Terminal, nhấn `Ctrl+C` tại đúng Terminal đó. Nếu app được Codespaces chạy nền:

```bash
ps -eo pid,args | grep '[p]ython.*server.py'
```

Kiểm tra đúng tiến trình SỨA của codespace này rồi dùng `kill <PID>` với mã tiến trình tương ứng. Không gõ nguyên chữ `<PID>` và không dừng chương trình khác. Đóng tab trình duyệt không dừng server.

**Không xóa database cũ, thư mục `data`, hoặc WAL/SHM đang hoạt động.** Giữ database demo và các database thật cũ để tham khảo/khôi phục riêng.

## 3. Nhập hai file Excel

Trong Terminal Codespaces/Linux:

```bash
.venv/bin/python import_excel.py \
  --inventory "attachments/SỨA CAFÉ.xlsx" \
  --cost "attachments/QUẢN LÝ COST + CÔNG THỨC ĐỊNH LƯỢNG SỨA CAFE FINALz.xlsx"
```

| Cờ | Nội dung |
| --- | --- |
| `--inventory` | Bắt buộc: đường dẫn file tồn kho/bán hàng `SỨA CAFÉ.xlsx`. |
| `--cost` | Bắt buộc: đường dẫn file COST FINAL có menu/giá vốn/định lượng. |
| `--output` | Tùy chọn: JSON đích. Mặc định là `data/seed.json` trong thư mục app, kể cả khi gọi script từ thư mục khác. |
| `--overwrite` | Tùy chọn: cho phép thay JSON đích đã tồn tại. Không tự sửa hoặc làm mới database. |

Đặt đường dẫn có khoảng trắng hoặc dấu tiếng Việt trong dấu ngoặc kép. Script đọc giá trị Excel đã lưu, không chạy macro hay công thức Excel. Kết quả chỉ in số lượng bản ghi, không in giá vốn/doanh thu chi tiết.

Nếu `data/seed.json` đã tồn tại, script dừng để tránh ghi đè. Chỉ sau khi giữ bản sao JSON/database và xác nhận muốn thay JSON, chạy lại lệnh với `--overwrite`. Cờ này **không** phải công cụ cập nhật an toàn số dư database đã vận hành.

Muốn kiểm tra một bản nhập mà chưa cho app sử dụng:

```bash
.venv/bin/python import_excel.py \
  --inventory "attachments/SỨA CAFÉ.xlsx" \
  --cost "attachments/QUẢN LÝ COST + CÔNG THỨC ĐỊNH LƯỢNG SỨA CAFE FINALz.xlsx" \
  --output "attachments/seed-preview.json"
```

App chỉ tự đọc `data/seed.json`, không tự đọc đường dẫn `--output` tùy ý. Preview cũng là dữ liệu thật và phải giữ ngoài Git.

## 4. Khởi động dữ liệu thật bằng database riêng

Sau khi đã tạo `data/seed.json` và dừng app demo, chọn một đường dẫn database **chưa tồn tại**, ví dụ:

```bash
test ! -e data/sua-real.sqlite3
```

Lệnh trả thành công khi đường dẫn chưa tồn tại. Nếu file đã có, không xóa nó: kiểm tra đó có phải database thật đang dùng không. Muốn thử lần nhập hoàn toàn mới, chọn tên mới như `data/sua-real-v2.sqlite3`, giữ nguyên các database cũ.

Khởi động thủ công trong Terminal và giữ Terminal này chạy:

```bash
export SUA_DB=data/sua-real.sqlite3
export HOST=127.0.0.1
export PORT=8000
if [ "${CODESPACES:-}" = "true" ]; then export SUA_SECURE_COOKIE=1; fi
.venv/bin/python server.py
```

Mở **Ports → 8000 → Open in Browser**, giữ **Private**. Với database mới, tự tạo lại tài khoản chủ quán. Đối chiếu menu, giá bán, tồn, công thức và báo cáo trước khi ghi giao dịch thật; không tạo doanh thu thử trong database vận hành.

Mỗi lần mở Terminal/codespace mới, phải dùng đúng `SUA_DB` để tiếp tục database thật. Lệnh `export` trong một Terminal không tự tồn tại ở Terminal mới hoặc lần khởi động khác. Nếu script tự khởi động không được đặt `SUA_DB`, nó dùng mặc định `data/sua.sqlite3`; hãy dừng tiến trình mặc định rồi chạy lại đúng lệnh trên. Không chạy hai server tranh cùng cổng.

Trên Windows local, dùng `.venv\Scripts\python.exe` thay `.venv/bin/python`. Trong PowerShell, đặt `$env:SUA_DB = "data/sua-real.sqlite3"` trước khi khởi động từ cùng Terminal; xem `WINDOWS.md`. Không dùng `SUA_SECURE_COOKIE=1` cho localhost HTTP.

## 5. Kiểm tra không đưa dữ liệu thật lên Git

Ví dụ trong Codespaces:

```bash
git check-ignore data/seed.json attachments/ data/sua-real.sqlite3
git status --short
```

Kết quả ignore phải liệt kê các đường dẫn riêng tư tương ứng; chúng không được xuất hiện trong danh sách chuẩn bị commit. Nếu đã bị theo dõi từ trước, `.gitignore` không tự xóa dữ liệu khỏi lịch sử Git: dừng push và xử lý riêng.

## Phạm vi và giới hạn nhập liệu

- Menu/giá/giá vốn: các dòng hợp lệ trong `04_Cost_Menu_ChiTiet`.
- Tồn: dòng có tên, đơn vị, giá nhập và số tồn hợp lệ trong `Quan Ly Kho V3`; giữ đơn vị đóng gói gốc.
- Định lượng/BTP: `03_DinhLuong_TungMon` và `02_Cost_Cot_Topping`.
- Doanh thu lịch sử: ngày Excel hợp lệ, tổng dương trong các khối được hỗ trợ của `Bán Hàng`. Không suy đoán ngày thiếu năm, số lượng món hoặc lợi nhuận lịch sử.

Nhập JSON chưa xác nhận quy đổi giữa hai file, chưa bật tự trừ kho, chưa nhập/phân loại chi phí lịch sử và chưa tính lại công thức Excel. Tồn là ảnh chụp tại thời điểm của file, cần kiểm kê trước vận hành. Đây là nạp đầu kỳ cho database mới, không phải đồng bộ số dư hai chiều với Excel.
