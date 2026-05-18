# Telegram Messages Resender

Production-like MVP Telegram-бота на Python 3.12 для перепаковки постов из канала-прослойки в целевой канал. Бот работает только через Telegram Bot API и aiogram 3: он не forward-ит сообщения, а создаёт новые публикации с тем же медиа и очищенным текстом.

## Сценарий

Есть два канала:

- канал-прослойка, куда вы вручную пересылаете посты;
- целевой канал, куда бот публикует новый очищенный пост.

Бот должен быть администратором в обоих каналах. При новом `channel_post` в канале-прослойке он выбирает маршрут из `config.yaml`, пытается скачать поддерживаемое медиа во временную папку, чистит текст, добавляет footer и публикует результат в целевой канал. Если публичный Bot API не даёт скачать большой файл, бот переиспользует исходный Telegram `file_id`.

## Pipeline

1. `handlers/channel_posts.py` принимает только `channel_post`.
2. `RouteResolver` сопоставляет `source_channel_id` с маршрутом.
3. `RuntimeDedupe` защищает текущий процесс от случайной повторной обработки одного `message_id`.
4. `MediaGroupAggregator` собирает альбомы по `media_group_id` и ждёт короткий timeout.
5. `TextCleaner` удаляет только строки со ссылками или канальным ссылочным мусором.
6. `TelegramFileDownloader` пытается скачать `photo`, `video`, `animation` в temp-директорию.
7. Если скачать файл нельзя, например из-за публичного Bot API лимита `getFile` на большие файлы, бот использует исходный Telegram `file_id`.
8. `Publisher` отправляет новый text/media/media group пост в целевой канал из локального файла или напрямую по `file_id`.
9. Временные файлы удаляются после попытки публикации.

## Поддерживаемый контент

Поддерживается:

- text-only posts;
- photo;
- video;
- animation / gif;
- media groups / albums из photo/video;
- смешанные входящие альбомы прагматично: photo/video отправляются альбомами, animation публикуется отдельным media-сообщением.

Не поддерживается в MVP: documents, audio, voice, video note, polls, stories и экзотические типы Telegram.

## Ограничения MVP

В проекте намеренно нет БД, Redis, Postgres, SQLite и persistent storage. Всё состояние хранится in-memory только в рамках текущего процесса:

- уже увиденные `message_id`;
- финализированные `media_group_id`;
- буфер собираемых альбомов.

После рестарта состояние не восстанавливается. Это позволяет вручную повторно переслать тот же исходный пост позже: бот снова его опубликует. Persistent dedupe можно добавить позже, если сценарий изменится.

## Footer

Footer задаётся в `routes[].footer_text`, например:

```yaml
footer_text: "🖤 [Channel](https://t.me/channellink) 🖤"
```

Правило формирования итогового текста одинаковое для text-only и media posts:

- если `cleaned_text` не пустой: `cleaned_text + "\n\n" + footer`;
- если `cleaned_text` пустой: только `footer`.

Если footer содержит Markdown-ссылку вида `[text](url)`, в Telegram отправляется видимый текст без markdown-разметки, а ссылка применяется через `text_link` entity. Например `🖤 [Channel](https://t.me/channellink) 🖤` публикуется как `🖤 Channel 🖤`, где `Channel` является inline link.

## Очистка текста

`TextCleaner` удаляет целые строки, где найдено:

- обычные URL: `https://...`, `http://...`, `www...`;
- Telegram-ссылки: `t.me/...`, `telegram.me/...`, `telegram.dog/...`, `tg://...`;
- Markdown-ссылки;
- HTML-ссылки `<a href="...">...</a>`;
- URL/text_link entities от Telegram;
- очевидный канальный мусор с `@channel`, особенно строки только с mention или с промо-словами.

Обычный текст и хештеги не удаляются. Форматирование по Telegram entities сохраняется по возможности: offsets пересчитываются после удаления строк. Если entity пересекает удалённый фрагмент или становится невалидной, она безопасно отбрасывается.

