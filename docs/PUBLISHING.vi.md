# Đẩy lên GitHub — danh sách việc phải làm

> Viết ngày 2026-11-12. Làm theo thứ tự. Bước nào chưa xong thì **chưa đẩy**.

## 0. 🔴 Đổi tên trước — tên "Keel" đã có người dùng cho đúng loại sản phẩm này

Tra ngày 2026-11-12 (🆕 nguồn do AI tìm, đã mở trang kết quả tìm kiếm, chưa đọc từng repo):

| Repo | Là gì | Mức đụng |
| :-- | :-- | :-- |
| [`qiweiz94/keel`](https://github.com/qiweiz94/keel) | *Guardrails for AI coding agents* cho Claude Code, Cursor, Codex, Gemini CLI; cài bằng `npx @get-keel/cli` | **Trùng thẳng**: cùng tên, cùng loại sản phẩm, cùng khách hàng |
| [`keel-hq/keel`](https://github.com/keel-hq/keel) | Công cụ cập nhật triển khai Kubernetes, khoảng 2,7k sao, có trang keel.sh | Trùng tên trong giới DevOps |
| [`rockerlabs/keel`](https://github.com/rockerlabs/keel) | Lớp ngữ cảnh cho AI coding assistant | Trùng tên, gần lĩnh vực |

Hệ quả nếu giữ tên: người tìm "keel agent" ra sản phẩm khác; khó đăng ký nhãn hiệu; dễ bị yêu cầu đổi tên sau khi đã
có khách. **Đổi bây giờ rẻ hơn rất nhiều.**

### Gợi ý tên (cùng hình ảnh "chạy nhanh mà không lật")

| Tên | Nghĩa | Ưu | Nhược |
| :-- | :-- | :-- | :-- |
| **Outrigger** ⭐ | cái phao gắn bên hông xuồng: nhờ nó xuồng chạy nhanh mà không lật | đúng ý nhất; lần tìm ngày 2026-11-12 không thấy sản phẩm guardrail nào dùng | dài, người Việt khó đọc |
| **Hoa Tiêu** (`hoatieu`) | người dẫn tàu qua vùng nước nguy hiểm vào cảng | bản sắc Việt, có câu chuyện để kể, gần như chắc chắn không đụng ai | khách nước ngoài cần một dòng giải thích |
| **Ballast** | khối nặng đáy tàu giữ thăng bằng | ngắn, dễ nhớ | là từ thông dụng, nhiều dự án phần mềm khác lĩnh vực đã dùng |
| **Leeboard** | tấm chắn hông giúp thuyền không trôi dạt | lạ, ít trùng | ít người biết nghĩa |

Chọn xong phải kiểm **bốn chỗ** trước khi chốt: tên repo trên GitHub · tên gói trên npm và PyPI (để dành cho sau) ·
tên miền · nhãn hiệu (tra WIPO Global Brand Database và Cục Sở hữu trí tuệ Việt Nam, nhóm 9 và 42).

### Đổi tên trong mã nguồn

Tên đang nằm ở: thư mục `.keel/`, file `keel.toml`, `KEEL.md`, chuỗi `KEEL BLOCKED`, mã duyệt `K-…`, marker
`<!-- keel:start -->`, tên gói Python `keel`, README và tài liệu. Đổi bằng một lượt tìm–thay có kiểm, rồi chạy lại
toàn bộ test. Các project đã cài (hiện chỉ `Downloads/Web`) cài lại sau khi đổi.

## 1. Điền chỗ còn trống

- [ ] `NOTICE`: thay `[COPYRIGHT OWNER …]` bằng tên chủ bản quyền.
- [ ] `README.md`: thay `<you>/<repo>` trong lệnh `git clone`.
- [ ] Repo trả phí: `LICENSE-COMMERCIAL.md` còn các ô `[…]` và **phải được luật sư xem** trước khi bán.

## 2. Kiểm lần cuối trên máy

```bash
python -X utf8 -m unittest discover -s tests
```

- [ ] 72 test qua.
- [ ] **Kiểm tra sống ở chế độ bypass** trong một project đã cài (README, mục Install). Chưa làm bước này thì
      chưa được viết "chặn được khi bypass" ở bất cứ đâu.
- [ ] `python .keel/engine/cli.py notify-test` — thử thông báo thật.
- [ ] Repo trả phí: chạy test MATLAB của demo một lần trên máy có MATLAB.

## 3. Soát thứ không được lên GitHub

```bash
git ls-files | grep -iE "\.env|secret|token|\.pem|\.key|notify\.toml|state/"
```

- [ ] Lệnh trên không in ra gì (ngoài file luật có chữ "secret" trong tên, nếu có).
- [ ] Không có đường dẫn máy cá nhân (`C:\Users\…`) hay email riêng trong file sẽ công khai:

```bash
git grep -n -iE "C:\\\\Users|Downloads/|@gmail" -- . ":!docs/PUBLISHING.vi.md"
```

- [ ] Tên tác giả trong lịch sử commit đúng ý bạn (`git log --format="%an <%ae>" | sort -u`). Email trong commit
      sẽ **công khai vĩnh viễn**; muốn giấu thì dùng địa chỉ `…@users.noreply.github.com` của GitHub trước khi đẩy.

## 4. Tạo repo và đẩy

Trên GitHub tạo **hai repo rỗng** (không tick "Add README"):

| Repo | Chế độ | Nội dung |
| :-- | :-- | :-- |
| `<tên>` | **Public** | thư mục `keel-agent` |
| `<tên>-pro` | **Private** | thư mục `keel-agent-pro` |

```bash
git remote add origin https://github.com/<you>/<tên>.git
```

```bash
git push -u origin main
```

Làm lại hai lệnh trên trong thư mục repo trả phí với `<tên>-pro`. Kiểm ngay trên web rằng repo `-pro` hiện chữ **Private**.

## 5. Sau khi đẩy

- [ ] Mô tả repo (About): *Guardrails, cost levels and record templates for AI coding agents running with full permissions.*
- [ ] Topics: `ai-agents` `claude-code` `guardrails` `agent-safety` `hooks` `developer-tools`
- [ ] Bật *Private vulnerability reporting* (Settings → Security) và thêm `SECURITY.md` nói cách báo lỗ hổng.
- [ ] Tạo release `v0.2.0` kèm ghi chú: có gì, chưa có gì (chép mục *Honest limits*).
- [ ] Bật bảo vệ nhánh `main` (cấm force-push).

## 6. Bối cảnh cạnh tranh — nên biết trước khi viết lời giới thiệu

Lần tìm ngày 2026-11-12 cho thấy đã có nhiều repo "agent guardrails" cho Claude Code (chặn lệnh nguy hiểm, chặn lộ
khoá, cổng test). Phần **khác biệt** của sản phẩm này, nên đặt lên đầu README:

1. **Mức chi phí L0–L3** và luật "đề xuất phương án rẻ nhất trước" — các bộ khác chỉ chặn, không quản chi phí.
2. **Pack cho phần mềm kỹ thuật** (MATLAB: quét `.m`, phân biệt chạy ngầm với mở giao diện) — chưa thấy bộ nào làm.
3. **Bộ hồ sơ và quy trình** (12 template, phỏng vấn dựng quy trình riêng) — các bộ khác chỉ có hook.
4. **Duyệt gắn SHA, chỉ người duyệt được**, xoá mềm có manifest, bảng rủi ro nối tới từng test.
5. **Song ngữ Việt – Anh.**
