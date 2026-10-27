# Hamyon bot

Telegram moliya boti: xarajat/daromad, naqd/karta, qarzlar, tahlil.

## Ishga tushirish
1. Telegramda @BotFather ga `/newbot` yozing va token oling.
2. O'rnatish:
   ```
   pip install -r requirements.txt
   ```
3. Token bilan ishga tushirish:
   - Mac/Linux: `BOT_TOKEN="123:ABC" python bot.py`
   - Windows (PowerShell): `$env:BOT_TOKEN="123:ABC"; python bot.py`

## Ishlatish
- `25000 taksi` — xarajat (kategoriya avtomatik)
- `+3m maosh` — daromad (k = ming, m = million)
- `berdim Ali 200000` — Ali menga qarz
- `oldim Vali 100000` — men Valiga qarzman
- Pastdagi tugmalar: Balans, Tahlil, Tarix, Qarzlar

Ma'lumotlar `hamyon.db` (SQLite) faylida saqlanadi.
