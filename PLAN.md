# PLAN — Web app quản lý SỨA cà phê

**Phiên bản:** 1.0 · **Ngày:** 02/11/2026
**Thương hiệu:** SỨA cà phê · **Giao diện:** tiếng Việt, tông hồng
**Phạm vi ban đầu:** một quán, hỗ trợ máy tính và điện thoại.

**Bản phát hành GitHub:** mã nguồn và dữ liệu giả lập; không kèm workbook, seed hoặc database kinh doanh thật. Các số lượng thống kê Excel dưới đây mô tả lần nhập riêng trong môi trường phát triển.

Tài liệu mô tả yêu cầu sản phẩm, hiện trạng bản phát triển và kế hoạch hoàn thiện. Các chức năng đề xuất chưa được xem là đã triển khai hoặc đã được chủ quán xác nhận.

## 1. Mục tiêu

- Quản lý bán đồ uống và bánh tại một nơi.
- Theo dõi nguyên liệu, bán thành phẩm, lượng bánh mỗi ngày và hao hụt.
- Biết doanh thu, giá vốn, chi phí và lợi nhuận theo ngày/tháng.
- Xuất phiếu thanh toán PDF tiếng Việt và tra lại đơn đã bán.
- Tận dụng dữ liệu Excel hiện có, giảm nhập liệu trùng và tránh sai lệch tồn kho.

**Thước đo nghiệm thu:** không cộng trùng doanh thu bánh; không trừ hai lần giá vốn; không phát sinh tồn âm ngoài chính sách được cho phép; mỗi thay đổi tiền/kho truy được về chứng từ và người thực hiện; dữ liệu khôi phục được từ bản sao lưu.

## 2. Người dùng và quyền đề xuất

App đã có ba vai trò kiểm tra tại API/UI. Ma trận dưới đây là phạm vi mục tiêu; nhân viên kho hiện điều chỉnh số lượng và xem công thức, phần sản xuất mẻ/lô vẫn chưa có.

| Vai trò | Công việc | Giới hạn |
| --- | --- | --- |
| Chủ quán | Cấu hình, giá bán/giá vốn, tài khoản, báo cáo lợi nhuận, duyệt điều chỉnh, sao lưu | Có toàn quyền; thao tác nhạy cảm phải có nhật ký |
| Thu ngân | Tạo đơn, ghi nhận thanh toán, tải/in PDF, xem ca của mình | Không xem giá vốn/lợi nhuận hoặc tự sửa giá nếu chưa được cấp quyền |
| Nhân viên kho/bếp | Nhập kho, sản xuất cốt, kiểm đếm, theo dõi bánh | Không sửa doanh thu; thay đổi tồn cần lý do và quyền phù hợp |

Một người có thể kiêm nhiều vai trò. Chỉ tạo các vai trò thực tế quán sử dụng.

## 3. Dữ liệu đầu vào và hiện trạng

| Nguồn | Dữ liệu đang sử dụng | Lưu ý |
| --- | --- | --- |
| `SỨA CAFÉ.xlsx` | 64 dòng tồn hợp lệ; 95 dòng doanh thu có ngày Excel hợp lệ | Tồn theo hộp/túi…; không mặc định là tồn thực tế hôm nay |
| `QUẢN LÝ COST + CÔNG THỨC ĐỊNH LƯỢNG SỨA CAFE FINALz.xlsx` | 111 món/size; 378 dòng định lượng; 19 công thức bán thành phẩm | Ưu tiên cho menu/giá/công thức; giá vốn là kết quả Excel đã lưu |

Các điểm phải đối soát:

- Danh mục nguyên liệu giữa hai file khác tên và quy cách; chưa có bảng ghép mã đáng tin cậy.
- File COST có danh mục nguyên liệu riêng, chưa nhập toàn bộ thành tồn kho vận hành.
- Có khác biệt công thức/sản lượng mẻ giữa hai file; COST ghi giá vốn có sai số 5–10%.
- Một ô ngày không hợp lệ trong file nguồn không được sử dụng. Các khối ngày dạng văn bản thiếu năm chưa nhập tự động.
- Chưa nhập chi phí lịch sử vì có cả mua nguyên liệu, chi phí vận hành và khoản cá nhân cần phân loại.
- Chưa có danh mục bánh, hạn dùng và quy tắc giữ/hủy bánh được xác nhận.

### Phần đã có trong bản phát triển (cập nhật sau đợt code G2)

