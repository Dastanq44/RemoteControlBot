import os
import re
import subprocess
import datetime
import tempfile
import pyautogui
import ctypes
import psutil
import time
import pyperclip
import pytesseract
from PIL import Image
from PIL import ImageOps


from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import InputFile
from faster_whisper import WhisperModel

# --- Prevent sleep (while program is running) ---
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

# --- Bot config ---
BOT_TOKEN = "" #ADD TELEGRAM BOT TOKEN HERE
AUTHORIZED_USER_ID = #GET USER ID FROM TELEGRAM GET USER ID BOT

# --- Program paths --- 
PROGRAMS = {
    "discord": r"C:\Users\Дастан\AppData\Local\Discord\Update.exe --processStart Discord.exe", #Personalized for me
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "yandex": r"C:\Users\Дастан\Desktop\Yandex.lnk",
    "steam": r"C:\Users\Public\Desktop\Steam.lnk"
}

# --- Initialize Whisper model ---
model = WhisperModel("medium", device="cpu") #CAN CHANGE TO SMALL/LARGE DEPENDING ON YOUR PC OR WANTED SPEED

# --- Cursor IDE helpers ---
def cursor_focus():
    """Click to hide tabs, then click Cursor icon to open IDE"""
    try:
        # Close tabs (bottom-right corner) 
        pyautogui.click(2552, 1563)  #CHANGE TO THE COORDINATES OF BOTTOM-RIGTH CORNER ON YOUR SCREEN
        time.sleep(0.5)

        # Open Cursor IDE (taskbar icon) 
        pyautogui.click(212, 1577)   #CHANGE TO THE COORDINATES OF CURSOR ON YOUR TASKBAR 
        time.sleep(2)  # wait for Cursor to open
        return "✅ Cursor IDE focused."
    except Exception as e:
        return f"❌ Cursor focus failed: {e}"

def cursor_prompt_send(prompt: str):
    """Focus Cursor IDE and send a prompt to assistant box"""
    try:
        msg = cursor_focus()
        time.sleep(1)

        # Click assistant input box
        pyautogui.click(2200, 1340) #CHANGE TO THE COORDINATES OF INPUT BOX IN CURSOR
        time.sleep(0.5)

        # Type the prompt
        pyautogui.typewrite(prompt, interval=0.02)

        # Press Enter
        pyautogui.press("enter")
        return f"{msg}\n✅ Sent prompt to Cursor: {prompt}"
    except Exception as e:
        return f"❌ Cursor prompt failed: {e}"

def get_cursor_code():
    """Focus Cursor, copy code from editor, return as text"""
    try:
        cursor_focus()  # your existing function
        time.sleep(1)

        # Click on editor window (where code is) 
        pyautogui.click(1050, 330) #CHANGE TO THE COORDINATES OF CODESPACE IN CURSOR
        time.sleep(0.3)

        # Select all + copy
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)

        text = pyperclip.paste()
        return text if text else "⚠️ Clipboard empty, nothing copied."
    except Exception as e:
        return f"❌ Failed to copy code: {e}"


# --- Helpers ---
def ocr_text(image):
    """Preprocess image for better OCR"""
    gray = image.convert("L")  # grayscale
    gray = ImageOps.invert(gray)  # invert colors
    gray = gray.resize((gray.width * 2, gray.height * 2))  # upscale
    return pytesseract.image_to_string(gray, config="--psm 7").strip()

