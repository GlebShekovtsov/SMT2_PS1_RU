# Shin Megami Tensei II (PS1) — Русский перевод [Alpha]

Фанатский перевод **Shin Megami Tensei II** для PlayStation 1 (SLPM-86924, Rev 1) на русский язык.  
Форк инструментария английского перевода [Roman215/smt2-psx-translation](https://github.com/Roman215/smt2-psx-translation).

> **Статус: ранняя альфа-версия (0.1.0-alpha)**  
> Переведены текстовые банки, меню, системные строки, основная графика интерфейсов и титры роликов, но **полное игровое прохождение и финальная литературная редактура ещё не выполнены**. Возможны опечатки, несогласованные падежи и непроверенные ветки в переговорах с демонами.

## Скачать патч

Готовый `.xdelta`-патч и инструкция находятся в разделе **[Releases](https://github.com/GlebShekovtsov/SMT2_PS1_RU/releases/tag/v0.1.0-alpha)**.

Репозиторий не содержит игровых данных и образов. Для применения патча или самостоятельной сборки требуется собственный образ **Shin Megami Tensei II (Japan) (Rev 1)** (`MODE2/2352`, `222 694 416` байт, SHA-256 `c86fed4d6cefd676fe9c707f099f3fcc97c64b0ee1220ac5b3a47f1a6e2f1235`).

## Самостоятельная сборка

### Требования

- **Python 3.10+**
- **Исходный образ** `Shin Megami Tensei II (Japan) (Rev 1)` в формате BIN (`MODE2/2352`, `222 694 416` байт).
- **FFmpeg** (в `PATH` или через `--ffmpeg`) и **psxavenc** (скачивается автоматически либо передаётся через `--psxavenc`) — нужны для пересборки видеороликов (опенинг и Game Over). Без них можно собрать образ флагом `--skip-movies`.
- **xdelta3** в `PATH` или Python-пакет `pyxdelta` (`pip install pyxdelta`) — только если нужен `.xdelta`-патч (флаг `--xdelta`).

### 1. Выгрузка и подготовка текста

Каталог `text/` с игровыми строками намеренно исключён из репозитория. Перед сборкой со своим переводом выгрузите текст из оригинального образа:

```bash
python ru/extract.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --out text
```

После этого:
1. Заполните переводы в `text/*.json` (поле `ru`) или влейте готовые партии перевода:
   ```bash
   python ru/merge.py --text text path/to/batch.json
   ```
2. Проверьте теги, ширины строк, лимиты слотов и выполните пробное сжатие банков:
   ```bash
   python ru/check.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --text text
   ```

> Если каталог `text/` не создан, `build_ru.py` соберёт образ с английским текстом на базе русского конвейера.

### 2. Сборка образа и патча

Полная сборка (`build/SMT2_RU.bin`, `build/SMT2_RU.cue` и `build/SMT2_RU.xdelta`):

```bash
python build_ru.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --text text --xdelta
```

Полезные параметры `build_ru.py`:
- `--output-dir DIR` — каталог для собранных файлов (по умолчанию `build`)
- `--skip-movies` — оставить японские видеоролики без перекодирования (не требует `ffmpeg` и `psxavenc`)
- `--stub-untranslated` — заменить непереведённые диалоги на `~` для тестовых сборок частичного перевода
- `--no-enhancements` — отключить геймплейные улучшения английского патча (включая Demon Compendium)

### Дополнительно

- [README_RU.md](README_RU.md) — подробное техническое устройство конвейера и инструментов
- [TRANSLATION_GUIDE.md](TRANSLATION_GUIDE.md) — правила и ограничения для переводчиков
- [CHANGELOG.md](CHANGELOG.md), [RELEASING.md](RELEASING.md)
