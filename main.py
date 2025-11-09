import os
from ai_providers.rate_limited_ai_wrapper import (
    PROVIDER_FROM_ENV,
    ask_gpt_multi_message,
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from PIL import Image
import io
from utils.images import openai_requirements_image_resize, encode_image_to_data_url
from config import MAX_IMAGES_PER_MESSAGE

"""
Note:
Currently, it's limiting the number of messages from the user by keeping only the last MAX_MESSAGES_NUM messages.
It was selected as the most user-friendly option, even if it's costlier.
Some possible alternative strategies:
- maybe detect a change of topic and reset the chat
- add the reset chat button
- reset after a night
--- save the ts of the latest msg
--- if the latest msg by the user was yesterday, and more than 5h elapsed, then reset

"""


PROVIDER_INDICATORS = {  # the indicators are case-insensitive
    "openai": ["o:", "о:"],  # Russian and Latin
    "anthropic": ["a:", "а:", "c:", "с:"],  # Russian and Latin
}  # if the user message starts with any of the indicators, use the provider

SELECTED_PROVIDER = None

# Retrieve token from environment variable
TOKEN = os.getenv("TELEGRAM_LLM_BOT_TOKEN")
if not TOKEN:
    raise ValueError(
        "No token provided. Set the TELEGRAM_BOT_TOKEN environment variable."
    )


allowed_ids_str = os.getenv("ALLOWED_USER_IDS")

# Convert the string of comma-separated integers to a list of integers
ALLOWED_USER_IDS = [int(user_id.strip()) for user_id in allowed_ids_str.split(",")]

SYSTEM_MSG = """
Sie sind ein hilfreicher Assistent.
Dies ist ein Instant-Messaging-Chat, also halten Sie Ihre Antworten kurz und präzise. Geben Sie aber eine ausführliche Antwort, wenn Sie dem Nutzer damit am besten helfen können. 
Zum Beispiel, wenn der Benutzer eine einfache Frage gestellt hat, ist eine kurze Antwort vorzuziehen. Wenn der Benutzer jedoch eine komplizierte E-Mail schreiben möchte, schreiben Sie sie vollständig. 
Oft ist es hilfreich, dem Benutzer Fragen zu stellen, um ihm einen maßgeschneiderten Rat zu geben oder das Thema zu vertiefen. 
Aber der Benutzer tippt nicht gerne, also versuchen Sie, unnötige Fragen zu vermeiden. Und es ist besser, eine Frage zu stellen, NACHDEM Sie dem Nutzer bereits geholfen haben, als eine Option zum Weitermachen. 
Verwenden Sie die Sprache des Benutzers, es sei denn, eine Aufgabe erfordert etwas anderes.
"""

MAX_MESSAGES_NUM = 100
MAX_IMAGE_SIZE_MB = 30

MESSAGES_BY_USER = {}

def is_file_too_large(file_size_bytes: int | None, max_size_mb: int) -> bool:
    try:
        return isinstance(file_size_bytes, int) and file_size_bytes > max_size_mb * 1024 * 1024
    except Exception:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("In the start function...")

    user = update.effective_user

    if True:
        keyboard = [[InlineKeyboardButton("Start", callback_data="start_game")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome_message = f"Hello {user.first_name}, ich bin dein hilfreicher Assistent! Clicke 'Start'"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_message,
            reply_markup=reply_markup,
        )


async def start_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "Wie kann ich dir helfen?"
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.edit_message_text(text)


async def start_game_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    await start_new_game(update, context)


def update_provider_from_user_input(user_input):
    switch7 = False
    report = ""
    for provider, indicators in PROVIDER_INDICATORS.items():
        for indicator in indicators:
            if user_input.lower().startswith(indicator):
                global SELECTED_PROVIDER
                if provider != SELECTED_PROVIDER:
                    switch7 = True
                    if SELECTED_PROVIDER is None:
                        SELECTED_PROVIDER = PROVIDER_FROM_ENV
                    report = f"{SELECTED_PROVIDER} -> {provider}"
                    print(report)
                SELECTED_PROVIDER = provider
                return switch7, report
    return switch7, report


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("In the handle_message function...")
    user_id = update.effective_user.id

    if user_id in ALLOWED_USER_IDS:
        user_input = update.message.text
        user_input = user_input.strip()
        print(f"User input: {user_input}")

        # get the provider from the user input
        switch7, report = update_provider_from_user_input(user_input)
        if switch7:
            await update.message.reply_text(report)

        # remove the provider indicator from the start of the message, but only from the start
        for provider, indicators in PROVIDER_INDICATORS.items():
            for indicator in indicators:
                if user_input.lower().startswith(indicator):
                    user_input = user_input[len(indicator) :].strip()

        if user_id in MESSAGES_BY_USER:
            MESSAGES_BY_USER[user_id].append(
                {"role": "user", "content": user_input},
            )

        else:  # the user posted his first message
            MESSAGES_BY_USER[user_id] = [
                {"role": "system", "content": SYSTEM_MSG},
                {"role": "user", "content": user_input},
            ]

        # answer = ask_gpt_single_message(user_input, SYSTEM_MSG, max_length=500)
        answer = ask_gpt_multi_message(
            MESSAGES_BY_USER[user_id],
            max_length=500,
            user_defined_provider=SELECTED_PROVIDER,
        )

        MESSAGES_BY_USER[user_id].append(
            {"role": "assistant", "content": answer},
        )

        # remove the oldest messages. We keep only the last MAX_MESSAGES_NUM messages
        if len(MESSAGES_BY_USER[user_id]) > MAX_MESSAGES_NUM:
            MESSAGES_BY_USER[user_id] = MESSAGES_BY_USER[user_id][-MAX_MESSAGES_NUM:]
            # attach the system message to the beginning
            MESSAGES_BY_USER[user_id].insert(
                0, {"role": "system", "content": SYSTEM_MSG}
            )
        print(f"Messages length: {len(MESSAGES_BY_USER[user_id])}")

        await update.message.reply_text(answer)
    else:
        answer = f"Eh? Du hast doch keine Berechtigung. Deine user_id ist {user_id}."
        print(answer)
        await update.message.reply_text(answer)


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("In the handle_photo_message function...")
    user_id = update.effective_user.id

    if user_id in ALLOWED_USER_IDS:
        try:
            # Reject media groups (albums) when only 1 image per message is allowed
            if update.message.media_group_id is not None and MAX_IMAGES_PER_MESSAGE == 1:
                msg = f"Too many images in one message (album). Allowed: {MAX_IMAGES_PER_MESSAGE}."
                print(msg)
                await update.message.reply_text(msg)
                return
            photos = update.message.photo
            if not photos:
                await update.message.reply_text("got an image")
                return
            # Debug: Telegram PhotoSize reported size
            reported_photo_size = getattr(photos[-1], "file_size", None)
            print(f"DEBUG(photo): PhotoSize.file_size={reported_photo_size} bytes")
            # Pre-check size (Telegram photo sizes are server-compressed, so we also check post-download size below)
            if is_file_too_large(getattr(photos[-1], "file_size", None), MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return

            file_id = photos[-1].file_id
            file = await context.bot.get_file(file_id)
            # Debug: Telegram File reported size
            reported_file_size = getattr(file, "file_size", None)
            print(f"DEBUG(photo): File.file_size={reported_file_size} bytes")
            if is_file_too_large(getattr(file, "file_size", None), MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return

            bio = io.BytesIO()
            await file.download_to_memory(out=bio)
            # Post-download size check (definitive)
            bytes_len = bio.getbuffer().nbytes
            print(f"DEBUG(photo): downloaded bytes_len={bytes_len} bytes (~{bytes_len/1024/1024:.2f} MB)")
            if is_file_too_large(bytes_len, MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return
            bio.seek(0)
            img = Image.open(bio)
            w, h = img.size
            print(f"DEBUG(photo): original downloaded image size={w}x{h}")

            # Resize to OpenAI requirements and encode
            img_resized = openai_requirements_image_resize(img)
            rw, rh = img_resized.size
            print(f"DEBUG(photo): resized image size={rw}x{rh}")
            data_url = encode_image_to_data_url(img_resized, fmt="JPEG")

            image_content = {"type": "image_url", "image_url": {"url": data_url}}
            content_parts = []
            if isinstance(update.message.caption, str) and len(update.message.caption.strip()) > 0:
                print(f"DEBUG(photo): caption_len={len(update.message.caption.strip())}")
                content_parts.append({"type": "text", "text": update.message.caption.strip()})
            content_parts.append(image_content)

            if user_id in MESSAGES_BY_USER:
                MESSAGES_BY_USER[user_id].append({"role": "user", "content": content_parts})
            else:
                MESSAGES_BY_USER[user_id] = [
                    {"role": "system", "content": SYSTEM_MSG},
                    {"role": "user", "content": content_parts},
                ]

            answer = ask_gpt_multi_message(
                MESSAGES_BY_USER[user_id],
                max_length=500,
                user_defined_provider=SELECTED_PROVIDER,
            )

            MESSAGES_BY_USER[user_id].append({"role": "assistant", "content": answer})
            if len(MESSAGES_BY_USER[user_id]) > MAX_MESSAGES_NUM:
                MESSAGES_BY_USER[user_id] = MESSAGES_BY_USER[user_id][-MAX_MESSAGES_NUM:]
                MESSAGES_BY_USER[user_id].insert(0, {"role": "system", "content": SYSTEM_MSG})

            await update.message.reply_text(answer)
        except Exception as e:
            print(f"Error handling photo: {e}")
            await update.message.reply_text("Sorry, failed to process the image.")
    else:
        answer = f"Eh? Du hast doch keine Berechtigung. Deine user_id ist {user_id}."
        print(answer)
        await update.message.reply_text(answer)

async def handle_image_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("In the handle_image_document_message function...")
    user_id = update.effective_user.id

    if user_id in ALLOWED_USER_IDS:
        try:
            # Reject media groups (albums) for documents as well when limit is 1
            if update.message.media_group_id is not None and MAX_IMAGES_PER_MESSAGE == 1:
                msg = f"Too many images in one message (album). Allowed: {MAX_IMAGES_PER_MESSAGE}."
                print(msg)
                await update.message.reply_text(msg)
                return
            doc = update.message.document
            if not doc or not isinstance(doc.mime_type, str) or not doc.mime_type.startswith("image/"):
                return
            print(f"DEBUG(doc): name={getattr(doc, 'file_name', None)}, mime={doc.mime_type}, file_size={getattr(doc, 'file_size', None)} bytes")
            # Pre-check size on the document (original size preserved for documents)
            if is_file_too_large(getattr(doc, "file_size", None), MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return

            file = await context.bot.get_file(doc.file_id)
            print(f"DEBUG(doc): File.file_size={getattr(file, 'file_size', None)} bytes")
            if is_file_too_large(getattr(file, "file_size", None), MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return

            bio = io.BytesIO()
            await file.download_to_memory(out=bio)
            bytes_len = bio.getbuffer().nbytes
            print(f"DEBUG(doc): downloaded bytes_len={bytes_len} bytes (~{bytes_len/1024/1024:.2f} MB)")
            if is_file_too_large(bytes_len, MAX_IMAGE_SIZE_MB):
                msg = f"File size exceeds the maximum limit of {MAX_IMAGE_SIZE_MB}MB. Please send a smaller image."
                print(msg)
                await update.message.reply_text(msg)
                return
            bio.seek(0)
            img = Image.open(bio)
            w, h = img.size
            print(f"DEBUG(doc): original downloaded image size={w}x{h}")

            img_resized = openai_requirements_image_resize(img)
            rw, rh = img_resized.size
            print(f"DEBUG(doc): resized image size={rw}x{rh}")
            # Preserve format when reasonable, default to JPEG
            fmt = "JPEG"
            if isinstance(doc.mime_type, str) and "png" in doc.mime_type:
                fmt = "PNG"
            data_url = encode_image_to_data_url(img_resized, fmt=fmt)

            image_content = {"type": "image_url", "image_url": {"url": data_url}}
            content_parts = []
            if isinstance(update.message.caption, str) and len(update.message.caption.strip()) > 0:
                print(f"DEBUG(doc): caption_len={len(update.message.caption.strip())}")
                content_parts.append({"type": "text", "text": update.message.caption.strip()})
            content_parts.append(image_content)

            if user_id in MESSAGES_BY_USER:
                MESSAGES_BY_USER[user_id].append({"role": "user", "content": content_parts})
            else:
                MESSAGES_BY_USER[user_id] = [
                    {"role": "system", "content": SYSTEM_MSG},
                    {"role": "user", "content": content_parts},
                ]

            answer = ask_gpt_multi_message(
                MESSAGES_BY_USER[user_id],
                max_length=500,
                user_defined_provider=SELECTED_PROVIDER,
            )

            MESSAGES_BY_USER[user_id].append({"role": "assistant", "content": answer})
            if len(MESSAGES_BY_USER[user_id]) > MAX_MESSAGES_NUM:
                MESSAGES_BY_USER[user_id] = MESSAGES_BY_USER[user_id][-MAX_MESSAGES_NUM:]
                MESSAGES_BY_USER[user_id].insert(0, {"role": "system", "content": SYSTEM_MSG})

            await update.message.reply_text(answer)
        except Exception as e:
            print(f"Error handling image document: {e}")
            await update.message.reply_text("Sorry, failed to process the image document.")
    else:
        answer = f"Eh? Du hast doch keine Berechtigung. Deine user_id ist {user_id}."
        print(answer)
        await update.message.reply_text(answer)


async def restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = f"Keine Berechtigung für user_id {user_id}."
    print(text)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Keine Berechtigung für user_id {user_id}.",
    )


def main():
    print("In the main function...")
    app = Application.builder().token(TOKEN).build()

    """Restrict fhs bot to the specified user_id.
    NOTE: this should be always the first handler, to prevent the bot from responding to unauthorized users.
    """
    restrict_handler = MessageHandler(~filters.User(ALLOWED_USER_IDS), restrict)
    app.add_handler(restrict_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_game_callback, pattern="^start_game$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_image_document_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
