# FHD OnlineChat 0.18 — исходники

Исходники клиента и основного сервера из FHD_OnlineChat_0.18_DAILY_CLEAR_TEST.zip без изменения кода. Готовой DLL, EXE игры, пользовательских настроек и ключей доступа в этом архиве нет.

## Сборка DLL

1. Установите Zig 0.13.0 и добавьте zig.exe в PATH.
2. Откройте папку Mods/OtherMods/FHD_OnlineChat/SOURCE.
3. Запустите BUILD_ZIG.cmd. DLL появится в соседней папке Native.
4. Для установки скопируйте папку FHD_OnlineChat в Mods/OtherMods игры и включите мод. Нужен XenoNativeLoader >=0.6.5, который устанавливается отдельно. Поддерживаются две сборки EXE, указанные в README_FIRST_RU.txt и compat_profiles.h.

Проверенный способ сборки: Zig 0.13.0, target x86-windows-gnu. BUILD_MSVC_X86.cmd оставлен как альтернативный путь, здесь не проверялся. font16.h уже готов; повторно генерировать шрифт для сборки не нужно.

## Состав

- bridge.c: WebSocket, имена/настройки, дата комнаты, обработка сообщений.
- overlay.c: D3D9-панель, ввод, общий и личные чаты, видимость и суточная очистка.
- compat_profiles.h: два профиля EXE; chat_event.h и chat_preferences.h: общие структуры.
- header_icons.h, font16.h и make_font.py: иконки и шрифт.
- plugin*.def, BUILD_*.cmd: экспорты и сборка.
- server.js: код основного Cloudflare Worker и Durable Object ChatRoom. Использует binding CHAT и SQLite; в рабочем сервисе уже опубликована версия 0.18. Для локальной сборки DLL аккаунт Cloudflare не нужен. Учётные данные и доступ к существующему сервису архив не предоставляет.
- QA: скрипты, результаты, технический анализ и изображения проверок.

Подробности реализации: SOURCE/BUILD_NOTES_RU.txt. Проверки и их ограничения: TEST_REPORT_RU.md и SOURCE/QA/README_RU.txt. Новая версия не запускалась здесь в настоящей игре на Windows.

## Повторение быстрых проверок клиента

Скрипт QA/emulate018.py ожидает tests_runtime018.dll в папке SOURCE. Из SOURCE:

```bat
zig cc -target x86-windows-gnu -shared -O2 -fno-builtin -DFHD_TEST bridge.c overlay.c plugin_zig.def -luser32 -lgdi32 -lwinhttp -lshell32 -o tests_runtime018.dll
python -m pip install pefile unicorn Pillow
python QA/emulate018.py
```

Для части проверок видимости нужны два оригинальных EXE в SOURCE/upload/Rangers.exe и SOURCE/upload/Rangers(1).exe. Они не входят в архив. Для полного дополнительного набора передайте два пути EXE аргументами. Детали см. QA/README_RU.txt.

Серверные проверки: Node.js 24 с node:sqlite, команда из SOURCE: `node QA/server.test.mjs`. Никаких сообщений в настоящий чат этот тест не отправляет.

SHA256_MANIFEST.json содержит контрольные суммы всех остальных файлов архива.
