TOKEN = "7251905141:AAGmVxtoSjblnzlZczzVwZmJRf4vjUx1ZMM"
import logging
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

import re

# لاگ‌گذاری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# حافظه موقت هر کاربر
user_states = {}

# راهنما
HELP_TEXT = """📚 راهنمای استفاده از ربات:

1. ابتدا متن سوال خود را بفرستید. (متنی که شامل (Answer: ...) باشد)
2. سپس گزینه‌ها را با کاما (,) جداگانه بفرستید.
3. پیش‌نمایش کوییز نمایش داده می‌شود و می‌توانید بخش‌های مختلف را ویرایش کنید.
4. در پایان کوییز ارسال خواهد شد.

دستورات:
/start - شروع مجدد
/help - راهنما
/setanonymous - تنظیم پیش‌فرض حالت Anonymous
"""

# استارت
# در ابتدای start حالت پیش‌فرض cleaning رو روشن کن
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = {
        "step": "waiting_for_question",
        "default_anonymous": True,
        "clean_question": True,
        "clean_options": True,
    }
    await update.message.reply_text(HELP_TEXT)
    await update.message.reply_text("✏️ ابتدا متن کوییز خود را ارسال کنید.")
# help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)
    await update.message.reply_text("برای شروع، /start را بزنید.")

# تنظیم anonymous پیش‌فرض
async def set_anonymous(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🙈 بله، anonymous باشد", callback_data="default_anonymous_yes")],
        [InlineKeyboardButton("👁️‍🗨️ خیر، public باشد", callback_data="default_anonymous_no")]
    ]
    await update.message.reply_text("🔧 حالت پیش‌فرض anonymous بودن کوییز را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))

def clean_options(text):
    # اول عبارت Choices: یا Options: رو حذف کن، حتی اگر وسط جمله باشه
    text = re.sub(r'(?i)(Choices|Options):', '', text)

    lines = text.strip().splitlines()
    cleaned_options = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # اگر خطی با کاما جدا شده بود (چند گزینه تو یه خط)، تکه تکه کن
        parts = [p.strip() for p in line.split(',')]
        for part in parts:
            # عدد و نقطه‌ی اول هر گزینه رو حذف کن
            part = re.sub(r'^\d+[\.-]?\s*', '', part)
            if part:
                cleaned_options.append(part)

    return cleaned_options
    
# دریافت پیام‌های کاربر
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_states:
        user_states[user_id] = {}

    state = user_states[user_id]

    if state.get("step") == "waiting_for_question":
        # پردازش سوال
        answer = extract_answer(text)
        if not answer:
            await update.message.reply_text("❗️ لطفاً متنی بفرستید که (Answer: ...) داشته باشد.")
            return

        if state.get("clean_question", True):
            question_text, explanation = clean_question_and_explanation(text)
        else:
            question_text = text
            explanation = "No Title"

        state.update({
            "question_text": question_text,
            "answer": answer,
            "explanation": explanation,
            "step": "waiting_for_options"
        })
        await update.message.reply_text("✅ حالا گزینه‌ها را با کاما جداگانه ارسال کنید.")

    elif state.get("step") == "waiting_for_options":
        # پردازش گزینه‌ها
        if state.get("clean_options", True):
            options = clean_options(text)
        else:
            options = [opt.strip() for opt in text.split(',') if opt.strip()]

        if len(options) != 4:
            await update.message.reply_text("❗️ لطفاً دقیقاً ۴ گزینه با کاما بفرستید.")
            return
        if state["answer"].lower() not in [opt.lower() for opt in options]:
            await update.message.reply_text(f"❗️ جواب صحیح ({state['answer']}) در بین گزینه‌ها نیست.")
            return

        correct_id = [opt.lower() for opt in options].index(state["answer"].lower())

        is_anon = state.get("default_anonymous", True)

        state.update({
            "options": options,
            "correct_option_id": correct_id,
            "is_anonymous": is_anon,
            "step": "preview"
        })
        await show_preview(update, context, user_id)

    elif state.get("step") == "preview_editing":
        edit_field = state.get("edit_field")
        if edit_field == "question":
            if state.get("clean_question", True):
                question_text, explanation = clean_question_and_explanation(text)
            else:
                question_text = text
                explanation = "No Title"
            state.update({
                "question_text": question_text,
                "explanation": explanation
            })
        elif edit_field == "options":
            if state.get("clean_options", True):
                options = clean_options(text)
            else:
                options = [opt.strip() for opt in text.split(',') if opt.strip()]
            if len(options) != 4:
                await update.message.reply_text("❗️ لطفاً دقیقاً ۴ گزینه بفرستید.")
                return
            if state["answer"].lower() not in [opt.lower() for opt in options]:
                await update.message.reply_text(f"❗️ جواب صحیح ({state['answer']}) در بین گزینه‌ها نیست.")
                return
            correct_id = [opt.lower() for opt in options].index(state["answer"].lower())
            state["options"] = options
            state["correct_option_id"] = correct_id
        elif edit_field == "answer":
            answer = text.strip()
            if answer.lower() not in [opt.lower() for opt in state["options"]]:
                await update.message.reply_text(f"❗️ جواب صحیح ({answer}) در بین گزینه‌ها نیست.")
                return
            correct_id = [opt.lower() for opt in state["options"]].index(answer.lower())
            state["answer"] = answer
            state["correct_option_id"] = correct_id
        elif edit_field == "explanation":
            state["explanation"] = text

        state["step"] = "preview"
        await show_preview(update, context, user_id)

# دکمه ها
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id)

    if not state:
        return

    data = query.data

    if data == "confirm":
        await send_quiz(query, context, user_id)
        user_states.pop(user_id, None)

    elif data.startswith("edit_"):
        field = data.split("_", 1)[1]
        state["edit_field"] = field
        state["step"] = "preview_editing"

        if field == "question":
            await query.message.reply_text(f"✏️ سوال فعلی:\n{state['question_text']}\n\nلطفاً سوال اصلاح شده را ارسال کنید.")
        elif field == "options":
            await query.message.reply_text(f"✏️ گزینه‌های فعلی:\n{', '.join(state['options'])}\n\nلطفاً گزینه‌های اصلاح شده را با کاما جدا کنید و بفرستید.")
        elif field == "answer":
            await query.message.reply_text(f"✏️ جواب صحیح فعلی:\n{state['answer']}\n\nلطفاً جواب صحیح اصلاح شده را وارد کنید.")
        elif field == "explanation":
            await query.message.reply_text(f"✏️ توضیحات فعلی:\n{state['explanation']}\n\nلطفاً توضیحات اصلاح شده را وارد کنید.")

    elif data == "toggle_anonymous":
        state["is_anonymous"] = not state["is_anonymous"]
        await show_preview(query, context, user_id)

    elif data == "toggle_clean_question":
        state["clean_question"] = not state.get("clean_question", True)
        await show_preview(query, context, user_id)

    elif data == "toggle_clean_options":
        state["clean_options"] = not state.get("clean_options", True)
        await show_preview(query, context, user_id)

    elif data == "default_anonymous_yes":
        state["default_anonymous"] = True
        await query.message.reply_text("✅ حالت پیش‌فرض روی public تنظیم شد.")
    elif data == "default_anonymous_no":
        state["default_anonymous"] = False
        await query.message.reply_text("✅ حالت پیش‌فرض روی anonymous تنظیم شد.")
