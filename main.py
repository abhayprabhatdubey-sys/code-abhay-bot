import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ================= CONFIGURATION =================
# Highlighted Railway Environment Variables
TOKEN = os.environ.get("8596154779:AAFMFy7PB3NbzNCWRuHi4IxoeugM9LfKP9g")
OWNER_ID = int(os.environ.get("7634311488"))
UPI_ID = os.environ.get("abhay-op.315@ptyes")
 API_ID = os.environ.get("35155488")
 API_HASH = os.environ.get("9ee6b40363f94481d48dea8a3a871728")

# States for ConversationHandlers
ADD_BALANCE_USER, ADD_BALANCE_AMT = range(2)
DEPOSIT_AMT, DEPOSIT_UTR = range(2, 4)
SELL_ID_DATA = 5

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= DATABASE LAYER =================
def init_db():
    conn = sqlite3.connect('premium_store.db')
    c = conn.cursor()
    # Users & Balance
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, 
                 is_reseller INTEGER DEFAULT 0, joined_at TEXT)''')
    # Stock System
    c.execute('''CREATE TABLE IF NOT EXISTS stock 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, country TEXT, 
                 product_name TEXT, data TEXT, price REAL)''')
    # Orders & Deposits
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_info TEXT, 
                 price REAL, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits 
                 (utr TEXT PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT)''')
    # Referral System
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (referrer_id INTEGER, referred_id INTEGER)''')
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect('premium_store.db')
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone: res = c.fetchone()
    if fetchall: res = c.fetchall()
    if commit: conn.commit()
    conn.close()
    return res

# ================= UI HELPER =================
def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Products", callback_data='buy_cat')],
        [InlineKeyboardButton("💰 Deposit", callback_data='deposit'), InlineKeyboardButton("👤 Profile", callback_data='profile')],
        [InlineKeyboardButton("🤝 Sell ID", callback_data='sell_id'), InlineKeyboardButton("🔗 Refer", callback_data='refer')],
        [InlineKeyboardButton("📜 Orders", callback_data='orders_history')]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='admin_main')])
    return InlineKeyboardMarkup(keyboard)

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Auto Register
    db_query("INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?, ?, ?)", 
             (user.id, user.username, datetime.now().strftime("%Y-%m-%d")), commit=True)
    
    await update.message.reply_text(
        f"🔥 Welcome to Premium Store\nHi {user.first_name}, choose an option below:",
        reply_markup=main_menu_keyboard(user.id),
        parse_mode='Markdown'
    )

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = db_query("SELECT balance, is_reseller FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    text = (f"👤 User Profile\n"
            f"━━━━━━━━━━━━━━\n"
            f"🆔 ID: {user_id}\n"
            f"💰 Balance: ₹{user_data[0]}\n"
            f"⭐ Role: {'Reseller' if user_data[1] else 'User'}")
    
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_home')]])
    await query.edit_message_text(text, reply_markup=back_kb, parse_mode='Markdown')

# ================= SELL ID WORKFLOW =================
async def sell_id_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("📝 Sell your ID\nSend the ID details (Phone, Session, or API info). Admin will verify and add balance.")
    return SELL_ID_DATA

async def sell_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    details = update.message.text
    
    # Notify Admin
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"appr_sell_{user.id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"rejc_sell_{user.id}")]
    ])
    await context.bot.send_message(
        OWNER_ID, 
        f"📩 New ID Sell Request\nFrom: {user.id}\nDetails: {details}",
        reply_markup=admin_kb
    )
    await update.message.reply_text("✅ Details sent to admin. Please wait for verification.")
    return ConversationHandler.END

# ================= DEPOSIT SYSTEM (UTR) =================
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(f"💳 Deposit Funds\nSend amount to: {UPI_ID}\n\nMin: ₹10\nEnter amount you want to add:")
    return DEPOSIT_AMT

async def deposit_amt_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['dep_amt'] = update.message.text
    await update.message.reply_text("Now send the 12-digit UTR Number of the transaction:")
    return DEPOSIT_UTR

async def deposit_utr_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    utr = update.message.text
    amount = context.user_data['dep_amt']
    user_id = update.effective_user.id
    
    # Basic UTR check
    if len(utr) != 12 or not utr.isdigit():
        await update.message.reply_text("❌ Invalid UTR. Must be 12 digits. Try again /start")
        return ConversationHandler.END
    
    # Save to DB
    try:
        db_query("INSERT INTO deposits (utr, user_id, amount, status) VALUES (?, ?, ?, ?)", 
                 (utr, user_id, amount, "Pending"), commit=True)
        
        # Notify Admin
        admin_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"dep_appr_{utr}")]])
        await context.bot.send_message(OWNER_ID, f"💰 New Deposit\nUser: {user_id}\nAmt: ₹{amount}\nUTR: {utr}", reply_markup=admin_kb)
        
        await update.message.reply_text("✅ Deposit request sent. Waiting for admin approval.")
    except:
        await update.message.reply_text("❌ This UTR was already submitted.")
    
    return ConversationHandler.END

# ================= ADMIN ACTIONS =================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("dep_appr_"):
        utr = data.replace("dep_appr_", "")
        dep = db_query("SELECT user_id, amount FROM deposits WHERE utr = ?", (utr,), fetchone=True)
        if dep:
            db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (dep[1], dep[0]), commit=True)
            db_query("DELETE FROM deposits WHERE utr = ?", (utr,), commit=True)
            await context.bot.send_message(dep[0], f"✅ Your deposit of ₹{dep[1]} has been approved!")
            await query.edit_message_text(f"✅ Approved UTR: {utr}")

# ================= MAIN APP =================
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # Conversation for Selling
    sell_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(sell_id_start, pattern='sell_id')],
        states={SELL_ID_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_id_received)]},
        fallbacks=[CommandHandler("cancel", start)]
    )

    # Conversation for Deposit
    dep_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_start, pattern='deposit')],
        states={
            DEPOSIT_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amt_rec)],
            DEPOSIT_UTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_utr_rec)]
        },
        fallbacks=[CommandHandler("cancel", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_profile, pattern='profile'))
    app.add_handler(CallbackQueryHandler(start, pattern='back_home'))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern='dep_appr_'))
    app.add_handler(sell_conv)
    app.add_handler(dep_conv)

    print("Bot is running...")
    app.run_polling()

if name == 'main':
    main()
