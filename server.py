"""SỨA local development server. Run behind HTTPS before remote use."""
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import secrets
import sqlite3
import time
import tempfile
import threading
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zoneinfo import ZoneInfo

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

BASE = Path(__file__).parent
PRIVATE_SEED = BASE / 'data/seed.json'
DEMO = not PRIVATE_SEED.is_file()
SEED = json.loads((BASE / 'data/demo.json' if DEMO else PRIVATE_SEED).read_text(encoding='utf-8'))
def resolve_database(configured):
    configured = Path(configured).resolve()
    marker = configured.with_suffix('.active.json')
    if not marker.exists():
        return configured
    data = json.loads(marker.read_text(encoding='utf-8'))
    name = data.get('database', '')
    if not re.fullmatch(r'sua-live-[0-9a-f]{32}\.sqlite3', name):
        raise ValueError('Cấu hình dữ liệu đang dùng không hợp lệ. Giữ nguyên dữ liệu và kiểm tra bản sao lưu.')
    selected = configured.parent / name
    if selected.resolve().parent != configured.parent:
        raise ValueError('Cấu hình database phải nằm cùng thư mục dữ liệu.')
    if not selected.is_file():
        raise ValueError('Không tìm thấy database đang dùng. Không tạo database rỗng; hãy kiểm tra bản sao lưu.')
    return selected


CONFIG_DB = Path(os.environ.get('SUA_DB', str(BASE / 'data/sua.sqlite3'))).resolve()
DB = resolve_database(CONFIG_DB)
DATASET_LOCK = threading.RLock()
PDF_FONT = BASE / 'assets/fonts/DejaVuSans.ttf'
TZ = ZoneInfo('Asia/Ho_Chi_Minh')
DEFAULT_SETTINGS = dict(name='SỨA CÀ PHÊ', address='', phone='', footer='Cảm ơn bạn đã ghé SỨA!')
ROLES = {'owner', 'cashier', 'inventory'}


