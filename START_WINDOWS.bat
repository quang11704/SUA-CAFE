@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title SỨA cà phê

pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist "server.py" goto missing_files
if not exist "requirements.txt" goto missing_files
if not exist "assets\fonts\DejaVuSans.ttf" goto missing_font

echo.
echo SỨA CÀ PHÊ - CHẠY TRÊN WINDOWS
echo Cửa sổ này cần mở trong suốt thời gian sử dụng app.
echo.

if exist ".venv\Scripts\python.exe" goto check_venv
if exist ".venv" goto incompatible_venv

py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>&1
if not errorlevel 1 goto create_with_launcher

if not exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto python_missing
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>&1
if errorlevel 1 goto python_missing

echo [1/4] Tạo môi trường Python riêng cho app...
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv ".venv"
if errorlevel 1 goto venv_failed
goto check_venv

:create_with_launcher
echo [1/4] Tạo môi trường Python riêng cho app...
py -3.12 -m venv ".venv"
if errorlevel 1 goto venv_failed

:check_venv
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>&1
if errorlevel 1 goto incompatible_venv

echo [2/4] Kiểm tra và cài thư viện từ requirements.txt...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto install_failed

echo [3/4] Chuẩn bị dữ liệu, giữ nguyên đơn hàng và tồn kho đã lưu...
".venv\Scripts\python.exe" -c "import server; server.init()"
if errorlevel 1 goto init_failed

".venv\Scripts\python.exe" -c "import socket,sys; s=socket.socket(); s.settimeout(1); code=s.connect_ex(('127.0.0.1',8000)); s.close(); sys.exit(1 if code == 0 else 0)"
if errorlevel 1 goto port_busy

set "HOST=127.0.0.1"
set "PORT=8000"
set "SUA_SECURE_COOKIE=0"
echo [4/4] Khởi động app tại http://127.0.0.1:8000
echo Trình duyệt sẽ tự mở sau khi máy chủ sẵn sàng.
echo Lần đầu: tự tạo tài khoản chủ quán trên giao diện.
echo Dừng app: nhấn Ctrl+C hoặc đóng cửa sổ này.
echo.

start "" /b ".venv\Scripts\python.exe" -c "import time,urllib.request,webbrowser; exec('for _ in range(60):\n try:\n  r=urllib.request.urlopen(\'http://127.0.0.1:8000/api/health\',timeout=1)\n  r.close()\n  webbrowser.open(\'http://127.0.0.1:8000\')\n  break\n except Exception:\n  time.sleep(1)')"
".venv\Scripts\python.exe" "server.py"
if errorlevel 1 goto server_failed
popd
endlocal
exit /b 0

:python_missing
echo Chưa tìm thấy Python 3.12 trên máy.
echo Mở PowerShell hoặc Terminal và chạy:
echo.
echo     winget install --id Python.Python.3.12 -e
echo.
echo Hoặc tải Python 3.12 từ trang chính thức:
echo     https://www.python.org/downloads/windows/
echo Khi dùng trình cài đặt, chọn Add python.exe to PATH.
echo Cài xong, đóng cửa sổ này và mở lại START_WINDOWS.bat.
echo Nếu không muốn cài gì, dùng GitHub Codespaces theo WINDOWS.md.
goto failed

:incompatible_venv
echo Đã có thư mục .venv nhưng không phải môi trường Python 3.12 Windows dùng được.
echo App không tự xóa hoặc ghi đè thư mục này.
echo Hãy dùng một bản tải ZIP mới từ GitHub, hoặc chuyển .venv cũ ra ngoài thư mục app rồi chạy lại.
echo Giữ nguyên thư mục data nếu muốn tiếp tục sử dụng dữ liệu quán hiện có.
goto failed

:venv_failed
echo Không tạo được môi trường Python. Kiểm tra quyền ghi thư mục và Python 3.12.
echo Nếu .venv được tạo dở, hãy chuyển nó ra ngoài thư mục app trước khi thử lại.
goto failed

:install_failed
echo Cài thư viện thất bại. Kiểm tra kết nối Internet và thông báo lỗi phía trên.
echo Không cần xóa database; sau khi xử lý kết nối, chạy lại file này.
goto failed

:init_failed
echo Không chuẩn bị được dữ liệu. Kiểm tra thông báo lỗi phía trên.
echo Không xóa thư mục data; hãy sao lưu trước khi sửa chữa hoặc nâng cấp.
goto failed

:port_busy
echo Cổng 8000 đang được sử dụng, có thể app đã chạy ở cửa sổ khác.
echo Nếu đúng là SỨA, mở http://127.0.0.1:8000 để sử dụng.
echo Nếu là chương trình khác, đóng đúng chương trình đó trước khi chạy lại app.
goto failed

:missing_files
echo Thiếu server.py hoặc requirements.txt. Hãy giải nén đầy đủ mã nguồn trước khi chạy.
goto failed

:missing_font
echo Thiếu assets\fonts\DejaVuSans.ttf. Hãy tải bản mã nguồn đầy đủ từ GitHub.
echo Font này cần thiết để xuất PDF tiếng Việt.
goto failed

:server_failed
echo Máy chủ đã dừng do lỗi. Giữ lại thông báo lỗi phía trên để kiểm tra.
goto failed

:folder_error
echo Không mở được thư mục chứa app. Hãy giải nén app vào thư mục bạn có quyền sử dụng.
pause
endlocal
exit /b 1

:failed
echo.
pause
popd
endlocal
exit /b 1
