"""Import privately supplied workbooks without executing Excel formulas."""
import argparse
import datetime
import json
from pathlib import Path

import openpyxl


def extract(inventory_path, cost_path):
    inventory = openpyxl.load_workbook(inventory_path, data_only=True, keep_links=False)
    try:
        cost = openpyxl.load_workbook(cost_path, data_only=True, keep_links=False)
        try:
            menu = []
            for row in list(cost['04_Cost_Menu_ChiTiet'].values)[4:]:
                if isinstance(row[0], (float, int)) and row[1] and isinstance(row[8], (float, int)):
                    menu.append(dict(id=row[1], category=row[2], name=row[3], size=row[4], cost=row[7], price=row[8]))
            stock = []
            for row in list(inventory['Quan Ly Kho V3'].values)[1:]:
                if row[1] and row[2] and isinstance(row[3], (float, int)) and isinstance(row[6], (float, int)):
                    stock.append(dict(id=len(stock) + 1, name=row[1], unit=row[2], price=row[3], qty=row[6],
                                      minimum=row[7] if isinstance(row[7], (float, int)) else 0, note=str(row[9] or '')))
            recipes = []
            for row in list(cost['03_DinhLuong_TungMon'].values)[4:]:
                if row[1] and isinstance(row[5], (float, int)):
                    recipes.append(dict(product=row[1], name=row[4], qty=row[5], unit=row[6], source=row[7]))
            batches = [dict(name=row[2], formula=row[3], yield_qty=row[5], unit=row[6])
                       for row in list(cost['02_Cost_Cot_Topping'].values)[4:]
                       if isinstance(row[0], (float, int))]
            # Preserve cash totals only; never infer historical item sales or profit.
            history = []
            for row in list(inventory['Bán Hàng'].values)[1:]:
                for offset in [8, 15, 21]:
                    if (isinstance(row[offset], datetime.datetime)
                            and isinstance(row[offset + 3], (float, int)) and row[offset + 3] > 0):
                        history.append(dict(date=row[offset].date().isoformat(), cash=row[offset + 1] or 0,
                                            transfer=row[offset + 2] or 0, total=row[offset + 3]))
            return dict(menu=menu, stock=stock, recipes=recipes, batches=batches, history=history)
        finally:
            cost.close()
    finally:
        inventory.close()


def main():
    parser = argparse.ArgumentParser(description='Nhập hai file Excel riêng tư thành dữ liệu SỨA. Không sửa database.')
    parser.add_argument('--inventory', required=True, type=Path, help='File Excel tồn kho SỨA CAFÉ.xlsx')
    parser.add_argument('--cost', required=True, type=Path, help='File Excel COST FINAL / công thức')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'data/seed.json',
                        help='JSON đích; mặc định data/seed.json trong thư mục app')
    parser.add_argument('--overwrite', action='store_true', help='Cho phép ghi đè JSON đích đã tồn tại')
    args = parser.parse_args()
    for path in [args.inventory, args.cost]:
        if not path.is_file():
            parser.error(f'Không tìm thấy file đầu vào: {path}')
    if args.output.resolve() in {args.inventory.resolve(), args.cost.resolve()}:
        parser.error('File đầu ra không được trùng file Excel nguồn.')
    if args.output.exists() and not args.overwrite:
        parser.error('JSON đích đã tồn tại. Giữ bản sao trước; chỉ dùng --overwrite khi muốn thay thế file này.')
    try:
        seed = extract(args.inventory, args.cost)
        contents = json.dumps(seed, ensure_ascii=False, indent=2, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting files created during workbook loading.
        with args.output.open('w' if args.overwrite else 'x', encoding='utf-8') as output:
            output.write(contents)
    except FileExistsError:
        parser.error('JSON đích vừa được tạo bởi tiến trình khác; chưa ghi đè.')
    except KeyError as error:
        parser.error(f'Thiếu sheet bắt buộc trong Excel: {error}')
    except (OSError, ValueError, TypeError, IndexError) as error:
        parser.error(f'Không nhập được dữ liệu: {error}')
    print('Đã tạo JSON riêng tư; không thay đổi database hiện có.')
    print(json.dumps({key: len(value) for key, value in seed.items()}, ensure_ascii=False))
    print('Dùng database mới qua SUA_DB khi chuyển từ demo sang dữ liệu thật; xem IMPORT_EXCEL.md.')


if __name__ == '__main__':
    main()
