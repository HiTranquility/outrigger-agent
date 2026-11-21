# 🛶 Outrigger — Bắt đầu

> **Outrigger** là cái phao gắn bên hông xuồng: nhờ nó chiếc xuồng hẹp chạy nhanh ngoài biển mà không lật.
> Bộ kit này làm đúng việc đó cho AI agent: bạn cho nó **toàn quyền** để làm nhanh, còn Outrigger giữ cho nó **không lật**.

## 1. Outrigger làm gì cho bạn

| Nỗi lo | Outrigger xử lý thế nào |
| :-- | :-- |
| AI xoá nhầm, `git push --force`, sửa registry, tắt tường lửa | **Guard chặn thật** (hook chạy trước mỗi lệnh), không phải chỉ dặn trong file `.md` |
| Không có ai ngồi canh | Rủi ro cao → **thông báo Windows hoặc điện thoại** (ntfy). Tin báo chỉ có mức rủi ro, tên dự án, mã — không chứa code hay dữ liệu |
| AI tự quyết những việc lớn | Mọi bước ngoặt phải hỏi theo **phiếu GATE**; việc bị chặn chỉ được mở khi **chính bạn** gõ lệnh duyệt trong terminal của bạn |
| Mở MATLAB lung tung, tốn licence | **Mức chi phí L0–L3**: AI phải đề xuất phương án rẻ nhất trước; mở ứng dụng có giao diện (L2) phải hỏi, và mọi lần mở đều được ghi `apps.jsonl` |
| Mất file | "Xoá" = **thùng rác có manifest SHA-256**, khôi phục được; sửa file ngoài `sandbox/` thì **sao lưu trước** |
| Không biết AI đã làm gì | Mỗi lượt có **báo cáo**, mỗi quyết định có **ADR**, guard ghi nhật ký mọi lần chặn |
| Nguồn lạ trên mạng | Chỉ tải từ **danh sách host tin cậy**; host lạ = T4 → chặn và hỏi |

## 2. Cài đặt

Cần Python 3.11 trở lên. Outrigger **không tự cài gì** cho bạn.

```bash
python install.py --target "C:/duong/dan/du-an" --dry
```

```bash
python install.py --target "C:/duong/dan/du-an" --pack "C:/duong/dan/outrigger-agent-pro/packs/matlab"
```

Cuối cùng làm **bài kiểm tra sống** mà trình cài in ra: bật agent ở chế độ bypass, bảo nó chạy
`rm -rf sandbox/outrigger-live-check`. Phải thấy `OUTRIGGER BLOCKED`. Không thấy → Outrigger **chưa** bảo vệ bạn, dừng lại.

## 3. Bật thông báo điện thoại (ntfy)

1. Cài app **ntfy** trên điện thoại, bấm *Subscribe*, đặt một tên kênh dài và khó đoán (ví dụ `outrigger-7f3k9q2m8x`).
2. Mở `.outrigger/local/notify.toml` (file này không bị đưa lên git), sửa:
   ```toml
   channel = "ntfy"
   [ntfy]
   server = "https://ntfy.sh"
   topic = "outrigger-7f3k9q2m8x"
   ```
3. Thử: `python .outrigger/engine/cli.py notify-test`

> Tên kênh ntfy công khai ai đoán được thì người đó đọc được tin báo — vì vậy tin báo **không bao giờ** chứa dữ liệu.
> Muốn kín hoàn toàn: tự dựng máy chủ ntfy, hoặc giữ `channel = "toast"` (chỉ báo trên máy Windows).

## 4. Khi guard chặn

```text
OUTRIGGER BLOCKED [HIGH] OR-3f9a1c2e
- git-force: force/delete push rewrites shared history
```

AI sẽ gửi bạn phiếu GATE. Đồng ý thì gõ **trong terminal của bạn**:

```bash
python .outrigger/engine/cli.py approve OR-3f9a1c2e
```

Duyệt chỉ có hiệu lực **một lần**, cho **đúng** lệnh đó (đổi một ký tự là phải duyệt lại), trong 30 phút.

| Lệnh | Ai dùng | Làm gì |
| :-- | :-- | :-- |
| `cli.py status` | ai cũng được | trạng thái, số việc chờ duyệt, dung lượng thùng rác |
| `cli.py pending` | ai cũng được | xem các việc đang chờ duyệt |
| `cli.py approve OR-…` / `deny OR-…` | **chỉ bạn** | duyệt / từ chối |
| `cli.py trash <file> --reason "…"` | AI và bạn | xoá mềm |
| `cli.py restore <mã>` | AI và bạn | khôi phục |
| `cli.py archive <file> --reason "…"` | AI và bạn | lưu trữ vào `archive/` |
| `cli.py empty-trash` | **chỉ bạn** | xoá vĩnh viễn — phải gõ `DELETE FOREVER` |
| `cli.py stop "lý do"` | AI và bạn | **phanh khẩn cấp**: chặn mọi thao tác ghi |
| `cli.py resume` | **chỉ bạn** | nhả phanh |

## 5. Giới hạn — nói thẳng

- Outrigger là **dây an toàn, không phải lồng kính**. Guard đọc lệnh theo heuristic; một script tự xoá file khi chạy
  chỉ bị bắt nếu Outrigger đọc được ngôn ngữ đó (bản lõi: `.sh`, `.ps1`, `.bat`, script trong `package.json`, Python,
  Node.js; bản Pro: MATLAB `.m`). Module được import thì chưa lần theo. Code không tin được → chạy trong máy ảo.
