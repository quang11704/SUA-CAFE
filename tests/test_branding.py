import base64,io,json,secrets,sys,tempfile,threading,unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from test_app import Client
from test_live_import import sample_uploads

class BrandingTest(unittest.TestCase):
 def setUp(self):
  self.old=server.DB;self.tmp=tempfile.TemporaryDirectory();server.DB=Path(self.tmp.name)/'test.sqlite3'
  seed=json.loads((server.BASE/'data/demo.json').read_text());server.init(seed=seed,demo=True)
  self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  threading.Thread(target=self.http.serve_forever,daemon=True).start();self.url='http://127.0.0.1:'+str(self.http.server_port)
  self.owner=Client(self.url);self.password=secrets.token_hex(12);self.owner.login('brand_owner',self.password,setup=True)
 def tearDown(self):
  self.http.shutdown();self.http.server_close();server.DB=self.old;self.tmp.cleanup()
 def logo(self,color='pink'):
  b=io.BytesIO();Image.new('RGB',(40,30),color).save(b,format='PNG');return b.getvalue()
 def save(self,color='pink'):
  raw=self.logo(color);status,data=self.owner.call('branding',{'logo':{'name':'logo.png','base64':base64.b64encode(raw).decode()},'font':'script'});self.assertEqual(status,201,data);return raw
 def sale(self):
  status,data=self.owner.call('orders',dict(request_key=secrets.token_hex(12),items=[dict(id='CF01_M',qty=1)],payment='Tiền mặt'));self.assertEqual(status,201,data);return data['id']
 def test_logo_exact_bytes_auth_and_settings_merge(self):
  raw=self.save();s=self.owner.state();url=s['settings']['logo_url'].removeprefix('/api/')
  self.assertEqual(self.owner.call(url),(200,raw));self.assertEqual(Client(self.url).call(url)[0],401)
  self.owner.call('settings',dict(name='Sứa Café',address='',phone='',footer='Cảm ơn'))
  self.assertEqual(self.owner.state()['settings']['logo_url'],s['settings']['logo_url'])
 def test_snapshot_logo_old_invoice_and_print(self):
  self.save();old_logo=self.owner.state()['settings']['logo_url'];oid=self.sale();self.save('blue')
  current=self.owner.state();self.assertNotEqual(old_logo,current['settings']['logo_url'])
  status,page=self.owner.call(f'print/{oid}?dataset={current["dataset_id"]}&auto=1');self.assertEqual(status,200)
  self.assertIn(old_logo.encode(),page);self.assertNotIn(current['settings']['logo_url'].encode(),page);self.assertIn(b'data-auto-print="1"',page);self.assertNotIn(('#'+str(oid)).encode(),page)
  self.assertEqual(self.owner.call('invoice/'+str(oid))[0],200)
  self.owner.call('branding',dict(remove_logo=True,font='classic'))
  self.assertFalse(self.owner.state()['settings']['logo_url']);self.assertEqual(self.owner.call(old_logo.removeprefix('/api/'))[0],200)
 def test_invalid_logo_and_font_do_not_replace(self):
  self.save();before=self.owner.state()['settings']
  for data in [{'font':'bad'},{'logo':{'name':'x.svg','base64':base64.b64encode(b'<svg/>').decode()}},{'logo':{'name':'x.png','base64':'%%'} }]:
   self.assertEqual(self.owner.call('branding',data)[0],400)
   self.assertEqual(self.owner.state()['settings'],before)
 def test_role_bound_print_and_branding(self):
  oid=self.sale();self.owner.call('users',dict(username='brand_staff',password=self.password,display_name='staff',role='cashier'))
  staff=Client(self.url);staff.login('brand_staff',self.password)
  self.assertEqual(staff.call('branding',dict(font='classic'))[0],403)
  self.assertEqual(staff.call('print/'+str(oid))[0],403)
  self.assertEqual(Client(self.url).call('print/'+str(oid))[0],401)
 def test_logo_survives_real_import(self):
  raw=self.save();url=self.owner.state()['settings']['logo_url']
  status,job=self.owner.call('import/preview',sample_uploads());self.assertEqual(status,201,job)
  status,result=self.owner.call('import/apply',dict(job_id=job['job_id'],confirmed=True,inventory_date=server.now()[:10]));self.assertEqual(status,201,result)
  self.owner.state();self.assertEqual(self.owner.call(url.removeprefix('/api/')),(200,raw))
 def test_print_toppings_and_no_script_injection(self):
  self.owner.call('toppings',dict(id='TEST_CREAM',name='Kem Muối',price=5000,cost=1000,cost_known=True,active=True))
  status,result=self.owner.call('orders',dict(request_key=secrets.token_hex(12),items=[dict(id='CF01_M',qty=2,toppings=[dict(id='TEST_CREAM',qty=2)])],payment='Tiền mặt',note='<script>bad()</script>'));self.assertEqual(status,201,result)
  status,html=self.owner.call('print/'+str(result['id']));self.assertEqual(status,200);self.assertIn('64.000'.encode(),html);self.assertIn('Kem Muối'.encode(),html);self.assertNotIn(b'<script>bad()',html)

if __name__=='__main__':unittest.main()
