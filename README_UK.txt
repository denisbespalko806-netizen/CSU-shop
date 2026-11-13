csu•shop Telegram Mini App

1. Розпакуй ZIP на комп'ютері.
2. Створи репозиторій GitHub і завантаж усі файли та папку static.
3. У Render створи New -> Blueprint і вибери цей репозиторій.
4. Render попросить секретні значення:
   BOT_TOKEN = токен від BotFather
   BOT_USERNAME = username бота без @
   ADMIN_PIN = придумай довгий PIN (не 2580)
   WEBAPP_URL = https://НАЗВА-СЕРВІСУ.onrender.com
   Після першого створення сервісу Render покаже адресу; внеси її в WEBAPP_URL і зроби redeploy.
5. У BotFather: /mybots -> твій бот -> Bot Settings -> Menu Button -> Configure menu button.
   URL: адреса Render, наприклад https://csu-shop.onrender.com
   Назва кнопки: Відкрити магазин
6. Ти і друг маєте відкрити бота та натиснути /start, щоб бот запам'ятав ваші чати для сповіщень.
7. Адмінка відкривається кнопкою «Адмін» у Mini App. Доступ обмежений username зі списку ADMIN_USERNAMES та PIN.
8. Для замовлень потрібен точний Telegram username у Telegram профілях. Якщо username зміниться, онови ADMIN_USERNAMES у Render.
9. Фото товарів додаються за прямим HTTPS-посиланням до зображення.

ВАЖЛИВО:
- Не публікуй BOT_TOKEN або ADMIN_PIN у GitHub.
- Цей шаблон використовує SQLite на постійному диску Render.
- У Render потрібен платний план із persistent disk. Без диска дані можуть зникнути після перезапуску.
- Адмін-авторизація Mini App перевіряє підпис Telegram initData на сервері.