1. Tám màn hình: tổng quan, bán hàng, đơn hàng, kho, bánh mỗi ngày, báo cáo, menu/công thức, cài đặt/nhân viên.
2. Khởi tạo chủ quán không có mật khẩu mặc định; đăng nhập, phiên 12 giờ, CSRF, giới hạn thử đăng nhập, đổi mật khẩu và thu hồi phiên.
3. Quyền owner/cashier/inventory kiểm tra tại API; thu ngân chỉ xem đơn của mình và không nhận cost; nhân viên kho không nhận giá nhập/cost/lợi nhuận.
4. Chủ quán thêm/sửa/ngừng bán món, đổi giá/cost ước tính. Snapshot đơn và thông tin quán trên PDF không bị sửa theo danh mục.
5. Chốt đơn tiền mặt/chuyển khoản, ghi chú, giảm giá cho chủ quán; chống tạo đơn trùng theo mã yêu cầu, UI hỗ trợ retry sau khi mất phản hồi/reload.
6. Tìm/lọc đơn, tải PDF có wrap dòng và nhiều trang; hoàn toàn bộ đơn bằng chứng từ riêng, không tự hoàn nguyên liệu hay giá vốn đã dùng.
7. Kho thủ công chống tồn âm trong transaction, lịch sử biến động; sổ bánh và chi phí có hủy bản ghi kèm nhật ký.
8. Báo cáo ngày/tháng phía server; hoàn tiền theo ngày hoàn; xuất CSV; doanh thu lịch sử xem riêng.
9. Cấu hình thông tin quán/PDF, quản lý nhân viên, nhật ký trước/sau, tải backup SQLite nhất quán.
10. Migration bổ sung schema v1 bảo toàn dữ liệu cũ; kiểm thử tích hợp và browser chạy trên database tạm, gồm tình huống đồng thời và mất phản hồi thanh toán.

**Đợt nhập thật:** đã có upload XLSX và xem trước trên UI chủ quán, đối soát tồn/ngày, chuyển database riêng có backup demo, giữ tài khoản/cấu hình, chống replay/tab cũ và khôi phục lựa chọn database sau restart. Dữ liệu thật không đưa lên repo.

**Chưa có:** tự trừ nguyên liệu, tính cost động, quy đổi đã xác nhận, quản lý mẻ/lô/hạn dùng, nhập kho kèm giá vốn thực tế, danh mục bánh/chuyển dư/POS bánh, ca bán, hoàn một phần, đồng bộ/nhập cập nhật Excel vào dữ liệu đã vận hành, backup theo lịch hoặc triển khai production. Bản hiện tại vẫn là bản phát triển nội bộ; phần G2 được triển khai một phần, không đánh dấu toàn bộ P0 đã hoàn thành. Bảng bên dưới là baseline yêu cầu; trạng thái được cập nhật theo phạm vi cụ thể, phần “Có cơ bản” vẫn cần nghiệm thu đầy đủ.

## 4. Quy ước ưu tiên và trạng thái

- **P0:** bắt buộc trước khi đưa vào vận hành thật.
- **P1:** hoàn thiện nghiệp vụ kho, công thức và báo cáo.
- **P2:** mở rộng sau khi vận hành ổn định.
- **Có cơ bản:** đã có một phần; vẫn cần đáp ứng các tiêu chí bổ sung trong yêu cầu.
- **Chưa có:** cần triển khai.

## 5. Functional requirements — Yêu cầu chức năng

### 5.1. Cài đặt quán và tài khoản

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-01 | Cấu hình tên quán, logo, địa chỉ, số điện thoại, chân trang PDF | P0 | Có cấu hình tên/địa chỉ/điện thoại/chân trang; chưa logo | Chủ quán chỉnh được; phiếu mới dùng thông tin tương ứng, phiếu cũ giữ được thông tin đã phát hành |
| FR-02 | Đăng nhập, đăng xuất, đổi mật khẩu, khóa tài khoản | P0 | Đã triển khai, kiểm thử tích hợp | Không có phiên hợp lệ không đọc/ghi được dữ liệu; mật khẩu được băm, không lưu dạng rõ |
| FR-03 | Phân quyền theo vai trò | P0 | Đã triển khai ở API/UI | Máy chủ kiểm tra quyền từng thao tác; thu ngân không lấy được cost/lợi nhuận bằng API |
| FR-04 | Nhật ký thay đổi dữ liệu quan trọng | P0 | Có nhật ký trước/sau và người thực hiện cho thao tác hiện có | Lưu ai, lúc nào, chứng từ, trước/sau và lý do; người thường không sửa/xóa được nhật ký |

### 5.2. Menu, giá bán và công thức

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-05 | Danh mục nhóm món, món, size, trạng thái còn bán | P0 | Có thêm/sửa/ngừng bán món/size | Tạo/sửa/ngừng bán qua giao diện; không xóa mất tham chiếu trên đơn cũ |
| FR-06 | Giá bán và lịch sử thay đổi giá | P0 | Có sửa giá, audit và snapshot đơn; chưa lịch giá tương lai | Đơn đã chốt giữ giá cũ; đơn mới dùng giá đang hiệu lực |
| FR-07 | Định lượng theo món/size, bao bì và hao hụt | P1 | Tra cứu công thức | Nhập mã nguyên liệu/BTP, lượng, đơn vị; kiểm tra thiếu quy đổi và lưu phiên bản |
| FR-08 | Tính lại giá vốn và biên lợi nhuận | P1 | Cost Excel tĩnh | Thay giá nguyên liệu/công thức cập nhật cost hiện hành; không ghi đè cost của đơn quá khứ |
| FR-09 | Cảnh báo món có margin thấp hoặc thiếu dữ liệu cost | P1 | Chưa có | Hiển thị ngưỡng cấu hình; không coi thiếu cost là cost bằng 0 |

