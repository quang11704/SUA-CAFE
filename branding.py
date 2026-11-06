"""SỨA identity and receipts. Logo originals are stored privately in SQLite."""
import base64
import binascii
import html
import io
import json
import warnings
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_FILES = {'BeVietnamPro-SemiBold.ttf', 'GreatVibes-Regular.ttf', 'Lobster-Regular.ttf', 'BeVietnamPro-Regular.ttf', 'DejaVuSans.ttf'}


def init_schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS brand_assets(id TEXT PRIMARY KEY,mime TEXT NOT NULL,data BLOB NOT NULL)')


def settings_view(settings):
    result = dict(settings)
    result['brand_font'] = result.get('brand_font', 'script')
    result['logo_url'] = '/api/brand-assets/' + result['logo_id'] if result.get('logo_id') else ''
    return result


def save(app, c, user, data):
    app.require(user, 'owner')
    original = json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])
    settings = dict(original)
    font = data.get('font', settings.get('brand_font', 'script'))
    if font not in {'script', 'classic'}:
        raise app.ApiError(400, 'Kiểu chữ không hợp lệ.')
    settings['brand_font'] = font
    if data.get('remove_logo') is True:
        settings.pop('logo_id', None)
    part = data.get('logo')
    if part is not None:
        if not isinstance(part, dict) or not isinstance(part.get('base64'), str) or len(part['base64']) > 2800000:
            raise app.ApiError(400, 'Logo cần là PNG/JPG tối đa 2 MB.')
        try:
            raw = base64.b64decode(part['base64'], validate=True)
            if not raw or len(raw) > 2 * 1024 * 1024:
                raise ValueError('Dung lượng logo')
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    kind = image.format
                    if kind not in {'PNG', 'JPEG'} or image.width * image.height > 4_194_304 or max(image.size) > 4096:
                        raise ValueError('Kích thước logo')
                    image.verify()
        except (ValueError, binascii.Error, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise app.ApiError(400, 'Chọn ảnh PNG/JPG hợp lệ, tối đa 2 MB và 4 triệu điểm ảnh. SVG hoặc ảnh quá lớn chưa được hỗ trợ.')
        asset_id = app.hashlib.sha256(raw).hexdigest()
        c.execute('INSERT OR IGNORE INTO brand_assets(id,mime,data) VALUES(?,?,?)', (asset_id, 'image/png' if kind == 'PNG' else 'image/jpeg', raw))
        settings['logo_id'] = asset_id
    c.execute('UPDATE settings SET data=? WHERE id=1', (app.encode(settings),))
    # Keep prior logo bytes: old receipts refer to their immutable asset ID.
    app.audit(c, user, 'branding.save', 'shop',
              before={'logo_id': original.get('logo_id'), 'brand_font': original.get('brand_font', 'script')},
              after={'logo_id': settings.get('logo_id'), 'brand_font': font})


def asset(c, asset_id):
    return c.execute('SELECT mime,data FROM brand_assets WHERE id=?', (asset_id,)).fetchone()


def _font(app, name, file):
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(app.BASE / 'assets/fonts' / file)))


