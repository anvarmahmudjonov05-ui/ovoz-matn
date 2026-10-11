"""
Ovoz -> Matn (Windows)
Ctrl+Shift tugmalarini USHLAB TURING -> gapiring -> qo'yib yuboring.
Matn avtomatik ravishda hozir faol turgan oynaga (Word, Telegram, brauzer...) yoziladi.

Ovoz tanish: faster-whisper (lokal, internetsiz, o'zbek tilini qo'llaydi).
"""
import os
import sys
import threading
import time

import keyboard
import numpy as np
import pyperclip
import pystray
import sounddevice as sd
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw

# ---------------- SOZLAMALAR ----------------
MODEL_SIZE = "small"     # tiny / base / small / medium / large-v3  (kattasi aniqroq, lekin sekinroq)
LANGUAGE = "uz"          # "uz" - o'zbek, "ru" - rus, "en" - ingliz, None - avtomatik aniqlash
SAMPLE_RATE = 16000
MIN_SECONDS = 0.4        # bundan qisqa yozuv e'tiborga olinmaydi
# --------------------------------------------


APP_NAME = "OvozMatn"


def resource_path(rel):
    """.exe ichiga joylangan fayllarga yo'l (PyInstaller) yoki oddiy papka."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


def set_autostart(enable):
    import winreg
    path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
    cmd = f'"{path}"' if getattr(sys, "frozen", False) else f'"{sys.executable}" "{path}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
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


ICON_LOADING = make_icon("orange")
ICON_IDLE = make_icon("green")
ICON_REC = make_icon("red")


class VoiceTyper:
    def __init__(self):
        self.model = None
        self.recording = False
        self.frames = []
        self.stream = None
        self.started_at = 0.0
        self.lock = threading.Lock()
        self.tray = pystray.Icon(
            "ovoz_matn",
            ICON_LOADING,
            "Model yuklanmoqda...",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Windows bilan birga ochilsin",
                    self.toggle_autostart,
                    checked=lambda item: autostart_enabled(),
                ),
                pystray.MenuItem("Chiqish", self.quit),
            ),
        )

    # ---------- holat ----------
    def set_state(self, icon, title):
        self.tray.icon = icon
        self.tray.title = title

    # ---------- model ----------
    def load_model(self):
        try:
            bundled = resource_path("model")
            source = bundled if os.path.isdir(bundled) else MODEL_SIZE
            self.model = WhisperModel(source, device="cpu", compute_type="int8")
            self.set_state(ICON_IDLE, "Tayyor: Ctrl+Shift ni ushlab gapiring")
        except Exception as e:
            self.set_state(ICON_LOADING, f"Xato: {e}")

    # ---------- yozib olish ----------
    def _audio_cb(self, indata, frames, time_info, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start_recording(self):
        with self.lock:
            if self.recording or self.model is None:
                return
            self.frames = []
            self.recording = True
            self.started_at = time.time()
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._audio_cb
            )
            self.stream.start()
            self.set_state(ICON_REC, "Yozilmoqda...")

    def cancel_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self._close_stream()
            self.set_state(ICON_IDLE, "Tayyor: Ctrl+Shift ni ushlab gapiring")

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self._close_stream()
            frames = self.frames
            duration = time.time() - self.started_at
        if duration < MIN_SECONDS or not frames:
            self.set_state(ICON_IDLE, "Tayyor: Ctrl+Shift ni ushlab gapiring")
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
        self.set_state(ICON_LOADING, "Matnga o'girilmoqda...")
        try:
            segments, _ = self.model.transcribe(
                audio, language=LANGUAGE, beam_size=5, vad_filter=True
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            if text:
                self.paste(text + " ")
        except Exception as e:
            print("Xato:", e)
        finally:
            self.set_state(ICON_IDLE, "Tayyor: Ctrl+Shift ni ushlab gapiring")

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
            pyperclip.copy(old)  # eski clipboard qaytariladi

    # ---------- klaviatura ----------
    def on_key(self, e):
        name = (e.name or "").lower()
        is_mod = "ctrl" in name or "shift" in name
        if e.event_type == "down":
            if self.recording and not is_mod:
                self.cancel_recording()  # boshqa tugma bosildi (masalan Ctrl+Shift+T)
            elif not self.recording and keyboard.is_pressed("ctrl") and keyboard.is_pressed("shift"):
                self.start_recording()
        elif e.event_type == "up" and is_mod and self.recording:
            self.stop_recording()

    def toggle_autostart(self, icon, item):
        try:
            set_autostart(not autostart_enabled())
        except Exception as e:
            print("Avtoyuklash xatosi:", e)

    def quit(self, *_):
        keyboard.unhook_all()
        self.tray.stop()

    def run(self):
        keyboard.hook(self.on_key)
        threading.Thread(target=self.load_model, daemon=True).start()
        self.tray.run()


if __name__ == "__main__":
    VoiceTyper().run()
