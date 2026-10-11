"""
Ovoz -> Matn (Windows)
Ctrl+Shift tugmalarini USHLAB TURING -> gapiring -> qo'yib yuboring.
Matn avtomatik ravishda faol turgan oynaga (Word, Telegram, brauzer...) yoziladi.

Ovoz tanish: Google nutq tanish xizmati (internet kerak).
"""
import os
import sys
import time
import traceback

# --- Log fayl: %LOCALAPPDATA%\OvozMatn\log.txt ---
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "OvozMatn")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "log.txt")
try:
    _log = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log
except Exception:
    pass


def log(msg):
    try:
        print(time.strftime("%H:%M:%S"), msg, flush=True)
    except Exception:
        pass


def fatal(msg):
    log(msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, f"{msg}\n\nLog fayl:\n{LOG_PATH}", "OvozMatn xatosi", 0x10
        )
    except Exception:
        pass


import io
import json
import threading
import wave

try:
    import requests
    import keyboard
    import numpy as np
    import pyperclip
    import pystray
    import sounddevice as sd
    import speech_recognition as sr
    from PIL import Image, ImageDraw
except Exception:
    fatal("Kutubxona yuklanmadi:\n" + traceback.format_exc()[-600:])
    sys.exit(1)

# ---------------- SOZLAMALAR ----------------
# "uz-UZ" o'zbek, "ru-RU" rus, "en-US" ingliz
LANGUAGE = "uz-UZ"
SAMPLE_RATE = 16000
MIN_SECONDS = 0.4        # bundan qisqa yozuv e'tiborga olinmaydi
# --------------------------------------------

CONFIG_PATH = os.path.join(LOG_DIR, "sozlamalar.json")
DEFAULT_CONFIG = {
    "elevenlabs_api_key": "",
    "elevenlabs_til": "uzb",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        log("Sozlamalarni o'qib bo'lmadi:\n" + traceback.format_exc())
    return cfg


def open_config():
    load_config()
    try:
        os.startfile(CONFIG_PATH)
    except Exception:
        log("Sozlamalar faylini ochib bo'lmadi")


def pcm_to_wav(pcm_bytes):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm_bytes)
    return buf.getvalue()


