import os
import sqlite3
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================
TOKEN = os.getenv("8596154779:AAFMFy7PB3NbzNCWRuHi4IxoeugM9LfKP9g")
OWNER_ID = int(os.getenv("7634311488"))
UPI_ID = os.getenv("abhay-op.315@ptyes")

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stock(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price REAL
)
""")

conn.commit()

def create_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    conn.commit()

# ================= FLASK WEB (RENDER KEEP ALIVE) =================
app = Flask(name)

@app.route("/")
def home():
    return "🔥 V100000 BOT RUNNING"

@app.route("/health")
def health():
    return {"status": "ok"}

# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    create_user(uid)

    keyboard = [
        [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
        [InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("💳 Deposit", callback_data="deposit")]
    ]

    if uid == OWNER_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])

    await update.message.reply_text(
        "🔥 V100000 ULTRA BOT\nChoose option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "wallet":
        cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        bal = cur.fetchone()[0]
        await q.edit_message_text(f"💰 Balance: ₹{bal}")

    elif q.data == "shop":
        cur.execute("SELECT * FROM stock")
        items = cur.fetchall()

        text = "🛒 SHOP:\n\n"
        for i in items:
            text += f"{i[1]} - ₹{i[2]}\n"

        await q.edit_message_text(text or "No stock")

    elif q.data == "deposit":
        await q.edit_message_text(
            f"💳 Pay via UPI:\n{UPI_ID}\n\nSend screenshot to admin."
        )

    elif q.data == "admin" and uid == OWNER_ID:
        await q.edit_message_text(
            "⚙️ ADMIN PANEL\n\n/addstock name price"
        )

async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    name = context.args[0]
    price = float(context.args[1])

    cur.execute("INSERT INTO stock(name,price) VALUES(?,?)", (name, price))
    conn.commit()

    await update.message.reply_text("✅ Stock added")

# ================= START BOT =================
def run_bot():
    app_bot = Application.builder().token(TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("addstock", addstock))
    app_bot.add_handler(CallbackQueryHandler(menu))

    print("BOT RUNNING...")
    app_bot.run_polling()

# ================= RUN BOTH =================
if name == "main":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
