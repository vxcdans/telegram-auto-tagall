# Telegram Auto TagAll Bot

Telegram group TagAll bot menggunakan Python dan SQLite.

## Commands

- /start — panduan
- /tagme — mendaftar agar bisa di-mention
- /untagme — keluar dari daftar
- /tagcount — menghitung anggota terdaftar
- /tagall — menjalankan TagAll (admin)
- /tagstop — menghentikan TagAll (admin)

Bot hanya me-mention anggota yang secara sukarela menggunakan /tagme.

## Install

    git clone https://github.com/vxcdans/telegram-auto-tagall.git
    cd telegram-auto-tagall
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    nano .env
    python bot.py

Jangan unggah file .env atau token bot ke GitHub.
