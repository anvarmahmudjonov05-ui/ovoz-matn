OVOZ -> MATN (Windows) - BITTA EXE

EXE NI YASASH (faqat bir marta, 2 yo'l):

A) O'Z KOMPYUTERINGIZDA (Python 3.10+ kerak, "Add Python to PATH" belgilang)
   exe_yasash.bat ni ikki marta bosing -> dist\OvozMatn.exe tayyor bo'ladi.

B) PYTHON O'RNATMASDAN (GitHub orqali)
   1) github.com da bepul akkaunt oching, yangi repository yarating.
   2) Shu papkadagi hamma fayllarni (.github papkasi bilan) repository ga yuklang.
   3) Actions -> "EXE yasash" -> Run workflow.
   4) 5-10 daqiqadan so'ng "OvozMatn-exe" artifactini yuklab oling.

ISHLATISH
- OvozMatn.exe ni ikki marta bosing (o'rnatish va internet kerak emas).
- Tray da doira: to'q sariq = yuklanmoqda, yashil = tayyor, qizil = yozilmoqda.
- Kursorni yozmoqchi bo'lgan joyga qo'ying, Ctrl+Shift ni USHLAB TURIB gapiring, qo'yib yuboring.
- Tray dagi doira ustida o'ng tugma: "Windows bilan birga ochilsin" / "Chiqish".

ESLATMA
- EXE hajmi ~600 MB atrofida; har ochilganda 10-30 soniya yuklanishi mumkin.
- Windows Defender birinchi safar ogohlantirsa: "More info" -> "Run anyway".
- Administrator sifatida ochilgan dasturlarga yozish uchun OvozMatn.exe ni ham administrator sifatida ishga tushiring.
