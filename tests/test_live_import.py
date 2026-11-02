"""Private Excel activation tests built entirely from synthetic workbooks."""
import base64
import http.cookiejar
import io
import json
import secrets
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def workbook_upload(workbook, name):
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return {'name': name, 'base64': base64.b64encode(stream.getvalue()).decode('ascii')}


def sample_uploads(*, duplicate_menu=False, negative_stock=False, missing_sheet=False):
    inventory = openpyxl.Workbook()
    stock = inventory.active
    stock.title = 'Quan Ly Kho V3'
    stock.append(['Nhóm', 'Tên', 'Đơn vị', 'Giá', 'Nhập', 'Xuất', 'Tồn', 'Tối thiểu', 'Giá trị', 'Ghi chú'])
    stock.append(['Test', 'Test beans', 'g', 100, 0, 0, -1 if negative_stock else 1000, 100, 0, 'Synthetic only'])
    sales = inventory.create_sheet('Bán Hàng')
    sales.append(['Column ' + str(i) for i in range(26)])

    cost = openpyxl.Workbook()
    menu = cost.active
    menu.title = '04_Cost_Menu_ChiTiet'
    for number in range(4):
        menu.append(['Header ' + str(number)])
    menu.append([1, 'LIVE_M', 'Coffee', 'Live coffee', 'M', 2000, 0, 2000, 26000])
    if duplicate_menu:
        menu.append([2, 'LIVE_M', 'Coffee', 'Duplicate code', 'M', 2000, 0, 2000, 26000])
    recipes = cost.create_sheet('03_DinhLuong_TungMon')
    for number in range(4):
        recipes.append(['Header ' + str(number)])
    recipes.append([1, 'LIVE_M', 'Live coffee', 'M', 'Test beans', 10, 'g', 'Kho NVL'])
    batches = cost.create_sheet('02_Cost_Cot_Topping')
    for number in range(4):
        batches.append(['Header ' + str(number)])
    batches.append([1, 'BTP_TEST', 'Test batch', '10g Test beans', 1000, 100, 'ml', 10, 'Synthetic only'])
    if missing_sheet:
        del cost['03_DinhLuong_TungMon']
    return {
        'inventory': workbook_upload(inventory, 'inventory-test.xlsx'),
        'cost': workbook_upload(cost, 'cost-test.xlsx'),
    }