### 5.3. Bán hàng và thanh toán

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-10 | Tìm/lọc món, chọn size, thêm/xóa/đổi số lượng | P0 | Có cơ bản | Tổng tiền khớp giá máy chủ; từ chối món không bán, số lượng âm/lẻ không hợp lệ |
| FR-11 | Ghi chú đơn/món và giảm giá theo quyền | P1 | Có ghi chú đơn và giảm số tiền cho owner; chưa ghi chú riêng từng món | Giảm giá không vượt số tiền hợp lệ; lưu lý do, người cấp và số trước/sau giảm |
| FR-12 | Chốt thanh toán tiền mặt/chuyển khoản | P0 | Có cơ bản | Chỉ ghi doanh thu khi chốt; chuyển khoản hiện là nhân viên xác nhận thủ công |
| FR-13 | Ngăn tạo đơn trùng khi bấm lại/mất mạng | P0 | Có idempotency theo user/key và retry qua reload | Gửi lại cùng mã yêu cầu trả cùng đơn; không tạo thêm doanh thu hoặc trừ kho lần nữa |
| FR-14 | Tra đơn, lọc ngày/ca/phương thức thanh toán | P0 | Có mã/tên món, ngày, trạng thái; chưa ca | Tìm được đơn theo mã; tổng danh sách khớp báo cáo cùng bộ lọc |
| FR-15 | Hủy/hoàn tiền sau thanh toán có kiểm soát | P0 | Có hoàn toàn bộ, audit; chưa hoàn một phần/hoàn kho | Không xóa đơn gốc; có chứng từ đảo, lý do, người duyệt; hoàn tiền và hoàn kho là quyết định riêng |
| FR-16 | Mở/đóng ca, đối soát tiền mặt/chuyển khoản | P1 | Chưa có | Lưu tiền đầu ca, thu/chi, tiền đếm, chênh lệch; đơn thuộc một ca rõ ràng |

### 5.4. Kho nguyên liệu và bán thành phẩm

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-17 | Danh mục nguyên liệu và đơn vị chuẩn | P0 | Có tồn theo đóng gói | Mỗi nguyên liệu có mã duy nhất, g/ml/cái hoặc đơn vị phù hợp và hệ số quy đổi xác nhận |
| FR-18 | Nhập kho có số lượng, đơn giá, nhà cung cấp, chứng từ | P0 | Chỉ điều chỉnh số lượng | Phiếu nhập cập nhật tồn và giá trị kho trong cùng giao dịch; lưu giá lịch sử |
| FR-19 | Xuất/hủy/kiểm kê điều chỉnh kho | P0 | Có cơ bản | Không âm kho; phân loại lý do; có người thực hiện; kiểm kê lưu chênh lệch, không ghi đè âm thầm |
| FR-20 | Cảnh báo tồn tối thiểu và xem lịch sử biến động | P0 | Có cảnh báo và lịch sử trên UI; chưa lọc lịch sử | Lọc nguyên liệu và thời gian; tồn cuối = tồn đầu + tổng biến động hợp lệ |
| FR-21 | Sản xuất cốt/topping theo mẻ | P1 | Chỉ tra công thức | Hoàn tất mẻ trừ nguyên liệu, cộng BTP theo sản lượng thực tế; thiếu đầu vào phải từ chối toàn bộ |
| FR-22 | Tự trừ kho khi chốt đơn | P1 | Chưa có | Dùng công thức đã xác nhận; khóa kiểm tra tồn và ghi đơn/xuất kho nguyên tử; không trừ kép nguyên liệu đã dùng sản xuất BTP |
| FR-23 | Theo dõi lô, ngày nhập, hạn dùng | P1 | Chưa có | Cảnh báo cận/hết hạn; không dùng lô hết hạn; thứ tự xuất ưu tiên hạn gần nhất khi phù hợp |

### 5.5. Bánh mỗi ngày

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-24 | Danh mục bánh, giá bán/giá vốn, hạn dùng | P0 | Nhập tay theo dòng sổ | Có mã bánh, nguồn nhập/tự làm; giá cũ giữ nguyên trên giao dịch đã chốt |
| FR-25 | Nhập/làm bánh, ghi bán/hủy theo ngày và lô | P0 | Sổ tổng hợp cơ bản | Không bán + hủy vượt khả dụng; lịch sử được giữ khi sửa bằng chứng từ điều chỉnh |
| FR-26 | Bánh bán qua POS và quản lý bánh dư | P1 | Chưa tích hợp POS/chuyển dư | Một giao dịch chỉ tạo doanh thu một lần; bánh dư chỉ chuyển khi còn hạn và được xác nhận |
| FR-27 | Báo cáo số nhập/bán/hủy/còn và tỷ lệ hao hụt | P1 | Có số theo dòng | Tổng ngày/tháng đối chiếu được với sổ lô; chi phí bánh hủy thể hiện riêng |

