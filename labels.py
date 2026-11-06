"""Sized cup labels, printable through a locally installed label-printer driver."""
import html
import json
import math
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

DEFAULTS = dict(width_mm=50, height_mm=30, margin_mm=1, font_pt=9)


def options(values):
    result = {}
    for key, default in DEFAULTS.items():
        raw = values.get(key, default)
        if isinstance(raw, bool):
            raise ValueError('Kích thước tem không hợp lệ.')
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError('Kích thước tem không hợp lệ.')
        result[key] = value
    if not (20 <= result['width_mm'] <= 100 and 20 <= result['height_mm'] <= 150
            and 0 <= result['margin_mm'] <= 5 and 6 <= result['font_pt'] <= 14):
        raise ValueError('Tem rộng 20–100 mm, cao 20–150 mm, lề 0–5 mm, chữ 6–14 pt.')
    return result


def config(settings):
    return options(settings.get('label_printer') or {})


def wrap(text, width, size):
    lines = []
    for paragraph in str(text).split('\n'):
        remaining = paragraph or ' '
        while remaining:
            end = 0
            for char in remaining:
                if pdfmetrics.stringWidth(remaining[:end+1], 'SuaLabel', size) > width:
                    break
                end += 1
            end = max(end, 1)
            if end < len(remaining) and ' ' in remaining[:end]:
                end = remaining.rfind(' ', 0, end)+1
            lines.append(remaining[:end].strip())
            remaining = remaining[end:]
    return lines


def render(app, order, settings, query):
    if 'SuaLabel' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('SuaLabel', str(app.BASE/'assets/fonts/BeVietnamPro-Regular.ttf')))
    cfg = config(settings)
    for key in DEFAULTS:
        if key in query:
            cfg[key] = query[key][0]
    cfg = options(cfg)
    start = int(query.get('start', ['1'])[0])
    items = json.loads(order['items'])
    total = sum(int(item['qty']) for item in items)
    count = int(query.get('count', [str(min(200, total))])[0])
    if not 1 <= count <= 200 or not 1 <= start <= total or start + count-1 > total:
        raise ValueError('Mỗi lượt in 1–200 tem, chọn phạm vi nằm trong số ly của đơn.')
    shop = json.loads(order['shop_json']) if order.get('shop_json') else app.DEFAULT_SETTINGS
    width = (cfg['width_mm']-2*cfg['margin_mm'])*72/25.4 - 2
    height = (cfg['height_mm']-2*cfg['margin_mm'])*72/25.4 - 2
    pages, cursor, overflow = [], 0, False
    for item in items:
        quantity = int(item['qty'])
        lo, hi = max(start, cursor+1), min(start+count-1, cursor+quantity)
        for index in range(lo, hi+1):
            text = [shop['name'], f"{item['name']} · {item['size']}"]
            text.extend(f"+ {t['name']} × {t['qty']}" for t in item.get('toppings', []))
            if item.get('note'):
                text.append('Ly: '+item['note'])
            if order.get('note'):
                text.append('Đơn: '+order['note'])
            text.extend([f"{index}/{total} · {order['created'][11:16]}",
                         f"{app.money(item['price']):,} đ/ly".replace(',', '.')])
            size = cfg['font_pt']
            while True:
                lines = [line for text_line in text for line in wrap(text_line, width, size)]
                if len(lines)*size*1.16 <= height or size <= 6:
                    break
                size = max(6, size-.5)
            if len(lines)*size*1.16 > height:
                overflow = True
            pages.append((lines, size))
        cursor += quantity
    esc = lambda value: html.escape(str(value), quote=True)
    fields = ''.join(f'<label>{title}<input type="number" step="0.5" name="{key}" value="{cfg[key]}" required></label>'
                     for key, title in [('width_mm','Rộng (mm)'),('height_mm','Cao (mm)'),('margin_mm','Lề (mm)'),('font_pt','Chữ (pt)')])
    sheets = ''.join(f'<section class="label" style="font-size:{size}pt">'+''.join(f'<div>{esc(line) or "&nbsp;"}</div>' for line in lines)+'</section>' for lines, size in pages)
    warning = '<p class="warning">Nội dung quá dài cho khổ tem này. Tăng chiều cao/rộng hoặc chọn cỡ chữ nhỏ hơn rồi xem lại. Chưa gửi lệnh in để tránh cắt mất nội dung.</p>' if overflow else ''
    auto = query.get('auto', ['0'])[0] == '1' and not overflow
    return f'''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tem SỨA</title><link rel="stylesheet" href="/labels.css"><style>@page{{size:{cfg['width_mm']}mm {cfg['height_mm']}mm;margin:0}}.label{{width:{cfg['width_mm']}mm;height:{cfg['height_mm']}mm;padding:{cfg['margin_mm']}mm;line-height:1.16}}</style><body data-auto-print="{'1' if auto else '0'}"><aside class="tools"><h1>Tem dán từng ly</h1><p>Chọn máy in tem đã cài trên Windows. Khổ giấy trong driver phải trùng khổ tem; tỷ lệ 100%, tắt đầu/chân trang. Giá trên tem là giá mỗi ly gồm topping, trước giảm giá đơn.</p><form>{fields}<input type="hidden" name="dataset" value="{esc(query.get('dataset',[''])[0])}"><label>Từ ly<input type="number" min="1" max="{total}" name="start" value="{start}" required></label><label>Số tem (tối đa 200/lượt)<input type="number" min="1" max="200" name="count" value="{count}" required></label><button>Xem lại</button></form>{warning}<button id="print-labels" {'disabled' if overflow else ''}>In {count} tem</button><p>{start}–{start+count-1} / {total} ly. Có thể chọn lại phạm vi để in một phần hoặc in bù; không tạo thêm đơn hàng.</p></aside><main>{sheets}</main><script src="/labels.js"></script></body></html>'''.encode('utf-8')
