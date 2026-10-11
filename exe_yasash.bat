@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/4] Muhit tayyorlanmoqda...
python -m venv venv || goto :err
call venv\Scripts\activate
pip install -r requirements.txt pyinstaller huggingface_hub || goto :err
echo [2/4] Ovoz modeli yuklanmoqda (~500 MB)...
python yuklab_model.py || goto :err
echo [3/4] EXE yasalmoqda (bir necha daqiqa)...
pyinstaller --noconfirm --onefile --noconsole --name OvozMatn ^
  --add-data "model;model" ^
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all av ^
  --collect-all onnxruntime --collect-all sounddevice --collect-all _sounddevice_data ^
  ovoz_matn.py || goto :err
echo [4/4] TAYYOR: dist\OvozMatn.exe
pause
exit /b 0
:err
echo XATO yuz berdi. Yuqoridagi xabarni o'qing.
pause
exit /b 1
