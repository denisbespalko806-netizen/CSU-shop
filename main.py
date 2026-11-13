import os, json, hmac, hashlib, secrets, sqlite3, asyncio
from urllib.parse import parse_qsl
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
import uvicorn

TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")
ADMIN_USERNAMES = {x.strip().lower().lstrip("@") for x in os.getenv("ADMIN_USERNAMES", "denis_2611,Menager_Combo_Stunt_Ukraine").split(",") if x.strip()}
ADMIN_PIN = os.environ["ADMIN_PIN"]
DB_PATH = os.getenv("DB_PATH", "/var/data/csu_shop.db")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")
if not WEBAPP_URL:
    raise RuntimeError("Set WEBAPP_URL to your public Render URL")

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
app = FastAPI(title="csu•shop")
app.mount("/static", StaticFiles(directory="static"), name="static")
bot = Bot(TOKEN)
dp = Dispatcher()
admin_chats = set()
admin_sessions = set()

@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

with db() as con:
    con.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT '',
        price REAL NOT NULL, photo TEXT DEFAULT '', kind TEXT NOT NULL DEFAULT 'normal',
        available INTEGER NOT NULL DEFAULT 1, variants TEXT NOT NULL DEFAULT '{}')""")
    con.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, customer TEXT, phone TEXT,
        city TEXT, address TEXT, items TEXT, total REAL, created TEXT DEFAULT CURRENT_TIMESTAMP)""")

def valid_init_data(init_data: str):
    if not init_data:
        return None
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        their_hash = data.pop("hash")
        auth_date = int(data.get("auth_date", "0"))
        # Reject stale Mini App sessions older than 24 hours.
        import time
        if abs(time.time() - auth_date) > 86400:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        ours = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(ours, their_hash):
            return None
        user = json.loads(data.get("user", "{}"))
        return user
    except Exception:
        return None

def user_from_header(authorization):
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "Open this shop from Telegram")
    user = valid_init_data(authorization[4:])
    if not user:
        raise HTTPException(401, "Telegram session invalid or expired")
    return user

def require_admin(authorization, pin):
    user = user_from_header(authorization)
    username = (user.get("username") or "").lower()
    if username not in ADMIN_USERNAMES:
        raise HTTPException(403, "Admin access is not allowed")
    if not pin or not secrets.compare_digest(pin, ADMIN_PIN):
        raise HTTPException(403, "Incorrect PIN")
    return user

class Login(BaseModel):
    pin: str
class ProductIn(BaseModel):
    name: str
    description: str = ""
    price: float
    photo: str = ""
    kind: str = "normal"
    available: bool = True
    variants: dict = {}
class OrderIn(BaseModel):
    customer: str
    phone: str
    city: str
    address: str
    items: list
    total: float

@app.get("/")
async def home():
    return FileResponse("static/index.html")

@app.get("/api/products")
async def products():
    with db() as con:
        rows = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return [dict(r) | {"variants": json.loads(r["variants"])} for r in rows]

@app.post("/api/admin/check")
async def admin_check(body: Login, authorization: str = Header(default="")):
    user = user_from_header(authorization)
    if (user.get("username") or "").lower() not in ADMIN_USERNAMES:
        raise HTTPException(403, "This Telegram account is not an administrator")
    if not secrets.compare_digest(body.pin, ADMIN_PIN):
        raise HTTPException(403, "Incorrect PIN")
    return {"ok": True}

@app.post("/api/admin/products")
async def add_product(body: ProductIn, authorization: str = Header(default=""), x_admin_pin: str = Header(default="")):
    require_admin(authorization, x_admin_pin)
    if body.price < 0 or body.kind not in ("normal", "shirt"):
        raise HTTPException(400, "Invalid product")
    with db() as con:
        cur = con.execute("INSERT INTO products(name,description,price,photo,kind,available,variants) VALUES(?,?,?,?,?,?,?)",
            (body.name, body.description, body.price, body.photo, body.kind, int(body.available), json.dumps(body.variants)))
        pid = cur.lastrowid
    return {"id": pid}

@app.put("/api/admin/products/{pid}")
async def update_product(pid: int, body: ProductIn, authorization: str = Header(default=""), x_admin_pin: str = Header(default="")):
    require_admin(authorization, x_admin_pin)
    with db() as con:
        cur = con.execute("UPDATE products SET name=?,description=?,price=?,photo=?,kind=?,available=?,variants=? WHERE id=?",
            (body.name, body.description, body.price, body.photo, body.kind, int(body.available), json.dumps(body.variants), pid))
        if not cur.rowcount: raise HTTPException(404, "Product not found")
    return {"ok": True}

@app.delete("/api/admin/products/{pid}")
async def delete_product(pid: int, authorization: str = Header(default=""), x_admin_pin: str = Header(default="")):
    require_admin(authorization, x_admin_pin)
    with db() as con:
        con.execute("DELETE FROM products WHERE id=?", (pid,))
    return {"ok": True}

@app.post("/api/orders")
async def create_order(body: OrderIn, authorization: str = Header(default="")):
    user = user_from_header(authorization)
    if not body.items or not body.customer.strip() or not body.phone.strip():
        raise HTTPException(400, "Fill in all required fields")
    items_text = json.dumps(body.items, ensure_ascii=False)
    with db() as con:
        cur = con.execute("INSERT INTO orders(username,customer,phone,city,address,items,total) VALUES(?,?,?,?,?,?,?)",
            (user.get("username",""), body.customer, body.phone, body.city, body.address, items_text, body.total))
        order_id = cur.lastrowid
    text = (f"🛍 НОВЕ ЗАМОВЛЕННЯ csu•shop №{order_id}\n"
            f"Клієнт: {body.customer}\nТелефон: {body.phone}\nМісто: {body.city}\n"
            f"Доставка: {body.address}\nТовари: {items_text}\nСума: {body.total:g} грн\n"
            f"Telegram: @{user.get('username','немає')}")
    for chat_id in list(admin_chats):
        try: await bot.send_message(chat_id, text)
        except Exception: pass
    return {"ok": True, "id": order_id}

@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES:
        admin_chats.add(message.chat.id)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛍 Відкрити csu•shop", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )
    await message.answer("Вітаємо в csu•shop! Натисніть кнопку, щоб відкрити магазин 👇", reply_markup=keyboard)

@dp.message()
async def admin_start_hint(message: Message):
    if message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES:
        admin_chats.add(message.chat.id)
        await message.answer("Ви зареєстровані для отримання замовлень. Магазин відкривається кнопкою нижче через /start.")

@app.on_event("startup")
async def startup():
    app.state.polling_task = asyncio.create_task(dp.start_polling(bot))

@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "polling_task", None)
    if task:
        task.cancel()
    await bot.session.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
