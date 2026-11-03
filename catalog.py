"""Owner-reviewed public retail menu and server-priced toppings."""
import json
import re
import unicodedata
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / 'data/menu_2026_11.json'


def normalize_name(value):
    value = unicodedata.normalize('NFKD', value.casefold().replace('đ', 'd'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r'[^a-z0-9]+', ' ', value).strip()
    # Explicit lexical aliases only; never fuzzy-match different drinks.
    value = re.sub(r'\bca phe\b', 'cafe', value)
    aliases = {'cafe dalgonal': 'cafe dalgona', 'phindi hanh nhan': 'phin di hanh nhan'}
    return aliases.get(value, value)


def _id(app, value):
    value = app.text(value, 'Mã món/topping', 60)
    if not re.fullmatch('[A-Za-z0-9_-]+', value):
        raise ValueError('Mã chỉ gồm chữ, số, gạch ngang và gạch dưới')
    return value


def _bool(value, label):
    if not isinstance(value, bool):
        raise ValueError(label + ' phải là giá trị có/không hợp lệ')
    return int(value)


def load_catalog(app):
    data = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    app.text(data['version'], 'Phiên bản menu', 100)
    for key in ['products', 'toppings', 'suggestions']:
        if not isinstance(data.get(key), list):
            raise ValueError('Danh mục menu không hợp lệ')
    if not data['products'] or len(data['products']) > 1000 or len(data['toppings']) > 100:
        raise ValueError('Danh mục menu vượt giới hạn')
    ids = set()
    for product in data['products']:
        product['id'] = _id(app, product['id'])
        if product['id'] in ids:
            raise ValueError('Mã món trong menu bị trùng')
        ids.add(product['id'])
        for field in ['name', 'category', 'size']:
            product[field] = app.text(product[field], field, 120)
        product['price'] = app.money(product['price'])
    topping_ids = set()
    for topping in data['toppings']:
        topping['id'] = _id(app, topping['id'])
        if topping['id'] in topping_ids:
            raise ValueError('Mã topping trong menu bị trùng')
        topping_ids.add(topping['id'])
        topping['name'] = app.text(topping['name'], 'Tên topping', 120)
        topping['price'] = app.money(topping['price'])
        if topping.get('scope','general') not in {'general','suggested'}:
            raise ValueError('Phạm vi topping không hợp lệ')
        topping['scope'] = topping.get('scope','general')
    names = {normalize_name(p['name']) for p in data['products']}
    combinations = set()
    for suggestion in data['suggestions']:
        suggestion['product_name'] = app.text(suggestion['product_name'], 'Tên món gợi ý', 120)
        if suggestion['topping_id'] not in topping_ids or normalize_name(suggestion['product_name']) not in names:
            raise ValueError('Gợi ý topping tham chiếu món/topping không tồn tại')
        key = (normalize_name(suggestion['product_name']), suggestion['topping_id'])
        if key in combinations:
            raise ValueError('Gợi ý topping bị trùng')
        combinations.add(key)
        suggestion['price'] = app.money(suggestion['price'])
    return data


def _match(product, existing):
    matches = [p for p in existing if normalize_name(p['name']) == normalize_name(product['name'])
               and p['size'].casefold() == product['size'].casefold()]
    # Active records take precedence over archived versions, but never choose
    # between multiple current candidates with the same normalized name/size.
    active = [p for p in matches if p.get('active', 1)]
    matches = active or matches
    return matches[0] if len(matches) == 1 else None


def preview(app, c):
    data = load_catalog(app)
    existing = [dict(r) for r in c.execute('SELECT * FROM products')]
    existing_toppings = [dict(r) for r in c.execute('SELECT * FROM toppings')]
    products = []
    for product in data['products']:
        match = _match(product, existing)
        known = bool(match and match.get('cost_known', 1))
        products.append(dict(product, matched_product_id=match['id'] if match else None,
                             cost_known=known, matched_cost=match['cost'] if known else None))
    toppings = []
    for topping in data['toppings']:
        matches = [t for t in existing_toppings if normalize_name(t['name']) == normalize_name(topping['name'])]
        match = matches[0] if len(matches) == 1 else None
        known = bool(match and match['cost_known'])
        toppings.append(dict(topping, cost_known=known, matched_cost=match['cost'] if known else None))
    return dict(version=data['version'], products=products, toppings=toppings, suggestions=data['suggestions'],
                counts={'products': len(products), 'toppings': len(toppings), 'suggestions': len(data['suggestions'])},
                missing_cost_products=sum(not p['cost_known'] for p in products),
                missing_cost_toppings=sum(not t['cost_known'] for t in toppings),
                already_applied=app.metadata(c, 'catalog_version') == data['version'],
                warnings=['Giá bán lấy từ menu mới. Chỉ giữ giá vốn khi ghép được duy nhất tên món và size; món/topping còn thiếu giá vốn sẽ chưa tính lợi nhuận.',
                          'Giá topping gợi ý dưới món được giữ riêng với giá topping chung. Các giá và mức cộng thêm đều tính bằng VNĐ.',
                          'Áp dụng sẽ ngừng bán danh mục cũ, giữ nguyên đơn hàng, tồn kho và lịch sử.'])


def apply(app, c, user, payload):
    if payload.get('confirmed') is not True:
        raise app.ApiError(400, 'Cần xác nhận đã kiểm tra menu mới trước khi áp dụng')
    reviewed = preview(app, c)
    if payload.get('version') != reviewed['version']:
        raise app.ApiError(409, 'Phiên bản menu đã thay đổi; hãy mở bản xem trước mới')
    if reviewed['already_applied']:
        return dict(applied=True, version=reviewed['version'], replayed=True, counts=reviewed['counts'],dataset_id=app.metadata(c,'dataset_id'))
    previous_version = app.metadata(c, 'catalog_version')
    # Retirement preserves all snapshots and permits older item references.
    c.execute('UPDATE products SET active=0')
    c.execute('UPDATE toppings SET active=0')
    c.execute('DELETE FROM product_toppings')
    for product in reviewed['products']:
        old = c.execute('SELECT * FROM products WHERE id=?', (product['id'],)).fetchone()
        new = {k: product[k] for k in ['id', 'name', 'category', 'size', 'price']}
        new.update(cost=app.money(product['matched_cost']) if product['cost_known'] else 0,
                   cost_known=int(product['cost_known']), active=1)
        c.execute('INSERT INTO products(id,name,category,size,price,cost,cost_known,active) VALUES(:id,:name,:category,:size,:price,:cost,:cost_known,:active) ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category,size=excluded.size,price=excluded.price,cost=excluded.cost,cost_known=excluded.cost_known,active=1',new)
        app.audit(c,user,'product.catalog',new['id'],dict(old) if old else None,new)
    for topping in reviewed['toppings']:
        new = {k: topping[k] for k in ['id', 'name', 'price', 'scope']}
        new.update(cost=app.money(topping['matched_cost']) if topping['cost_known'] else 0,
                   cost_known=int(topping['cost_known']))
        c.execute('INSERT INTO toppings(id,name,price,cost,cost_known,scope,active) VALUES(:id,:name,:price,:cost,:cost_known,:scope,1) ON CONFLICT(id) DO UPDATE SET name=excluded.name,price=excluded.price,cost=excluded.cost,cost_known=excluded.cost_known,scope=excluded.scope,active=1',new)
    for suggestion in reviewed['suggestions']:
        for product in reviewed['products']:
            if normalize_name(product['name']) == normalize_name(suggestion['product_name']):
                c.execute('INSERT INTO product_toppings(product_id,topping_id,price_override) VALUES(?,?,?)',
                          (product['id'],suggestion['topping_id'],suggestion['price']))
    previous_links = json.loads(app.metadata(c,'catalog_recipe_links','{}'))
    recipe_links = {}
    for product in reviewed['products']:
        original = product['matched_product_id']
        seen = set()
        while original and original in previous_links and original not in seen:
            seen.add(original)
            original = previous_links[original]
        if original and original != product['id']:
            recipe_links[product['id']] = original
    c.execute("INSERT OR REPLACE INTO app_metadata VALUES('catalog_recipe_links',?)",(app.encode(recipe_links),))
    c.execute("INSERT OR REPLACE INTO app_metadata VALUES('catalog_version',?)",(reviewed['version'],))
    revision=app.secrets.token_hex(16)
    c.execute("INSERT OR REPLACE INTO app_metadata VALUES('dataset_id',?)",(revision,))
    app.audit(c,user,'catalog.apply',reviewed['version'],{'version':previous_version},{'counts':reviewed['counts']})
    return dict(applied=True,version=reviewed['version'],counts=reviewed['counts'],dataset_id=revision,
                missing_cost_products=reviewed['missing_cost_products'],missing_cost_toppings=reviewed['missing_cost_toppings'])


def save_topping(app, c, user, payload):
    topping = dict(id=_id(app,payload.get('id')),name=app.text(payload.get('name'),'Tên topping',120),
                   price=app.money(payload['price']),active=_bool(payload.get('active',True),'Trạng thái topping'))
    topping['cost_known'] = _bool(payload.get('cost_known','cost' in payload),'Trạng thái giá vốn')
    topping['cost'] = app.money(payload['cost']) if topping['cost_known'] else 0
    old = c.execute('SELECT * FROM toppings WHERE id=?',(topping['id'],)).fetchone()
    topping['scope'] = payload.get('scope', old['scope'] if old else 'general')
    if topping['scope'] not in {'general','suggested'}:
        raise ValueError('Phạm vi topping không hợp lệ')
    c.execute('INSERT INTO toppings(id,name,price,cost,active,cost_known,scope) VALUES(:id,:name,:price,:cost,:active,:cost_known,:scope) ON CONFLICT(id) DO UPDATE SET name=excluded.name,price=excluded.price,cost=excluded.cost,active=excluded.active,cost_known=excluded.cost_known,scope=excluded.scope',topping)
    revision=app.secrets.token_hex(16)
    c.execute("INSERT OR REPLACE INTO app_metadata VALUES('dataset_id',?)",(revision,))
    app.audit(c,user,'topping.save',topping['id'],dict(old) if old else None,topping)
    return {'dataset_id':revision}


def build_item(app, c, line):
    if not isinstance(line,dict):
        raise ValueError('Dòng món không hợp lệ')
    row = c.execute('SELECT * FROM products WHERE id=? AND active=1',(line['id'],)).fetchone()
    if not row:
        raise app.ApiError(400,'Món đã ngừng bán hoặc không tồn tại')
    item = dict(row)
    item['qty'] = app.quantity(line['qty'])
    item['base_price'] = item['price']
    modifiers = line.get('toppings',[])
    if not isinstance(modifiers,list) or len(modifiers)>30:
        raise ValueError('Tối đa 30 loại topping trên một dòng món')
    quantities = {}
    for modifier in modifiers:
        if not isinstance(modifier,dict):
            raise ValueError('Topping không hợp lệ')
        tid = _id(app,modifier.get('id'))
        qty = app.quantity(modifier.get('qty',1))
        quantities[tid] = quantities.get(tid,0)+qty
        if quantities[tid]>20:
            raise ValueError('Tối đa 20 phần cho mỗi loại topping trên một ly')
    item['toppings'] = []
    item['cost_known'] = int(bool(item['cost_known']))
    for tid,qty in sorted(quantities.items()):
        topping = c.execute('SELECT * FROM toppings WHERE id=? AND active=1',(tid,)).fetchone()
        if not topping:
            raise app.ApiError(400,'Topping đã ngừng bán hoặc không tồn tại')
        topping = dict(topping)
        override = c.execute('SELECT price_override FROM product_toppings WHERE product_id=? AND topping_id=?',(item['id'],tid)).fetchone()
        if topping['scope'] == 'suggested' and not override:
            raise app.ApiError(400,'Topping gợi ý này không áp dụng cho món đã chọn')
        price = override[0] if override and override[0] is not None else topping['price']
        topping = dict(id=tid,name=topping['name'],qty=qty,price=price,cost=topping['cost'],cost_known=topping['cost_known'])
        item['price'] += qty*price
        item['cost'] += qty*topping['cost']
        item['cost_known'] = int(bool(item['cost_known'] and topping['cost_known']))
        item['toppings'].append(topping)
    return item