def elevenlabs_text(pcm_bytes, api_key, lang):
    r = requests.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": api_key},
        files={"file": ("audio.wav", pcm_to_wav(pcm_bytes), "audio/wav")},
        data={"model_id": "scribe_v2", "language_code": lang, "tag_audio_events": "false"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    return r.json().get("text", "").strip()


APP_NAME = "OvozMatn"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


def set_autostart(enable):
    import winreg
    frozen = getattr(sys, "frozen", False)
    path = sys.executable if frozen else os.path.abspath(__file__)
    cmd = f'"{path}"' if frozen else f'"{sys.executable}" "{path}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


def make_icon(color):
    img = Image.new("RGB", (64, 64), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=color)
    return img


ICON_BUSY = make_icon("orange")
ICON_IDLE = make_icon("green")
ICON_REC = make_icon("red")
READY = "Tayyor: Ctrl+Shift ni ushlab gapiring"


class VoiceTyper:
    def __init__(self):
        self.recording = False
        self.frames = []
        self.stream = None
        self.started_at = 0.0
        self.lock = threading.Lock()
        self.recognizer = sr.Recognizer()
        self.tray = pystray.Icon(
            "ovoz_matn",
            ICON_IDLE,
            READY,
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Windows bilan birga ochilsin",
                    self.toggle_autostart,
                    checked=lambda item: autostart_enabled(),
                ),
                pystray.MenuItem("Sozlamalar (ElevenLabs kalit)", lambda icon, item: open_config()),
                pystray.MenuItem("Chiqish", self.quit),
            ),
        )

    def set_state(self, icon, title):
        self.tray.icon = icon
        self.tray.title = title

    # ---------- yozib olish ----------
    def _audio_cb(self, indata, frames, time_info, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start_recording(self):
        with self.lock:
            if self.recording:
                return
            self.frames = []
            self.recording = True
            self.started_at = time.time()
            try:
                self.stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._audio_cb
                )
                self.stream.start()
            except Exception:
                self.recording = False
                log("Mikrofon xatosi:\n" + traceback.format_exc())
                self.set_state(ICON_IDLE, "Mikrofon topilmadi")
                return
            self.set_state(ICON_REC, "Yozilmoqda...")

    def cancel_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self._close_stream()
            self.set_state(ICON_IDLE, READY)

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self._close_stream()
            frames = self.frames
            duration = time.time() - self.started_at
        if duration < MIN_SECONDS or not frames:
            self.set_state(ICON_IDLE, READY)
            return
        audio = np.concatenate(frames).flatten()
        threading.Thread(target=self.transcribe_and_type, args=(audio,), daemon=True).start()

    def _close_stream(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    # ---------- matnga o'girish va yozish ----------
    def transcribe_and_type(self, audio):
        self.set_state(ICON_BUSY, "Matnga o'girilmoqda...")
        try:
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            text = ""
            cfg = load_config()
            key = (cfg.get("elevenlabs_api_key") or "").strip()
            done = False
            if key:
                try:
                    text = elevenlabs_text(pcm, key, cfg.get("elevenlabs_til") or "uzb")
                    done = True
                except Exception:
                    log("ElevenLabs xatosi, Google ishlatiladi:\n" + traceback.format_exc())
                    try:
                        self.tray.notify("ElevenLabs ishlamadi (kalit/internet?). Google ishlatildi.", "OvozMatn")
                    except Exception:
                        pass
            if not done:
                data = sr.AudioData(pcm, SAMPLE_RATE, 2)
                text = self.recognizer.recognize_google(data, language=LANGUAGE).strip()
            if text:
                text = text[0].upper() + text[1:]
                self.paste(text + " ")
        except sr.UnknownValueError:
            log("Gap tushunilmadi")
        except sr.RequestError as e:
            log(f"Internet/Google xatosi: {e}")
            self.set_state(ICON_IDLE, "Internet yo'q yoki Google javob bermadi")
            try:
                self.tray.notify("Internet yo'q yoki Google javob bermadi.", "OvozMatn")
            except Exception:
                pass
            return
        except Exception:
            log("Xato:\n" + traceback.format_exc())
        self.set_state(ICON_IDLE, READY)

    def paste(self, text):
        try:
            old = pyperclip.paste()
        except Exception:
            old = None
        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        time.sleep(0.2)
        if old is not None:
            pyperclip.copy(old)

    # ---------- klaviatura ----------
    def on_key(self, e):
        name = (e.name or "").lower()
        is_mod = "ctrl" in name or "shift" in name
        if e.event_type == "down":
            if self.recording and not is_mod:
                self.cancel_recording()
            elif not self.recording and keyboard.is_pressed("ctrl") and keyboard.is_pressed("shift"):
                self.start_recording()
        elif e.event_type == "up" and is_mod and self.recording:
            self.stop_recording()

    def toggle_autostart(self, icon, item):
        try:
            set_autostart(not autostart_enabled())
        except Exception:
            log("Avtoyuklash xatosi:\n" + traceback.format_exc())

    def quit(self, *_):
        keyboard.unhook_all()
        self.tray.stop()

    def _setup(self, icon):
        icon.visible = True
        try:
            icon.notify("Tayyor! Ctrl+Shift ni ushlab gapiring.", "OvozMatn")
        except Exception:
            pass

    def run(self):
        log("Ilova ishga tushdi")
        keyboard.hook(self.on_key)
        self.tray.run(setup=self._setup)


if __name__ == "__main__":
    try:
        VoiceTyper().run()
    except Exception:
        fatal("Ilova to'xtadi:\n" + traceback.format_exc()[-600:])
