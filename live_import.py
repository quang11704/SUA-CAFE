"""Private Excel onboarding. Uploaded workbooks never enter the Git checkout."""
import base64
import binascii
import io
import json
import os
import re
import secrets
import sqlite3
import tempfile
import warnings
import zipfile
from pathlib import Path

from import_excel import extract

FILE_LIMIT = 8 * 1024 * 1024
TTL = 30 * 60


def _counts(seed):
    return {key: len(seed[key]) for key in ['menu', 'stock', 'recipes', 'batches', 'history']}


def _is_demo(app, c):
    return app.metadata(c, 'source_mode', 'demo' if app.DEMO else 'excel') == 'demo'


def status(app, c):
    demo = _is_demo(app, c)
    counts = {table: c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
              for table in ['products', 'stock', 'orders', 'expenses', 'cakes']}
    counts['menu'] = counts.pop('products')
    backup = app.metadata(c, 'demo_backup_file')
    return dict(can_import=demo, demo=demo, expires_minutes=30, current_counts=counts,
                backup_available=bool(backup), inventory_date=app.metadata(c, 'inventory_date'),
                reason='' if demo else 'Quán đã dùng dữ liệu thật. Không nhập lại theo cách thay toàn bộ dữ liệu; hãy quản lý danh mục và nhập/xuất trong app.')


def demo_backup(app, c):
    name = app.metadata(c, 'demo_backup_file', '')
    if not re.fullmatch(r'sua-demo-backup-[0-9a-f]{32}\.sqlite3', name):
        raise app.ApiError(404, 'Không có bản dùng thử được cất riêng.')
    path = Path(app.DB).parent / name
    if not path.is_file():
        raise app.ApiError(404, 'Không tìm thấy bản sao. Giữ nguyên các database để kiểm tra.')
    return path.read_bytes()


