import json,re,secrets,unittest
import server
import test_branding
from test_app import Client

class LabelTest(unittest.TestCase):
 setUp=test_branding.BrandingTest.setUp
 tearDown=test_branding.BrandingTest.tearDown
 def order(self,items=None,note=''):
  data=dict(request_key=secrets.token_hex(12),items=items or [dict(id='CF01_M',qty=3,note='Ít đá')],payment='Tiền mặt',note=note)
  status,result=self.owner.call('orders',data);self.assertEqual(status,201,result);return result['id']
 def test_one_label_each_cup_50x30_and_snapshot(self):
  oid=self.order()
  status,raw=self.owner.call('labels/'+str(oid));self.assertEqual(status,200)
  text=raw.decode();self.assertEqual(text.count('<section class="label"'),3)
  self.assertIn('size:50.0mm 30.0mm',text)
  for i in range(1,4):self.assertIn(str(i)+'/3',text)
  self.assertIn('Ít đá',text);self.assertIn('22.000 đ/ly',text)
  self.owner.call('products',dict(id='CF01_M',name='Changed',category='Test',size='M',price=99000,cost=1,active=True))
  raw=self.owner.call('labels/'+str(oid))[1].decode()
  self.assertIn('22.000 đ/ly',raw);self.assertNotIn('99.000 đ/ly',raw)
 def test_toppings_notes_and_html_escape(self):
  self.owner.call('toppings',dict(id='TOP_TEST',name='Kem Muối',price=5000,cost=1000,active=True,cost_known=True))
  oid=self.order([dict(id='CF01_M',qty=1,toppings=[dict(id='TOP_TEST',qty=2)],note='<script>x()</script>')])
  status,raw=self.owner.call('labels/'+str(oid));self.assertEqual(status,200)
  text=raw.decode();self.assertIn('32.000 đ/ly',text);self.assertIn('Kem Muối × 2',text);self.assertNotIn('<script>x()',text);self.assertIn('&lt;script&gt;',text)
 def test_partial_reprint_does_not_create_order(self):
  oid=self.order();before=len(self.owner.state()['orders'])
  for _ in range(2):
   status,raw=self.owner.call(f'labels/{oid}?start=2&count=2');self.assertEqual(status,200)
   self.assertEqual(raw.decode().count('<section class="label"'),2)
   self.assertIn('2/3',raw.decode());self.assertNotIn('1/3',raw.decode())
  self.assertEqual(len(self.owner.state()['orders']),before)
  for query in ['start=0','count=201','start=3&count=2','width_mm=nan','height_mm=10']:
   self.assertEqual(self.owner.call(f'labels/{oid}?{query}')[0],400)
 def test_settings_validation_and_preservation(self):
  s=self.owner.state()['settings'];self.assertEqual(self.owner.call('label-settings',dict(width_mm=50,height_mm=40,margin_mm=1,font_pt=8))[0],201)
  self.assertEqual(self.owner.state()['settings']['name'],s['name'])
  for width in [0,101,'nan',True]:self.assertEqual(self.owner.call('label-settings',dict(width_mm=width))[0],400)
  self.assertEqual(self.owner.state()['settings']['label_printer']['height_mm'],40)
 def test_access_and_stale_links(self):
  oid=self.order();self.assertEqual(Client(self.url).call('labels/'+str(oid))[0],401)
  self.owner.call('users',dict(username='label_staff',display_name='Staff',password=self.password,role='cashier'))
  staff=Client(self.url);staff.login('label_staff',self.password)
  self.assertEqual(staff.call('labels/'+str(oid))[0],403)
  self.assertEqual(staff.call('label-settings',{})[0],403)
  status,data=staff.call('orders',dict(request_key=secrets.token_hex(12),items=[dict(id='CF01_M',qty=1)],payment='Tiền mặt'));self.assertEqual(status,201)
  self.assertEqual(staff.call('labels/'+str(data['id']))[0],200)
  self.assertEqual(self.owner.call('labels/'+str(oid)+'?dataset=old')[0],409)
 def test_long_content_prevents_automatic_clipped_print(self):
  oid=self.order(note='Ghi chú rất dài '*30)
  status,raw=self.owner.call('labels/'+str(oid)+'?auto=1&width_mm=20&height_mm=20');self.assertEqual(status,200)
  self.assertIn('Nội dung quá dài'.encode(),raw);self.assertIn(b'data-auto-print="0"',raw);self.assertIn(b'id="print-labels" disabled',raw)

if __name__=='__main__':unittest.main()