# پیش‌نمایش
async def show_preview(update_or_query, context: ContextTypes.DEFAULT_TYPE, user_id):
    state = user_states[user_id]
    text = f"""📋 پیش‌نمایش کوییز:

📝 سوال:
{state['question_text']}

🧠 گزینه‌ها:
1- {state['options'][0]}
2- {state['options'][1]}
3- {state['options'][2]}
4- {state['options'][3]}

✅ جواب درست: {state['answer']}

📚 توضیحات: {state['explanation']}

🙈 Anonymous: {"بله" if state['is_anonymous'] else "خیر"}

🧹 Clean Question: {"✅ روشن" if state.get('clean_question', True) else "❌ خاموش"}
🧹 Clean Options: {"✅ روشن" if state.get('clean_options', True) else "❌ خاموش"}
"""
    buttons = [
        [InlineKeyboardButton("✅ تایید نهایی", callback_data="confirm")],
        [InlineKeyboardButton("✏️ ویرایش سوال", callback_data="edit_question")],
        [InlineKeyboardButton("✏️ ویرایش گزینه‌ها", callback_data="edit_options")],
        [InlineKeyboardButton("✏️ ویرایش جواب صحیح", callback_data="edit_answer")],
        [InlineKeyboardButton("✏️ ویرایش توضیحات", callback_data="edit_explanation")],
        [
            InlineKeyboardButton("🧹 Clean Question", callback_data="toggle_clean_question"),
            InlineKeyboardButton("🧹 Clean Options", callback_data="toggle_clean_options")
        ],
        [InlineKeyboardButton("🙈 تغییر Anonymous", callback_data="toggle_anonymous")]
    ]
    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update_or_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
# ارسال کوییز
async def send_quiz(query, context: ContextTypes.DEFAULT_TYPE, user_id):
    state = user_states[user_id]
    await context.bot.send_poll(
        chat_id=user_id,
        question=state["question_text"],
        options=state["options"],
        type=Poll.QUIZ,
        correct_option_id=state["correct_option_id"],
        is_anonymous=state["is_anonymous"],
        explanation=state["explanation"]
    )

# ابزار کمکی
def extract_answer(text):
    match = re.search(r'\(Answer:\s*(.*?)\)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def clean_question_and_explanation(text):
    lines = text.strip().splitlines()
    title = ""
    body_lines = []

    for i, line in enumerate(lines):
        if i == 0 and re.match(r'^[A-Za-z]+ #\d+', line):
            title = line.strip()
            continue
        if i == 1 and re.search(r'(Easy|Medium|Hard)', line, re.IGNORECASE):
            continue
        body_lines.append(line)

    question_body = "\n".join(body_lines)
    question_body = re.sub(r'\(Answer:.*?\)', '____________', question_body)
    return question_body.strip(), title or "No Title"

# ساخت اپ
app = ApplicationBuilder().token(TOKEN).build()

# اضافه کردن هندلرها
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("setanonymous", set_anonymous))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.add_handler(CallbackQueryHandler(handle_buttons))

print("🤖 Bot is running...")
app.run_polling()