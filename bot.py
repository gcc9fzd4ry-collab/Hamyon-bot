import asyncio
import os
import re
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

TOKEN = os.getenv("BOT_TOKEN", "")
DB = "hamyon.db"

CATEGORIES = {
    "🍔 Oziq-ovqat": ["non", "go'sht", "gosht", "bozor", "market", "korzinka", "ovqat", "osh", "lavash", "kafe", "restoran", "choy", "tushlik", "kofe"],
    "🚕 Transport": ["taksi", "taxi", "yandex", "benzin", "metro", "avtobus", "yo'l", "yol", "gaz", "mashina"],
    "🏠 Uy-joy": ["ijara", "svet", "kommunal", "suv", "internet", "uy"],
    "📱 Aloqa": ["telefon", "tarif", "paynet", "uzmobile", "beeline", "ucell", "mobiuz"],
    "👕 Kiyim": ["kiyim", "ko'ylak", "oyoq kiyim", "krossovka", "shim"],
    "💊 Salomatlik": ["dori", "apteka", "shifokor", "klinika", "tish"],
    "🎮 Ko'ngilochar": ["kino", "o'yin", "oyin", "konsert", "park", "obuna"],
    "📚 Ta'lim": ["kurs", "kitob", "dars", "o'qish", "oqish"],
    "🎁 Sovg'a": ["sovga", "sovg'a", "tug'ilgan", "tugilgan", "to'y", "toy"],
}
OTHER = "📦 Boshqa"
INCOME_CAT = "💼 Daromad"

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Balans"), KeyboardButton(text="📊 Tahlil")],
        [KeyboardButton(text="🧾 Tarix"), KeyboardButton(text="🤝 Qarzlar")],
        [KeyboardButton(text="❓ Yordam")],
    ],
    resize_keyboard=True,
)

HELP = (
    "👋 <b>Hamyon bot</b>\n\n"
    "<b>Xarajat:</b> <code>25000 taksi</code>\n"
    "<b>Daromad:</b> <code>+3000000 maosh</code>\n"
    "<b>Qarz berdim:</b> <code>berdim Ali 200000</code>\n"
    "<b>Qarz oldim:</b> <code>oldim Vali 100000</code>\n\n"
    "Summada 'k' ishlatsa bo'ladi: <code>25k</code>, <code>1.5m</code>\n"
    "Yozgandan keyin pastdagi tugmalar bilan <b>naqd/karta</b> va <b>kategoriyani</b> o'zgartirish mumkin."
)