### 5.6. Doanh thu, chi phí và lợi nhuận

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-28 | Tổng quan và báo cáo ngày/tháng | P0 | Có cơ bản | Dùng múi giờ quán; tiền mặt + chuyển khoản khớp doanh thu trước các điều chỉnh được nêu rõ |
| FR-29 | Ghi/phân loại chi phí vận hành | P0 | Có nhóm và hủy bản ghi có lý do; chưa đính kèm chứng từ | Có nhóm, chứng từ, người nhập; sửa/hủy có lịch sử; tách khoản cá nhân và mua hàng tồn kho |
| FR-30 | Lãi gộp, hao hụt và lợi nhuận vận hành | P0 | Có giảm giá, hoàn theo ngày hoàn, tách hủy bánh; chưa giá vốn kho thực tế | Nêu công thức và dữ liệu thiếu; hoàn tiền/giảm giá/hủy kho ảnh hưởng đúng, không trừ vốn hai lần |
| FR-31 | Báo cáo theo món, size, nhóm, phương thức | P1 | Chưa có | Tổng chi tiết khớp tổng báo cáo; chỉ người được cấp quyền xem cost/margin |
| FR-32 | Doanh thu lịch sử và đối soát Excel | P1 | Xem riêng dữ liệu đã nhập | Gắn nguồn/thời kỳ; chặn nhập trùng; không suy diễn lợi nhuận khi thiếu giá vốn |
| FR-33 | Xuất báo cáo CSV/Excel | P1 | Có CSV tổng hợp theo ngày/tháng và quyền owner | Tôn trọng bộ lọc, quyền và định dạng tiếng Việt; mở được bằng Excel, không tạo công thức từ văn bản người dùng |

### 5.7. Phiếu PDF, nhập dữ liệu và sao lưu

| Mã | Yêu cầu | Ưu tiên | Hiện trạng | Tiêu chí nghiệm thu |
| --- | --- | --- | --- | --- |
| FR-34 | Xuất/tải lại phiếu thanh toán PDF | P0 | Có cơ bản | Đúng tên quán, mã, giờ, món/size/lượng/giá/tổng, thanh toán; không lỗi dấu; đơn dài không cắt mất nội dung |
| FR-35 | Mẫu in phù hợp khổ giấy quán | P1 | Khổ PDF cố định | Xác nhận A4/80mm/58mm, xem trước và thử in; không tràn tên món dài |
| FR-36 | Nhập Excel có xem trước và bảng lỗi | P1 | Có nhập đầu kỳ qua UI, review/tồn/ngày, chặn nhập đè dữ liệu thật; CLI giữ để thay thế | Ghép mã thủ công khi mơ hồ; chỉ áp dụng sau xác nhận; tải được báo cáo dòng nhập/bỏ qua/lỗi và chống nhập lại |
| FR-37 | Sao lưu/khôi phục dữ liệu | P0 | Có tải backup và kiểm thử phục hồi; chưa lịch tự động | Sao lưu nhất quán, lưu ngoài máy chạy; phục hồi thử thành công; không ghi đè DB khi nâng cấp |

## 6. Business rules — Quy tắc nghiệp vụ

1. **Tiền tệ:** VNĐ. Bản vận hành dùng số nguyên cho tiền thanh toán; cost nội bộ có độ chính xác thập phân và quy tắc làm tròn nhất quán. Không dùng số thực nhị phân làm chuẩn kế toán.
2. **Ngày kinh doanh:** mặc định `Asia/Ho_Chi_Minh` cho quán Việt Nam; cần xác nhận nếu chốt ngày sau nửa đêm. Lưu thời điểm có múi giờ, báo cáo theo ngày kinh doanh.
3. **Doanh thu thuần:** tổng tiền hàng − giảm giá − giá trị hoàn; chỉ tính đơn đã chốt, không tính giỏ nháp.
4. **Lãi gộp:** doanh thu thuần − giá vốn hàng đã bán. **Lợi nhuận vận hành ước tính:** lãi gộp − hao hụt/hủy − chi phí vận hành đã ghi. Thuế, khấu hao và các khoản khác chỉ được tính khi có chính sách và dữ liệu tương ứng.
5. **Mua nguyên liệu:** tăng tài sản tồn kho; không đồng thời trừ vào chi phí vận hành khi đã ghi nhận giá vốn lúc bán. Dòng tiền chi mua hàng là chỉ tiêu riêng.
6. **Phương pháp giá vốn đề xuất:** bình quân gia quyền cho nguyên liệu mua vào; BTP nhận cost thực tế của mẻ. Cần chủ quán xác nhận trước triển khai. Giá vốn ước tính công thức và giá vốn xuất kho thực tế phải được phân biệt.
7. **Công thức:** tham chiếu mã nguyên liệu/BTP và phiên bản. Khi sản xuất BTP đã trừ nguyên liệu thô, bán món chỉ trừ lượng BTP sử dụng, không bung công thức trừ thô thêm lần nữa.
8. **Tồn đầu kỳ:** phải xác nhận ngày kiểm kê. Không kết hợp tồn chụp hiện tại với doanh thu quá khứ để suy ngược tồn nếu thiếu chứng từ.
9. **Bánh:** giai đoạn hiện tại dùng sổ bánh tổng hợp riêng. Khi chuyển sang POS, chốt ngày chuyển đổi và ngừng tạo doanh thu trùng từ sổ; tồn dư chuyển ngày có dấu vết.
10. **Hoàn/hủy:** món đã làm thường không hoàn nguyên liệu về kho. Phải ghi nhận tình trạng hàng thực tế, không mặc định hoàn tiền là hoàn kho.
11. **Chuyển khoản:** ghi nhận phương thức thanh toán không đồng nghĩa ngân hàng đã xác thực giao dịch; chỉ tự xác nhận khi tích hợp ngân hàng riêng.
12. **PDF:** là phiếu thanh toán thông thường. Hóa đơn điện tử thuế là tích hợp riêng với nhà cung cấp và yêu cầu pháp lý tương ứng.

