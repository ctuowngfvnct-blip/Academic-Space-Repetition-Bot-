# SRBot — Spaced Repetition & Deadline Tracker

Telegram bot cá nhân giúp một sinh viên (đang học ~7 môn/kỳ) theo dõi lịch ôn tập theo
spaced repetition và deadline bài tập, thay thế việc ghi tay trên giấy.

> File này dành cho **dev/agent tiếp tục phát triển dự án**. Hướng dẫn cài đặt/sử dụng
> hàng ngày (cho end-user) nằm ở [`HDSD.md`](./HDSD.md) — đọc file đó nếu chỉ cần biết
> cách dùng bot, không cần sửa code.

---

## 1. Tổng quan kiến trúc

```
Telegram (client: iPhone + laptop, không cần app riêng)
        │  long polling (getUpdates)
        ▼
   bot.py  (python-telegram-bot v22.x, async)
        │  gọi trực tiếp các hàm sync
        ▼
   database.py  (sqlite3, không dùng ORM)
        │
        ▼
   SQLite file (đường dẫn theo env DB_PATH)
```

- **Không có HTTP server / webhook.** Bot dùng long-polling (`application.run_polling()`),
  tự chủ động hỏi Telegram API liên tục. Điều này quan trọng khi cấu hình hosting — xem
  mục 5 (Known Issues).
- **Single container, single process.** Không có worker riêng; job nhắc hàng ngày chạy
  bằng `JobQueue` tích hợp sẵn trong `python-telegram-bot` (nền APScheduler), cùng process
  với bot, không phải cron job tách biệt.
- **Đa người dùng đã được tính đến ở tầng data** (mọi bảng đều có `chat_id`), nhưng hiện
  tại chỉ có 1 user thật sự dùng. Không có concept "auth" hay "role" — bất kỳ ai gửi
  `/start` cho bot đều được đăng ký nhận nhắc.

## 2. Cấu trúc file

| File | Vai trò |
|---|---|
| `bot.py` | Entry point. Định nghĩa toàn bộ command handler Telegram + job nhắc hàng ngày + hàm `main()`. |
| `database.py` | Toàn bộ logic truy cập SQLite: tạo bảng, CRUD cho study session / review item / assignment / settings. Không có migration framework — thay đổi schema phải tự viết `ALTER TABLE` thủ công hoặc xoá DB làm lại (chấp nhận được vì đây là dữ liệu cá nhân, ít rủi ro). |
| `requirements.txt` | Pin cứng `python-telegram-bot[job-queue]==22.8`. **Lưu ý:** bản `21.6` KHÔNG tương thích Python 3.14 trở lên (xem mục 5). |
| `Dockerfile` | Build image chạy `python bot.py`, đọc `DB_PATH` từ env (mount vào `/data` khi chạy trên Fly). |
| `fly.toml` | Cấu hình deploy Fly.io. **Cố ý KHÔNG có khối `[http_service]`** — xem mục 5, đây là nguồn gốc 1 bug đã gặp. |
| `HDSD.md` | Hướng dẫn sử dụng cho end-user (tiếng Việt), không phải tài liệu kỹ thuật. |

## 3. Data model (SQLite)

```
study_sessions          review_items                  assignments
─────────────────       ─────────────────             ─────────────────
id                       id                             id
chat_id                  session_id  ──FK──▶            chat_id
subject                  chat_id                        name
topic                    round_number (1-5)             subject (nullable)
start_date               due_date                       deadline_date
created_at               done / done_date                done
                                                         created_at

settings
─────────────────
chat_id (PK)
reminder_hour
reminder_minute
```

- **Spaced repetition hiện tại là cố định**, không phải thuật toán thích ứng kiểu SM-2:
  `REVIEW_INTERVALS = [1, 3, 7, 14, 30]` (ngày), khai báo ở đầu `database.py`. Mỗi lần
  `/hoc` được gọi, hệ thống sinh sẵn **5 row `review_items`** với `due_date` tính trước,
  không sinh động theo kết quả ôn tập (không có ease factor).
- ID hiển thị cho người dùng có tiền tố phân biệt bảng: `R<id>` cho `review_items`,
  `A<id>` cho `assignments` (parse trong `_parse_ref()` ở `bot.py`).
- Không có soft-delete; `/huy` xoá row thật (`DELETE`).

## 4. Chạy dev / test local

```bash
pip install -r requirements.txt
export BOT_TOKEN="..."          # lấy từ @BotFather
python bot.py                    # long-polling, Ctrl+C để dừng
```

Test logic DB không cần token Telegram (không phụ thuộc network):

```python
import database as db
db.init_db()
db.add_study_session(chat_id=1, subject="Test", topic="Topic", start_date=...)
```

Không có test suite tự động (`pytest` v.v.) hiện tại — nếu thêm feature phức tạp hơn,
nên bổ sung test cho `database.py` trước vì đó là phần logic thuần, dễ test nhất.

