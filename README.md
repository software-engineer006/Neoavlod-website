# Neoavlod IT Academy veb-sayti

Neoavlod — Qibray tumanidagi IT va zamonaviy kasblar akademiyasi uchun yaratilgan production-ready landing page va lid yig‘ish tizimi. Frontend sof HTML5, CSS3 va Vanilla JavaScript’da; backend esa FastAPI, Pydantic, SQLite va HTTPX yordamida yozilgan.

## Imkoniyatlar

- 320 px dan 4K ekranlargacha moslashadigan mobile-first interfeys
- Brauzer xotirasida saqlanadigan light/dark rejim
- Intersection Observer asosidagi yumshoq animatsiyalar
- O‘zbekiston raqamlari uchun `+998 XX XXX-XX-XX` avtomatik maskasi
- Client va server tomonida qat’iy validatsiya
- UTM parametrlarini saqlash va har bir lid bilan backendga uzatish
- SQLite bazasini avtomatik yaratish
- Yangi lid haqida Telegram administratoriga Toshkent vaqti bilan xabar
- CORS, TrustedHost, xavfsizlik headerlari va Nginx rate limiting

## Loyiha tuzilmasi

```text
Neoavlod-website/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── backend/
│   ├── main.py
│   └── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Lokal ishga tushirish

### 1. Backend

Python 3.10 yoki undan yangi versiya talab qilinadi.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..
cp .env.example .env
```

`.env` ichidagi `BOT_TOKEN` va `ADMIN_CHAT_ID` qiymatlarini haqiqiy Telegram ma’lumotlari bilan almashtiring. Keyin:

```bash
cd backend
source venv/bin/activate
ENVIRONMENT=development uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Tekshirish:

```bash
curl http://127.0.0.1:8000/health
```

Kutiladigan javob:

```json
{"status":"ok","service":"neoavlod-backend"}
```

### 2. Frontend

Yangi terminal oynasida loyiha ildizidan frontendni `3000`-portda ishga tushiring:

```bash
cd frontend
python3 -m http.server 3000 --bind 127.0.0.1
```

Brauzerda `http://localhost:3000` manzilini oching. Lokal rejimda JavaScript API so‘rovlarini avtomatik ravishda `http://localhost:8000/api/leads` manziliga yuboradi.

### API ni qo‘lda tekshirish

```bash
curl -i -X POST http://127.0.0.1:8000/api/leads \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://localhost:3000' \
  -d '{
    "first_name": "Ali",
    "last_name": "Karimov",
    "phone": "+998 90 123-45-67",
    "course": "Kiberxavfsizlik",
    "utm_source": "instagram",
    "utm_medium": "stories",
    "utm_campaign": "local_test",
    "utm_content": "open_lesson",
    "utm_term": "qibray_it"
  }'
```

Telegram sozlanmagan bo‘lsa ham ariza bazaga saqlanadi, javobdagi `notification_sent` qiymati `false` bo‘ladi.

---

# Ubuntu VPS ga production deployment

Quyidagi yo‘riqnoma Ubuntu 22.04/24.04 va `eduneo.uz` domeni server IP manziliga yo‘naltirilgan holat uchun yozilgan. Barcha buyruqlar `root` foydalanuvchisi nomidan bajariladi.

## 1. Serverga ulanish va tizimni yangilash

```bash
ssh root@SERVER_IP
apt update
apt upgrade -y
apt install -y git curl ufw python3 python3-pip python3-venv
```

