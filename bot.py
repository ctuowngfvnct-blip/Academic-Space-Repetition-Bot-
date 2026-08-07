"""
bot.py — Bot Telegram theo dõi spaced repetition + deadline bài tập.

Lệnh chính:
  /start                          - đăng ký nhận nhắc nhở
  /hoc <Môn> - <Chủ đề>            - log 1 buổi học, tự tạo lịch ôn 1-3-7-14-30 ngày
  /baitap <Tên> - <YYYY-MM-DD> [- <Môn>]  - thêm deadline bài tập
  /homnay                         - liệt kê những gì đến hạn hôm nay (kể cả quá hạn)
  /tuan                           - liệt kê những gì đến hạn trong 7 ngày tới
  /list                           - liệt kê TẤT CẢ việc đang chờ (chưa hoàn thành)
  /xong <R12 | A5>                - đánh dấu hoàn thành review #12 hoặc assignment #5
  /huy <R12 | A5>                 - xoá 1 mục
  /giobao <HH:MM>                 - đặt giờ nhận nhắc mỗi ngày (mặc định 07:00)
  /help                           - hướng dẫn
"""

import logging
import os
from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


# ---------------- Helpers ----------------

def today() -> date:
    return datetime.now(TZ).date()


def fmt_review_line(row) -> str:
    overdue = " ⚠️ QUÁ HẠN" if row["due_date"] < today().isoformat() else ""
    return f"  R{row['id']} • {row['subject']} - {row['topic']} (lần {row['round_number']}/5, hạn {row['due_date']}){overdue}"


def fmt_assignment_line(row) -> str:
    overdue = " ⚠️ QUÁ HẠN" if row["deadline_date"] < today().isoformat() else ""
    subj = f" [{row['subject']}]" if row["subject"] else ""
    return f"  A{row['id']} • {row['name']}{subj} (hạn {row['deadline_date']}){overdue}"


def build_due_message(chat_id: int, up_to: date, header: str) -> str:
    reviews = db.get_due_reviews(chat_id, up_to)
    assignments = db.get_due_assignments(chat_id, up_to)

    if not reviews and not assignments:
        return f"{header}\n\n✅ Không có gì đến hạn. Nghỉ ngơi thôi!"

    parts = [header, ""]
    if reviews:
        parts.append("📚 Cần ôn tập:")
        parts.extend(fmt_review_line(r) for r in reviews)
        parts.append("")
    if assignments:
        parts.append("📝 Bài tập / deadline:")
        parts.extend(fmt_assignment_line(a) for a in assignments)

    parts.append("\nDùng /xong R<id> hoặc /xong A<id> để đánh dấu hoàn thành.")
    return "\n".join(parts)