## 7. Luồng sử dụng chính

### A. Bán hàng và xuất phiếu — luồng mục tiêu

Đăng nhập → chọn/mở ca → tìm món và size → thêm giỏ → xác nhận số lượng/giảm giá → server kiểm tra quyền, giá, công thức, tồn → chốt đơn và biến động kho trong một transaction → trả mã đơn → xuất PDF. Nếu thiếu tồn hoặc lưu thất bại, không ghi một phần đơn. Gửi lại yêu cầu không tạo đơn thứ hai.

### B. Nhập hàng và sản xuất cốt — luồng mục tiêu

Chọn nguyên liệu/lô → nhập lượng và đơn giá → kiểm tra quy đổi → lưu phiếu nhập → sản xuất theo công thức mẻ → nhập sản lượng thực tế → ghi hao hụt → trừ nguyên liệu, cộng BTP → kiểm tra tồn và giá trị sau mẻ.

### C. Quản lý bánh — luồng mục tiêu

Đầu ngày: kiểm tra bánh dư còn hạn + nhập/làm mới → trong ngày: bán qua POS → cuối ngày: kiểm đếm → ghi hủy và nguyên nhân → xác nhận bánh được chuyển sang hôm sau → báo cáo số bán/tồn/hao hụt.

### D. Chốt ngày — luồng mục tiêu

Kết ca → đối soát tiền mặt và chuyển khoản → kiểm tra đơn hoàn/hủy → ghi đủ chi phí → xem doanh thu/giá vốn/hao hụt/lợi nhuận → giải trình chênh lệch → sao lưu dữ liệu. Báo cáo chưa đủ dữ liệu phải hiển thị trạng thái ước tính.

## 8. Màn hình và trải nghiệm

| Màn hình | Nội dung chính |
| --- | --- |
| Đăng nhập | Tài khoản, mật khẩu, thông báo lỗi, phiên hết hạn |
| Tổng quan | Doanh thu, đơn hàng, lợi nhuận theo quyền, cảnh báo tồn/hạn dùng, biểu đồ |
| Bán hàng | Tìm món/size, nhóm món, giỏ, ghi chú, thanh toán, PDF |
| Đơn hàng & ca | Bộ lọc, chi tiết, lịch sử, tải PDF, hoàn/hủy theo quyền, đối soát |
| Kho | Danh mục, nhập/xuất, kiểm kê, biến động, giá trị kho, lô/hạn dùng |
| Sản xuất & công thức | Định lượng món, công thức mẻ, sản lượng thực tế, phiên bản, cost |
| Bánh mỗi ngày | Nhập/làm, bán, hủy, tồn dư, hạn dùng |
| Báo cáo & chi phí | Ngày/tháng, nhóm món, lợi nhuận, vận hành, xuất báo cáo |
| Cài đặt | Thông tin quán, nhân viên/quyền, mẫu PDF, nhập Excel, sao lưu |

Giao diện dùng nền hồng nhạt, nút chính hồng đậm, chữ dễ đọc; không truyền trạng thái chỉ bằng màu. Các form có nhãn, lỗi cụ thể và xác nhận thao tác nhạy cảm. Hỗ trợ bàn phím, màn hình 390px và desktop; bảng rộng cuộn trong vùng bảng, không làm tràn cả trang.

## 9. Non-functional requirements — Yêu cầu phi chức năng

Các chỉ tiêu dưới đây là mục tiêu cần đo, chưa phải kết quả đã đạt.