## 5. Trạng thái hiện tại / Known issues

### ✅ Đã fix
- **Python 3.14 + PTB 21.6 không tương thích** (`RuntimeError: no current event loop`).
  → Nâng lên `python-telegram-bot==22.8` trong `requirements.txt`. Đừng hạ version xuống
  dưới 22.4 nếu môi trường chạy Python ≥3.14.

### 🟡 Đang xử lý / cần xác minh lại
- **Fly.io tự "autostop" machine dù bot vẫn đang hoạt động bình thường.**
  Log lỗi đặc trưng: `App <name> has excess capacity, autostopping machine ... 0 out of 1
  machines left running`. Xảy ra sau khoảng vài phút không có traffic — nhưng bot dùng
  long-polling (không có HTTP traffic vào) nên bị hiểu nhầm là "web service rảnh rỗi".
  - **Nguyên nhân gốc:** khi chạy `fly launch`, Fly CLI tự động thêm khối `[http_service]`
    vào `fly.toml` với `auto_stop_machines = "stop"` và `min_machines_running = 0` — mặc
    định này chỉ hợp lý cho web app, **không hợp lý cho long-polling worker**.
  - **Fix đã áp dụng:** xoá hẳn khối `[http_service]` khỏi `fly.toml` trong repo.
  - **CẦN LƯU Ý:** `fly apps restart` KHÔNG áp dụng lại `fly.toml` — nó chỉ khởi động lại
    machine với cấu hình cũ đã lưu trên Fly. Phải dùng `fly deploy` (hoặc để CI/CD chạy
    `flyctl deploy`) để áp dụng file `fly.toml` mới. Dùng `fly config show` để xem cấu
    hình THẬT đang áp dụng trên Fly server (nguồn chân lý, không phải file local) —
    nếu vẫn thấy `http_service` ở đó nghĩa là chưa deploy đúng.
  - **Trạng thái tại thời điểm viết file này: đang chờ xác nhận sau lần `fly deploy` thủ
    công gần nhất có hết bị autostop hay không.** Nếu agent/dev đọc file này và thấy bot
    vẫn bị mất kết nối định kỳ, đây là nghi phạm đầu tiên cần kiểm tra lại.

### Chưa làm / hạn chế đã biết
- Không có health check hay alerting nếu bot crash ngoài việc tự xem `fly logs`.
- Không có rate-limit hay validate input mạnh cho các lệnh (`/hoc`, `/baitap`) — sai định
  dạng thì chỉ báo lỗi cú pháp đơn giản, không gợi ý sửa thông minh.
- Volume `srbot_data` trên Fly là **single point of failure** cho dữ liệu — chưa có backup
  tự động. Nếu volume bị mất, toàn bộ lịch sử học/deadline mất theo.
- Chưa test kỹ trường hợp nhiều review/assignment dồn lại cùng lúc (ví dụ sau kỳ thi dài
  ngày không mở bot) — `/homnay` sẽ liệt kê tất cả quá hạn dồn lại, có thể dài, chưa có
  phân trang hay giới hạn hiển thị.

## 6. Roadmap / ý tưởng mở rộng (chưa làm, ưu tiên tuỳ nhu cầu người dùng)

- Đổi từ interval cố định sang SM-2 hoặc thuật toán thích ứng (người dùng đã cân nhắc lúc
  đầu nhưng chọn interval cố định cho đơn giản trước).
- Web dashboard xem tổng quan (người dùng ban đầu cân nhắc rồi bỏ, ưu tiên Telegram thuần).
- Giới hạn/ưu tiên số lượng review hiển thị mỗi ngày khi dồn quá nhiều (đã note với user
  là điểm cần theo dõi nếu về sau thấy `/homnay` quá tải).
- Backup định kỳ SQLite (ví dụ export ra Telegram file mỗi tuần, hoặc dùng Litestream).
- Test suite cho `database.py`.

## 7. Deploy pipeline

- Hosting: **Fly.io** (region `sin`), miễn phí, chọn vì có persistent volume free tier —
  quan trọng vì cần data không mất khi machine restart, khác Render free tier hay wipe disk.
- CI/CD: push lên GitHub → GitHub Actions chạy `flyctl deploy` (workflow file không nằm
  trong thư mục project này, xem trực tiếp trong `.github/workflows/` trên repo GitHub của
  chủ dự án).
- Secret cần thiết trên Fly: `BOT_TOKEN` (set bằng `fly secrets set BOT_TOKEN=...`, không
  lưu trong code hay `fly.toml`).
- Secret cần thiết trên GitHub Actions: `FLY_API_TOKEN` (đã từng bị thiếu/dán sai 1 lần
  lúc setup ban đầu, đã fix bằng cách thêm lại secret trên GitHub repo settings).