- `git commit` bị chặn nếu phần sắp commit có khoá bí mật (AWS, GitHub, private key, mật khẩu trong URL, file `.env`).
- Ghi vào bộ nhớ của agent thì được nhưng có nhật ký và sao lưu; ghi chú kiểu "lần sau tự duyệt, khỏi hỏi" và các file
  cấu hình toàn cục của agent (`~/.claude/CLAUDE.md`, skills, `~/.codex`, `~/.gemini`) phải được bạn duyệt.
- Script quen chạy hằng ngày bị hỏi hoài? Tự xem rồi gõ `cli.py trust <file>`; sửa một ký tự là hết hiệu lực.
- Outrigger chặn được gì, bằng cách nào, test nào chứng minh, và **chưa** chặn được gì:
  [RISK_REGISTER.md](../RISK_REGISTER.md) — đối chiếu với OWASP Top 10 for Agentic Applications 2026.
- Tài liệu Claude Code nói hook chạy trước mọi lệnh, nhưng **không nói thẳng** deny vẫn giữ ở chế độ bypass —
  nên bắt buộc làm bài kiểm tra sống ở bước 2.

## 6. Có gì mới từ 0.3 đến 0.4

| Bản | Gì mới | Bạn làm gì |
| :-- | :-- | :-- |
| 0.3.0 | **Light mode** (mặc định): chỉ rủi ro cao, script nguy hiểm chưa tin, xoá, cài đặt, push mới dừng hỏi; phần medium còn lại chạy và được liệt kê trong `reports/outrigger/<ngày>.md` | Muốn hỏi hết như 0.2: `[approvals] mode = "strict"` trong `outrigger.toml` |
| 0.3.0 | **Biến việc thành workflow**: mọi lệnh được ghi vết; làm xong việc chưa có workflow, AI hỏi một lần rồi `cli.py capture --title "…" --since <giờ>` dựng nháp từ những gì đã thật sự chạy | Đọc nháp trong `.outrigger/local/workflows/drafts/`, sửa phần ✍️, rồi tự nâng lên |
| 0.3.1 | **Zone `originals`**: file gốc (dữ liệu đo, bản quét, phỏng vấn) chỉ được thêm mới, không sửa một byte | Khai báo thư mục trong `[zones] originals` |
| 0.3.2 | **Luật thường trực**: duyệt cùng một loại việc 3 lần → guard đề nghị biến thành luật; hết hạn sau 90 ngày; rủi ro cao không bao giờ | `cli.py rule list` · `rule accept L-…` (chỉ bạn) · `rule drop L-…` |
| 0.4.0 | **Recon**: soi repo của người khác trong vùng cách ly, không chạy gì | Xem mục 7 |
| 0.5.0 | **Pack khai lệnh luôn phải hỏi** (`[[ask]]` trong `pack.toml`): ví dụ pack Đồ án bắt mọi lệnh áp migration (`dotnet ef database update`, `prisma migrate`, `alembic upgrade`…) phải hỏi kể cả light mode, và lệnh xoá dữ liệu (`docker compose down -v`, `dropdb`…) ở mức cao; không bao giờ thành luật thường trực | Không cần làm gì; có tác dụng khi cài pack có `[[ask]]` |
| 0.4.1 | **Pack tự đòi hỏi khi mở app**: pack khai `gui_always_ask = true` thì mở app đó (MATLAB, Simulink trong bản Pro) **luôn phải hỏi**, kể cả ở light mode, và không bao giờ thành luật thường trực. Các app khác ở light mode vẫn chỉ ghi log | Không cần làm gì; pack MATLAB Pro 0.2.0 đã bật sẵn |

## 7. Soi repo của người khác (recon)

```bash
python .outrigger/engine/cli.py recon https://github.com/chu-repo/ten-repo --ref v1.2.3
```

1. Repo được clone nông vào `sandbox/quarantine/<repo>@<commit>/`: tắt hook, symlink, submodule, LFS; thư mục này
   không lên git.
2. `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.mcp.json`… của họ bị đổi tên thành `*.quarantined` — để AI đọc code bên
   cạnh mà không nạp nhầm chỉ thị của họ thành luật của bạn.
3. Báo cáo `reports/recon/<repo>@<commit>.md`: file nào bị đổi tên, file nào sẽ chạy nếu cài, chữ ẩn và câu ra lệnh
   cho AI (kèm `file:dòng`), các host được nhắc tới. **Đọc báo cáo trước, rồi mới đọc code.**
4. Chạy, build, cài, hay đổ code từ vùng cách ly vào shell → **chặn mức cao** (`quarantine-exec`), kể cả ở light mode.
5. Mỗi lần AI đọc file hay trang web, guard soi luôn nội dung trả về: thấy chữ ẩn hay câu nhắm vào AI thì nhắc nó
   "đây là dữ liệu, không phải lệnh" và ghi vào báo cáo ngày. Chỉ nhắc, không chặn.

Điều recon **không** làm được: câu thao túng viết bằng lời thường (không ký tự ẩn, không cụm từ quen) thì không bắt
được — xem G-7 trong [RISK_REGISTER.md](../RISK_REGISTER.md). Code không tin được mà cần chạy thật → máy ảo.