## Альбомы

Telegram присылает альбом несколькими `channel_post` с одним `media_group_id`. Бот буферизует их в памяти и ждёт `bot.media_group_collect_timeout_seconds`. После timeout группа сортируется по `message_id`, подготавливает media через локальное скачивание или fallback на `file_id`, затем публикуется.

Bot API разрешает максимум 10 элементов в одном `sendMediaGroup`, поэтому альбомы больше 10 делятся на части по `publishing.max_media_per_album`. Caption ставится на первый элемент первой группы, если помещается в лимит Telegram caption. Если итоговый текст длиннее лимита caption, бот отправляет альбом без caption, а текст отдельным follow-up сообщением сразу после него.

## Bot API упрощения

- Caption limit считается как 1024 Python-символа. Для типичных постов этого достаточно; очень редкие UTF-16 edge cases могут потребовать доработки.
- `sendMediaGroup` используется для photo/video. Animation в альбоме отправляется отдельно, потому что Bot API не делает gif нормальным элементом альбома.
- Публичный Bot API ограничивает `getFile` для больших файлов. Если Telegram отвечает `file is too big`, бот не считает это фатальной ошибкой и публикует media через существующий `file_id`.
- Если локальное скачивание падает по другой причине, ошибка логируется отдельно, а MVP всё равно пытается опубликовать media через `file_id`, потому что бинарное содержимое не модифицируется.
- Local Bot API server with `--local` можно добавить позже, если понадобится скачивать большие файлы без публичного лимита. Для текущего MVP это не обязательно.

## Создание и настройка бота

1. Откройте [BotFather](https://t.me/BotFather).
2. Создайте бота командой `/newbot`.
3. Скопируйте token.
4. Добавьте бота администратором в канал-прослойку.
5. Добавьте бота администратором в целевой канал с правом публикации сообщений.

Чтобы узнать `channel_id`, можно временно добавить бота в канал и посмотреть `chat.id` в логах при входящем `channel_post`, либо использовать сторонний Bot API helper вроде `getUpdates` после тестового поста. Для каналов ID обычно выглядит как `-100...`.

## Конфигурация

Скопируйте пример:

```powershell
Copy-Item config.yaml.example config.yaml
```

Заполните:

- `bot.token`;
- `routes[].source_channel_id`;
- `routes[].target_channel_id`;
- `routes[].footer_text`;
- при необходимости параметры `cleaner` и `publishing`.

Конфиг валидируется при старте. Если token оставлен как `PUT_BOT_TOKEN_HERE`, приложение завершится с ошибкой.

## Установка и запуск

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.yaml.example config.yaml
python -m app.main --config config.yaml
```

Бот запускается через long polling. Webhook, Docker и systemd не обязательны для MVP, но архитектура не мешает добавить их позже.

## Логи

Логи идут в консоль. Полезные события:

- `bot started`;
- `config loaded`;
- `message received`;
- `route matched`;
- `media group collecting`;
- `media group finalized`;
- `local media download started`;
- `local media download success`;
- `local media download skipped: using telegram file_id`;
- `file downloaded`;
- `publish via telegram file_id`;
- `publish via local file`;
- `text cleaned`;
- `publish started`;
- `publish success`;
- `publish skipped as duplicate`;
- `publish failed`;
- `temp files removed`.

Уровень задаётся в `bot.log_level`.

## Тесты

```powershell
pytest
```

Покрыты базовые проверки `TextCleaner`, YAML config validation, runtime dedupe и media group aggregator.

## Что можно добавить позже

- webhook;
- деплой на VPS;
- systemd unit;
- Dockerfile;
- persistent dedupe;
- SQLite для очередей и восстановления альбомов после рестарта;
- более строгий parser Markdown/HTML entities;
- отдельную retry-политику публикации.