| Mã | Yêu cầu | Mục tiêu nghiệm thu |
| --- | --- | --- |
| NFR-01 | Bảo mật | HTTPS khi triển khai; session an toàn; kiểm tra quyền server; chống CSRF khi dùng cookie; giới hạn thử đăng nhập; không đưa DB/secrets vào Git |
| NFR-02 | Nhất quán | Chốt đơn/xuất kho nguyên tử; idempotency; kiểm tra hai yêu cầu cùng bán lượng tồn cuối; không phát sinh dữ liệu dở dang |
| NFR-03 | Hiệu năng | Trên cấu hình triển khai đã thống nhất, thử với 10.000 đơn và 5 phiên hoạt động: API đọc p95 ≤ 1 giây, chốt đơn ≤ 2 giây, PDF ≤ 5 giây; ghi riêng PDF đơn dài |
| NFR-04 | Lưu trữ | Migration có phiên bản, sao lưu trước nâng cấp, khởi động lại không làm mất đơn/tồn |
| NFR-05 | Sao lưu | Mục tiêu mất dữ liệu tối đa 24 giờ, khôi phục trong 4 giờ; cần xác nhận với chủ quán và kiểm chứng bằng diễn tập |
| NFR-06 | Khả dụng | Giao diện phản hồi trên mobile/desktop; thông báo lỗi mạng rõ; không báo thanh toán thành công khi chưa được server xác nhận |
| NFR-07 | Quan sát vận hành | Log lỗi, mã yêu cầu, health check; không ghi mật khẩu hoặc dữ liệu nhạy cảm không cần thiết |
| NFR-08 | Tương thích | Kiểm tra Chrome/Edge desktop, Chrome Android, Safari iOS và mở PDF trên thiết bị thật |

## 10. Mô hình dữ liệu mục tiêu

| Nhóm bảng | Nội dung |
| --- | --- |
| `shop_settings`, `users`, `roles`, `user_roles`, `sessions` | Thông tin quán và phân quyền |
| `products`, `product_variants`, `price_versions` | Món, size, giá hiệu lực và trạng thái bán |
| `ingredients`, `units`, `unit_conversions`, `suppliers` | Danh mục nguyên liệu và quy đổi |
| `recipe_versions`, `recipe_lines`, `production_batches` | Công thức có phiên bản và mẻ sản xuất thực tế |
| `inventory_lots`, `stock_documents`, `stock_movements`, `stock_counts` | Lô, chứng từ, biến động và kiểm kê; bảng số dư là dữ liệu đối chiếu/cache |
| `orders`, `order_items`, `payments`, `refunds`, `shifts` | Đơn, dòng món, thanh toán, hoàn và ca |
| `cake_batches`, `cake_movements` | Bánh theo lô/ngày; liên kết dòng đơn khi bán qua POS |
| `expenses`, `expense_categories` | Chi phí vận hành có phân loại |
| `import_jobs`, `import_errors`, `legacy_daily_revenue` | Nguồn nhập, lỗi, doanh thu cũ tách riêng |
| `audit_logs`, `backup_runs` | Dấu vết thay đổi và trạng thái sao lưu |

Mỗi chứng từ cần ID, thời điểm, người tạo, trạng thái và liên kết nguồn. Dòng đơn lưu snapshot tên/size/giá bán/giảm giá/cost; sửa danh mục không sửa lịch sử. Bổ sung ràng buộc khóa ngoại, unique, check và chỉ mục; không dùng xóa dây chuyền làm mất chứng từ tài chính.

Schema ban đầu có bảng `orders`, `stock`, `movements`, `expenses`, `cakes` trong SQLite và danh mục trong `data/seed.json`. Đợt G2 đã bổ sung products, users, sessions, login_attempts, settings, refunds, audit_logs, migrations và các cột snapshot/actor/trạng thái. Mô hình mục tiêu còn lại cần migration, không được thay DB hiện tại bằng DB rỗng.

## 11. Kiến trúc và kế hoạch kỹ thuật

**Hiện tại:** HTML/CSS/JavaScript thuần → Python HTTP server → SQLite; ReportLab tạo PDF; openpyxl nhập Excel một lần. Bản này phù hợp thử nghiệp vụ nội bộ, chưa là cấu hình production.

**Hướng phát triển đề xuất:** giữ giao diện hiện có; tách API/dịch vụ nghiệp vụ; chuyển server sang framework có hỗ trợ xác thực, validation và migration (ví dụ FastAPI), dùng công cụ migration tương ứng. Chọn framework cụ thể khi bắt đầu giai đoạn vận hành, không đổi công nghệ chỉ để đổi.

- Một quán, một máy chủ, ít người dùng: SQLite có thể tiếp tục dùng nếu quản lý transaction, khóa ghi và sao lưu đúng.
- Nhiều phiên ghi đồng thời hoặc nhiều chi nhánh: đánh giá PostgreSQL bằng bài test tải trước quyết định chuyển.
- Deployment cần app server production, HTTPS/reverse proxy, nơi lưu dữ liệu bền vững và lịch sao lưu ngoài máy chủ.
- Không dựa vào live process hoặc filesystem tạm của môi trường phát triển để lưu dữ liệu vận hành lâu dài.