Firewall orqali faqat SSH, HTTP va HTTPS portlarini oching:

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status
```

## 2. Repozitoriyni `/root` ichiga klonlash

```bash
cd /root
git clone <REPO_URL> Neoavlod-website
cd /root/Neoavlod-website
```

`<REPO_URL>` o‘rniga GitHub yoki GitLab repozitoriy manzilini kiriting.

## 3. Frontendni alohida joylashtirish

Frontend statik fayllarini Nginx o‘qiy oladigan katalogga nusxalang:

```bash
mkdir -p /var/www/Neoavlod-Frontend
cp -r /root/Neoavlod-website/frontend/* /var/www/Neoavlod-Frontend/
chown -R www-data:www-data /var/www/Neoavlod-Frontend
find /var/www/Neoavlod-Frontend -type d -exec chmod 755 {} \;
find /var/www/Neoavlod-Frontend -type f -exec chmod 644 {} \;
```

Muhim: backend fayllarini `/var/www` ichiga ko‘chirmang. Backend `/root/Neoavlod-website/backend` ichida ishlaydi; Nginx unga faqat `127.0.0.1:8000` orqali murojaat qiladi.

## 4. Backend virtual muhitini sozlash

```bash
cd /root/Neoavlod-website/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
deactivate
```

Environment faylini yarating:

```bash
cd /root/Neoavlod-website
cp .env.example .env
nano .env
```

Production `.env` namunasi:

```dotenv
BOT_TOKEN=1234567890:AAExampleRealTelegramBotToken
ADMIN_CHAT_ID=-1001234567890
DATABASE_URL=leads.db
ALLOWED_ORIGINS=http://localhost,http://localhost:8000,https://eduneo.uz,http://eduneo.uz
ENVIRONMENT=production
LOG_LEVEL=INFO
```

Telegram Bot tokenini [@BotFather](https://t.me/BotFather) orqali oling. Botni admin guruhiga qo‘shib, xabar yuborish huquqini bering. `.env` maxfiy fayl bo‘lgani sababli uning ruxsatlarini cheklang:

```bash
chmod 600 /root/Neoavlod-website/.env
```

Backendni systemd’dan oldin tekshiring:

```bash
cd /root/Neoavlod-website/backend
set -a
source ../.env
set +a
./venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Boshqa terminaldan `curl http://127.0.0.1:8000/health` ni tekshiring, so‘ng `Ctrl+C` bilan jarayonni to‘xtating.

## 5. Systemd service yaratish

```bash
nano /etc/systemd/system/neoavlod-backend.service
```

Faylning to‘liq matni:

```ini
[Unit]
Description=Neoavlod FastAPI Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/Neoavlod-website/backend
EnvironmentFile=/root/Neoavlod-website/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/root/Neoavlod-website/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5
TimeoutStopSec=20
KillSignal=SIGINT

# Service hardening
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/root/Neoavlod-website/backend
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
```

Servisni faollashtiring va ishga tushiring:

```bash
systemctl daemon-reload
systemctl enable neoavlod-backend
systemctl start neoavlod-backend
systemctl status neoavlod-backend --no-pager
```

Loglarni real vaqtda ko‘rish:

```bash
journalctl -u neoavlod-backend -f
```

## 6. Nginx veb-serveri

Nginx o‘rnating:

```bash
apt install -y nginx
```

Sayt konfiguratsiyasini yarating:

```bash
nano /etc/nginx/sites-available/eduneo.uz
```

Faylning to‘liq matni:

```nginx
limit_req_zone $binary_remote_addr zone=neoavlod_api:10m rate=10r/m;

server {
    listen 80;
    listen [::]:80;
    server_name eduneo.uz www.eduneo.uz;

    root /var/www/Neoavlod-Frontend;
    index index.html;

    client_max_body_size 64k;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; frame-src https://yandex.uz; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; upgrade-insecure-requests" always;

    location /api/ {
        limit_req zone=neoavlod_api burst=5 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 15s;
        proxy_read_timeout 15s;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(css|js|svg|png|jpg|jpeg|webp|ico)$ {
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
        try_files $uri =404;
    }

    location ~ /\. {
        deny all;
    }
}
```

Konfiguratsiyani yoqing va tekshiring:

```bash
ln -s /etc/nginx/sites-available/eduneo.uz /etc/nginx/sites-enabled/eduneo.uz
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx
```

Brauzerda `http://eduneo.uz` ni oching. DNS hali tarqalmagan bo‘lsa, `dig +short eduneo.uz` natijasi server IP bilan bir xil ekanini tekshiring.

## 7. SSL sertifikati

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d eduneo.uz -d www.eduneo.uz
```

Certbot so‘raganda HTTP’dan HTTPS’ga avtomatik yo‘naltirishni tanlang. Avtomatik yangilanish holatini va sinovini tekshiring:

```bash
systemctl status certbot.timer --no-pager
certbot renew --dry-run
```

Yakuniy tekshiruv:

```bash
curl -I https://eduneo.uz
curl https://eduneo.uz/health
systemctl status neoavlod-backend nginx --no-pager
```

## 8. Keyingi yangilanishlarni chiqarish

```bash
cd /root/Neoavlod-website
git pull --ff-only
source backend/venv/bin/activate
pip install --no-cache-dir -r backend/requirements.txt
deactivate
cp -r frontend/* /var/www/Neoavlod-Frontend/
chown -R www-data:www-data /var/www/Neoavlod-Frontend
systemctl restart neoavlod-backend
nginx -t && systemctl reload nginx
```

## Ma’lumotlar bazasi zaxira nusxasi

SQLite WAL rejimida ishlaydi. Izchil zaxira olish uchun `sqlite3` ichki backup buyrug‘idan foydalaning:

```bash
apt install -y sqlite3
mkdir -p /root/backups/neoavlod
sqlite3 /root/Neoavlod-website/backend/leads.db ".backup '/root/backups/neoavlod/leads-$(date +%F-%H%M).db'"
```

Zaxira katalogini serverdan tashqaridagi xavfsiz joyga muntazam nusxalash tavsiya qilinadi.

## UTM marketing test havolalari

Quyidagi havolalar sahifa ochilganda marketing atributlarini brauzer xotirasiga yozadi. Forma yuborilganda ular SQLite va Telegram xabariga qo‘shiladi.

| Kurs | Kanal | Test havolasi |
|---|---|---|
| Kiberxavfsizlik | Instagram Stories | `https://eduneo.uz/?utm_source=instagram&utm_medium=stories&utm_campaign=kiberxavfsizlik_qabul_2026&utm_content=hakerlikdan_himoya_video&utm_term=kiberxavfsizlik_qibray` |
| Kiberxavfsizlik | Facebook Ads | `https://eduneo.uz/?utm_source=facebook&utm_medium=paid_social&utm_campaign=cyber_qibray_2026&utm_content=ota_onalar_uchun_banner&utm_term=axborot_xavfsizligi` |
| Python & Vibe Coding | Telegram kanal | `https://eduneo.uz/?utm_source=telegram&utm_medium=channel_post&utm_campaign=vibe_coding_startap_2026&utm_content=ai_bilan_dasturlash&utm_term=python_kursi_toshkent` |
| Python & Vibe Coding | Instagram Post | `https://eduneo.uz/?utm_source=instagram&utm_medium=post&utm_campaign=python_ai_qabul_2026&utm_content=mvp_yaratish_karusel&utm_term=vibe_coding_qibray` |
| Ingliz tili | Instagram Reels | `https://eduneo.uz/?utm_source=instagram&utm_medium=reels&utm_campaign=english_global_2026&utm_content=ielts_natija_video&utm_term=ingliz_tili_qibray` |
| Ingliz tili | Telegram kanal | `https://eduneo.uz/?utm_source=telegram&utm_medium=channel_post&utm_campaign=ielts_grant_2026&utm_content=bepul_ochiq_dars&utm_term=ielts_75` |
| Yapon tili | Facebook Ads | `https://eduneo.uz/?utm_source=facebook&utm_medium=paid_social&utm_campaign=japan_career_2026&utm_content=tokio_karyera_banner&utm_term=yapon_tili_qibray` |
| Yapon tili | Instagram Stories | `https://eduneo.uz/?utm_source=instagram&utm_medium=stories&utm_campaign=jlpt_qabul_2026&utm_content=n3_n2_imkoniyat&utm_term=yaponiyada_ish` |

UTM parametrlarisiz tashriflar `utm_source=organic` sifatida qayd etiladi, qolgan UTM maydonlari `null` bo‘ladi.

## Muammolarni aniqlash

- `502 Bad Gateway`: `systemctl status neoavlod-backend` va `journalctl -u neoavlod-backend -n 100` ni tekshiring.
- Forma serverga ulanmayapti: Nginx `/api/` proxy konfiguratsiyasi va brauzer Console/Network panelini tekshiring.
- Telegram xabari kelmayapti: token, chat ID va botning guruhdagi huquqlarini tekshiring; lid bazaga baribir saqlanadi.
- Nginx ishga tushmayapti: `nginx -t` ko‘rsatgan fayl va qatorni tuzating.
- SSL olinmayapti: domenning `A`/`AAAA` yozuvlari aynan VPS manziliga yo‘naltirilganini tekshiring.

## Xavfsizlik eslatmalari

- `.env` va `*.db` fayllarini Git’ga yubormang.
- Bot tokeni oshkor bo‘lsa, BotFather orqali darhol bekor qilib, yangisini oling.
- Server paketlarini muntazam yangilang va zaxira nusxalarini tekshirib boring.
- API faqat belgilangan origin va hostlardan kelgan so‘rovlarni qabul qiladi.
