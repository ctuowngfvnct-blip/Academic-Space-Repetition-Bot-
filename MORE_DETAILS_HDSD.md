# SRBot — Spaced Repetition & Deadline Tracker (Telegram Bot)

Bot Telegram cá nhân giúp theo dõi việc học và deadline mà không cần ghi tay:

1. **Log buổi học** → tự sinh lịch ôn tập theo spaced repetition cố định (1-3-7-14-30 ngày sau ngày học).
2. **Lưu deadline bài tập/assignment** → nhắc khi gần đến hạn.
3. **Nhắc tự động mỗi ngày** (giờ tự chọn) + tra cứu theo yêu cầu bất cứ lúc nào (`/homnay`, `/tuan`, `/list`).

Dùng được cả trên iPhone lẫn laptop vì chỉ cần app Telegram — bot chạy trên cloud (Fly.io) 24/7, không phụ thuộc thiết bị nào bật hay tắt.

---

## 1. Cấu trúc project

```
srbot/
├── bot.py            # Toàn bộ logic bot: command handlers, job nhắc hàng ngày
├── database.py       # Lớp truy cập SQLite: study_sessions, review_items, assignments, settings
├── requirements.txt  # Dependency (python-telegram-bot)
├── Dockerfile         # Build image để deploy lên Fly.io
├── fly.toml           # Cấu hình Fly.io (region, volume, resource size)
└── README.md
```

**Database schema (SQLite, 1 file duy nhất):**
- `study_sessions` — mỗi lần log `/hoc`: môn, chủ đề, ngày bắt đầu.
- `review_items` — 5 mốc ôn tập sinh tự động cho mỗi session (round 1→5, ứng với +1/+3/+7/+14/+30 ngày).
- `assignments` — deadline bài tập, độc lập với spaced repetition.
- `settings` — lưu `chat_id` + giờ nhắc mỗi ngày của từng user.

## 2. Lệnh bot

| Lệnh | Ý nghĩa |
|---|---|
| `/start` | Đăng ký nhận nhắc nhở (lưu chat_id) |
| `/hoc <Môn> - <Chủ đề>` | Log buổi học hôm nay, tự sinh 5 mốc ôn tập |
| `/baitap <Tên> - <YYYY-MM-DD> [- <Môn>]` | Thêm deadline bài tập |
| `/homnay` | Việc cần làm hôm nay (gồm cả quá hạn) |
| `/tuan` | Việc đến hạn trong 7 ngày tới |
| `/list` | Toàn bộ việc đang chờ (chưa hoàn thành) |
| `/xong R12` hoặc `/xong A5` | Đánh dấu hoàn thành review #12 / bài tập #5 |
| `/huy R12` hoặc `/huy A5` | Xoá 1 mục |
| `/giobao 07:30` | Đặt giờ nhắc tự động mỗi ngày (mặc định 07:00, giờ VN) |
| `/help` | Xem lại hướng dẫn |

Ví dụ dùng thực tế:

```
/hoc Discrete Math - Graph Theory
/baitap Assignment 2 - 2026-08-20 - Discrete Math
/homnay
/xong R3
```

## 3. Setup & chạy thử ở local

```bash
git clone <repo-url> && cd srbot
pip install -r requirements.txt
export BOT_TOKEN="token_lấy_từ_BotFather"   # Windows PowerShell: $env:BOT_TOKEN="..."
python bot.py
```