def connect(path=None):
    c = sqlite3.connect(path if path is not None else DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


def stamp():
    return int(time.time())


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + hashed


def check_password(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


def text(value, label, limit=200, required=True):
    if not isinstance(value, str) or len(value.strip()) > limit or any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ValueError(f'{label} không hợp lệ (tối đa {limit} ký tự)')
    value = value.strip()
    if required and not value:
        raise ValueError(f'Thiếu {label.lower()}')
    return value


def positive(value, zero=False):
    if isinstance(value, bool):
        raise ValueError('Giá trị số không hợp lệ')
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Giá trị số không hợp lệ')
    if not math.isfinite(n) or n > 10**10 or n < 0 or (not zero and n == 0):
        raise ValueError('Số lượng hoặc số tiền không hợp lệ')
    return n


def money(value, zero=True):
    positive(value, zero)
    try:
        result = int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if not zero and result == 0:
            raise ValueError('Số tiền phải lớn hơn 0 VNĐ')
        return result
    except InvalidOperation:
        raise ValueError('Số tiền không hợp lệ')


def quantity(value, zero=False):
    q = positive(value, zero)
    if not q.is_integer() or q > 100000:
        raise ValueError('Số lượng phải là số nguyên, tối đa 100.000')
    return int(q)


def date_string(value):
    datetime.strptime(value, '%Y-%m-%d')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Ngày không hợp lệ')
    return value


def credentials(data):
    username = text(data.get('username'), 'Tên đăng nhập', 40).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}', username):
        raise ValueError('Tên đăng nhập: 3–40 ký tự a-z, số, dấu chấm, gạch dưới hoặc gạch ngang')
    password = data.get('password')
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise ValueError('Mật khẩu cần 10–128 ký tự')
    return username, password


def audit(c, user, action, entity, before=None, after=None):
    c.execute('INSERT INTO audit_logs(created,user_id,username,action,entity,before_json,after_json) VALUES(?,?,?,?,?,?,?)',
              (now(), user['id'], user['username'], action, str(entity), encode(before), encode(after)))


def init(db_path=None, seed=None, demo=None):
    target = Path(DB if db_path is None else db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    selected_seed = SEED if seed is None else seed
    selected_demo = DEMO if demo is None else demo
    with connect(target) as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, created TEXT, payment TEXT, total REAL, cost REAL, items TEXT);
        CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY,qty REAL);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,created TEXT,stock_id INTEGER,delta REAL,note TEXT);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,date TEXT,name TEXT,amount REAL);
        CREATE TABLE IF NOT EXISTS cakes(id INTEGER PRIMARY KEY,date TEXT,name TEXT,received INTEGER,sold INTEGER,waste INTEGER,price REAL,cost REAL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(id INTEGER PRIMARY KEY,peer TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS attempts_peer ON login_attempts(peer,created);
        CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,category TEXT NOT NULL,name TEXT NOT NULL,size TEXT NOT NULL,price INTEGER NOT NULL,cost INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS toppings(id TEXT PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,cost INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,cost_known INTEGER NOT NULL DEFAULT 0,scope TEXT NOT NULL DEFAULT 'general');
        CREATE TABLE IF NOT EXISTS product_toppings(product_id TEXT NOT NULL REFERENCES products(id),topping_id TEXT NOT NULL REFERENCES toppings(id),price_override INTEGER,PRIMARY KEY(product_id,topping_id));
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY,created TEXT NOT NULL,user_id INTEGER,username TEXT NOT NULL,action TEXT NOT NULL,entity TEXT NOT NULL,before_json TEXT,after_json TEXT);
        CREATE TABLE IF NOT EXISTS refunds(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),created TEXT NOT NULL,amount INTEGER NOT NULL,reason TEXT NOT NULL,user_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY,applied TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS app_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS import_jobs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),created INTEGER NOT NULL,expires INTEGER NOT NULL,seed_json TEXT NOT NULL,warnings_json TEXT NOT NULL);
        ''')
        c.execute('BEGIN IMMEDIATE')
        import branding
        branding.init_schema(c)
        stored_kind = c.execute("SELECT value FROM app_metadata WHERE key='source_kind'").fetchone()
        if stored_kind and stored_kind[0] == 'database':
            selected_seed = load_seed(c)
            selected_demo = metadata(c, 'source_mode', 'excel') == 'demo'
        seed_identity = ('demo:' if selected_demo else 'excel:') + digest(encode(selected_seed))
        previous_seed = c.execute("SELECT value FROM app_metadata WHERE key='seed_identity'").fetchone()
        if previous_seed and previous_seed[0] != seed_identity:
            raise ValueError('Database không khớp nguồn dữ liệu hiện tại. Giữ database cũ, sao lưu và chọn một file SUA_DB mới khi đổi demo/Excel hoặc nhập lại seed. Xem IMPORT_EXCEL.md.')
        c.execute("INSERT OR IGNORE INTO app_metadata VALUES('seed_identity',?)", (seed_identity,))
        for key, value in {'seed_json': encode(selected_seed), 'source_mode': 'demo' if selected_demo else 'excel',
                           'source_kind': 'database' if seed is not None else 'file', 'dataset_id': secrets.token_hex(16)}.items():
            c.execute('INSERT OR IGNORE INTO app_metadata VALUES(?,?)', (key, value))
        additions = {
            'products': {'cost_known': 'INTEGER NOT NULL DEFAULT 1'},
            'toppings': {'scope': "TEXT NOT NULL DEFAULT 'general'"},
            'orders': {'user_id': 'INTEGER', 'request_key': 'TEXT', 'fingerprint': 'TEXT', 'status': "TEXT NOT NULL DEFAULT 'paid'", 'shop_json': 'TEXT', 'note': "TEXT NOT NULL DEFAULT ''", 'discount': 'INTEGER NOT NULL DEFAULT 0', 'subtotal': 'INTEGER', 'cost_complete': 'INTEGER NOT NULL DEFAULT 1'},
            'expenses': {'category': "TEXT NOT NULL DEFAULT 'Khác'", 'user_id': 'INTEGER', 'voided': 'INTEGER NOT NULL DEFAULT 0'},
            'cakes': {'user_id': 'INTEGER', 'voided': 'INTEGER NOT NULL DEFAULT 0'},
            'movements': {'user_id': 'INTEGER'},
        }
        for table, fields in additions.items():
            existing = {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}
            for column, spec in fields.items():
                if column not in existing:
                    c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {spec}')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS order_request ON orders(user_id,request_key)')
        c.execute('CREATE INDEX IF NOT EXISTS order_created ON orders(created)')
        c.executemany('INSERT OR IGNORE INTO stock VALUES(?,?)', [(s['id'], s['qty']) for s in selected_seed['stock']])
        c.executemany('INSERT OR IGNORE INTO products(id,category,name,size,price,cost) VALUES(?,?,?,?,?,?)',
                      [(p['id'], p['category'], p['name'], p['size'], money(p['price']), money(p['cost'])) for p in selected_seed['menu']])
        c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (encode(DEFAULT_SETTINGS),))
        c.execute('INSERT OR IGNORE INTO migrations VALUES(1,?)', (now(),))
        c.execute('PRAGMA user_version=1')


def metadata(c, key, default=None):
    row = c.execute('SELECT value FROM app_metadata WHERE key=?', (key,)).fetchone()
    return row[0] if row else default


def load_seed(c):
    stored = metadata(c, 'seed_json')
    return json.loads(stored) if stored else SEED


class ApiError(Exception):
    def __init__(self, status, message, code=None):
        self.status, self.message, self.code = status, message, code


def require(user, *roles):
    if user['role'] not in roles:
        raise ApiError(403, 'Bạn không có quyền thực hiện thao tác này')


def build_state(c, user):
    owner = user['role'] == 'owner'
    stock_user = user['role'] in {'owner', 'inventory'}
    seed = load_seed(c)
    state = dict(toppings=[dict(r) for r in c.execute('SELECT * FROM toppings ORDER BY rowid')],
                 product_toppings=[dict(r) for r in c.execute('SELECT * FROM product_toppings')],
                 catalog_version=metadata(c,'catalog_version'),menu_version=metadata(c,'catalog_version'),demo=metadata(c, 'source_mode', 'demo' if DEMO else 'excel') == 'demo',
                 dataset_id=metadata(c, 'dataset_id'), inventory_date=metadata(c, 'inventory_date'), menu=[dict(r) for r in c.execute('SELECT * FROM products ORDER BY rowid')],
                 stock=[], recipes=[], batches=[], history=[], orders=[], expenses=[], cakes=[], movements=[], refunds=[], audit=[], users=[],
                 settings=__import__('branding').settings_view(json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])),
                 user={k: user[k] for k in ('id', 'username', 'display_name', 'role')})
    if stock_user:
        qty = {r['id']: r['qty'] for r in c.execute('SELECT * FROM stock')}
        state['stock'] = [dict(s, qty=qty[s['id']]) for s in seed['stock']]
        state['movements'] = [dict(r) for r in c.execute('SELECT * FROM movements ORDER BY id DESC')]
        state['recipes'], state['batches'] = list(seed['recipes']), seed['batches']
        links = json.loads(metadata(c, 'catalog_recipe_links', '{}'))
        for new_id, old_id in links.items():
            state['recipes'].extend(dict(r, product=new_id) for r in seed['recipes'] if r['product'] == old_id)
    if owner or user['role'] == 'cashier':
        query = 'SELECT * FROM orders' + ('' if owner else ' WHERE user_id=?') + ' ORDER BY id DESC'
        state['orders'] = [dict(r) for r in c.execute(query, () if owner else (user['id'],))]
        state['refunds'] = [dict(r) for r in c.execute('SELECT * FROM refunds ORDER BY id DESC') if owner or any(o['id'] == r['order_id'] for o in state['orders'])]
    if owner:
        for table in ['expenses', 'cakes']:
            state[table] = [dict(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY id DESC')]
        state['history'] = seed['history']
        state['users'] = [dict(r) for r in c.execute('SELECT id,username,display_name,role,active FROM users ORDER BY id')]
        state['audit'] = [dict(r) for r in c.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 250')]
    else:
        for product in state['menu']:
            product.pop('cost')
        for topping in state['toppings']:
            topping.pop('cost')
        for order in state['orders']:
            order.pop('cost')
            items = json.loads(order['items'])
            for item in items:
                item.pop('cost', None)
                for topping in item.get('toppings',[]):
                    topping.pop('cost',None)
            order['items'] = encode(items)
        # Inventory staff may manage quantities, but do not receive purchase prices or recipe costs.
        for item in state['stock']:
            item.pop('price', None)
    return state


def report(c, period):
    if not re.fullmatch(r'\d{4}-\d{2}(-\d{2})?', period):
        raise ValueError('Kỳ báo cáo không hợp lệ')
    datetime.strptime(period, '%Y-%m-%d' if len(period) == 10 else '%Y-%m')
    orders = [dict(r) for r in c.execute('SELECT * FROM orders WHERE created LIKE ?', (period + '%',))]
    refunds = [dict(r) for r in c.execute('SELECT * FROM refunds WHERE created LIKE ?', (period + '%',))]
    cakes = [dict(r) for r in c.execute('SELECT * FROM cakes WHERE voided=0 AND date LIKE ?', (period + '%',))]
    expenses = [dict(r) for r in c.execute('SELECT * FROM expenses WHERE voided=0 AND date LIKE ?', (period + '%',))]
    gross = sum(money(o['total']) for o in orders) + sum(money(b['price']) * b['sold'] for b in cakes)
    returned = sum(r['amount'] for r in refunds)
    cost = sum(money(o['cost']) for o in orders) + sum(money(b['cost']) * b['sold'] for b in cakes)
    waste = sum(money(b['cost']) * b['waste'] for b in cakes)
    operating = sum(money(e['amount']) for e in expenses)
    incomplete = sum(not o['cost_complete'] for o in orders)
    return dict(incomplete_cost_orders=incomplete, period=period, gross=gross, refunds=returned, revenue=gross-returned, cost=cost, waste=waste,
                expenses=operating, profit=None if incomplete else gross-returned-cost-waste-operating, count=len(orders))


def invoice(order):
    import branding
    return branding.invoice(sys.modules[__name__], order)


class Handler(BaseHTTPRequestHandler):
    def send(self, data, status=200, kind='application/json; charset=utf-8', cookie=None, filename=None):
        raw = encode(data).encode() if not isinstance(data, bytes) else data
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(raw)

    def current_user(self, c, needed=True):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        token = cookies.get('sua_session')
        token = token.value if token else ''
        session = c.execute('SELECT s.*,u.username,u.display_name,u.role,u.active,u.id FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>? AND active=1', (digest(token), stamp())).fetchone()
        if needed and not session:
            raise ApiError(401, 'Vui lòng đăng nhập lại')
        return dict(session) if session else None

    def csrf(self, user):
        if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), user['csrf']):
            raise ApiError(403, 'Phiên xác nhận không hợp lệ. Vui lòng tải lại trang.')

    def check_dataset(self, c, supplied=None):
        expected = metadata(c, 'dataset_id', '')
        if not hmac.compare_digest(supplied if supplied is not None else self.headers.get('X-Sua-Dataset', ''), expected):
            raise ApiError(409, 'Dữ liệu quán đã thay đổi. Vui lòng tải lại và kiểm tra đơn trước khi tiếp tục.', 'DATASET_CHANGED')

    def session_cookie(self, token, expire=False):
        secure = '; Secure' if os.environ.get('SUA_SECURE_COOKIE') == '1' else ''
        return f'sua_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if expire else 43200}{secure}'

    def do_GET(self):
        try:
            with DATASET_LOCK:
                self.get()
        except ApiError as e:
            self.send(dict(error=e.message, **({'code': e.code} if e.code else {})), e.status)
        except (ValueError, TypeError, KeyError):
            self.send({'error': 'Dữ liệu yêu cầu không hợp lệ'}, 400)
        except Exception:
            self.log_error('GET failed')
            self.send({'error': 'Không thể xử lý. Vui lòng thử lại hoặc kiểm tra máy chủ.'}, 500)

    def get(self):
        path = urlsplit(self.path).path
        paths = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/receipt.css': 'receipt.css', '/receipt.js': 'receipt.js'}
        if path in paths:
            f = BASE / 'static' / paths[path]
            return self.send(f.read_bytes(), kind={'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'css': 'text/css'}[f.suffix[1:]])
        if path.startswith('/assets/fonts/'):
            import branding
            name = path.rsplit('/', 1)[-1]
            if name not in branding.FONT_FILES:
                raise ApiError(404, 'Không tìm thấy font')
            return self.send((BASE / 'assets/fonts' / name).read_bytes(), kind='font/ttf')
        if path == '/api/health':
            with connect() as c:
                c.execute('SELECT 1').fetchone()
            return self.send({'status': 'ok', 'schema': 1})
        with connect() as c:
            if path == '/api/session':
                user = self.current_user(c, False)
                return self.send({'authenticated': bool(user), 'setup_needed': not bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone()),
                                  'csrf': user['csrf'] if user else None,
                                  'user': {k: user[k] for k in ('id', 'username', 'display_name', 'role')} if user else None})
            user = self.current_user(c)
            if path == '/api/state':
                return self.send(build_state(c, user))
            if path.startswith('/api/brand-assets/'):
                import branding
                asset_id = path.rsplit('/', 1)[-1]
                if not re.fullmatch('[0-9a-f]{64}', asset_id):
                    raise ApiError(404, 'Không tìm thấy logo')
                logo = branding.asset(c, asset_id)
                if not logo:
                    raise ApiError(404, 'Không tìm thấy logo')
                return self.send(bytes(logo['data']), kind=logo['mime'])
            if path == '/api/catalog/preview':
                require(user,'owner')
                import catalog
                return self.send(catalog.preview(sys.modules[__name__],c))
            if path in {'/api/import/status', '/api/import/demo-backup'}:
                require(user, 'owner')
                import live_import
                if path.endswith('/status'):
                    return self.send(live_import.status(sys.modules[__name__], c))
                data = live_import.demo_backup(sys.modules[__name__], c)
                return self.send(data, kind='application/octet-stream', filename='SUA-demo-before-live.sqlite3')
            if path.startswith('/api/invoice/') or path.startswith('/api/print/'):
                self.check_dataset(c, parse_qs(urlsplit(self.path).query).get('dataset', [None])[0])
                order = c.execute('SELECT * FROM orders WHERE id=?', (int(path.rsplit('/', 1)[1]),)).fetchone()
                if not order:
                    raise ApiError(404, 'Không tìm thấy đơn hàng')
                if user['role'] != 'owner' and not (user['role'] == 'cashier' and order['user_id'] == user['id']):
                    raise ApiError(403, 'Không có quyền xem đơn hàng này')
                if path.startswith('/api/print/'):
                    import branding
                    auto = parse_qs(urlsplit(self.path).query).get('auto', ['0'])[0] == '1'
                    return self.send(branding.receipt_html(sys.modules[__name__], dict(order), auto), kind='text/html; charset=utf-8')
                return self.send(invoice(dict(order)), kind='application/pdf', filename=f"SUA-{order['id']}.pdf")
            if path in {'/api/report', '/api/export'}:
                require(user, 'owner')
                period = parse_qs(urlsplit(self.path).query).get('period', [now()[:10]])[0]
                result = report(c, period)
                if path == '/api/report':
                    return self.send(result)
                stream = io.StringIO()
                writer = csv.writer(stream)
                writer.writerow(['Kỳ', 'Doanh thu trước hoàn', 'Hoàn tiền', 'Doanh thu thuần', 'Giá vốn', 'Hủy bánh', 'Chi phí', 'Lợi nhuận ước tính', 'Số đơn'])
                writer.writerow([result[k] for k in ['period', 'gross', 'refunds', 'revenue', 'cost', 'waste', 'expenses', 'profit', 'count']])
                return self.send(stream.getvalue().encode('utf-8-sig'), kind='text/csv; charset=utf-8', filename=f'SUA-report-{period}.csv')
            if path == '/api/backup':
                require(user, 'owner')
                # Make a standalone file without a WAL sidecar before downloading.
                with tempfile.TemporaryDirectory(prefix='sua-backup-') as folder:
                    target = Path(folder) / 'backup.sqlite3'
                    backup = sqlite3.connect(target)
                    try:
                        c.backup(backup)
                        backup.execute('PRAGMA journal_mode=DELETE')
                    finally:
                        backup.close()
                    data = target.read_bytes()
                audit(c, user, 'backup.download', 'database')
                return self.send(data, kind='application/octet-stream', filename=f'SUA-backup-{now()[:10]}.sqlite3')
        raise ApiError(404, 'Không tìm thấy')

    def do_POST(self):
        try:
            with DATASET_LOCK:
                result, cookie = self.post()
            self.send(result, 201, cookie=cookie)
        except ApiError as e:
            self.send(dict(error=e.message, **({'code': e.code} if e.code else {})), e.status)
        except ValueError as e:
            self.send({'error': str(e) or 'Dữ liệu không hợp lệ'}, 400)
        except (KeyError, TypeError, OverflowError):
            self.send({'error': 'Dữ liệu không hợp lệ hoặc thiếu trường bắt buộc'}, 400)
        except sqlite3.IntegrityError:
            self.send({'error': 'Mã hoặc tài khoản đã tồn tại, vui lòng kiểm tra lại'}, 409)
        except Exception:
            self.log_error('POST failed')
            self.send({'error': 'Không lưu được dữ liệu. Vui lòng thử lại.'}, 500)

    def post(self):
        path = urlsplit(self.path).path
        if self.headers.get('X-Sua-Request') != '1':
            raise ApiError(403, 'Yêu cầu không hợp lệ')
        origin = self.headers.get('Origin')
        # Codespaces may preserve the external Origin while rewriting Host for
        # its localhost tunnel. Trust only this instance's HTTPS origin, built
        # from platform-provided environment names; never trust forwarded headers.
        codespaces_origin = None
        if os.environ.get('CODESPACES') == 'true':
            name = os.environ.get('CODESPACE_NAME', '')
            domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '')
            port = os.environ.get('PORT', '8000')
            if re.fullmatch(r'[a-z0-9-]+', name) and domain == 'app.github.dev' and re.fullmatch(r'\d{1,5}', port):
                codespaces_origin = f'https://{name}-{port}.{domain}'
        same_host = origin and urlsplit(origin).scheme in {'http', 'https'} and urlsplit(origin).netloc == self.headers.get('Host')
        if (origin and not same_host and origin != codespaces_origin) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise ApiError(403, 'Không chấp nhận yêu cầu từ trang khác')
        import_path = path in {'/api/import/preview', '/api/import/apply'}
        if import_path:
            with connect() as auth:
                actor = self.current_user(auth)
                require(actor, 'owner')
                self.csrf(actor)
                if path.endswith('/preview'):
                    self.check_dataset(auth)
        size = int(self.headers.get('Content-Length', 0))
        if not 0 < size <= (24 * 1024 * 1024 if path == '/api/import/preview' else (3 * 1024 * 1024 if path == '/api/branding' else 100000)):
            raise ValueError('Yêu cầu quá lớn hoặc trống')
        d = json.loads(self.rfile.read(size))
        if not isinstance(d, dict):
            raise ValueError('Yêu cầu không hợp lệ')
        if path in {'/api/setup', '/api/login'}:
            return self.login(d, setup=path == '/api/setup')
        if import_path:
            import live_import
            return live_import.handle(self, sys.modules[__name__], path, d), None
        cookie = None
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            user = self.current_user(c)
            self.csrf(user)
            if path in {'/api/orders','/api/products','/api/stock','/api/refunds','/api/cakes','/api/expenses','/api/void','/api/catalog/apply','/api/toppings'}:
                self.check_dataset(c)
            if path == '/api/branding':
                require(user, 'owner')
                import branding
                branding.save(sys.modules[__name__], c, user, d)
                return {}, None
            if path == '/api/logout':
                c.execute('DELETE FROM sessions WHERE token_hash=?', (user['token_hash'],))
                return {}, self.session_cookie('', True)
            if path == '/api/password':
                old = c.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()[0]
                if not isinstance(d.get('current'), str) or not check_password(d['current'], old):
                    raise ApiError(403, 'Mật khẩu hiện tại không đúng')
                _, password = credentials(dict(username=user['username'], password=d.get('password')))
                c.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(password), user['id']))
                c.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
                audit(c, user, 'password.change', user['id'])
                return {}, self.session_cookie('', True)
            if path == '/api/catalog/apply':
                require(user,'owner')
                import catalog
                return catalog.apply(sys.modules[__name__],c,user,d), None
            if path == '/api/toppings':
                require(user,'owner')
                import catalog
                return catalog.save_topping(sys.modules[__name__],c,user,d), None
            if path == '/api/orders':
                require(user, 'owner', 'cashier')
                key = text(d.get('request_key'), 'Mã yêu cầu', 100)
                fingerprint = digest(encode({k: d.get(k) for k in ['items', 'payment', 'discount', 'note']}))
                previous = c.execute('SELECT * FROM orders WHERE user_id=? AND request_key=?', (user['id'], key)).fetchone()
                if previous:
                    if previous['fingerprint'] != fingerprint:
                        raise ApiError(409, 'Mã yêu cầu đã dùng cho nội dung khác; kiểm tra đơn trước khi tiếp tục')
                    return {'id': previous['id'], 'replayed': True}, None
                if not isinstance(d.get('items'), list) or not 1 <= len(d['items']) <= 200:
                    raise ValueError('Đơn hàng không hợp lệ')
                import catalog
                items = [catalog.build_item(sys.modules[__name__],c,x) for x in d['items']]
                payment = d.get('payment')
                if payment not in {'Tiền mặt', 'Chuyển khoản'}:
                    raise ValueError('Thanh toán không hợp lệ')
                subtotal = sum(p['price'] * p['qty'] for p in items)
                discount = money(d.get('discount', 0))
                if discount:
                    require(user, 'owner')
                if discount > subtotal or subtotal > 10**10:
                    raise ValueError('Tổng tiền hoặc giảm giá không hợp lệ')
                note = text(d.get('note', ''), 'Ghi chú', 500, False)
                settings = c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0]
                cur = c.execute('INSERT INTO orders(created,payment,total,cost,items,user_id,request_key,fingerprint,shop_json,note,discount,subtotal,cost_complete) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (now(), payment, subtotal-discount, sum(p['cost'] * p['qty'] for p in items), encode(items), user['id'], key, fingerprint, settings, note, discount, subtotal, int(all(p['cost_known'] for p in items))))
                audit(c, user, 'order.create', cur.lastrowid, after={'total': subtotal-discount})
                return {'id': cur.lastrowid}, None
            if path == '/api/refunds':
                require(user, 'owner')
                order = c.execute('SELECT * FROM orders WHERE id=?', (quantity(d['order_id']),)).fetchone()
                if not order:
                    raise ApiError(404, 'Không tìm thấy đơn hàng')
                reason = text(d.get('reason'), 'Lý do hoàn', 500)
                if order['status'] == 'refunded':
                    return {'order_id': order['id'], 'replayed': True}, None
                c.execute('INSERT INTO refunds(order_id,created,amount,reason,user_id) VALUES(?,?,?,?,?)', (order['id'], now(), money(order['total']), reason, user['id']))
                c.execute("UPDATE orders SET status='refunded' WHERE id=?", (order['id'],))
                audit(c, user, 'order.refund', order['id'], before={'status': 'paid'}, after={'status': 'refunded', 'reason': reason, 'amount': money(order['total'])})
                return {}, None
            if path == '/api/products':
                require(user, 'owner')
                pid = text(d.get('id'), 'Mã món', 50)
                if not re.fullmatch('[A-Za-z0-9_-]+', pid):
                    raise ValueError('Mã món chỉ gồm chữ, số, _ và -')
                if not isinstance(d.get('cost_known',True),bool):
                    raise ValueError('Trạng thái giá vốn phải là giá trị có/không hợp lệ')
                p = dict(id=pid, name=text(d.get('name'), 'Tên món', 100), category=text(d.get('category'), 'Nhóm món', 60), size=text(d.get('size'), 'Size', 20),
                         price=money(d['price']), cost=money(d['cost']) if d.get('cost_known', True) else 0, cost_known=1 if d.get('cost_known', True) else 0, active=1 if d.get('active', True) else 0)
                old = c.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
                c.execute('INSERT INTO products(id,name,category,size,price,cost,cost_known,active) VALUES(:id,:name,:category,:size,:price,:cost,:cost_known,:active) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category,size=excluded.size,price=excluded.price,cost=excluded.cost,cost_known=excluded.cost_known,active=excluded.active', p)
                audit(c, user, 'product.save', pid, before=dict(old) if old else None, after=p)
                revision = secrets.token_hex(16)
                c.execute("INSERT OR REPLACE INTO app_metadata VALUES('dataset_id',?)", (revision,))
                return {'dataset_id': revision}, None
            if path == '/api/settings':
                require(user, 'owner')
                fields = {k: text(d.get(k, ''), k, 200, k == 'name') for k in DEFAULT_SETTINGS}
                old = json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])
                settings = dict(old, **fields)
                c.execute('UPDATE settings SET data=? WHERE id=1', (encode(settings),))
                audit(c, user, 'settings.save', 'shop', old, settings)
                return {}, None
            if path == '/api/users':
                require(user, 'owner')
                if d.get('id'):
                    target = c.execute('SELECT * FROM users WHERE id=?', (quantity(d['id']),)).fetchone()
                    if not target:
                        raise ApiError(404, 'Không tìm thấy tài khoản')
                    if target['id'] == user['id']:
                        raise ApiError(400, 'Không thể tự khóa hoặc đổi quyền của tài khoản đang sử dụng')
                    role = d.get('role')
                    if role not in ROLES:
                        raise ValueError('Vai trò không hợp lệ')
                    c.execute('UPDATE users SET role=?,active=? WHERE id=?', (role, 1 if d.get('active') else 0, target['id']))
                    c.execute('DELETE FROM sessions WHERE user_id=?', (target['id'],))
                    audit(c, user, 'user.update', target['id'], after={'role': role, 'active': bool(d.get('active'))})
                else:
                    username, password = credentials(d)
                    role = d.get('role')
                    if role not in ROLES:
                        raise ValueError('Vai trò không hợp lệ')
                    cur = c.execute('INSERT INTO users(username,password_hash,display_name,role) VALUES(?,?,?,?)',
                                    (username, password_hash(password), text(d.get('display_name'), 'Tên hiển thị', 80), role))
                    audit(c, user, 'user.create', cur.lastrowid, after={'username': username, 'role': role})
                return {}, None
            if path == '/api/stock':
                require(user, 'owner', 'inventory')
                q = float(d['delta'])
                positive(abs(q))
                if abs(q) < 0.000001 or abs(q) > 100000:
                    raise ValueError('Số lượng không hợp lệ')
                sid = quantity(d['id'])
                r = c.execute('SELECT qty FROM stock WHERE id=?', (sid,)).fetchone()
                if not r or round(r['qty'] + q, 6) < 0:
                    raise ApiError(400, 'Xuất kho vượt số tồn')
                note = text(d.get('note'), 'Lý do nhập/xuất', 500)
                after = round(r['qty'] + q, 6)
                c.execute('UPDATE stock SET qty=? WHERE id=?', (after, sid))
                c.execute('INSERT INTO movements(created,stock_id,delta,note,user_id) VALUES(?,?,?,?,?)', (now(), sid, round(q, 6), note, user['id']))
                audit(c, user, 'stock.adjust', sid, {'qty': r['qty']}, {'qty': after, 'note': note})
                return {}, None
            if path == '/api/expenses':
                require(user, 'owner')
                values = (date_string(d['date']), text(d.get('name'), 'Tên chi phí', 200), money(d['amount'], False), text(d.get('category', 'Khác'), 'Nhóm chi phí', 60), user['id'])
                cur = c.execute('INSERT INTO expenses(date,name,amount,category,user_id) VALUES(?,?,?,?,?)', values)
                audit(c, user, 'expense.create', cur.lastrowid, after={'date': values[0], 'amount': values[2]})
                return {}, None
            if path == '/api/cakes':
                require(user, 'owner')
                values = [quantity(d[k], True) for k in ['received', 'sold', 'waste']]
                if values[1] + values[2] > values[0]:
                    raise ApiError(400, 'Số bánh bán + hủy không được vượt số nhập')
                cur = c.execute('INSERT INTO cakes(date,name,received,sold,waste,price,cost,user_id) VALUES(?,?,?,?,?,?,?,?)',
                                (date_string(d['date']), text(d.get('name'), 'Tên bánh', 100), *values, money(d['price']), money(d['cost']), user['id']))
                audit(c, user, 'cake.create', cur.lastrowid, after={'name': d['name'], 'received': values[0], 'sold': values[1], 'waste': values[2]})
                return {}, None
            if path == '/api/void':
                require(user, 'owner')
                table = d.get('type')
                if table not in {'expenses', 'cakes'}:
                    raise ValueError('Loại không hợp lệ')
                reason = text(d.get('reason'), 'Lý do hủy', 500)
                previous = c.execute(f'SELECT * FROM {table} WHERE id=?', (quantity(d['id']),)).fetchone()
                if not previous:
                    raise ApiError(404, 'Không tìm thấy bản ghi')
                if not previous['voided']:
                    c.execute(f'UPDATE {table} SET voided=1 WHERE id=?', (previous['id'],))
                    audit(c, user, table + '.void', previous['id'], dict(previous), {'reason': reason})
                return {}, None
            raise ApiError(404, 'Không tìm thấy')

    def login(self, d, setup=False):
        # No preconfigured password. First owner can only be created from loopback.
        if setup and self.client_address[0] not in {'127.0.0.1', '::1'}:
            raise ApiError(403, 'Khởi tạo chủ quán trên máy chủ trước khi cho truy cập từ xa')
        peer = self.client_address[0]
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM login_attempts WHERE created<?', (stamp()-900,))
            if c.execute('SELECT COUNT(*) FROM login_attempts WHERE peer=?', (peer,)).fetchone()[0] >= 10:
                raise ApiError(429, 'Đã thử quá nhiều lần. Vui lòng đợi 15 phút.')
            c.execute('INSERT INTO login_attempts(peer,created) VALUES(?,?)', (peer, stamp()))
        username, password = credentials(d)
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if setup:
                if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                    raise ApiError(409, 'Quán đã có tài khoản chủ; vui lòng đăng nhập')
                c.execute('INSERT INTO users(username,password_hash,display_name,role) VALUES(?,?,?,?)',
                          (username, password_hash(password), text(d.get('display_name'), 'Tên hiển thị', 80), 'owner'))
            row = c.execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
            # Equal work for missing username; never expose whether an account exists.
            stored = row['password_hash'] if row else ('00'*16 + ':' + '00'*32)
            valid = check_password(password, stored)
            if not row or not valid:
                raise ApiError(401, 'Tên đăng nhập hoặc mật khẩu không đúng')
            user = dict(row)
            c.execute('DELETE FROM sessions WHERE expires<?', (stamp(),))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), user['id'], csrf, stamp()+43200))
            c.execute('DELETE FROM login_attempts WHERE peer=?', (peer,))
            audit(c, user, 'account.setup' if setup else 'account.login', user['id'])
            return {'csrf': csrf, 'user': {k: user[k] for k in ('id', 'username', 'display_name', 'role')}}, self.session_cookie(token)


if __name__ == '__main__':
    init()
    host, port = os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000'))
    print(f'SỨA server: {host}:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