# ---------------- Command handlers ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.upsert_settings(chat_id)
    schedule_daily_job(context.application, chat_id)
    await update.message.reply_text(
        "Chào m! Bot theo dõi spaced repetition + deadline đã sẵn sàng.\n\n"
        "Gõ /help để xem toàn bộ lệnh.\n"
        "Mặc định t sẽ nhắc mỗi ngày lúc 07:00 (giờ VN). "
        "Đổi giờ bằng /giobao HH:MM."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(__doc__)


async def hoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = " ".join(context.args)
    if " - " not in text:
        await update.message.reply_text(
            "Cú pháp: /hoc <Môn> - <Chủ đề>\nVí dụ: /hoc Discrete Math - Graph Theory"
        )
        return
    subject, topic = text.split(" - ", 1)
    subject, topic = subject.strip(), topic.strip()
    if not subject or not topic:
        await update.message.reply_text("Thiếu môn hoặc chủ đề. Xem lại cú pháp /hoc.")
        return

    start_date = today()
    db.add_study_session(chat_id, subject, topic, start_date)
    dates = [(start_date + timedelta(days=o)).isoformat() for o in db.REVIEW_INTERVALS]
    await update.message.reply_text(
        f"✅ Đã log: {subject} - {topic} (bắt đầu {start_date.isoformat()})\n"
        f"Lịch ôn tập: {', '.join(dates)}"
    )


async def baitap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = " ".join(context.args)
    partss = [p.strip() for p in text.split(" - ")]
    if len(partss) < 2:
        await update.message.reply_text(
            "Cú pháp: /baitap <Tên bài tập> - <YYYY-MM-DD> [- <Môn>]\n"
            "Ví dụ: /baitap Assignment 2 - 2026-08-20 - Discrete Math"
        )
        return
    name = partss[0]
    deadline_str = partss[1]
    subject = partss[2] if len(partss) > 2 else None

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("Ngày hạn phải theo định dạng YYYY-MM-DD, ví dụ 2026-08-20.")
        return

    aid = db.add_assignment(chat_id, name, deadline, subject)
    await update.message.reply_text(f"✅ Đã thêm bài tập A{aid}: {name} (hạn {deadline.isoformat()})")


async def homnay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = build_due_message(chat_id, today(), f"📅 Việc cần làm hôm nay ({today().isoformat()}):")
    await update.message.reply_text(msg)


async def tuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    end = today() + timedelta(days=7)
    msg = build_due_message(chat_id, end, f"📅 Việc đến hạn từ nay đến {end.isoformat()}:")
    await update.message.reply_text(msg)


async def list_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reviews, assignments = db.list_all_pending(chat_id)
    if not reviews and not assignments:
        await update.message.reply_text("Hiện không có review hay bài tập nào đang chờ.")
        return
    parts = ["📋 Toàn bộ việc đang chờ:", ""]
    if reviews:
        parts.append("📚 Ôn tập:")
        parts.extend(fmt_review_line(r) for r in reviews)
        parts.append("")
    if assignments:
        parts.append("📝 Bài tập:")
        parts.extend(fmt_assignment_line(a) for a in assignments)
    await update.message.reply_text("\n".join(parts))


def _parse_ref(ref: str):
    """Parse 'R12' hoặc 'A5' -> ('R'|'A', 12)"""
    ref = ref.strip().upper()
    if len(ref) < 2 or ref[0] not in ("R", "A") or not ref[1:].isdigit():
        return None, None
    return ref[0], int(ref[1:])


async def xong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Cú pháp: /xong R12  hoặc  /xong A5")
        return
    kind, item_id = _parse_ref(context.args[0])
    if kind is None:
        await update.message.reply_text("Không nhận dạng được ID. Dùng dạng R12 (review) hoặc A5 (assignment).")
        return
    ok = db.mark_review_done(item_id, chat_id) if kind == "R" else db.mark_assignment_done(item_id, chat_id)
    if ok:
        await update.message.reply_text(f"✅ Đã đánh dấu hoàn thành {context.args[0].upper()}.")
    else:
        await update.message.reply_text("Không tìm thấy mục này (hoặc đã hoàn thành trước đó).")


async def huy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Cú pháp: /huy R12  hoặc  /huy A5")
        return
    kind, item_id = _parse_ref(context.args[0])
    if kind is None:
        await update.message.reply_text("Không nhận dạng được ID.")
        return
    ok = db.delete_review(item_id, chat_id) if kind == "R" else db.delete_assignment(item_id, chat_id)
    if ok:
        await update.message.reply_text(f"🗑️ Đã xoá {context.args[0].upper()}.")
    else:
        await update.message.reply_text("Không tìm thấy mục này.")


async def giobao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Cú pháp: /giobao HH:MM  (ví dụ /giobao 07:30)")
        return
    try:
        hh, mm = context.args[0].split(":")
        hh, mm = int(hh), int(mm)
        assert 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        await update.message.reply_text("Giờ không hợp lệ. Ví dụ đúng: /giobao 07:30")
        return

    db.upsert_settings(chat_id, hour=hh, minute=mm)
    schedule_daily_job(context.application, chat_id, hour=hh, minute=mm)
    await update.message.reply_text(f"⏰ Đã đặt giờ nhắc hàng ngày: {hh:02d}:{mm:02d} (giờ VN)")


# ---------------- Scheduled job ----------------

async def daily_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    msg = build_due_message(chat_id, today(), f"🔔 Nhắc nhở hôm nay ({today().isoformat()}):")
    await context.bot.send_message(chat_id=chat_id, text=msg)


def schedule_daily_job(application: Application, chat_id: int, hour: int | None = None, minute: int | None = None):
    """Tạo (hoặc thay thế) job nhắc hàng ngày cho 1 chat_id."""
    if hour is None or minute is None:
        settings = db.get_settings(chat_id)
        hour = settings["reminder_hour"] if settings else 7
        minute = settings["reminder_minute"] if settings else 0

    job_name = f"daily_{chat_id}"
    for job in application.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()

    application.job_queue.run_daily(
        daily_reminder_job,
        time=dtime(hour=hour, minute=minute, tzinfo=TZ),
        chat_id=chat_id,
        name=job_name,
    )


async def on_startup(application: Application):
    """Khi bot khởi động lại (sau khi deploy/restart), khôi phục tất cả job nhắc từ DB."""
    for row in db.get_all_settings():
        schedule_daily_job(application, row["chat_id"], row["reminder_hour"], row["reminder_minute"])
    logger.info("Đã khôi phục job nhắc cho %d user.", len(db.get_all_settings()))


def main():
    if not BOT_TOKEN:
        raise SystemExit("Thiếu BOT_TOKEN. Đặt biến môi trường BOT_TOKEN trước khi chạy.")

    db.init_db()

    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("hoc", hoc))
    application.add_handler(CommandHandler("baitap", baitap))
    application.add_handler(CommandHandler("homnay", homnay))
    application.add_handler(CommandHandler("tuan", tuan))
    application.add_handler(CommandHandler("list", list_all))
    application.add_handler(CommandHandler("xong", xong))
    application.add_handler(CommandHandler("huy", huy))
    application.add_handler(CommandHandler("giobao", giobao))

    logger.info("Bot đang chạy...")
    application.run_polling()


if __name__ == "__main__":
    main()
