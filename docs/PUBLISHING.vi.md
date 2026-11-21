# Đẩy lên GitHub — danh sách việc phải làm

> Viết ngày 2026-11-12. Làm theo thứ tự. Bước nào chưa xong thì **chưa đẩy**.

## 0. Tên sản phẩm — đã chốt "Outrigger" (2026-11-12)

Tên cũ "Keel" trùng thẳng với [`qiweiz94/keel`](https://github.com/qiweiz94/keel) (guardrails cho AI coding agent),
nên đã đổi. Lý do và kết quả tra tên nằm ở [ADR-0008](adr/0008-rename-keel-to-outrigger.md).

| Chỗ cần kiểm | Kết quả ngày 2026-11-12 |
| :-- | :-- |
| GitHub | Không có sản phẩm AI agent nào tên Outrigger (74 repo có chữ này, đều khác lĩnh vực) ✅ |
| PyPI | Tên `outrigger` **đã có chủ** (công cụ tin sinh học, 2017) → nếu phát hành gói thì dùng `outrigger-agent` |
| npm | Tên `outrigger` **đã có chủ** (2016) → dùng `outrigger-agent` |
| Nhãn hiệu | ⚠️ **Chưa tra.** Tra WIPO Global Brand Database và Cục Sở hữu trí tuệ Việt Nam, nhóm 9 và 42. "Outrigger" cũng là tên một chuỗi khách sạn (khác nhóm ngành) |
| Tên miền | ⚠️ Chưa tra |

- [ ] Tra nhãn hiệu và tên miền trước khi in tên lên bất cứ thứ gì tốn tiền.

## 1. Điền chỗ còn trống

- [x] `NOTICE`: chủ bản quyền = HiTranquility (2026-11-21).
- [x] `README.md`: lệnh clone trỏ tới `HiTranquility/outrigger-agent` (2026-11-21).
- [ ] Repo trả phí: `LICENSE-COMMERCIAL.md` còn các ô `[…]` và **phải được luật sư xem** trước khi bán.

## 2. Kiểm lần cuối trên máy

```bash
python -X utf8 -m unittest discover -s tests
```

- [x] 155 test qua (0.4.1, 2026-11-21).
- [ ] **Kiểm tra sống ở chế độ bypass** trong một project đã cài (README, mục Install). Chưa làm bước này thì
      chưa được viết "chặn được khi bypass" ở bất cứ đâu. **Đã đẩy lên khi bước này chưa làm** (quyết định của chủ
      repo 2026-11-21); README chỉ nói người dùng phải tự kiểm, không tuyên bố đã chặn được.
- [ ] `python .outrigger/engine/cli.py notify-test` — thử thông báo thật.
- [ ] Repo trả phí: chạy test MATLAB của demo một lần trên máy có MATLAB.

## 3. Soát thứ không được lên GitHub

```bash
git ls-files | grep -iE "\.env|secret|token|\.pem|\.key|notify\.toml|state/"
```

- [x] Lệnh trên không in ra gì (2026-11-21).
- [x] (2026-11-21) Không có đường dẫn máy cá nhân (`C:\Users\…`) hay email riêng trong file sẽ công khai:

```bash
git grep -n -iE "C:\\\\Users|Downloads/|@gmail" -- . ":!docs/PUBLISHING.vi.md"
```

- [x] (2026-11-21) Tác giả mọi commit đã đổi sang `179889289+HiTranquility@users.noreply.github.com` trước lần
      đẩy đầu; lịch sử cũ giữ trong `outrigger-backups/*.bundle` ngoài repo. Tên tác giả trong lịch sử commit đúng ý bạn (`git log --format="%an <%ae>" | sort -u`). Email trong commit
      sẽ **công khai vĩnh viễn**; muốn giấu thì dùng địa chỉ `…@users.noreply.github.com` của GitHub trước khi đẩy.

## 4. Tạo repo và đẩy

Trên GitHub tạo **hai repo rỗng** (không tick "Add README"):

| Repo | Chế độ | Nội dung |
| :-- | :-- | :-- |
| `<tên>` | **Public** | thư mục `outrigger-agent` |
| `<tên>-pro` | **Private** | thư mục `outrigger-agent-pro` |

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