class ImportClient:
    def __init__(self, url):
        self.url = url
        self.csrf = ''
        self.dataset_id = ''
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, data=None, headers=None):
        request_headers = {
            'Content-Type': 'application/json',
            'X-Sua-Request': '1',
            'X-CSRF-Token': self.csrf,
            'X-Sua-Dataset': self.dataset_id,
        }
        request_headers.update(headers or {})
        request = urllib.request.Request(self.url + '/api/' + path,
            data=json.dumps(data).encode('utf-8') if data is not None else None,
            headers=request_headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read()
                result = json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw
                return response.status, result
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def login(self, username, password, setup=False):
        status, result = self.call('setup' if setup else 'login',
            {'username': username, 'password': password, 'display_name': username})
        if status != 201:
            raise AssertionError((status, result))
        self.csrf = result['csrf']
        self.state()

    def state(self):
        status, result = self.call('state')
        if status != 200:
            raise AssertionError((status, result))
        self.dataset_id = result['dataset_id']
        return result


class LiveImportTest(unittest.TestCase):
    def setUp(self):
        self.original_db = server.DB
        self.tmp = tempfile.TemporaryDirectory(prefix='sua-import-test-')
        self.source_db = Path(self.tmp.name) / 'demo.sqlite3'
        self.demo_seed = json.loads((Path(__file__).resolve().parents[1] / 'data/demo.json').read_text(encoding='utf-8'))
        server.DB = self.source_db
        server.init(seed=self.demo_seed, demo=True)
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.http.server_port)
        self.password = secrets.token_urlsafe(20)
        self.owner = ImportClient(self.url)
        self.owner.login('import_owner', self.password, setup=True)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
        server.DB = self.original_db
        self.tmp.cleanup()

    def preview(self, client=None, payload=None):
        status, result = (client or self.owner).call('import/preview', payload or sample_uploads())
        self.assertEqual(status, 201, result)
        return result

    def apply_payload(self, preview):
        return {'job_id': preview['job_id'], 'confirmed': True,
                'inventory_date': server.now()[:10], 'stock_quantities': {'1': 900}}

    def activate(self, preview=None):
        preview = preview or self.preview()
        payload = self.apply_payload(preview)
        status, result = self.owner.call('import/apply', payload)
        self.assertEqual(status, 201, result)
        self.assertTrue(result['activated'])
        return preview, payload, result

    def demo_sale(self):
        product = self.owner.state()['menu'][0]
        status, result = self.owner.call('orders', {
            'request_key': secrets.token_hex(16),
            'items': [{'id': product['id'], 'qty': 1}], 'payment': 'Tiền mặt'})
        self.assertEqual(status, 201, result)
        return result['id']

    def test_preview_is_review_only_and_has_counts(self):
        before = self.owner.state()
        preview = self.preview()
        self.assertEqual(preview['counts'], {'menu': 1, 'stock': 1, 'recipes': 1, 'batches': 1, 'history': 0})
        self.assertEqual(preview['menu'][0]['id'], 'LIVE_M')
        self.assertEqual(preview['stock'][0]['qty'], 1000)
        self.assertIsInstance(preview['warnings'], list)
        after = self.owner.state()
        self.assertTrue(after['demo'])
        self.assertEqual(after['menu'], before['menu'])
        self.assertEqual(after['stock'], before['stock'])
        self.assertEqual(Path(server.DB), self.source_db)
        self.assertFalse(list(Path(self.tmp.name).glob('*.xlsx')))

    def test_activation_preserves_accounts_settings_and_original_demo(self):
        order_id = self.demo_sale()
        self.assertEqual(self.owner.call('settings', {
            'name': 'Quán thử nhập riêng', 'address': 'Địa chỉ mẫu', 'phone': '', 'footer': 'Cảm ơn'})[0], 201)
        self.assertEqual(self.owner.call('users', {
            'username': 'retained_staff', 'password': self.password,
            'display_name': 'Retained staff', 'role': 'cashier'})[0], 201)
        old_dataset = self.owner.dataset_id
        _, _, result = self.activate()
        self.assertTrue(result['backup_available'])
        state = self.owner.state()
        self.assertFalse(state['demo'])
        self.assertNotEqual(state['dataset_id'], old_dataset)
        self.assertEqual([item['id'] for item in state['menu']], ['LIVE_M'])
        self.assertEqual(state['stock'][0]['qty'], 900)
        self.assertEqual(state['orders'], [])
        self.assertEqual(state['expenses'], [])
        self.assertEqual(state['cakes'], [])
        self.assertEqual(state['movements'], [])
        self.assertEqual(state['settings']['name'], 'Quán thử nhập riêng')
        self.assertIn('retained_staff', [user['username'] for user in state['users']])
        self.assertTrue(self.source_db.is_file())
        with sqlite3.connect(self.source_db) as source:
            self.assertEqual(source.execute('SELECT COUNT(*) FROM orders WHERE id=?', (order_id,)).fetchone()[0], 1)
        status, archive = self.owner.call('import/demo-backup')
        self.assertEqual(status, 200)
        backup_path = Path(self.tmp.name) / 'downloaded-demo-backup.sqlite3'
        backup_path.write_bytes(archive)
        with sqlite3.connect(backup_path) as restored:
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(restored.execute('SELECT COUNT(*) FROM orders WHERE id=?', (order_id,)).fetchone()[0], 1)
        status, import_status = self.owner.call('import/status')
        self.assertEqual(status, 200)
        self.assertFalse(import_status['can_import'])
        self.assertFalse(import_status['demo'])
        self.assertTrue(import_status['backup_available'])
        self.assertEqual(import_status['inventory_date'], server.now()[:10])

    def test_apply_replay_and_stale_dataset_orders(self):
        old_dataset = self.owner.dataset_id
        _, payload, _ = self.activate()
        live_path = Path(server.DB)
        status, repeated = self.owner.call('import/apply', payload, headers={'X-Sua-Dataset': old_dataset})
        self.assertEqual(status, 201, repeated)
        self.assertTrue(repeated['activated'])
        self.assertEqual(Path(server.DB), live_path)
        status, failure = self.owner.call('orders', {
            'request_key': secrets.token_hex(16), 'items': [{'id': 'LIVE_M', 'qty': 1}],
            'payment': 'Tiền mặt'}, headers={'X-Sua-Dataset': old_dataset})
        self.assertEqual(status, 409)
        self.assertEqual(failure['code'], 'DATASET_CHANGED')
        self.owner.state()
        status, order = self.owner.call('orders', {
            'request_key': secrets.token_hex(16), 'items': [{'id': 'LIVE_M', 'qty': 1}],
            'payment': 'Tiền mặt'})
        self.assertEqual(status, 201, order)
        self.assertEqual(len(self.owner.state()['orders']), 1)
        self.assertEqual(self.owner.call('import/preview', sample_uploads())[0], 409)

    def test_activation_marker_and_seed_survive_initialization(self):
        self.activate()
        live_db = Path(server.DB)
        marker = self.source_db.with_name(self.source_db.stem + '.active.json')
        self.assertTrue(marker.is_file())
        selection = json.loads(marker.read_text(encoding='utf-8'))
        self.assertEqual((self.source_db.parent / selection['database']).resolve(), live_db.resolve())
        self.assertEqual(server.resolve_database(self.source_db).resolve(), live_db.resolve())
        server.DB = server.resolve_database(self.source_db)
        server.init()
        state = self.owner.state()
        self.assertFalse(state['demo'])
        self.assertEqual([p['id'] for p in state['menu']], ['LIVE_M'])
        self.assertEqual(state['stock'][0]['qty'], 900)
        with server.connect() as connection:
            seed = server.load_seed(connection)
        self.assertEqual([p['id'] for p in seed['menu']], ['LIVE_M'])
        self.assertEqual(seed['stock'][0]['qty'], 900)

    def test_apply_validation_leaves_demo_unchanged(self):
        preview = self.preview()
        base = self.apply_payload(preview)
        invalid = [
            dict(base, confirmed=False),
            dict(base, inventory_date='not-a-date'),
            dict(base, stock_quantities={'1': -1}),
            dict(base, stock_quantities={'999': 1}),
            dict(base, stock_quantities={'1': 'NaN'}),
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                status, _ = self.owner.call('import/apply', payload)
                self.assertIn(status, [400, 409])
                self.assertEqual(Path(server.DB), self.source_db)
                self.assertTrue(self.owner.state()['demo'])
        self.assertFalse(self.source_db.with_name(self.source_db.stem + '.active.json').exists())
        self.activate(preview)

    def test_expired_job_and_other_owner_cannot_activate(self):
        preview = self.preview()
        with server.connect() as connection:
            connection.execute('UPDATE import_jobs SET expires=? WHERE id=?', (server.stamp() - 1, preview['job_id']))
        self.assertIn(self.owner.call('import/apply', self.apply_payload(preview))[0], [400, 409, 410])
        self.assertEqual(Path(server.DB), self.source_db)
        preview = self.preview()
        self.owner.call('users', {'username': 'other_owner', 'password': self.password,
                                 'display_name': 'Other owner', 'role': 'owner'})
        other = ImportClient(self.url)
        other.login('other_owner', self.password)
        self.assertIn(other.call('import/apply', self.apply_payload(preview))[0], [403, 404])
        self.assertEqual(Path(server.DB), self.source_db)

    def test_import_endpoints_require_owner_csrf_and_dataset(self):
        anonymous = ImportClient(self.url)
        self.assertEqual(anonymous.call('import/status')[0], 401)
        self.assertEqual(anonymous.call('import/preview', sample_uploads())[0], 401)
        self.owner.call('users', {'username': 'stock_worker', 'password': self.password,
                                 'display_name': 'Stock worker', 'role': 'inventory'})
        worker = ImportClient(self.url)
        worker.login('stock_worker', self.password)
        for route, payload in [('import/preview', sample_uploads()), ('import/apply', {})]:
            self.assertEqual(worker.call(route, payload)[0], 403)
        for route in ['import/status', 'import/demo-backup']:
            self.assertEqual(worker.call(route)[0], 403)
        self.assertEqual(self.owner.call('import/preview', sample_uploads(), headers={'X-CSRF-Token': 'invalid'})[0], 403)
        status, result = self.owner.call('import/preview', sample_uploads(), headers={'X-Sua-Dataset': 'stale'})
        self.assertEqual(status, 409)
        self.assertEqual(result['code'], 'DATASET_CHANGED')

    def test_malformed_workbooks_and_invalid_records_do_not_mutate_data(self):
        before = self.owner.state()
        broken = sample_uploads()
        broken['inventory'] = {'name': 'not-a-workbook.xlsx', 'base64': base64.b64encode(b'not ZIP data').decode()}
        invalid_base64 = sample_uploads()
        invalid_base64['cost']['base64'] = '%%%invalid%%%'
        invalid_extension = sample_uploads()
        invalid_extension['cost']['name'] = 'macro.xlsm'
        cases = [broken, invalid_base64, invalid_extension,
                 sample_uploads(missing_sheet=True), sample_uploads(duplicate_menu=True),
                 sample_uploads(negative_stock=True)]
        for payload in cases:
            with self.subTest(kind=payload['inventory']['name'], cost=payload['cost']['name']):
                status, _ = self.owner.call('import/preview', payload)
                self.assertEqual(status, 400)
                self.assertEqual(self.owner.state()['menu'], before['menu'])
                self.assertEqual(Path(server.DB), self.source_db)

    def test_duplicate_history_is_flagged_without_creating_new_revenue(self):
        from datetime import datetime
        payload=sample_uploads()
        book=openpyxl.load_workbook(io.BytesIO(base64.b64decode(payload['inventory']['base64'])))
        sales=book['Bán Hàng']
        for row in [2,3]:
            sales.cell(row,22,datetime(2026,1,1))
            sales.cell(row,23,100)
            sales.cell(row,24,200)
            sales.cell(row,25,300)
        payload['inventory']=workbook_upload(book,'history-test.xlsx')
        preview=self.preview(payload=payload)
        self.assertEqual(preview['counts']['history'],2)
        self.assertTrue(any('trùng' in warning for warning in preview['warnings']))
        self.activate(preview)
        state=self.owner.state()
        self.assertEqual(len(state['history']),2)
        self.assertTrue(all(h['ambiguous'] for h in state['history']))
        self.assertEqual(state['orders'],[])
        self.assertEqual(self.owner.call('report?period=2026-01-01')[1]['revenue'],0)

    def test_exported_workbooks_without_dimensions(self):
        import re
        payload=sample_uploads()
        for part in payload.values():
            source=io.BytesIO(base64.b64decode(part['base64']));target=io.BytesIO()
            with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as dst:
                for entry in src.infolist():
                    data=src.read(entry.filename)
                    if entry.filename.startswith('xl/worksheets/'):
                        data=re.sub(rb'<dimension[^>]*/>',b'',data)
                    dst.writestr(entry.filename,data)
            part['base64']=base64.b64encode(target.getvalue()).decode('ascii')
        self.assertEqual(self.preview(payload=payload)['counts']['menu'],1)

    def test_old_invoice_links_cannot_resolve_live_ids(self):
        old=self.owner.dataset_id
        self.demo_sale()
        self.activate()
        self.owner.state()
        status,result=self.owner.call('orders',{'request_key':secrets.token_hex(16),
            'items':[{'id':'LIVE_M','qty':1}],'payment':'Tiền mặt'})
        self.assertEqual(status,201)
        invoice='invoice/'+str(result['id'])
        self.assertEqual(self.owner.call(invoice+'?dataset='+old)[0],409)
        self.assertEqual(self.owner.call(invoice,headers={'X-Sua-Dataset':''})[0],409)
        self.assertEqual(self.owner.call(invoice+'?dataset='+self.owner.dataset_id)[0],200)

    def test_each_upload_has_eight_megabyte_limit(self):
        payload = sample_uploads()
        stream = io.BytesIO(base64.b64decode(payload['inventory']['base64']))
        with zipfile.ZipFile(stream, 'a', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('synthetic-padding.bin', b'0' * (8 * 1024 * 1024))
        payload['inventory']['base64'] = base64.b64encode(stream.getvalue()).decode('ascii')
        status, result = self.owner.call('import/preview', payload)
        self.assertEqual(status, 400)
        self.assertIn('8 MB', result['error'])
        self.assertEqual(Path(server.DB), self.source_db)

    def test_zip_expansion_limit(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('xl/workbook.xml', '<workbook/>')
            archive.writestr('xl/worksheets/sheet1.xml', b'0' * (41 * 1024 * 1024))
        payload = sample_uploads()
        payload['inventory'] = {'name': 'expanded.xlsx', 'base64': base64.b64encode(stream.getvalue()).decode()}
        status, _ = self.owner.call('import/preview', payload)
        self.assertEqual(status, 400)
        self.assertEqual(Path(server.DB), self.source_db)


if __name__ == '__main__':
    unittest.main()
