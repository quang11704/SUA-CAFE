"""Server-priced modifiers and reviewed retail-menu updates (synthetic fixtures)."""
import json
import secrets
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import catalog
import server
from test_app import Client as BaseClient


class Client(BaseClient):
    def call(self,path,data=None,headers=None):
        status,result=super().call(path,data,headers)
        if status<400 and isinstance(result,dict) and result.get('dataset_id'):
            self.dataset_id=result['dataset_id']
        return status,result


class ToppingTest(unittest.TestCase):
    def setUp(self):
        self.old_db,self.old_catalog=server.DB,catalog.CATALOG_PATH
        self.tmp=tempfile.TemporaryDirectory(prefix='sua-toppings-')
        folder=Path(self.tmp.name)
        server.DB=folder/'test.sqlite3'
        seed=dict(menu=[
            dict(id='OLD_M',name='Cà phê sữa',category='Coffee',size='M',price=16000,cost=5000),
            dict(id='OTHER_M',name='Trà Thử',category='Tea',size='M',price=20000,cost=7000)],
            stock=[dict(id=1,name='Test stock',unit='g',price=1,qty=100,minimum=1,note='Synthetic')],
            recipes=[],batches=[],history=[])
        server.init(seed=seed,demo=True)
        self.catalog=dict(version='test-menu-v1',products=[
            dict(id='NEW_M',name='Cafe Sữa',category='Coffee',size='M',price=18000),
            dict(id='NEW_L',name='Cafe Sữa',category='Coffee',size='L',price=22000),
            dict(id='TEA_M',name='Trà Thử',category='Tea',size='M',price=26000)],
            toppings=[dict(id='T_GEN',name='Kem Muối',price=6000,scope='general'),
                      dict(id='T_SPEC',name='Kem Chanh',price=5000,scope='suggested')],
            suggestions=[dict(product_name='Cafe Sữa',topping_id='T_GEN',price=5000),
                         dict(product_name='Cafe Sữa',topping_id='T_SPEC',price=5000)])
        catalog.CATALOG_PATH=folder/'catalog.json'
        self.write_catalog()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.http.server_port)
        self.password=secrets.token_urlsafe(20)
        self.owner=Client(self.url);self.owner.login('test_owner',self.password,setup=True)

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
        server.DB=self.old_db
        catalog.CATALOG_PATH=self.old_catalog
        self.tmp.cleanup()

    def write_catalog(self):
        catalog.CATALOG_PATH.write_text(json.dumps(self.catalog,ensure_ascii=False),encoding='utf-8')

    def apply(self):
        status,data=self.owner.call('catalog/apply',{'version':self.catalog['version'],'confirmed':True})
        self.assertEqual(status,201,data)
        return data

    def sale(self,items,client=None,**extra):
        payload=dict(request_key=secrets.token_hex(16),items=items,payment='Tiền mặt',**extra)
        status,data=(client or self.owner).call('orders',payload)
        self.assertEqual(status,201,data)
        state=self.owner.state()
        return next(o for o in state['orders'] if o['id']==data['id']),payload

    def known_topping(self,price=6000,cost=1000,active=True):
        status,data=self.owner.call('toppings',dict(id='T_GEN',name='Kem Muối',price=price,cost=cost,cost_known=True,active=active))
        self.assertEqual(status,201,data)

    def test_review_apply_preserves_old_snapshots_and_costs(self):
        old,_=self.sale([dict(id='OLD_M',qty=1)])
        status,preview=self.owner.call('catalog/preview')
        self.assertEqual(status,200)
        self.assertEqual(preview['missing_cost_products'],1)
        matched=next(p for p in preview['products'] if p['id']=='NEW_M')
        self.assertEqual(matched['matched_product_id'],'OLD_M')
        self.assertEqual(matched['matched_cost'],5000)
        self.assertEqual(len([p for p in self.owner.state()['menu'] if p['active']]),2)
        self.apply()
        state=self.owner.state()
        self.assertEqual(state['catalog_version'],'test-menu-v1')
        self.assertEqual(state['menu_version'],'test-menu-v1')
        with server.connect() as connection:
            links=json.loads(server.metadata(connection,'catalog_recipe_links'))
        self.assertEqual(links.get('NEW_M'),'OLD_M')
        self.assertNotIn('NEW_L',links)
        self.assertEqual({p['id'] for p in state['menu'] if p['active']},{'NEW_M','NEW_L','TEA_M'})
        self.assertEqual(next(p for p in state['menu'] if p['id']=='NEW_M')['cost'],5000)
        self.assertEqual(next(p for p in state['menu'] if p['id']=='NEW_L')['cost_known'],0)
        archived=next(o for o in state['orders'] if o['id']==old['id'])
        self.assertEqual(archived['items'],old['items']);self.assertEqual(archived['cost'],5000)
        self.assertTrue(any(a['action']=='product.catalog' for a in state['audit']))
        self.assertTrue(any(a['action']=='catalog.apply' for a in state['audit']))

    def test_apply_requires_confirmation_version_and_is_idempotent(self):
        self.assertEqual(self.owner.call('catalog/apply',dict(version='test-menu-v1',confirmed=False))[0],400)
        self.assertEqual(self.owner.call('catalog/apply',dict(version='old-version',confirmed=True))[0],409)
        self.apply()
        self.assertEqual(self.owner.call('products',dict(id='NEW_M',name='Cafe Sữa',category='Coffee',size='M',price=23000,cost=5500,cost_known=True,active=True))[0],201)
        repeated=self.apply();self.assertTrue(repeated['replayed'])
        product=next(p for p in self.owner.state()['menu'] if p['id']=='NEW_M')
        self.assertEqual(product['price'],23000);self.assertEqual(product['cost'],5500)
        server.init()
        product=next(p for p in self.owner.state()['menu'] if p['id']=='NEW_M')
        self.assertEqual(product['price'],23000)

    def test_server_modifier_prices_duplicate_merge_and_snapshot(self):
        self.apply();self.known_topping()
        order,payload=self.sale([dict(id='NEW_M',qty=3,price=1,toppings=[
            dict(id='T_GEN',qty=1,price=0,cost=0),dict(id='T_GEN',qty=1)])],discount=1000)
        self.assertEqual(order['subtotal'],84000);self.assertEqual(order['total'],83000)
        self.assertEqual(order['cost'],21000);self.assertEqual(order['cost_complete'],1)
        item=json.loads(order['items'])[0]
        self.assertEqual(item['base_price'],18000);self.assertEqual(item['price'],28000)
        self.assertEqual(item['cost'],7000);self.assertEqual(item['toppings'][0]['qty'],2)
        self.assertEqual(item['toppings'][0]['price'],5000)
        self.known_topping(price=9000,cost=2000)
        old=next(o for o in self.owner.state()['orders'] if o['id']==order['id'])
        self.assertEqual(old['items'],order['items'])
        status,result=self.owner.call('orders',payload)
        self.assertEqual(status,201);self.assertEqual(result['id'],order['id'])
        self.assertTrue(result['replayed'])

    def test_variants_with_different_modifiers_stay_separate(self):
        self.apply();self.known_topping()
        order,_=self.sale([dict(id='NEW_M',qty=1),dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=1)])])
        self.assertEqual(order['total'],41000)
        items=json.loads(order['items']);self.assertEqual(len(items),2)
        self.assertEqual(items[0]['toppings'],[])
        self.assertEqual(items[1]['toppings'][0]['id'],'T_GEN')
        plain,_=self.sale([dict(id='TEA_M',qty=1,toppings=[dict(id='T_GEN',qty=1)])])
        self.assertEqual(plain['total'],32000)
        self.assertEqual(json.loads(plain['items'])[0]['toppings'][0]['price'],6000)

    def test_invalid_inactive_and_ineligible_modifiers_rejected(self):
        self.apply()
        invalid=[dict(id='NEW_M',qty=1,toppings={}),
                 dict(id='NEW_M',qty=1,toppings=[dict(id='MISSING',qty=1)]),
                 dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=-1)]),
                 dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=.5)]),
                 dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=11),dict(id='T_GEN',qty=10)]),
                 dict(id='TEA_M',qty=1,toppings=[dict(id='T_SPEC',qty=1)])]
        for item in invalid:
            with self.subTest(item=item):
                self.assertEqual(self.owner.call('orders',dict(request_key=secrets.token_hex(8),items=[item],payment='Tiền mặt'))[0],400)
        self.known_topping(active=False)
        self.assertEqual(self.owner.call('orders',dict(request_key='inactive-top',items=[dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=1)])],payment='Tiền mặt'))[0],400)
        self.assertEqual(self.owner.state()['orders'],[])

    def test_missing_cost_marks_report_incomplete_and_history_unchanged(self):
        self.apply()
        order,_=self.sale([dict(id='NEW_L',qty=1)])
        self.assertEqual(order['cost_complete'],0)
        status,report=self.owner.call('report?period='+server.now()[:10])
        self.assertEqual(status,200);self.assertEqual(report['revenue'],22000)
        self.assertEqual(report['incomplete_cost_orders'],1);self.assertIsNone(report['profit'])
        self.owner.call('products',dict(id='NEW_L',name='Cafe Sữa',category='Coffee',size='L',price=22000,cost=8000,cost_known=True,active=True))
        self.assertIsNone(self.owner.call('report?period='+server.now()[:10])[1]['profit'])
        self.assertEqual(next(o for o in self.owner.state()['orders'] if o['id']==order['id'])['cost_complete'],0)
        unknown_top,_=self.sale([dict(id='NEW_M',qty=1,toppings=[dict(id='T_SPEC',qty=1)])])
        self.assertEqual(unknown_top['cost_complete'],0)

    def test_cashier_cannot_edit_catalog_or_see_nested_cost(self):
        self.apply();self.known_topping()
        self.owner.call('users',dict(username='test_cashier',display_name='Cashier',password=self.password,role='cashier'))
        cashier=Client(self.url);cashier.login('test_cashier',self.password)
        for route in ['catalog/apply','toppings']:
            self.assertEqual(cashier.call(route,{})[0],403)
        self.assertEqual(cashier.call('catalog/preview')[0],403)
        order,_=self.sale([dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=1)])],client=cashier)
        state=cashier.state()
        self.assertTrue(all('cost' not in t for t in state['toppings']))
        item=json.loads(next(o for o in state['orders'] if o['id']==order['id'])['items'])[0]
        self.assertNotIn('cost',item)
        self.assertTrue(all('cost' not in t for t in item['toppings']))
        self.assertEqual(item['toppings'][0]['price'],5000)

    def test_ambiguous_cost_match_does_not_guess(self):
        self.owner.call('products',dict(id='AMBIG_M',name='Cafe Sữa',category='Coffee',size='M',price=17000,cost=7000,active=True))
        preview=self.owner.call('catalog/preview')[1]
        product=next(p for p in preview['products'] if p['id']=='NEW_M')
        self.assertFalse(product['cost_known']);self.assertIsNone(product['matched_cost'])
        self.apply()
        self.assertEqual(next(p for p in self.owner.state()['menu'] if p['id']=='NEW_M')['cost_known'],0)

    def test_menu_revision_blocks_stale_checkout(self):
        old=self.owner.dataset_id
        self.apply()
        self.assertNotEqual(self.owner.state()['dataset_id'],old)
        self.assertEqual(self.owner.call('orders',dict(request_key='stale-catalog',
            items=[dict(id='NEW_M',qty=1)],payment='Tiền mặt'),headers={'X-Sua-Dataset':old})[0],409)
        old=self.owner.dataset_id
        self.known_topping()
        self.assertNotEqual(self.owner.state()['dataset_id'],old)
        self.assertEqual(self.owner.call('orders',dict(request_key='stale-topping',
            items=[dict(id='NEW_M',qty=1,toppings=[dict(id='T_GEN',qty=1)])],payment='Tiền mặt'),
            headers={'X-Sua-Dataset':old})[0],409)

    def test_catalog_validation_rejects_broken_suggestions(self):
        self.catalog['suggestions'].append(dict(product_name='Unknown drink',topping_id='T_GEN',price=1))
        self.write_catalog()
        self.assertEqual(self.owner.call('catalog/preview')[0],400)
        self.assertEqual(self.owner.call('catalog/apply',dict(version='test-menu-v1',confirmed=True))[0],400)
        self.assertEqual(len([p for p in self.owner.state()['menu'] if p['active']]),2)


if __name__=='__main__':unittest.main()
