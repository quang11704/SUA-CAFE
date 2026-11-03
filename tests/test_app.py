import concurrent.futures
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class Client:
    def __init__(self, url):
        self.url, self.csrf, self.dataset_id = url, '', ''
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, data=None, headers=None):
        request_headers = {'X-Sua-Request': '1', 'X-CSRF-Token': self.csrf, 'X-Sua-Dataset': self.dataset_id}
        request_headers.update(headers or {})
        request = urllib.request.Request(self.url + '/api/' + path,
            data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
        try:
            with self.opener.open(request) as response:
                raw = response.read()
                result = json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw
                if isinstance(result, dict) and result.get('dataset_id'):
                    self.dataset_id = result['dataset_id']
                return response.status, result
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def login(self, username, password, setup=False):
        status, data = self.call('setup' if setup else 'login', dict(username=username, password=password, display_name=username))
        assert status == 201, (status, data)
        self.csrf = data['csrf']
        self.state()

    def state(self):
        status, state = self.call('state')
        assert status == 200, (status, state)
        self.dataset_id = state['dataset_id']
        return state


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.DB = Path(cls.tmp.name) / 'test.sqlite3'
        server.init()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.url = 'http://127.0.0.1:' + str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.password = secrets.token_urlsafe(20)
        cls.owner = Client(cls.url)
        cls.owner.login('owner', cls.password, setup=True)
        for role in ['cashier', 'inventory']:
            assert cls.owner.call('users',dict(username=role,password=cls.password,display_name=role,role=role))[0] == 201
            client = Client(cls.url)
            client.login(role, cls.password)
            setattr(cls, role, client)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.tmp.cleanup()

    def sale(self, client=None, **kwargs):
        data = dict(request_key=secrets.token_hex(16),items=[dict(id='CF01_M',qty=2,price=1)],payment='Tiền mặt')
        data.update(kwargs)
        status, result = (client or self.owner).call('orders', data)
        self.assertEqual(status, 201, result)
        return result['id'], data

    def test_auth_csrf_and_bootstrap(self):
        anonymous = Client(self.url)
        self.assertEqual(anonymous.call('state')[0], 401)
        self.assertEqual(anonymous.call('invoice/1')[0], 401)
        self.assertEqual(anonymous.call('setup',dict(username='second',password=self.password,display_name='second'))[0], 409)
        self.assertEqual(self.owner.call('expenses',dict(date='2026-11-02',name='Điện',amount=1),headers={'X-CSRF-Token':'wrong'})[0],403)
        self.assertEqual(self.owner.call('expenses',{},headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(anonymous.call('login',dict(username='owner',password='incorrectpassword'))[0],401)
        with server.connect() as c:
            stored=c.execute("SELECT password_hash FROM users WHERE username='owner'").fetchone()[0]
            self.assertNotIn(self.password,stored)
            self.assertTrue(server.check_password(self.password,stored))

    def test_codespaces_forwarded_origin(self):
        from unittest.mock import patch
        # Model the browser's external HTTPS Origin with an internal Host.
        expected='https://sua-example-8000.app.github.dev'
        with patch.dict(server.os.environ, {'CODESPACES':'true','CODESPACE_NAME':'sua-example',
                'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev','PORT':'8000'}):
            status,_=self.owner.call('stock',dict(id=1,delta=1,note='Codespaces origin test'),
                                     headers={'Origin':expected,'Sec-Fetch-Site':'same-origin'})
            self.assertEqual(status,201)
            for origin in ['https://other-8000.app.github.dev','https://evil.example',
                           'http://sua-example-8000.app.github.dev']:
                self.assertEqual(self.owner.call('stock',{},headers={'Origin':origin})[0],403)
            self.assertEqual(self.owner.call('stock',{},headers={'Origin':expected,'Sec-Fetch-Site':'cross-site'})[0],403)
        # Forwarded headers alone are never used as trusted origins.
        self.assertEqual(self.owner.call('stock',{},headers={'Origin':expected,'X-Forwarded-Host':'sua-example-8000.app.github.dev'})[0],403)

    def test_cashier_and_inventory_permissions(self):
        state=self.cashier.state()
        self.assertFalse(state['audit']);self.assertFalse(state['history']);self.assertFalse(state['stock'])
        self.assertTrue(all('cost' not in p for p in state['menu']))
        own_id,_=self.sale(self.cashier)
        owner_id,_=self.sale()
        state=self.cashier.state()
        self.assertIn(own_id,[o['id'] for o in state['orders']]);self.assertNotIn(owner_id,[o['id'] for o in state['orders']])
        for o in state['orders']:
            self.assertNotIn('cost',o)
            self.assertTrue(all('cost' not in item for item in json.loads(o['items'])))
        for path in ['report','backup','export','invoice/'+str(owner_id)]:
            self.assertEqual(self.cashier.call(path)[0],403,path)
        for path in ['products','users','settings','refunds','expenses','cakes','stock']:
            self.assertEqual(self.cashier.call(path,{})[0],403,path)
        inv=self.inventory.state()
        self.assertTrue(inv['stock']);self.assertTrue(inv['recipes']);self.assertFalse(inv['orders'])
        self.assertTrue(all('price' not in s for s in inv['stock']))
        self.assertEqual(self.inventory.call('orders',{})[0],403)

    def test_sale_snapshot_prices_and_pdf(self):
        product=dict(id='TEST_SNAP',name='Cà phê thử nghiệm tiếng Việt',category='Test',size='M',price=25000,cost=1234,active=True)
        self.assertEqual(self.owner.call('products',product)[0],201)
        self.assertEqual(self.owner.call('settings',dict(name='SỨA thử nghiệm',address='Địa chỉ có dấu',phone='0123456789',footer='Cảm ơn'))[0],201)
        oid,_=self.sale(items=[dict(id='TEST_SNAP',qty=2,price=1)],discount=1000,note='Ít đá')
        self.owner.call('products',dict(product,price=35000,cost=2000))
        self.owner.call('settings',dict(name='Tên mới',address='',phone='',footer=''))
        order=next(o for o in self.owner.state()['orders'] if o['id']==oid)
        self.assertEqual(order['total'],49000);self.assertEqual(order['cost'],2468)
        self.assertEqual(json.loads(order['shop_json'])['name'],'SỨA thử nghiệm')
        self.assertEqual(json.loads(order['items'])[0]['price'],25000)
        status,pdf=self.owner.call('invoice/'+str(oid));self.assertEqual(status,200)
        self.assertTrue(pdf.startswith(b'%PDF'));self.assertGreater(len(pdf),10000)
        self.assertEqual(self.owner.call('products',dict(product,active=False))[0],201)
        self.assertEqual(self.owner.call('orders',dict(request_key='inactive',items=[dict(id='TEST_SNAP',qty=1)],payment='Tiền mặt'))[0],400)

    def test_idempotency_replay_and_concurrent_requests(self):
        oid,payload=self.sale()
        status,result=self.owner.call('orders',payload);self.assertEqual(status,201);self.assertEqual(result['id'],oid)
        self.assertTrue(result['replayed'])
        self.assertEqual(self.owner.call('orders',dict(payload,payment='Chuyển khoản'))[0],409)
        payload=dict(payload,request_key=secrets.token_hex(16))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.owner.call('orders',payload),range(2)))
        self.assertTrue(all(r[0]==201 for r in results));self.assertEqual(results[0][1]['id'],results[1][1]['id'])
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM orders WHERE request_key=?',(payload['request_key'],)).fetchone()[0],1)

    def test_stock_atomic_concurrent_and_audit(self):
        self.inventory.state()
        sid=server.SEED['stock'][0]['id']
        with server.connect() as c:c.execute('UPDATE stock SET qty=1 WHERE id=?',(sid,))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.inventory.call('stock',dict(id=sid,delta=-1,note='Xuất thử')),range(2)))
        self.assertEqual(sorted(r[0] for r in results),[201,400])
        self.assertEqual(self.owner.state()['stock'][0]['qty'],0)
        self.assertEqual(self.owner.call('stock',dict(id=sid,delta=2,note='Nhập mới'))[0],201)
        self.assertEqual(self.owner.state()['stock'][0]['qty'],2)
        self.assertTrue(any(a['action']=='stock.adjust' for a in self.owner.state()['audit']))

    def test_refund_report_and_export(self):
        oid,_=self.sale()
        period=server.now()[:10]
        before=self.owner.call('report?period='+period)[1]
        status,_=self.owner.call('refunds',dict(order_id=oid,reason='Khách đổi ý'));self.assertEqual(status,201)
        after=self.owner.call('report?period='+period)[1]
        order=next(o for o in self.owner.state()['orders'] if o['id']==oid)
        self.assertEqual(after['revenue'],before['revenue']-order['total'])
        self.assertEqual(after['cost'],before['cost'])
        self.assertEqual(order['status'],'refunded')
        self.owner.call('refunds',dict(order_id=oid,reason='Gửi lại'))
        self.assertEqual(self.owner.call('report?period='+period)[1]['revenue'],after['revenue'])
        status,raw=self.owner.call('export?period='+period)
        self.assertEqual(status,200);self.assertIn('Doanh thu thuần',raw.decode('utf-8-sig'))
        self.assertEqual(self.owner.call('report?period=2026-99')[0],400)

    def test_cakes_expenses_void(self):
        date=server.now()[:10]
        before=self.owner.call('report?period='+date)[1]
        cake=dict(date=date,name='Bánh flan',received=10,sold=6,waste=1,price=15000,cost=6000)
        self.assertEqual(self.owner.call('cakes',cake)[0],201)
        self.assertEqual(self.owner.call('cakes',dict(cake,sold=11))[0],400)
        self.assertEqual(self.owner.call('expenses',dict(date=date,name='Điện',amount=50000,category='Điện nước'))[0],201)
        after=self.owner.call('report?period='+date)[1]
        self.assertEqual(after['revenue']-before['revenue'],90000)
        self.assertEqual(after['cost']-before['cost'],36000)
        self.assertEqual(after['waste']-before['waste'],6000)
        self.assertEqual(after['profit']-before['profit'],-2000)
        state=self.owner.state()
        for table in ['cakes','expenses']:
            self.assertEqual(self.owner.call('void',dict(type=table,id=state[table][0]['id'],reason='Nhập nhầm'))[0],201)
        final=self.owner.call('report?period='+date)[1]
        for key in ['revenue','cost','waste','expenses','profit']:self.assertEqual(final[key],before[key])

    def test_backup_is_restorable_and_init_preserves_work(self):
        oid,_=self.sale()
        self.owner.call('stock',dict(id=1,delta=3,note='Kiểm kê'))
        before=self.owner.state()
        status,data=self.owner.call('backup');self.assertEqual(status,200)
        restored=sqlite3.connect(':memory:');restored.deserialize(data)
        self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(restored.execute('SELECT COUNT(*) FROM orders WHERE id=?',(oid,)).fetchone()[0],1)
        self.assertEqual(restored.execute('SELECT qty FROM stock WHERE id=1').fetchone()[0],before['stock'][0]['qty'])
        restored.close();server.init();after=self.owner.state()
        self.assertEqual(before['stock'],after['stock']);self.assertEqual(before['orders'],after['orders'])

    def test_seed_identity_prevents_mixing(self):
        from unittest.mock import patch
        original=server.DB
        try:
            server.DB=Path(self.tmp.name)/'seed-identity.sqlite3'
            server.init()
            with patch.object(server,'DEMO',not server.DEMO):
                with self.assertRaisesRegex(ValueError,'không khớp'):
                    server.init()
            with server.connect() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM products').fetchone()[0],len(server.SEED['menu']))
        finally:server.DB=original

    def test_legacy_database_migration(self):
        original=server.DB
        try:
            server.DB=Path(self.tmp.name)/'legacy.sqlite3'
            c=sqlite3.connect(server.DB)
            c.executescript("CREATE TABLE orders(id INTEGER PRIMARY KEY,created TEXT,payment TEXT,total REAL,cost REAL,items TEXT); INSERT INTO orders VALUES(1,'2026-11-01T10:00:00+07:00','Tiền mặt',15000,1234.5,'[]'); CREATE TABLE stock(id INTEGER PRIMARY KEY,qty REAL); INSERT INTO stock VALUES(1,42);")
            c.close();server.init();server.init()
            with server.connect() as c:
                self.assertEqual(c.execute('SELECT qty FROM stock WHERE id=1').fetchone()[0],42)
                r=c.execute('SELECT * FROM orders WHERE id=1').fetchone()
                self.assertEqual(r['total'],15000);self.assertEqual(r['cost'],1234.5);self.assertEqual(r['status'],'paid')
        finally:server.DB=original

    def test_invalid_sales_and_money(self):
        for items in [[],[dict(id='CF01_M',qty=-1)],[dict(id='CF01_M',qty=0.5)],[dict(id='MISSING',qty=1)]]:
            self.assertEqual(self.owner.call('orders',dict(request_key=secrets.token_hex(8),items=items,payment='Tiền mặt'))[0],400)
        self.assertEqual(self.owner.call('expenses',dict(date='2026-11-02',name='Sai',amount=-1))[0],400)
        self.assertEqual(server.money('1234.5'),1235)
        for value in [True,'NaN','Infinity']:
            with self.assertRaises(ValueError):server.money(value)

    def test_lock_account_revokes_sessions(self):
        password=secrets.token_urlsafe(20)
        self.assertEqual(self.owner.call('users',dict(username='locked_user',password=password,display_name='User',role='cashier'))[0],201)
        client=Client(self.url);client.login('locked_user',password)
        user=next(u for u in self.owner.state()['users'] if u['username']=='locked_user')
        self.assertEqual(self.owner.call('users',dict(id=user['id'],role='cashier',active=False))[0],201)
        self.assertEqual(client.call('state')[0],401)
        self.assertEqual(self.owner.call('users',dict(id=self.owner.state()['user']['id'],role='cashier',active=False))[0],400)

    def test_login_rate_limit_and_expired_session(self):
        with server.connect() as c:
            c.execute('DELETE FROM login_attempts')
            c.executemany('INSERT INTO login_attempts(peer,created) VALUES(?,?)', [('127.0.0.1',server.stamp())]*10)
        try:
            self.assertEqual(Client(self.url).call('login',dict(username='owner',password=self.password))[0],429)
        finally:
            with server.connect() as c:c.execute('DELETE FROM login_attempts')
        client=Client(self.url);client.login('cashier',self.password)
        with server.connect() as c:
            c.execute('UPDATE sessions SET expires=0 WHERE csrf=?',(client.csrf,))
        self.assertEqual(client.call('state')[0],401)

    def test_long_invoice_and_refund_on_later_day(self):
        # The order stays on its business day; the refund belongs to its own day.
        oid,_=self.sale(items=[dict(id='CF01_M',qty=1)]*70,note='Ghi chú tiếng Việt '*20)
        with server.connect() as c:
            c.execute("UPDATE orders SET created='2026-01-01T10:00:00+07:00' WHERE id=?",(oid,))
        before=self.owner.call('report?period=2026-01-01')[1]
        self.assertEqual(self.owner.call('refunds',dict(order_id=oid,reason='Hoàn ngày khác'))[0],201)
        after=self.owner.call('report?period=2026-01-01')[1]
        self.assertEqual(before,after)
        status,pdf=self.owner.call('invoice/'+str(oid));self.assertEqual(status,200)
        import re
        self.assertGreater(len(re.findall(rb'/Type /Page\b',pdf)),1)

    def test_password_change_revokes_all_sessions(self):
        p=secrets.token_urlsafe(20)
        self.owner.call('users',dict(username='password_test',password=p,display_name='User',role='cashier'))
        one,two=Client(self.url),Client(self.url)
        one.login('password_test',p);two.login('password_test',p)
        new=secrets.token_urlsafe(20)
        self.assertEqual(one.call('password',dict(current='wrong',password=new))[0],403)
        self.assertEqual(one.call('password',dict(current=p,password=new))[0],201)
        self.assertEqual(two.call('state')[0],401)
        one.login('password_test',new)
        self.assertEqual(one.call('state')[0],200)


if __name__=='__main__':unittest.main()
