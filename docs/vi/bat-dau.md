# ⚓ Keel — Bắt đầu

> **Keel** (sống thuyền) là bộ phận giúp thuyền căng hết buồm mà không lật.
> Bộ kit này làm đúng việc đó cho AI agent: bạn cho nó **toàn quyền** để làm nhanh, còn Keel giữ cho nó **không lật**.

## 1. Keel làm gì cho bạn

| Nỗi lo | Keel xử lý thế nào |
| :-- | :-- |
| AI xoá nhầm, `git push --force`, sửa registry, tắt tường lửa | **Guard chặn thật** (hook chạy trước mỗi lệnh), không phải chỉ dặn trong file `.md` |
| Không có ai ngồi canh | Rủi ro cao → **thông báo Windows hoặc điện thoại** (ntfy). Tin báo chỉ có mức rủi ro, tên dự án, mã — không chứa code hay dữ liệu |
| AI tự quyết những việc lớn | Mọi bước ngoặt phải hỏi theo **phiếu GATE**; việc bị chặn chỉ được mở khi **chính bạn** gõ lệnh duyệt trong terminal của bạn |
| Mở MATLAB lung tung, tốn licence | **Mức chi phí L0–L3**: AI phải đề xuất phương án rẻ nhất trước; mở ứng dụng có giao diện (L2) phải hỏi, và mọi lần mở đều được ghi `apps.jsonl` |
| Mất file | "Xoá" = **thùng rác có manifest SHA-256**, khôi phục được; sửa file ngoài `sandbox/` thì **sao lưu trước** |
| Không biết AI đã làm gì | Mỗi lượt có **báo cáo**, mỗi quyết định có **ADR**, guard ghi nhật ký mọi lần chặn |
| Nguồn lạ trên mạng | Chỉ tải từ **danh sách host tin cậy**; host lạ = T4 → chặn và hỏi |

## 2. Cài đặt

Cần Python 3.11 trở lên. Keel **không tự cài gì** cho bạn.

```bash
python install.py --target "C:/duong/dan/du-an" --dry
```

```bash
python install.py --target "C:/duong/dan/du-an" --pack "C:/duong/dan/keel-agent-pro/packs/matlab"
```

Cuối cùng làm **bài kiểm tra sống** mà trình cài in ra: bật agent ở chế độ bypass, bảo nó chạy
`rm -rf sandbox/keel-live-check`. Phải thấy `KEEL BLOCKED`. Không thấy → Keel **chưa** bảo vệ bạn, dừng lại.

## 3. Bật thông báo điện thoại (ntfy)

1. Cài app **ntfy** trên điện thoại, bấm *Subscribe*, đặt một tên kênh dài và khó đoán (ví dụ `keel-7f3k9q2m8x`).
2. Mở `.keel/local/notify.toml` (file này không bị đưa lên git), sửa:
   ```toml
   channel = "ntfy"
   [ntfy]
   server = "https://ntfy.sh"
   topic = "keel-7f3k9q2m8x"
   ```
3. Thử: `python .keel/engine/cli.py notify-test`

> Tên kênh ntfy công khai ai đoán được thì người đó đọc được tin báo — vì vậy tin báo **không bao giờ** chứa dữ liệu.
> Muốn kín hoàn toàn: tự dựng máy chủ ntfy, hoặc giữ `channel = "toast"` (chỉ báo trên máy Windows).

## 4. Khi guard chặn

```text
KEEL BLOCKED [HIGH] K-3f9a1c2e
- git-force: force/delete push rewrites shared history
```

AI sẽ gửi bạn phiếu GATE. Đồng ý thì gõ **trong terminal của bạn**:

```bash
python .keel/engine/cli.py approve K-3f9a1c2e
```

Duyệt chỉ có hiệu lực **một lần**, cho **đúng** lệnh đó (đổi một ký tự là phải duyệt lại), trong 30 phút.

| Lệnh | Ai dùng | Làm gì |
| :-- | :-- | :-- |
| `cli.py status` | ai cũng được | trạng thái, số việc chờ duyệt, dung lượng thùng rác |
| `cli.py pending` | ai cũng được | xem các việc đang chờ duyệt |
| `cli.py approve K-…` / `deny K-…` | **chỉ bạn** | duyệt / từ chối |
| `cli.py trash <file> --reason "…"` | AI và bạn | xoá mềm |
| `cli.py restore <mã>` | AI và bạn | khôi phục |
| `cli.py archive <file> --reason "…"` | AI và bạn | lưu trữ vào `archive/` |
| `cli.py empty-trash` | **chỉ bạn** | xoá vĩnh viễn — phải gõ `DELETE FOREVER` |
| `cli.py stop "lý do"` | AI và bạn | **phanh khẩn cấp**: chặn mọi thao tác ghi |
| `cli.py resume` | **chỉ bạn** | nhả phanh |

## 5. Giới hạn — nói thẳng

- Keel là **dây an toàn, không phải lồng kính**. Guard đọc lệnh theo heuristic; một script tự xoá file khi chạy
  chỉ bị bắt nếu có pack quét ngôn ngữ đó (bản lõi có sẵn pack Python; bản Pro có MATLAB `.m`). Script `.sh`, `.js`,
  `.ps1` chưa được quét. Code không tin được → chạy trong máy ảo.
- Keel chặn được gì, bằng cách nào, test nào chứng minh, và **chưa** chặn được gì:
  [RISK_REGISTER.md](../RISK_REGISTER.md) — đối chiếu với OWASP Top 10 for Agentic Applications 2026.
- Tài liệu Claude Code nói hook chạy trước mọi lệnh, nhưng **không nói thẳng** deny vẫn giữ ở chế độ bypass —
  nên bắt buộc làm bài kiểm tra sống ở bước 2.
