# Рекламные ролики ресторана (NASHE MESTO) — отдельный пресет

Не связан с серией «Люди нашего места» (`scripts/reel/`) — общая только база (Remotion, ffmpeg, шрифты Inter).

Формат: Instagram Reels + Stories, 9:16, 1080×1920, H.264/AAC, 30 fps, ~13–15 с.
Принцип: **статичная брендовая рамка** (`src/promo/PromoAd.tsx`, композиция `Promo`)
+ **живое видео в большом окне** (`scripts/promo/preset.py` → `WINDOW`).

## Новая акция
1. `bash scripts/promo/setup.sh` (один раз; шрифты Great Vibes / Caveat с кириллицей).
2. Посмотреть исходник целиком (лист кадров), выбрать 13–15 с.
3. Создать `promos/<id>/spec.py` по образцу `promos/devichnik_2609/spec.py`:
   `CLIPS` (фрагменты, скорость, ключи кадрирования в секундах исходника), `AUDIO`, `GRADE`, `FRAME` (тексты, цвета).
4. `python3 scripts/promo/build.py <id> <видео>` — нарезка, апскейл, плавный slow-mo, props.
   Поменялись только ключи кадрирования/тексты → `--no-media`.
5. `python3 scripts/promo/render.py <id> --stills 0,120,300` — контрольные кадры (номера кадров).
6. `python3 scripts/promo/render.py <id>` → `out/<id>_master.mp4`, `out/<id>_preview.mp4`, `out/<id>_sheet.jpg`.

Ключ кадрирования `(t, fx, fy, zoom)`: точка исходника (0..1) ставится в центр окна,
`zoom 1` — ширина исходника = ширина окна; края не оголяются (clamp).
