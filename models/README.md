# Модель распознавания речи — можно скачать вручную

Если скачивание внутри Docker идёт слишком долго, скачайте 5 файлов браузером (или менеджером загрузок с докачкой)
и положите их в папку `models/whisper-large-v3-turbo/` рядом с этим файлом:

| Файл | Размер |
|---|---|
| [model.bin](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/model.bin) | 1,6 ГБ |
| [config.json](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/config.json) | 2 КБ |
| [preprocessor_config.json](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/preprocessor_config.json) | 1 КБ |
| [tokenizer.json](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/tokenizer.json) | 2,7 МБ |
| [vocabulary.json](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo/resolve/main/vocabulary.json) | 1 МБ |

Если huggingface.co не открывается — те же ссылки через зеркало: замените `huggingface.co` на `hf-mirror.com`.

Ничего настраивать не нужно: агент сам найдёт `models/whisper-large-v3-turbo/model.bin`.
Без этой папки модель скачается один раз при первом видео.
