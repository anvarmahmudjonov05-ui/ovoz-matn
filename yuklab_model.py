# Modelni "model" papkasiga yuklaydi (.exe ichiga joylash uchun)
from huggingface_hub import snapshot_download
snapshot_download(
    "Systran/faster-whisper-small",
    local_dir="model",
    allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"],
)
print("Model yuklandi")