### API đã có

| API | Chức năng hiện tại |
| --- | --- |
| `GET /api/state` | Toàn bộ trạng thái; cần tách, phân trang và lọc theo quyền trước production |
| `POST /api/orders` | Chốt đơn và snapshot giá/cost; có idempotency, snapshot, ghi chú/giảm giá; chưa tự trừ kho |
| `GET /api/invoice/{id}` | Tạo PDF từ đơn đã lưu |
| `POST /api/stock` | Điều chỉnh tồn có lý do |
| `POST /api/cakes` | Thêm dòng sổ bánh |
| `POST /api/expenses` | Thêm chi phí |

API G2 đã thêm session/setup/login/logout/password, products, settings, users, refunds, report, export, backup và void. API tiếp theo cần nhập kho/kiểm kê, sản xuất BTP, ca và nhập Excel. Quyền được kiểm tra ở server; không chỉ ẩn nút trên UI.

## 12. Lộ trình thực hiện và điều kiện hoàn thành

| Giai đoạn | Công việc chính | Đầu ra / điều kiện chuyển bước |
| --- | --- | --- |
| G0 — Bản phát triển hiện tại | Menu từ Excel, POS cơ bản, PDF, kho thủ công, sổ bánh, báo cáo | Đã có; dùng thử nội bộ, ghi nhận phản hồi, chưa coi là vận hành thật |
| G1 — Đối soát dữ liệu | Chốt danh mục bánh; ghép mã nguyên liệu; đơn vị/giá; tồn đầu và ngày kiểm kê; công thức/mẻ; chính sách cost | Danh mục và bảng quy đổi được chủ quán xác nhận; có danh sách dữ liệu chưa rõ; không bật tự trừ cho công thức chưa đủ |
| G2 — Nền tảng vận hành an toàn (đã có phần lõi, đang hoàn thiện) | Auth/quyền, nhật ký, migration, tiền chính xác, cấu hình quán/menu, chống trùng đơn, hoàn/hủy, sao lưu/phục hồi | Đạt các P0 liên quan; test quyền, đồng thời, dữ liệu cũ và phục hồi thành công |
| G3 — Kho/cốt/bánh liên thông | Chứng từ nhập/xuất, cost, sản xuất BTP, trừ kho POS, hạn dùng, bánh dư và thống nhất doanh thu bánh | Chạy kịch bản nhập → sản xuất → bán → hủy/hoàn → kiểm kê không lệch tồn/tiền |
| G4 — Báo cáo và nghiệm thu | Ca, báo cáo chi tiết, xuất dữ liệu, PDF khổ giấy, đối soát Excel, kiểm thử thiết bị | Chủ quán đối soát ngày mẫu và giai đoạn chạy thử ít nhất 7 ngày kinh doanh liên tiếp |
| G5 — Triển khai chính thức | Hosting/domain/HTTPS, DB bền vững, backup tự động, hướng dẫn và hỗ trợ sự cố | Đạt checklist go-live; theo dõi sau triển khai; có phương án quay lại bản cũ và phục hồi dữ liệu |

Chưa chốt ngày bàn giao hoặc chi phí vì phụ thuộc số người phát triển, dữ liệu đối soát, phạm vi phân quyền và hạ tầng. Sau G1, ước lượng từng hạng mục và chốt lịch với chủ quán.

## 13. Kế hoạch kiểm thử và nghiệm thu

| Kịch bản | Kết quả bắt buộc |
| --- | --- |
| Thay giá món sau khi bán | Đơn cũ/PDF cũ giữ snapshot; đơn mới dùng giá mới |
| Tạo đơn nhiều size | Giá, số lượng, tổng và PDF khớp; sửa giá trong request bị bỏ qua/từ chối |
| Nhấn thanh toán hai lần, timeout rồi retry | Chỉ có một đơn, một lần ghi tiền và một lần xuất kho |
| Hai thu ngân cùng bán lượng tồn cuối | Không cùng sử dụng vượt số tồn; yêu cầu thua nhận lỗi rõ |
| Nhập theo hộp, sử dụng theo g/ml | Hệ số quy đổi đã xác nhận; tồn và giá trị đối chiếu được bằng tay |
| Sản xuất BTP rồi bán món | Nguyên liệu trừ lúc sản xuất, BTP trừ lúc bán; không trừ kép |
| Bánh nhập 20, bán 12, hủy 2 | Còn 6; doanh thu 12 × giá; giá vốn bán và hao hụt tách đúng |
| Hoàn tiền món đã làm | Doanh thu điều chỉnh đúng; không mặc định tăng nguyên liệu |
| Đổi ngày/tháng, giao dịch sát 00:00 | Báo cáo theo ngày kinh doanh/múi giờ quán; không bỏ hoặc cộng trùng |
| Nhập lại cùng nguồn Excel | Cảnh báo/ngăn trùng; dòng lỗi có lý do; không mất dữ liệu cũ |
| Nhân viên gọi thẳng API hạn chế | Bị từ chối, không lộ cost/lợi nhuận hoặc thay đổi cấu hình |
| PDF nhiều trang/tên dài/tiếng Việt | Không lỗi dấu, tràn trang hoặc mất dòng; tổng khớp đơn |
| Khởi động lại/nâng cấp/khôi phục backup | Dữ liệu còn nguyên; kiểm thử đối soát tổng đơn, tiền, tồn sau khôi phục |

