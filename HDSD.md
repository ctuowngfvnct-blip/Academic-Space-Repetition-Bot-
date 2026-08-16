# SRBot — Spaced Repetition & Deadline Tracker (Telegram Bot)

Bot Telegram giúp:
1. Log buổi học → tự sinh lịch ôn tập theo spaced repetition cố định (1-3-7-14-30 ngày).
2. Lưu deadline bài tập/assignment.
3. Nhắc tự động mỗi ngày (giờ tự chọn) + tra cứu theo yêu cầu (`/homnay`, `/tuan`, `/list`).

Chạy được cả trên iPhone lẫn laptop vì chỉ cần app Telegram — bot chạy trên cloud (Fly.io), 24/7, không phụ thuộc thiết bị nào bật hay tắt.

---

## 1. Tạo bot Telegram (làm 1 lần, ngay trên điện thoại cũng được)

1. Mở Telegram, tìm **@BotFather**.
2. Gửi `/newbot`, đặt tên (VD: `My Study Tracker`) và username (phải kết thúc bằng `bot`, VD: `mystudy_track_bot`).
3. BotFather trả về 1 **token** dạng `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Lưu lại — đây là `BOT_TOKEN`.

## 2. Chạy thử ở local (laptop) trước khi deploy — không bắt buộc nhưng nên làm

```bash
cd srbot
pip install -r requirements.txt
export BOT_TOKEN="dán_token_vừa_lấy_vào_đây"
python bot.py
```

Sau đó vào Telegram, tìm đúng bot vừa tạo, bấm **Start** hoặc gõ `/start`. Nếu bot trả lời được là local chạy ổn — dừng lại (Ctrl+C) rồi chuyển sang deploy thật để có thông báo 24/7.

## 3. Deploy lên Fly.io (miễn phí, chạy 24/7, dữ liệu không mất khi restart)

Cài Fly CLI:

```bash
curl -L https://fly.io/install.sh | sh
fly auth signup     # hoặc fly auth login nếu đã có tài khoản
```

Trong thư mục `srbot/`:

```bash
fly launch --no-deploy
```

- Khi được hỏi, đặt tên app riêng (sửa luôn dòng `app = "..."` trong `fly.toml` cho khớp).
- Chọn region `sin` (Singapore) khi được hỏi, hoặc để mặc định như trong `fly.toml`.
- Từ chối tạo Postgres/Redis nếu được hỏi (không cần).

Tạo volume lưu trữ lâu dài cho SQLite (chỉ cần 1 lần):

```bash
fly volumes create srbot_data --region sin --size 1
```

Set biến môi trường token (bí mật, không lưu trong file):

```bash
fly secrets set BOT_TOKEN="dán_token_vào_đây"
```

Deploy:
 
```bash
fly deploy
```

Kiểm tra log để chắc bot đã chạy:

```bash
fly logs
```

Xong — giờ mở Telegram, gõ `/start` với bot, nó sẽ hoạt động 24/7 dù tắt điện thoại hay laptop.

## 4. Các lệnh dùng hàng ngày

| Lệnh | Ý nghĩa |
|---|---|
| `/hoc <Môn> - <Chủ đề>` | Log buổi học hôm nay, tự sinh 5 mốc ôn tập |
| `/baitap <Tên> - <YYYY-MM-DD> [- <Môn>]` | Thêm deadline bài tập |
| `/homnay` | Việc cần làm hôm nay (gồm cả quá hạn) |
| `/tuan` | Việc đến hạn trong 7 ngày tới |
| `/list` | Toàn bộ việc đang chờ (chưa hoàn thành) |
| `/xong R12` hoặc `/xong A5` | Đánh dấu hoàn thành review #12 / bài tập #5 |
| `/huy R12` hoặc `/huy A5` | Xoá 1 mục |
| `/giobao 07:30` | Đặt giờ nhắc tự động mỗi ngày |
| `/help` | Xem lại hướng dẫn |

Ví dụ thực tế:

```
/hoc Discrete Math - Graph Theory
/baitap Assignment 2 - 2026-08-20 - Discrete Math
/homnay
/xong R3
```

## 5. Cập nhật code sau này

Sửa `bot.py` / `database.py` xong, chỉ cần chạy lại:

```bash
fly deploy
```

Dữ liệu trong volume `srbot_data` (SQLite) không bị mất qua các lần deploy.

## 6. Giới hạn / lưu ý

- Interval ôn tập hiện đang cố định `1-3-7-14-30` ngày (định nghĩa trong `database.py`, biến `REVIEW_INTERVALS`) — có thể chỉnh tay nếu muốn.
- Fly.io free tier đủ cho 1 bot cá nhân dùng nhẹ; nếu sau này m mời thêm bạn dùng chung bot (multi-user) thì code đã hỗ trợ sẵn vì mọi dữ liệu đều theo `chat_id`.
- Timezone cố định `Asia/Ho_Chi_Minh` trong `bot.py`.