# ---------- DB ----------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS tx(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount INTEGER, kind TEXT, category TEXT, method TEXT,
            note TEXT, created TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS debt(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            person TEXT, amount INTEGER, direction TEXT,
            closed INTEGER DEFAULT 0, created TEXT)"""
        )


# ---------- helpers ----------
def fmt(n):
    return f"{int(n):,}".replace(",", " ")


def parse_amount(s):
    s = s.lower().replace(" ", "").replace(",", ".")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([km]?)", s)
    if not m:
        return None
    v = float(m.group(1))
    v *= {"k": 1_000, "m": 1_000_000, "": 1}[m.group(2)]
    return int(v)


def guess_category(note):
    t = note.lower()
    for cat, words in CATEGORIES.items():
        if any(w in t for w in words):
            return cat
    return OTHER


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def month_start(offset=0):
    d = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(abs(offset)):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.strftime("%Y-%m-%d %H:%M:%S")


def tx_keyboard(tx_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 Naqd", callback_data=f"m:{tx_id}:naqd"),
                InlineKeyboardButton(text="💳 Karta", callback_data=f"m:{tx_id}:karta"),
            ],
            [
                InlineKeyboardButton(text="🏷 Kategoriya", callback_data=f"cs:{tx_id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"d:{tx_id}"),
            ],
        ]
    )


def tx_text(row):
    sign = "+" if row["kind"] == "income" else "−"
    icon = "💵" if row["method"] == "naqd" else "💳"
    return (
        f"{'✅ Daromad' if row['kind']=='income' else '✅ Xarajat'} saqlandi\n"
        f"<b>{sign}{fmt(row['amount'])} so'm</b>\n"
        f"{row['category']} · {icon} {row['method'].capitalize()}\n"
        f"📝 {row['note'] or '—'}"
    )


def balances(uid):
    with db() as c:
        rows = c.execute(
            "SELECT method, kind, SUM(amount) s FROM tx WHERE user_id=? GROUP BY method, kind",
            (uid,),
        ).fetchall()
    res = {"naqd": 0, "karta": 0}
    for r in rows:
        res[r["method"]] += r["s"] if r["kind"] == "income" else -r["s"]
    return res


# ---------- bot ----------
dp = Dispatcher()


@dp.message(Command("start"))
@dp.message(F.text == "❓ Yordam")
async def start(m: Message):
    await m.answer(HELP, reply_markup=MENU, parse_mode="HTML")


@dp.message(F.text == "💰 Balans")
async def balance(m: Message):
    b = balances(m.from_user.id)
    with db() as c:
        r = c.execute(
            "SELECT direction, SUM(amount) s FROM debt WHERE user_id=? AND closed=0 GROUP BY direction",
            (m.from_user.id,),
        ).fetchall()
    d = {x["direction"]: x["s"] for x in r}
    owed_me, i_owe = d.get("berdim", 0), d.get("oldim", 0)
    await m.answer(
        f"💰 <b>Umumiy: {fmt(b['naqd'] + b['karta'])} so'm</b>\n\n"
        f"💵 Naqd: {fmt(b['naqd'])}\n"
        f"💳 Karta: {fmt(b['karta'])}\n\n"
        f"🤝 Menga qarz: {fmt(owed_me)}\n"
        f"🙇 Men qarzdorman: {fmt(i_owe)}\n"
        f"📈 Sof qarz: {'+' if owed_me - i_owe >= 0 else '−'}{fmt(abs(owed_me - i_owe))}",
        parse_mode="HTML",
    )


@dp.message(F.text == "🧾 Tarix")
async def history(m: Message):
    with db() as c:
        rows = c.execute(
            "SELECT * FROM tx WHERE user_id=? ORDER BY id DESC LIMIT 15", (m.from_user.id,)
        ).fetchall()
    if not rows:
        return await m.answer("Hali yozuv yo'q. Masalan: <code>25000 taksi</code>", parse_mode="HTML")
    lines = []
    for r in rows:
        sign = "+" if r["kind"] == "income" else "−"
        ic = "💵" if r["method"] == "naqd" else "💳"
        lines.append(f"{r['created'][5:16]}  {sign}{fmt(r['amount'])}  {r['category']} {ic}\n      <i>{r['note'] or ''}</i>")
    await m.answer("🧾 <b>So'nggi 15 ta:</b>\n\n" + "\n".join(lines), parse_mode="HTML")


def bar(p, n=10):
    k = round(p * n)
    return "█" * k + "░" * (n - k)


@dp.message(F.text == "📊 Tahlil")
async def analysis(m: Message):
    uid = m.from_user.id
    ms, prev = month_start(0), month_start(1)
    with db() as c:
        cats = c.execute(
            "SELECT category, SUM(amount) s FROM tx WHERE user_id=? AND kind='expense' AND created>=? GROUP BY category ORDER BY s DESC",
            (uid, ms),
        ).fetchall()
        inc = c.execute(
            "SELECT COALESCE(SUM(amount),0) s FROM tx WHERE user_id=? AND kind='income' AND created>=?",
            (uid, ms),
        ).fetchone()["s"]
        prev_exp = c.execute(
            "SELECT COALESCE(SUM(amount),0) s FROM tx WHERE user_id=? AND kind='expense' AND created>=? AND created<?",
            (uid, prev, ms),
        ).fetchone()["s"]
        meth = c.execute(
            "SELECT method, SUM(amount) s FROM tx WHERE user_id=? AND kind='expense' AND created>=? GROUP BY method",
            (uid, ms),
        ).fetchall()
    total = sum(r["s"] for r in cats)
    if not total:
        return await m.answer("Bu oy hali xarajat yo'q.")
    day = datetime.now().day
    text = [f"📊 <b>Shu oy tahlili</b>\n", f"💸 Xarajat: <b>{fmt(total)}</b>", f"💼 Daromad: <b>{fmt(inc)}</b>"]
    text.append(f"📉 Qoldi: <b>{'+' if inc - total >= 0 else '−'}{fmt(abs(inc - total))}</b>")
    text.append(f"📅 Kuniga o'rtacha: {fmt(total / day)}")
    if prev_exp:
        diff = (total - prev_exp) / prev_exp * 100
        text.append(f"↔️ O'tgan oyga nisbatan: {diff:+.0f}%")
    text.append("\n<b>Kategoriyalar:</b>")
    for r in cats:
        p = r["s"] / total
        text.append(f"{r['category']}\n{bar(p)} {p*100:.0f}% · {fmt(r['s'])}")
    text.append("\n<b>To'lov turi:</b>")
    for r in meth:
        text.append(f"{'💵' if r['method']=='naqd' else '💳'} {r['method'].capitalize()}: {fmt(r['s'])} ({r['s']/total*100:.0f}%)")
    top = cats[0]
    text.append(f"\n💡 Eng ko'p sarf: {top['category']} ({top['s']/total*100:.0f}%).")
    await m.answer("\n".join(text), parse_mode="HTML")


# ---- debts ----
def debts_view(uid):
    with db() as c:
        rows = c.execute(
            "SELECT * FROM debt WHERE user_id=? AND closed=0 ORDER BY direction, id", (uid,)
        ).fetchall()
    if not rows:
        return "Ochiq qarzlar yo'q 🎉", None
    text, kb = ["🤝 <b>Ochiq qarzlar</b>"], []
    for title, key in (("Menga qarz", "berdim"), ("Men qarzdorman", "oldim")):
        part = [r for r in rows if r["direction"] == key]
        if part:
            text.append(f"\n<b>{title} — {fmt(sum(r['amount'] for r in part))}</b>")
            for r in part:
                text.append(f"• {r['person']}: {fmt(r['amount'])} ({r['created'][:10]})")
                kb.append([InlineKeyboardButton(text=f"✅ Yopish: {r['person']} {fmt(r['amount'])}", callback_data=f"dc:{r['id']}")])
    return "\n".join(text), InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(F.text == "🤝 Qarzlar")
async def debts(m: Message):
    t, kb = debts_view(m.from_user.id)
    await m.answer(t, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("dc:"))
async def close_debt(cb: CallbackQuery):
    with db() as c:
        c.execute("UPDATE debt SET closed=1 WHERE id=? AND user_id=?", (int(cb.data[3:]), cb.from_user.id))
    t, kb = debts_view(cb.from_user.id)
    await cb.message.edit_text(t, reply_markup=kb, parse_mode="HTML")
    await cb.answer("Yopildi")


# ---- transactions ----
@dp.message(F.text.regexp(r"^(berdim|oldim)\s+", flags=re.I))
async def add_debt(m: Message):
    parts = m.text.split()
    direction = parts[0].lower()
    amount = parse_amount(parts[-1])
    person = " ".join(parts[1:-1])
    if not amount or not person:
        return await m.answer("Format: <code>berdim Ali 200000</code>", parse_mode="HTML")
    with db() as c:
        c.execute(
            "INSERT INTO debt(user_id,person,amount,direction,created) VALUES(?,?,?,?,?)",
            (m.from_user.id, person, amount, direction, now()),
        )
    word = "menga qarz" if direction == "berdim" else "men qarzdorman"
    await m.answer(f"🤝 Saqlandi: {person} — {fmt(amount)} so'm ({word})")


@dp.message(F.text.regexp(r"^[+\-]?\s*\d"))
async def add_tx(m: Message):
    txt = m.text.strip()
    income = txt.startswith("+")
    txt = txt.lstrip("+-").strip()
    first, _, note = txt.partition(" ")
    amount = parse_amount(first)
    if not amount:
        return await m.answer("Summani tushunmadim. Masalan: <code>25000 taksi</code>", parse_mode="HTML")
    cat = INCOME_CAT if income else guess_category(note)
    with db() as c:
        cur = c.execute(
            "INSERT INTO tx(user_id,amount,kind,category,method,note,created) VALUES(?,?,?,?,?,?,?)",
            (m.from_user.id, amount, "income" if income else "expense", cat, "naqd", note, now()),
        )
        row = c.execute("SELECT * FROM tx WHERE id=?", (cur.lastrowid,)).fetchone()
    await m.answer(tx_text(row), reply_markup=tx_keyboard(row["id"]), parse_mode="HTML")


def get_tx(tx_id, uid):
    with db() as c:
        return c.execute("SELECT * FROM tx WHERE id=? AND user_id=?", (tx_id, uid)).fetchone()


@dp.callback_query(F.data.startswith("m:"))
async def set_method(cb: CallbackQuery):
    _, tx_id, method = cb.data.split(":")
    with db() as c:
        c.execute("UPDATE tx SET method=? WHERE id=? AND user_id=?", (method, int(tx_id), cb.from_user.id))
    row = get_tx(int(tx_id), cb.from_user.id)
    await cb.message.edit_text(tx_text(row), reply_markup=tx_keyboard(row["id"]), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("cs:"))
async def choose_cat(cb: CallbackQuery):
    tx_id = cb.data[3:]
    cats = list(CATEGORIES) + [OTHER]
    kb = [[InlineKeyboardButton(text=c, callback_data=f"c:{tx_id}:{i}")] for i, c in enumerate(cats)]
    await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@dp.callback_query(F.data.startswith("c:"))
async def set_cat(cb: CallbackQuery):
    _, tx_id, i = cb.data.split(":")
    cat = (list(CATEGORIES) + [OTHER])[int(i)]
    with db() as c:
        c.execute("UPDATE tx SET category=? WHERE id=? AND user_id=?", (cat, int(tx_id), cb.from_user.id))
    row = get_tx(int(tx_id), cb.from_user.id)
    await cb.message.edit_text(tx_text(row), reply_markup=tx_keyboard(row["id"]), parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data.startswith("d:"))
async def delete_tx(cb: CallbackQuery):
    with db() as c:
        c.execute("DELETE FROM tx WHERE id=? AND user_id=?", (int(cb.data[2:]), cb.from_user.id))
    await cb.message.edit_text("🗑 O'chirildi")
    await cb.answer()


async def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan. README.md ga qarang.")
    init_db()
    await dp.start_polling(Bot(TOKEN))


if __name__ == "__main__":
    asyncio.run(main())