def wait_for_text_in_region(target_text, x1, y1, x2, y2, timeout=30, interval=1):
    """Wait until target_text appears in given screen region"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
        text_found = ocr_text(screenshot)
        if target_text.lower() in text_found.lower():
            return True
        time.sleep(interval)
    return False

def clean_text(text: str) -> str:
    """
    Clean decoded speech:
    - Remove punctuation/dots/extra signs
    - Convert multiple spaces to single
    """
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def transcribe_audio(file_path: str) -> str:
    """Run STT on an audio file and return cleaned text"""
    segments, info = model.transcribe(file_path, beam_size=5, language="en")
    text = " ".join([s.text.strip() for s in segments]).strip()
    return clean_text(text)

def execute_command(command: str) -> str:
    """Execute a text command like 'open discord'"""
    parts = command.lower().split(maxsplit=1)
    if not parts:
        return "⚠️ Empty command."

    verb = parts[0]
    target = parts[1] if len(parts) > 1 else None

    if verb == "open":
        if not target:
            return "⚠️ No program specified."
        if target not in PROGRAMS:
            return f"❌ Unknown program: {target}"
        try:
            subprocess.Popen(PROGRAMS[target], shell=True)
            return f"✅ Opened {target}"
        except Exception as e:
            return f"❌ Failed to open {target}: {e}"

    return f"⚠️ Unsupported command: {verb}"

def take_screenshot() -> str:
    """Takes a screenshot and saves it to a safe temp folder. Returns the filename."""
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(
        temp_dir, f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    )
    screenshot = pyautogui.screenshot()
    screenshot.save(filename, "JPEG")
    return filename

def get_system_info() -> str:
    """Return CPU, RAM, Disk, Battery usage summary"""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()

    info = [
        f"🖥 CPU: {cpu}%",
        f"💾 RAM: {memory.percent}%",
        f"📀 Disk: {disk.percent}%",
    ]
    if battery:
        info.append(f"🔋 Battery: {battery.percent}%{' (charging)' if battery.power_plugged else ''}")
    return "\n".join(info)

def get_top_processes(limit: int = 5, sort_by: str = "cpu") -> str:
    """Return top processes sorted by CPU or memory usage"""
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "memory":
        processes = sorted(processes, key=lambda p: p['memory_percent'], reverse=True)
    else:
        processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)

    lines = [f"Top {limit} processes by {sort_by.upper()}:\n"]
    for p in processes[:limit]:
        lines.append(
            f"PID {p['pid']:>5} | {p['name'][:20]:<20} "
            f"| CPU: {p['cpu_percent']:>4.1f}% | RAM: {p['memory_percent']:>4.1f}%"
        )
    return "\n".join(lines)

def steam_launch_dota(timeout: float = 25.0) -> str:
    """
    Open Steam, wait until 'Steam' appears in the header,
    then click Library → Dota 2 → Launch.
    """
    if "steam" not in PROGRAMS:
        return "❌ 'steam' is not configured in PROGRAMS."

    try:
        subprocess.Popen(PROGRAMS["steam"], shell=True)
    except Exception as e:
        return f"❌ Failed to launch Steam: {e}"

    # Wait for 'Steam' text in the header rectangle
    ok = wait_for_text_in_region("Steam", 57, 22, 127, 44, timeout=30, interval=1)
    if not ok:
        return "⚠️ Steam window text not detected within timeout."

    try: #CHANGE ALL THE COORDINATES BELOW
        time.sleep(1.0) 
        pyautogui.click(350, 80)   # Library Button coords
        time.sleep(0.8)
        pyautogui.click(90, 884)   # Dota 2 Page coords 
        time.sleep(2.0)
        pyautogui.click(580, 755)  # Dota 2 Launch coords
        return "✅ Steam detected. Launch sequence clicked: Library → Dota 2 → Launch."
    except Exception as e:
        return f"❌ Click sequence failed: {e}"




# --- Handlers ---
async def start(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    await update.message.reply_text("✅ Remote desktop bot ready.")

async def text_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    text = clean_text(update.message.text.strip())
    result = execute_command(text)
    await update.message.reply_text(f"📝 {text}\n\n{result}")

async def voice_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    file = await update.message.voice.get_file()
    path = f"voice_{update.message.message_id}.ogg"
    await file.download_to_drive(path)
    try:
        text = transcribe_audio(path)
        result = execute_command(text)
        await update.message.reply_text(f"🗣 {text}\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ STT Error: {e}")

async def screenshot_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    try:
        filename = take_screenshot()
        with open(filename, "rb") as f:
            await update.message.reply_photo(photo=InputFile(f))
        os.remove(filename)
    except Exception as e:
        await update.message.reply_text(f"❌ Screenshot error: {e}")

async def system_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    try:
        info = get_system_info()
        await update.message.reply_text(f"📊 System Info:\n\n{info}")
    except Exception as e:
        await update.message.reply_text(f"❌ System info error: {e}")

async def processes_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    try:
        text = get_top_processes(limit=5, sort_by="cpu")
        await update.message.reply_text(f"📊 {text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Processes error: {e}")

async def shutdown_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    try:
        await update.message.reply_text("⚠️ Shutting down the computer...")
        os.system("shutdown /s /t 0")  # shutdown immediately
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to shutdown: {e}")

# --- Cursor handlers ---
async def cursor_focus_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    result = cursor_focus()
    await update.message.reply_text(result)

async def cursor_prompt_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /cursor_prompt <your text>")
    prompt = " ".join(context.args)
    result = cursor_prompt_send(prompt)
    await update.message.reply_text(result)

async def cursor_code_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    
    text = get_cursor_code()
    
    # Telegram has ~4096 char limit per message
    if len(text) > 4000:
        with open("cursor_code.txt", "w", encoding="utf-8") as f:
            f.write(text)
        await update.message.reply_document(open("cursor_code.txt", "rb"))
        os.remove("cursor_code.txt")
    else:
        await update.message.reply_text(f"📄 Current Code:\n\n{text}")

async def steam_dota_handler(update, context):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return await update.message.reply_text("🚫 Unauthorized.")
    result = steam_launch_dota()
    await update.message.reply_text(result)



# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("screenshot", screenshot_handler))
    app.add_handler(CommandHandler("shutdown", shutdown_handler))
    app.add_handler(CommandHandler("system", system_handler))
    app.add_handler(CommandHandler("processes", processes_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(CommandHandler("cursor_focus", cursor_focus_handler))
    app.add_handler(CommandHandler("cursor_prompt", cursor_prompt_handler))
    app.add_handler(CommandHandler("cursor_code", cursor_code_handler))
    app.add_handler(CommandHandler("steam_dota", steam_dota_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