def invoice(app, order):
    _font(app, 'SuaBody', 'BeVietnamPro-Regular.ttf')
    _font(app, 'SuaBillBold', 'BeVietnamPro-SemiBold.ttf')
    _font(app, 'SuaClassic', 'DejaVuSans.ttf')
    shop = json.loads(order['shop_json']) if order.get('shop_json') else app.DEFAULT_SETTINGS
    font = 'SuaBody'
    logo_font = 'SuaBillBold'
    width, height = 226.77, 700  # 80 mm wide, long bills paginate.
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(width, height))
    pdf.setTitle(f"{shop['name']} - Phiếu thanh toán")
    y = height - 25
    logo = None
    if shop.get('logo_id'):
        with app.connect() as c:
            row = asset(c, shop['logo_id'])
            if row:
                logo = bytes(row['data'])
    if logo:
        image = ImageReader(io.BytesIO(logo))
        iw, ih = image.getSize()
        scale = min(155 / iw, 110 / ih)
        dw, dh = iw * scale, ih * scale
        pdf.drawImage(image, (width-dw)/2, y-dh, width=dw, height=dh, preserveAspectRatio=True, mask='auto')
        y -= dh + 15

    def line(value='', size=8.5, face=None, center=False):
        nonlocal y
        face = face or font
        for paragraph in str(value).replace('\t', ' ').split('\n'):
            remaining = paragraph or ' '
            while remaining:
                end = 0
                for char in remaining:
                    if pdfmetrics.stringWidth(remaining[:end+1], face, size) > width-32:
                        break
                    end += 1
                end = max(1, end)
                if end < len(remaining) and ' ' in remaining[:end]:
                    end = remaining.rfind(' ', 0, end) + 1
                if y < 28:
                    pdf.showPage()
                    y = height-25
                pdf.setFont(face, size)
                value = remaining[:end].strip()
                if center:
                    pdf.drawCentredString(width/2, y, value)
                else:
                    pdf.drawString(16, y, value)
                y -= size+7
                remaining = remaining[end:]

    line(shop['name'], 16, logo_font, True)
    for key in ['address', 'phone']:
        if shop.get(key):
            line(shop[key], center=True)
    line('PHIẾU THANH TOÁN', 10, center=True)
    line(order['created'][:16].replace('T', ' '), center=True)
    line(f"Thanh toán: {order['payment']}")
    line()
    for item in json.loads(order['items']):
        line(f"{item['name']} · {item['size']}", 10, 'SuaBillBold')
        for topping in item.get('toppings', []):
            line(f"+ {topping['name']} × {topping['qty']} phần/ly (+{topping['price']:,} đ/phần)", 8)
        if item.get('note'):
            line('Ghi chú ly: '+item['note'],8)
        line(f"{item['qty']} × {app.money(item['price']):,} = {app.money(item['qty'] * item['price']):,} đ")
    if order.get('discount'):
        line(f"Giảm giá: {order['discount']:,} đ")
    line(f"TỔNG CỘNG: {app.money(order['total']):,} đ", 12, 'SuaBillBold')
    if order.get('note'):
        line('Ghi chú: ' + order['note'])
    line(shop.get('footer', 'Cảm ơn bạn đã chọn chúng tôi!'), center=True)
    line('Phiếu thanh toán, không phải hóa đơn thuế.', 7, center=True)
    pdf.save()
    return buf.getvalue()


def receipt_html(app, order, auto=False):
    shop = json.loads(order['shop_json']) if order.get('shop_json') else app.DEFAULT_SETTINGS
    esc = lambda value: html.escape(str(value), quote=True)
    fmt = lambda value: f'{app.money(value):,}'.replace(',', '.') + ' ₫'
    rows = []
    for item in json.loads(order['items']):
        additions = ''.join(f'<div class="addition">+ {esc(t["name"])} × {t["qty"]} phần/ly · +{fmt(t["price"])}/phần</div>' for t in item.get('toppings', []))
        if item.get('note'):
            additions += '<div class="addition">Ghi chú ly: '+esc(item['note'])+'</div>'
        rows.append(f'<section class="item"><strong>{esc(item["name"])} · {esc(item["size"])}</strong>{additions}<div class="amount"><span>{item["qty"]} × {fmt(item["price"])}</span><span>{fmt(item["qty"]*item["price"])}</span></div></section>')
    logo = f'<img class="logo" src="/api/brand-assets/{esc(shop["logo_id"])}" alt="Logo {esc(shop["name"])}">' if shop.get('logo_id') else ''
    note = f'<p>Ghi chú: {esc(order["note"])}</p>' if order.get('note') else ''
    discount = f'<p class="amount"><span>Giảm giá</span><span>{fmt(order["discount"])}</span></p>' if order.get('discount') else ''
    contact_lines = '<br>'.join(esc(shop[key]) for key in ['address', 'phone'] if shop.get(key))
    contact = '<p class="center">'+contact_lines+'</p>' if contact_lines else ''
    return (f'''<!doctype html><html lang="vi" data-brand-font="{esc(shop.get('brand_font','script'))}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bill SỨA</title><link rel="stylesheet" href="/receipt.css"><body data-auto-print="{'1' if auto else '0'}"><div class="tools"><button id="print-receipt">In bill</button><button id="close-receipt">Đóng</button></div><main>{logo}<h1>{esc(shop['name'])}</h1>{contact}<h2>PHIẾU THANH TOÁN</h2><p class="center">{esc(order['created'][:16].replace('T', ' '))}</p><p>Thanh toán: {esc(order['payment'])}</p>{''.join(rows)}{discount}<p class="amount total"><strong>Tổng cộng</strong><strong>{fmt(order['total'])}</strong></p>{note}<p class="center">{esc(shop.get('footer','Cảm ơn bạn đã chọn chúng tôi!'))}</p><p class="center legal">Phiếu thanh toán, không phải hóa đơn thuế.</p></main><script src="/receipt.js"></script></body></html>''').encode('utf-8')