Token lấy bằng cách chat với **@BotFather** trên Telegram → `/newbot` → đặt tên → nhận token dạng `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.

Chạy local chỉ để **test nhanh** — bot sẽ ngừng ngay khi tắt terminal/laptop. Muốn chạy 24/7 thật sự thì phải deploy lên Fly.io (mục 4).

## 4. Deploy lên Fly.io (chạy 24/7, không phụ thuộc thiết bị)

Cài Fly CLI và đăng nhập:

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

Trong thư mục project:

```bash
fly launch --no-deploy
```

> ⚠️ **Quan trọng — xem mục Troubleshooting #2 bên dưới.** `fly launch` mặc định tự thêm khối `[http_service]` vào `fly.toml`. Bot này dùng long-polling (không phải web service), nên **phải xoá khối `[http_service]` đó đi** nếu CLI tự sinh ra, nếu không bot sẽ bị Fly tự tắt sau vài phút "rảnh".

Tạo volume lưu SQLite lâu dài (chỉ 1 lần):

```bash
fly volumes create srbot_data --region sin --size 1
```

Set token bí mật (không lưu trong file, không commit lên Git):

```bash
fly secrets set BOT_TOKEN="token_của_m"
```

Deploy:

```bash
fly deploy
```

Kiểm tra:

```bash
fly status      # machine phải ở trạng thái "started"
fly logs        # xem dòng "Bot đang chạy..." và "Application started"
```

## 5. CI/CD qua GitHub Actions (tuỳ chọn)

Nếu muốn mỗi lần push code lên GitHub tự động deploy lại:

1. Tạo Fly API token: `fly tokens create deploy`
2. Thêm token đó vào GitHub repo → Settings → Secrets → Actions → tên `FLY_API_TOKEN`
3. Workflow gọi `flyctl deploy` khi có push vào nhánh chính.

**Lưu ý:** `fly deploy` mới thực sự áp dụng cấu hình mới nhất trong `fly.toml` lên machine. Lệnh `fly apps restart` hay `fly machine start` **không** đọc lại `fly.toml` — chỉ khởi động lại machine với cấu hình cũ đang lưu trên Fly. Nếu sửa `fly.toml` mà thấy hành vi không đổi, luôn ưu tiên chạy lại `fly deploy` để chắc chắn, rồi dùng `fly config show` để xem cấu hình **thật** đang chạy trên server (nguồn chân lý, khác với file trên máy/repo).

## 6. Troubleshooting — các lỗi đã gặp trong quá trình build

### 6.1. `RuntimeError: There is no current event loop in thread 'MainThread'` khi chạy local

**Nguyên nhân:** máy chạy Python bản rất mới (3.14), vốn đã bỏ tính năng tự tạo event loop ngầm mà `python-telegram-bot` bản cũ (`21.6`) còn phụ thuộc vào. Bug này đã được cộng đồng PTB xác nhận và fix từ bản `22.4` trở lên.

**Fix:** nâng cấp thư viện trong `requirements.txt`:

```
python-telegram-bot[job-queue]==22.8
```

rồi `pip install -r requirements.txt --upgrade` (thêm `--upgrade` để pip gỡ bản cũ, tránh báo "already satisfied" mà không cài đè).

### 6.2. Bot chạy ổn vài phút rồi tự im lặng, dù machine trên Fly vẫn "started"

**Triệu chứng trong log:**

```
proxy[...] App <tên-app> has excess capacity, autostopping machine ... 0 out of 1 machines left running
```

**Nguyên nhân:** khi chạy `fly launch`, Fly CLI mặc định thêm khối `[http_service]` vào `fly.toml` với `auto_stop_machines = "stop"` và `min_machines_running = 0` — cấu hình dành cho web service muốn "scale về 0" khi rảnh. Bot này không mở HTTP port (chỉ long-polling ra ngoài tới Telegram API), nhưng Fly Proxy vẫn áp cơ chế autostop này, nên sau ~7-10 phút "không thấy traffic HTTP", nó tự tắt machine về 0 → bot ngưng nhận tin dù chưa hề crash hay lỗi gì.

**Fix:** xoá hẳn khối `[http_service]` khỏi `fly.toml` (bot không cần nó). Sau khi sửa file, **phải chạy `fly deploy`** (không phải `fly apps restart`) để áp dụng cấu hình mới, rồi xác nhận bằng:

```bash
fly config show
```

Nếu output không còn đoạn `http_service` nào, coi như đã sửa đúng. Theo dõi `fly logs` khoảng 15-20 phút để chắc dòng `autostopping machine` không xuất hiện lại.

## 7. Giới hạn / lưu ý

- Interval ôn tập hiện cố định `1-3-7-14-30` ngày, định nghĩa ở `database.py` (biến `REVIEW_INTERVALS`) — sửa tay nếu muốn đổi.
- Timezone cố định `Asia/Ho_Chi_Minh` trong `bot.py` (biến `TZ`).
- Fly.io free tier đủ cho 1 bot cá nhân dùng nhẹ. Code đã hỗ trợ multi-user sẵn (mọi dữ liệu tách theo `chat_id`), nên có thể mời thêm người dùng chung bot nếu muốn.
- SQLite lưu trong Fly volume (`/data/srbot.db`) — không mất dữ liệu qua các lần deploy, miễn là volume không bị xoá tay.