Kiểm thử hiện có là nền ban đầu, chưa thay thế toàn bộ bảng nghiệm thu. Khi phát triển từng yêu cầu, bổ sung test tự động phù hợp và ghi kết quả thực tế; không đánh dấu đạt cho test chưa chạy.

## 14. Thông tin chủ quán cần chốt

1. Địa chỉ, số điện thoại, logo; mẫu và khổ giấy muốn in.
2. Ai sử dụng, vai trò nào được xem lợi nhuận, sửa giá, hủy đơn hoặc điều chỉnh kho.
3. Danh mục bánh: tên, giá bán, giá nhập/tự làm, hạn dùng, cách xử lý bánh dư.
4. Ngày và số lượng tồn kiểm kê để làm tồn đầu kỳ.
5. Bảng ghép nguyên liệu giữa hai file; quy đổi hộp/túi sang g/ml và công thức/sản lượng mẻ chính thức.
6. Phương pháp giá vốn; xử lý hao hụt, bao bì, chi phí lịch sử và khoản cá nhân.
7. Có bán theo bàn, tại quầy, mang đi; cần số bàn hoặc ghi nợ khách không.
8. Giảm giá, thanh toán hỗn hợp, hoàn/hủy và quy tắc chốt ca/ngày.
9. Chạy trong quán hay truy cập từ xa; số người dùng đồng thời, máy in và thiết bị thực tế.
10. Mức sao lưu cần thiết, nơi lưu bản sao và người chịu trách nhiệm vận hành.

Các nội dung này không ngăn tiếp tục thử bản phát triển, nhưng phải chốt trước triển khai phần nghiệp vụ tương ứng.

## 15. Ngoài phạm vi cơ bản — chỉ thêm khi được yêu cầu

- Hóa đơn điện tử thuế, tự xác nhận chuyển khoản hoặc cổng thanh toán.
- Đa chi nhánh và điều chuyển kho giữa chi nhánh.
- Đặt hàng online/giao hàng và tích hợp nền tảng bên ngoài.
- Thành viên/tích điểm, voucher phức tạp, CRM.
- Chấm công/tính lương, sổ kế toán đầy đủ, tính thuế tự động.
- Chế độ bán offline và đồng bộ nhiều thiết bị khi mất mạng.

## 16. Checklist trước khi sử dụng thật

- [ ] Xác nhận menu, giá, công thức, quy đổi, tồn đầu và danh mục bánh.
- [ ] Hoàn thành tất cả P0 và các P1 quán chọn là bắt buộc.
- [ ] Đăng nhập, phân quyền và nhật ký được kiểm tra qua API.
- [ ] Chống đơn trùng, tồn âm và ghi giao dịch dở dang.
- [ ] Thống nhất cách tính cost, hao hụt, giảm giá và hoàn tiền.
- [ ] Đối soát doanh thu, thanh toán, giá vốn, chi phí và tồn trong đợt chạy thử.
- [ ] PDF đúng thông tin quán và in thử trên thiết bị thực tế.
- [ ] Sao lưu ngoài máy chạy và phục hồi thử thành công.
- [ ] Triển khai HTTPS, lưu trữ bền vững, giám sát và hướng dẫn sự cố.
- [ ] Bàn giao hướng dẫn bán hàng, chốt ca, nhập kho, kiểm kê và quản lý bánh.

**Hồ sơ bàn giao mục tiêu:** mã nguồn + cấu hình triển khai + migration + dữ liệu đầu kỳ đã đối soát + bộ kiểm thử/kết quả + tài liệu sử dụng + quy trình backup/restore. File PLAN này là đặc tả và lộ trình, không xác nhận các phần chưa triển khai đã hoàn thành.


## Cập nhật menu và bill từ ảnh mới

Đã bổ sung catalog 75 món/162 size, 20 mã topping (10 chung và 10 gợi ý), tính giá topping ở server, review/apply menu chủ quán, giỏ tách cấu hình, tùy chọn không in/in bill, logo tải riêng và font tiếng Việt có giấy phép. Chưa biết giá vốn thì không báo lợi nhuận bằng giá vốn 0. Đơn cũ và logo cũ giữ theo snapshot; công thức cũ chỉ liên kết khi ghép chắc chắn, kho chưa tự trừ. Các chi tiết cần chủ quán đối chiếu nằm ở MENU_REVIEW.md.
