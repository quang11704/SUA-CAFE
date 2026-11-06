# Chạy SỨA cà phê khi máy Windows chưa cài gì

**Bản GitHub công khai dùng dữ liệu mẫu.** Dữ liệu kinh doanh thật không có trong repo; khi cần, nhập riêng theo [IMPORT_EXCEL.md](IMPORT_EXCEL.md) và sao lưu trước khi chuyển dữ liệu.

## Cách 1 — Chạy ngay trên trình duyệt bằng GitHub Codespaces

Đây là cách nên dùng để thử app: không cần cài Python, Git hoặc Docker trên máy Windows.

1. Đăng nhập GitHub và mở kho **[quang11704/SUA-CAFE](https://github.com/quang11704/SUA-CAFE)**.
2. Trong danh sách branch phía trên các file, chọn **`feat/sua-cafe-management`**. Nếu chưa thấy branch, đợi việc push hoàn tất rồi tải lại trang.
3. Chọn **Code → Codespaces → Create codespace on feat/sua-cafe-management**.
4. Đợi GitHub chuẩn bị môi trường. SỨA tự cài và khởi động; khi bạn kết nối lại, app cũng tự kiểm tra/chạy lại. Codespace cũ cần Git: Pull rồi Codespaces: Rebuild Container một lần như README.
5. Trong tab **Ports**, mở cổng **8000** bằng biểu tượng **Open in Browser**. Giữ cổng ở chế độ **Private**.
6. Ở lần mở đầu tiên, tự tạo tài khoản chủ quán và mật khẩu. Sau đó vào **Cài đặt & nhân viên** để cập nhật thông tin quán hoặc tạo tài khoản nhân viên.

Không mở `127.0.0.1:8000` trên máy Windows để truy cập Codespaces: địa chỉ đó chỉ dùng cho app chạy ngay trên máy của bạn. Với Codespaces, dùng địa chỉ GitHub cung cấp ở tab Ports.

Codespaces cần quyền truy cập repo và hạn mức sử dụng của tài khoản GitHub; dịch vụ có thể tính phí khi vượt hạn mức. Đây là môi trường phát triển để thử app, chưa phải nơi triển khai vận hành quán lâu dài. Dữ liệu nằm trong codespace, không nằm trên máy Windows. Hãy tải backup trước khi xóa hoặc tạo lại codespace.

Sau khi thử app, dùng mục **Dữ liệu quán** để chọn hai file Excel và chuyển sang số liệu thật; xem [IMPORT_EXCEL.md](IMPORT_EXCEL.md). Không đưa workbook thật vào commit.

## Cách 2 — Cài Python một lần và chạy trên Windows

Không cần cài Git hoặc Node.js cho cách này. Bạn cần kết nối Internet khi tải Python, tải mã nguồn và cài thư viện lần đầu.

### Bước 1: cài Python 3.12

Mở **PowerShell** hoặc **Windows Terminal**, chạy:

```powershell
winget install --id Python.Python.3.12 -e
```

Nếu máy không có `winget`, vào trang chính thức **[python.org/downloads/windows](https://www.python.org/downloads/windows/)** và chọn trình cài **Python 3.12** phù hợp với máy. Trong trình cài, chọn **Add python.exe to PATH** và giữ Python Launcher nếu có tùy chọn này. Không tải trình cài từ website không rõ nguồn.

Cài xong, đóng Terminal cũ và mở lại. Kiểm tra:

```powershell
py -3.12 --version
```

Kết quả phải bắt đầu bằng `Python 3.12`. Launcher cũng nhận đường dẫn cài mặc định `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` nếu chưa có lệnh `py` trên PATH.

### Bước 2: tải mã nguồn

1. Mở **[branch feat/sua-cafe-management](https://github.com/quang11704/SUA-CAFE/tree/feat/sua-cafe-management)**.
2. Chọn **Code → Download ZIP**.
3. Giải nén đầy đủ ZIP, chẳng hạn vào `C:\SUA-CAFE`. Không chạy file bên trong cửa sổ xem ZIP.

### Bước 3: mở app

Nhấp đúp **`START_WINDOWS.bat`** trong thư mục vừa giải nén.

File này sẽ:

- Tìm Python 3.12 và tạo môi trường riêng `.venv` nếu chưa có.
- Cài đúng thư viện trong `requirements.txt`; không sửa Python hệ thống.
- Khởi tạo hoặc cập nhật cấu trúc dữ liệu mà không xóa đơn hàng và tồn kho cũ.
- Khởi động server và mở trình duyệt khi server đã sẵn sàng.

Nếu trình duyệt không tự mở, nhập **`http://127.0.0.1:8000`**. Lần đầu, tự đặt tài khoản chủ quán; app không có mật khẩu mặc định.

**Giữ cửa sổ chạy app mở trong lúc sử dụng.** Nhấn `Ctrl+C` hoặc đóng cửa sổ đó để dừng app. Lần sau, chỉ cần nhấp đúp `START_WINDOWS.bat` lần nữa. Server mặc định chỉ cho truy cập từ chính máy Windows này; không mở app trực tiếp ra Internet.

### Dữ liệu lưu ở đâu?

Ban đầu dữ liệu nằm tại **`data\sua.sqlite3`**. Sau chuyển dữ liệu thật qua giao diện, marker `data\sua.active.json` chọn file **`data\sua-live-<mã>.sqlite3`**; bản demo và backup riêng vẫn được giữ trong thư mục app. Đừng chỉ sao chép database demo cũ khi cần dữ liệu thật. Có thể có thêm các file WAL/SHM do SQLite tạo khi server đang chạy. Đây không phải dữ liệu tự đồng bộ lên GitHub.

- Vào **Cài đặt → Tải bản sao SQLite** để sao lưu nhất quán.
- Giữ bản sao ở nơi an toàn ngoài thư mục app và ngoài máy nếu có thể.
- Không xóa thư mục `data` khi gặp lỗi cài đặt.
- Khi tải phiên bản mã nguồn mới, sao lưu trước, dừng server rồi làm theo hướng dẫn nâng cấp trong README; không thay database thật bằng một database rỗng.
- Nếu bạn chủ động đặt biến môi trường `SUA_DB`, server dùng đường dẫn đó thay cho đường dẫn mặc định.

### Lỗi thường gặp

| Thông báo | Cách xử lý |
| --- | --- |
| Chưa tìm thấy Python 3.12 | Cài bằng lệnh trên, đóng cửa sổ cũ rồi mở lại launcher. Kiểm tra `py -3.12 --version`. |
| `.venv` không tương thích | Môi trường Linux từ Codespaces không dùng được trên Windows. Dùng bản ZIP mới từ GitHub hoặc chuyển riêng `.venv` cũ ra ngoài thư mục app; không xóa `data`. Launcher không tự ghi đè hoặc xóa môi trường cũ. |
| Cài thư viện thất bại | Xem lỗi ngay phía trên, kiểm tra Internet, rồi chạy lại. Không bỏ kiểm tra TLS hoặc xóa database để xử lý lỗi tải thư viện. |
| Cổng 8000 đang được sử dụng | Kiểm tra app có đang chạy ở cửa sổ khác không. Nếu đúng là SỨA, mở địa chỉ của app; nếu là chương trình khác, đóng đúng chương trình đó rồi chạy lại. |
| Thiếu font PDF | Tải và giải nén đầy đủ bản mã nguồn có `assets\fonts\DejaVuSans.ttf`. Không cần cài font vào Windows. Thư viện `tzdata` trong requirements cung cấp múi giờ Việt Nam trên Windows. |
| Thiếu `server.py` / `requirements.txt` | Chưa giải nén đầy đủ hoặc đang mở nhầm thư mục. Tìm thư mục có các file này rồi chạy launcher trong cùng thư mục. |

Launcher và hướng dẫn Windows chưa được chạy kiểm chứng trên máy Windows thực tế trong phiên phát triển Linux. Mã nguồn và các luồng app đã được kiểm tra trên môi trường cloud; nếu gặp lỗi riêng của Windows, giữ nguyên thông báo lỗi để chẩn đoán, không xóa dữ liệu quán.
