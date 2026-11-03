# Đối soát menu SỨA CAFÉ từ ảnh mới

Nguồn: hai ảnh menu do chủ quán gửi trong phiên làm việc. `data/menu_2026_11.json` chỉ chứa tên món, size và giá bán công khai từ ảnh; không chứa giá vốn, tồn kho hay doanh thu riêng tư.

## Danh mục đã chép

| Nhóm trên ảnh | Nhóm trong app | Món gốc | Biến thể size |
| --- | --- | ---: | ---: |
| TRÀ SỮA | Trà Sữa | 11 | 22 |
| COFFEE | Cà Phê | 9 | 18 |
| MATCHA | Matcha | 9 | 18 |
| CACAO | Cacao | 5 | 10 |
| SỮA CHUA | Sữa Chua | 7 | 7 |
| TRÀ TRÁI CÂY | Trà Trái Cây | 19 | 57 |
| ĐÁ XAY | Đá Xay | 5 | 10 |
| SPECIAL | Special | 10 | 20 |
| **Tổng** | | **75** | **162** |

- Giá `20` trên ảnh được lưu là `20000` VNĐ. Không có số thập phân hoặc quy đổi ngoại tệ.
- Sữa chua chỉ có **size L**, đúng cột giá trên ảnh. Không tự thêm size M.
- Trà trái cây có **M/L/XL**. Các nhóm còn lại có **M/L**.
- `Hồng Trà Kem Cheese` giữ giá **15.000 / 20.000 / 30.000** theo ảnh; không tự tính XL từ Hồng Trà + topping.
- `Trà Quýt Jeju` giữ giá **30.000 / 35.000 / 45.000** theo ảnh.
- Các món đã có thành phần trong tên (ví dụ Trà Sữa Kem Cheese, Dâu Latte Kem Dâu) là món riêng; không tự cộng thêm giá topping cho thành phần mặc định.
- Dấu sao trong ảnh là trang trí/gợi ý món; chưa được diễn giải thành thay đổi giá, khuyến mãi hoặc thành phần.
- Menu mới cần được chủ quán xem trước/xác nhận khi áp dụng. Không tự ghi đè giá vốn/công thức hay thay đổi đơn đã bán.

## Giá topping chung và giá cộng theo món

Catalog có **10 topping chung** (`scope: general`) ở chân ảnh và **10 thành phần cộng thêm theo gợi ý món** (`scope: suggested`). Có **30 gợi ý** nối tên món với topping và giá cộng được in ngay dưới món đó.

| Topping chung ở chân ảnh | Giá cộng |
| --- | ---: |
| Phô Mai Jerrry | 10.000 |
| Trân Châu Đen | 5.000 |
| Trân Châu Trắng | 5.000 |
| Kem Cheese | 8.000 |
| Kem Dẻo | 10.000 |
| Kem Muối | 6.000 |
| Kem Cheese Oreo | 10.000 |
| Hạt Nổ Củ Năng | 8.000 |
| Kem Trứng | 10.000 |
| Khúc Bạch | 10.000 |

Các dòng bắt đầu bằng `+` được gắn với **món gốc ngay phía trên**, đến khi xuất hiện tên món gốc tiếp theo. Chúng áp dụng cho các size đang có của món gốc đó. Không tự mở rộng giá ưu đãi/gợi ý này sang mọi món cùng nhóm.

Ví dụ khác giá cần giữ riêng:

- Cafe Sữa + Kem Muối: **5.000**; Kem Muối chung: **6.000**.
- Cafe Sữa / Matcha Latte / Matcha Oreo / Cacao Oreo + Kem Cheese: **5.000**; Kem Cheese chung: **8.000**.
- Cafe Sữa / Matcha Latte / Cacao Sữa Đá / Khoai Môn Latte + Kem Trứng: **8.000**; Kem Trứng chung: **10.000**.
- Kem Dẻo Buôn Mê gợi ý ở Cafe Sữa/Cacao Sữa Đá: **8.000**. Chưa khẳng định đây là cùng nguyên liệu với Kem Dẻo chung **10.000**; hai mã được giữ riêng.
- `Phô Mai` dưới Matcha Oreo/Cacao Oreo và `Phô Mai Jerrry` ở chân ảnh đều **10.000**, nhưng ảnh không khẳng định là cùng sản phẩm; giữ riêng tên/mã để chủ quán xác nhận.

Các gợi ý khác gồm Kem Chanh, Sương Sáo, Sữa Thái Lan, Sữa Hạt, Kem Matcha, Kem Dâu, Matcha và Sữa Dừa. Mỗi giá gợi ý được ghi rõ trong JSON; không suy ra từ giá vốn hoặc tự chế công thức.

## Chữ trên ảnh cần chủ quán xác nhận

1. Tên cà phê đọc được là **“Cafe Dalgonal”**; giữ nguyên thay vì tự sửa sang cách viết phổ biến “Dalgona”.
2. Topping phô mai ở chân ảnh đọc là **“Phô Mai Jerrry”** (ba chữ r). Cần xác nhận nếu tên mong muốn là Jerry/Jerry Cheese.
3. Ảnh ghi **“+ Sữa Thái Lan”** dưới Cafe Sữa Tươi và **“+ Sữa Thái”** dưới Cacao Latte, cùng giá 8.000. JSON dùng một mã `TOP_SUA_THAI_LAN` với tên Sữa Thái Lan cho hai gợi ý; nếu quán dùng hai sản phẩm khác nhau cần tách mã.
4. `Phindi Hạnh Nhân`, `Matcha Coldwhisk`, `Trà Lài Đác Thơm`, `Nhãn Dừa Bồng Tuyết` được chép theo cách đọc ảnh. Không dịch hoặc đổi thành món khác.

Không suy đoán giá vốn, hạn dùng, công thức nguyên liệu, giới hạn topping hoặc lượng topping từ các ảnh này. Những phần đó cần dữ liệu riêng đã đối soát.
