# Asset Registry

## Nói ngắn gọn

Trong định hướng mở của AgriOS, mỗi organization cần có khả năng khai báo tài sản và nguồn lực mình dùng để vận hành.

Runtime hiện tại đã có một phần của asset registry, chưa phải một asset catalog tổng quát hoàn chỉnh.

## 1. Những tài sản hoặc nguồn lực đang có lane rõ ràng

- plot
- crop cycle
- lot
- shared resource

## 2. Ý nghĩa nghiệp vụ

### Plot

Đơn vị đất hoặc vùng sản xuất.

### Crop Cycle

Mùa vụ hoặc chu kỳ sản xuất gắn với plot.

### Lot

Lô vật lý sau thu hoạch hoặc xử lý.

### Shared Resource

Nguồn lực dùng chung như xe, kho, labor pool, ngân sách marketing.

## 3. Điều chưa nên nói quá tay

Chưa nên mô tả runtime hiện tại như một asset registry tổng quát kiểu ERP full asset management.

Một số loại tài sản hoặc binding khác vẫn còn là future lane.

## 4. Ví dụ thực tế

- Tổ chức khai báo 3 plot đang trồng lúa.
- Một lot thành phẩm được release sau QC.
- Một xe tải và một kho chung được dùng bởi nhiều project scope.

## 5. Source of truth không

- Plot, crop cycle, lot, shared resource: Có, theo từng lane runtime đã ship.
- Asset registry tổng quát: Chưa.