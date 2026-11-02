#!/usr/bin/env bash
set -euo pipefail
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
.venv/bin/python - <<'PY'
import os,signal,time
from pathlib import Path
root=Path.cwd().resolve()
candidates=[]
if not Path('/proc').is_dir():
    raise SystemExit('Script này dùng cho Codespaces/Linux. Trên Windows, dừng cửa sổ app bằng Ctrl+C rồi chạy lại START_WINDOWS.bat.')
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():continue
    try:
        argv=(entry/'cmdline').read_bytes().split(b'\0')
        argv=[item for item in argv if item]
        if len(argv)!=2 or Path(os.fsdecode(argv[1])).name!='server.py':continue
        if Path(os.readlink(entry/'cwd')).resolve()!=root:continue
        if not Path(os.fsdecode(argv[0])).name.startswith('python'):continue
        candidates.append(int(entry.name))
    except (OSError,PermissionError):continue
if len(candidates)>1:
    raise SystemExit('Có nhiều server trong cùng thư mục. Chưa dừng tiến trình nào; hãy kiểm tra Terminal trước khi khởi động lại.')
for pid in candidates:
    os.kill(pid,signal.SIGTERM)
    for _ in range(30):
        try:
            state=(Path('/proc')/str(pid)/'stat').read_text().split()[2]
            if state=='Z':break
        except OSError:break
        time.sleep(.1)
    else:
        raise SystemExit('Server chưa dừng. Chưa khởi chạy thêm tiến trình; hãy kiểm tra Terminal.')
print('Đã kiểm tra/dừng server của đúng thư mục SỨA; dữ liệu được giữ nguyên.')
PY
bash .devcontainer/start.sh