def _workbook(app, part, label):
    if not isinstance(part, dict) or not isinstance(part.get('name'), str) or not part['name'].lower().endswith('.xlsx'):
        raise app.ApiError(400, f'{label}: hãy chọn file .xlsx.')
    encoded = part.get('base64')
    if not isinstance(encoded, str) or len(encoded) > ((FILE_LIMIT + 2) // 3) * 4:
        raise app.ApiError(400, f'{label}: dung lượng tối đa 8 MB.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise app.ApiError(400, f'{label}: nội dung tải lên không hợp lệ.')
    if not raw or len(raw) > FILE_LIMIT:
        raise app.ApiError(400, f'{label}: file trống hoặc vượt 8 MB.')
    stream = io.BytesIO(raw)
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(e.file_size for e in entries) > 40 * 1024 * 1024:
                raise ValueError('Giới hạn nội dung Excel')
            if not {'[Content_Types].xml', 'xl/workbook.xml'}.issubset(archive.namelist()):
                raise ValueError('Không phải workbook')
            if any(e.flag_bits & 1 or e.filename.lower().endswith('vbaproject.bin') for e in entries):
                raise ValueError('Workbook mã hóa hoặc có macro')
        stream.seek(0)
        return stream
    except (zipfile.BadZipFile, ValueError, OSError):
        raise app.ApiError(400, f'{label}: chỉ hỗ trợ Excel .xlsx không mã hóa, không macro, với tối đa 40 MB nội dung giải nén.')


def _validate(app, seed):
    # All arithmetic and records are checked before any database is changed.
    if not seed['menu'] or not seed['stock']:
        raise app.ApiError(400, 'Không tìm thấy menu hoặc tồn kho hợp lệ. Kiểm tra đúng hai file và các sheet yêu cầu.')
    ids = set()
    for p in seed['menu']:
        p['id'] = app.text(p['id'], 'Mã món', 50)
        if p['id'] in ids or not re.fullmatch('[A-Za-z0-9_-]+', p['id']):
            raise app.ApiError(400, 'Mã món trùng hoặc không hợp lệ. Sửa trong Excel trước khi nhập.')
        ids.add(p['id'])
        for key, label in [('name', 'Tên món'), ('category', 'Nhóm món'), ('size', 'Size')]:
            p[key] = app.text(p[key], label, 100)
        p['price'], p['cost'] = app.money(p['price']), app.money(p['cost'])
    for s in seed['stock']:
        s['name'] = app.text(s['name'], 'Tên nguyên liệu', 200)
        s['unit'] = app.text(s['unit'], 'Đơn vị', 60)
        s['qty'] = round(app.positive(s['qty'], True), 6)
        s['minimum'] = round(app.positive(s['minimum'], True), 6)
        s['price'] = app.money(s['price'])
        s['note'] = app.text(s['note'], 'Ghi chú quy cách', 1000, False)
    for r in seed['recipes']:
        if r['product'] not in ids:
            raise app.ApiError(400, 'Có định lượng tham chiếu mã món không nằm trong menu. Đối soát file COST trước khi nhập.')
        r['name'] = app.text(r['name'], 'Tên thành phần', 200)
        r['qty'] = app.positive(r['qty'], True)
        r['unit'] = app.text(r['unit'], 'Đơn vị định lượng', 60)
        r['source'] = app.text(r.get('source') or '', 'Nguồn định lượng', 100, False)
    for b in seed['batches']:
        b['name'] = app.text(b['name'], 'Tên bán thành phẩm', 200)
        b['formula'] = app.text(b['formula'], 'Công thức mẻ', 3000)
        b['yield_qty'] = app.positive(b['yield_qty'])
        b['unit'] = app.text(b['unit'], 'Đơn vị bán thành phẩm', 60)
    from collections import Counter
    dates = Counter(h['date'] for h in seed['history'])
    for h in seed['history']:
        app.date_string(h['date'])
        if dates[h['date']] > 1:
            h['ambiguous'] = True
        for key in ['cash', 'transfer', 'total']:
            h[key] = app.money(h[key])
    return seed


def _activated(app, c):
    return dict(activated=True, demo=False, counts=_counts(app.load_seed(c)), backup_available=True)


def handle(handler, app, path, data):
    with app.connect() as c:
        user = handler.current_user(c)
        app.require(user, 'owner')
        handler.csrf(user)
        if path.endswith('/apply') and data.get('job_id') and app.metadata(c, 'import_job_id') == data.get('job_id'):
            if app.metadata(c, 'import_user_id') != str(user['id']):
                raise app.ApiError(403, 'Chỉ chủ quán đã thực hiện lần nhập này được xác nhận lại kết quả.')
            return _activated(app, c)
        if not _is_demo(app, c):
            raise app.ApiError(409, 'Quán đã dùng dữ liệu thật; không thể thay dữ liệu qua luồng nhập đầu kỳ.')
        if path.endswith('/preview'):
            inventory = _workbook(app, data.get('inventory'), 'File tồn kho')
            cost = _workbook(app, data.get('cost'), 'File COST')
            try:
                with warnings.catch_warnings(record=True) as recorded:
                    warnings.simplefilter('always')
                    seed = _validate(app, extract(inventory, cost))
            except (app.ApiError, ValueError):
                raise
            except Exception:
                raise app.ApiError(400, 'Không đọc được mẫu Excel. Kiểm tra các sheet Quan Ly Kho V3, Bán Hàng, 04_Cost_Menu_ChiTiet, 03_DinhLuong_TungMon và 02_Cost_Cot_Topping; file cần lưu kết quả công thức.')
            notes = ['Tồn kho là số trong Excel. Hãy sửa số lượng theo kiểm kê thực tế và chọn đúng ngày kiểm kê.',
                     'Chưa tự trừ nguyên liệu khi bán: cần xác nhận ghép mã, quy đổi đơn vị và sản lượng mẻ.',
                     'Giá vốn lấy từ kết quả Excel đã lưu; lợi nhuận là ước tính. Chi phí lịch sử chưa nhập.',
                     'Doanh thu lịch sử được giữ riêng, không cộng vào doanh thu đơn mới. Các khối ngày văn bản thiếu năm không được suy đoán.']
            if recorded:
                notes.append(f'Excel có {len(recorded)} cảnh báo khi đọc (ví dụ ô định dạng ngày không hợp lệ). Các giá trị lỗi không được dùng làm số liệu hợp lệ.')
            duplicates = len({h['date'] for h in seed['history'] if h.get('ambiguous')})
            if duplicates:
                notes.append(f'{duplicates} ngày lịch sử bị trùng trong các khối Excel. Giữ từng dòng nguồn kèm dấu cảnh báo để đối soát; không gộp hoặc tính vào doanh thu mới.')
            mismatch = sum(1 for h in seed['history'] if h['cash'] + h['transfer'] != h['total'])
            if mismatch:
                notes.append(f'{mismatch} ngày lịch sử có tổng khác tiền mặt + chuyển khoản; giữ tổng theo file và cần đối soát riêng.')
            job = secrets.token_hex(24)
            c.execute('DELETE FROM import_jobs WHERE expires<? OR user_id=?', (app.stamp(), user['id']))
            c.execute('INSERT INTO import_jobs VALUES(?,?,?,?,?,?)', (job, user['id'], app.stamp(), app.stamp()+TTL, app.encode(seed), app.encode(notes)))
            app.audit(c, user, 'import.preview', job, after=_counts(seed))
            return dict(job_id=job, expires_at=app.stamp()+TTL, counts=_counts(seed), warnings=notes, menu=seed['menu'], stock=seed['stock'])
        if data.get('confirmed') is not True:
            raise app.ApiError(400, 'Cần xác nhận đã kiểm tra số liệu trước khi chuyển sang dùng thật.')
        inventory_date = app.date_string(data.get('inventory_date', ''))
        if inventory_date > app.now()[:10]:
            raise app.ApiError(400, 'Ngày kiểm kê không được ở tương lai.')
        job_id = app.text(data.get('job_id'), 'Mã bản xem trước', 80)
        if not re.fullmatch('[0-9a-f]{48}', job_id):
            raise app.ApiError(400, 'Mã bản xem trước không hợp lệ.')
        job = c.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise app.ApiError(404, 'Không tìm thấy bản xem trước. Hãy chọn lại hai file Excel.')
        if job['user_id'] != user['id']:
            raise app.ApiError(403, 'Bản xem trước thuộc tài khoản chủ quán khác.')
        if job['expires'] < app.stamp():
            raise app.ApiError(410, 'Bản xem trước đã hết hạn sau 30 phút. Hãy tải file lại.')
        seed = json.loads(job['seed_json'])
        changes = data.get('stock_quantities', {})
        known = {str(s['id']) for s in seed['stock']}
        if not isinstance(changes, dict) or not set(changes).issubset(known):
            raise app.ApiError(400, 'Danh sách điều chỉnh tồn không hợp lệ.')
        for stock in seed['stock']:
            if str(stock['id']) in changes:
                stock['qty'] = round(app.positive(changes[str(stock['id'])], True), 6)
        # Both stores remain private. The old demo file is never deleted.
        source = Path(app.DB).resolve()
        nonce = secrets.token_hex(16)
        target = source.parent / f'sua-live-{nonce}.sqlite3'
        backup_path = source.parent / f'sua-demo-backup-{nonce}.sqlite3'
        marker = source.with_suffix('.active.json')
        if marker.exists():
            raise app.ApiError(409, 'Đã có cấu hình dữ liệu đang hoạt động. Tải lại trang để kiểm tra trước khi tiếp tục.')
        destination = sqlite3.connect(backup_path)
        try:
            c.backup(destination)
            destination.execute('PRAGMA journal_mode=DELETE')
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise app.ApiError(500, 'Không kiểm tra được bản sao trước khi chuyển dữ liệu. Chưa đổi dữ liệu quán.')
        finally:
            destination.close()
        app.init(db_path=target, seed=seed, demo=False)
        with app.connect(target) as live:
            live.execute('BEGIN IMMEDIATE')
            # IDs remain stable for the accounts/session; no financial/demo rows copied.
            for table, columns in [('users', 'id,username,password_hash,display_name,role,active'),
                                   ('sessions', 'token_hash,user_id,csrf,expires')]:
                rows = c.execute(f'SELECT {columns} FROM {table}').fetchall()
                placeholders = ','.join('?' for _ in columns.split(','))
                live.executemany(f'INSERT INTO {table}({columns}) VALUES({placeholders})', [tuple(r) for r in rows])
            shop = c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0]
            live.execute('UPDATE settings SET data=? WHERE id=1', (shop,))
            for key, value in {'inventory_date': inventory_date, 'demo_backup_file': backup_path.name,
                               'import_job_id': job_id, 'import_user_id': str(user['id'])}.items():
                live.execute('INSERT OR REPLACE INTO app_metadata VALUES(?,?)', (key, value))
            app.audit(live, user, 'dataset.activate', app.metadata(live, 'dataset_id'),
                      before={'demo_dataset': app.metadata(c, 'dataset_id')}, after={'counts': _counts(seed), 'inventory_date': inventory_date})
            result = _activated(app, live)
        # Publish the local pointer atomically only after new DB + backup are complete.
        # A crash after replace is recovered on restart, before serving requests.
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=source.parent, prefix='.sua-pointer-', delete=False) as out:
                temp_name = out.name
                json.dump({'database': target.name}, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp_name, marker)
            temp_name = None
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
        app.DB = target
        return result
