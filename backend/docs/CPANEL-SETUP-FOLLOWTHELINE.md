# Setup JEJAKA500 di cPanel — Model Payung + Subdomain

Runbook memasang ekosistem **Follow the Line** di cPanel CloudHost:

```
followtheline.id                   ← pintu masuk (landing payung)
jejaka500.followtheline.id         → program JEJAKA500 (Jakarta)
gemma449.followtheline.id          → program GEMMA449 (Sumedang, nanti)
```

Semua file di dalam **satu folder** yang diizinkan dev 2:

```
/home/permatat/followtheline.id/          ← docroot payung
├── index.html                            ← landing payung
├── .htaccess                             ← force HTTPS, matikan autoindex
└── jejaka500/                            ← docroot subdomain JEJAKA500
    ├── index.html  assets/  .htaccess    ← SPA (vite build)
    └── api/                              ← Laravel 13 lengkap
        ├── public/                       ← entry Laravel (via /api)
        ├── storage/                      ← foto upload
        └── .env                          ← permission 600
```

| URL | Dilayani oleh |
|---|---|
| `https://followtheline.id/` | landing payung |
| `https://jejaka500.followtheline.id/` | SPA JEJAKA500 |
| `https://jejaka500.followtheline.id/api/...` | Laravel |
| `https://jejaka500.followtheline.id/admin` | Filament admin |
| `https://jejaka500.followtheline.id/up` | health check |

Keunggulan: tanpa beli domain sekarang; docroot root tidak berubah; HTTPS
`followtheline.id` sudah valid (Let's Encrypt wildcard `*.followtheline.id`,
s.d. 15 Feb 2027 — diverifikasi 18 Nov 2026); nanti kalau `jejaka500.id` +
`gemma449.id` dibeli, tinggal alias dengan docroot sama → nol downtime.

Status domain (18 Nov 2026): `followtheline.id` aktif (expiry 17 Nov 2027) ·
`jejaka500.id`/`.com`, `gemma449.id` belum terdaftar · `gemma449.com` /
`gemma499.com` **milik orang lain** (diparkir) · `api.followtheline.id`
tidak diperlukan.

> ⚠️ **Artefak Release `v1.0.0` tidak bisa dipakai** — dibangun untuk
> `api.jejaka500.id` yang tidak ada. Wajib build baru (Langkah 6).

## Langkah 1 — Login cPanel

Buka `http://103.63.24.171:2082`, user `permatat` + password dari file
kredensial lokal. Gagal login → minta ke pemberi kredensial, jangan tebak.

## Langkah 2 — Cek Prasyarat

| Cek | Menu cPanel | Syarat |
|---|---|---|
| Versi PHP | **MultiPHP Manager** | `8.3`/`8.4` |
| Ekstensi | **Select PHP Version → Extensions** | `mbstring`, `intl`, `json`, `openssl`, `pdo_mysql`, `fileinfo`, `zip`, `gd` |
| Terminal | **Terminal** | Ada = cepat. Tidak ada = Cron (Langkah 9B) |
| Batas upload | **MultiPHP INI Editor** | `upload_max_filesize ≥ 8M`, `post_max_size ≥ 10M`, `memory_limit ≥ 256M` |
| `open_basedir` | **MultiPHP INI Editor** | Mencakup `/home/permatat`, bukan hanya `public_html` |

Tiket support bila perlu:

> Mohon `open_basedir` mencakup `/home/permatat` untuk `followtheline.id`, dan
> aktifkan Terminal/SSH. Aplikasi Laravel perlu `vendor/`, `storage/`, `.env`
> di `/home/permatat/followtheline.id/jejaka500/api`.

## Langkah 3 — Buat Subdomain

**cPanel → Domains → Subdomains → Create Subdomain**:

| Field | Nilai |
|---|---|
| Subdomain | `jejaka500` |
| Domain | `followtheline.id` |
| Document Root | `/home/permatat/followtheline.id/jejaka500` |

Folder otomatis dibuat. Lalu **SSL/TLS Status** → centang
`jejaka500.followtheline.id` → **Run AutoSSL** → tunggu *Active*. Pastikan
`followtheline.id` juga *Active*.

## Langkah 4 — Database MySQL

**cPanel → MySQL Databases**: database `permatat_jejaka500`, user
`permatat_jejaka` + password kuat, **Add User To Database** → ALL PRIVILEGES.
Host `localhost`.

## Langkah 5 — Amankan Root Payung

**File Manager** → `/home/permatat/followtheline.id/`:

`.htaccess`:

```apache
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,NE,R=301]

Options -Indexes
```

`index.html` (landing minimal):

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Follow the Line</title>
</head>
<body>
  <h1>Follow the Line</h1>
  <p>Selamat datang di ekosistem Follow the Line.</p>
  <ul>
    <li><a href="https://jejaka500.followtheline.id">JEJAKA500 — Jakarta</a></li>
  </ul>
</body>
</html>
```

Verifikasi: `curl -s https://followtheline.id/ | grep -o "<title>.*</title>"`
→ harus `Follow the Line`, bukan `Index of /`.

## Langkah 6 — Build Artefak (WAJIB, v1.0.0 tidak berlaku)

**GitHub → Actions → Release (artefak cPanel) → Run workflow**:
branch `main`, input `api_base_url` =
`https://jejaka500.followtheline.id/api`. Tunggu hijau → tab **Artifacts** →
unduh `jejaka500-backend-*.zip` + `jejaka500-frontend-*.zip`.

## Langkah 7 — Upload Backend

**File Manager** → `/home/permatat/followtheline.id/jejaka500/`:

1. Upload backend ZIP → **Extract** (ZIP punya pembungkus `jejaka500/`, jadi
   hasilnya `jejaka500/jejaka500/`).
2. Masuk folder ter-dalam → select all → **Move** → destination
   `/home/permatat/followtheline.id/jejaka500/`.
3. Hapus folder kosong + ZIP.

Lewat Terminal (lebih cepat):

```bash
cd /home/permatat/followtheline.id/jejaka500
unzip ~/jejaka500-backend-*.zip -d .
mv jejaka500/* . 2>/dev/null; rm -rf jejaka500
```

Permission: folder `755`, file `644`, `api/storage/` + `api/bootstrap/cache/`
→ `775`. Aktifkan **Show Hidden Files**.

## Langkah 8 — Isi `.env`

Salin `api/deploy/cpanel/env.example` → buat `api/.env`, edit:

```dotenv
APP_NAME="JEJAKA500"
APP_ENV=production
APP_KEY=base64:HASIL_OPENSSL
APP_DEBUG=false
APP_URL=https://jejaka500.followtheline.id
TRUST_CF_CONNECTING_IP=false
CORS_ALLOWED_ORIGINS=https://jejaka500.followtheline.id
DB_CONNECTION=mysql
DB_HOST=localhost
DB_PORT=3306
DB_DATABASE=permatat_jejaka500
DB_USERNAME=permatat_jejaka
DB_PASSWORD=password_langkah_4
SESSION_DRIVER=database
SESSION_SECURE_COOKIE=true
QUEUE_CONNECTION=sync
CACHE_STORE=database
FILESYSTEM_DISK=public
ADMIN_NAME="Admin Jakarta"
ADMIN_EMAIL=email-anda@contoh.com
ADMIN_PASSWORD=minimal-12-karakter
WHATSAPP_NOTIFICATIONS_ENABLED=false
MIDTRANS_IS_PRODUCTION=false
```

`APP_KEY`: `echo "base64:$(openssl rand -base64 32)"`. Permission `.env` →
`600`. `QUEUE_CONNECTION=sync` wajib (tidak ada worker di shared hosting).

## Langkah 9 — Migrasi & Optimasi

**9A — Terminal (disarankan):**

```bash
cd /home/permatat/followtheline.id/jejaka500/api
php artisan optimize:clear
php artisan migrate --force
php artisan db:seed --force
php artisan storage:link
php artisan config:cache
php artisan view:cache
```

> Jangan `route:cache` — membuat `POST /api/register` 404.

**9B — Cron sekali-jalan (tanpa Terminal):** jadwal `*/5 * * * *`:
`cd .../api && /usr/local/bin/php artisan migrate --force >> /home/permatat/migrate.log 2>&1`.
Setelah `Nothing to migrate`: ganti ke `db:seed --force` (log `seed.log`),
lalu `storage:link` (log `link.log`). **Hapus cron setelah selesai.**
Symlink gagal → File Manager: klik kanan `api/storage/app/public` →
**Symlink** → target `.../api/public/storage`.

## Langkah 10 — Frontend + `.htaccess` SPA

**File Manager** → `/home/permatat/followtheline.id/jejaka500/`:

1. Upload frontend ZIP → **Extract di folder itu** (isi: `index.html`,
   `assets/`, `.htaccess`) → hapus ZIP.
2. Pastikan `.htaccess` ada di `jejaka500/.htaccess` (**bukan** `.htaccess`
   root payung).
3. **Edit** isinya menjadi:

```apache
Options -MultiViews -Indexes

<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /

    # ---- Laravel ----
    RewriteRule ^api/(.*)$ api/public/index.php [L,QSA]
    RewriteRule ^admin(/(.*))?$ api/public/index.php [L,QSA]
    RewriteRule ^livewire/(.*)$ api/public/index.php [L,QSA]
    RewriteRule ^up$ api/public/index.php [L,QSA]

    # ---- SPA ----
    RewriteCond %{REQUEST_FILENAME} -f [OR]
    RewriteCond %{REQUEST_FILENAME} -d
    RewriteRule ^ - [L]

    RewriteCond %{REQUEST_URI} \.[a-zA-Z0-9]{1,8}$
    RewriteRule ^ - [L,R=404]

    RewriteRule ^ index.html [L]
</IfModule>

<IfModule mod_headers.c>
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set X-Frame-Options "DENY"
    Header always set Permissions-Policy "camera=(),microphone=(),geolocation=()"
    <FilesMatch "^(index\.html|sw\.js|manifest\.webmanifest)$">
        Header set Cache-Control "no-cache, no-store, must-revalidate"
    </FilesMatch>
</IfModule>

<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType font/woff2 "access plus 1 year"
</IfModule>

<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/css application/javascript image/svg+xml
</IfModule>
```

4. Symlink foto:

```bash
ln -s api/public/storage /home/permatat/followtheline.id/jejaka500/storage
```

> Kalau `/api/*` 500/403: LiteSpeed menolak rewrite PHP di subfolder → ubah
> docroot subdomain ke `jejaka500/api/public/`. **Butuh persetujuan dev 2.**

## Langkah 11 — Verifikasi

```bash
# Root payung
curl -sI https://followtheline.id/ | grep -Ei "HTTP/|Location:"
curl -s https://followtheline.id/ | grep -o "<title>.*</title>"

# Subdomain
curl -s -o /dev/null -w "/up          -> %{http_code}\n" https://jejaka500.followtheline.id/up
curl -s -o /dev/null -w "/admin/login  -> %{http_code}\n" https://jejaka500.followtheline.id/admin/login
curl -s -o /dev/null -w "/             -> %{http_code}\n" https://jejaka500.followtheline.id/
curl -s -o /dev/null -w "/booking      -> %{http_code}\n" https://jejaka500.followtheline.id/booking
curl -s -o /dev/null -w "/aset hilang  -> %{http_code}\n" https://jejaka500.followtheline.id/assets/tidak-ada.js
curl -s https://jejaka500.followtheline.id/api/price-categories | head -c 300
curl -sI https://jejaka500.followtheline.id/ | grep -Ei "x-frame|x-content-type|referrer"
```

Ekspektasi: `/up` 200 · `/admin/login` 200 · `/booking` 200 · aset hilang 404
· `/api/price-categories` JSON · header keamanan ada.

Uji pendaftaran sekali (buka `/` → pilih paket → isi → submit → kode batch
muncul → baris di `registrations`), lalu suite QA:

```bash
QA_API_URL=https://jejaka500.followtheline.id \
QA_WEB_URL=https://jejaka500.followtheline.id \
  node qa/api-smoke.mjs
```

## Langkah 12 — Deploy Berikutnya (manual, sebelum SSH ada)

1. Actions → Release → Run workflow (`api_base_url` = URL subdomain)
2. Unduh dua ZIP
3. Upload & extract **di atas** folder lama: backend → `jejaka500/api/`,
   frontend → `jejaka500/`
4. `.env` tidak ikut ZIP → aman
5. Terminal: `optimize:clear` → `migrate --force` → `config:cache` →
   `view:cache`

> **Jangan** extract ZIP backend langsung ke `jejaka500/` — `app/` dan
> `vendor/` akan nyangkut di docroot SPA dan situs jadi 500.

## Migrasi ke Domain Sendiri (kalau dana siap)

Bukan migrasi file — docroot tetap, hanya alias baru:

| | Sekarang | Nanti |
|---|---|---|
| URL | `jejaka500.followtheline.id` | `jejaka500.id` |
| Docroot | `followtheline.id/jejaka500` | **sama** |
| File | sudah ada | tidak dipindah |
| Kerja | — | ± 30 menit |

1. Beli `jejaka500.id` + `gemma449.id` (± Rp250–350k/tahun). `.com` tidak
   tersedia (diparkir orang lain).
2. **Domains → Create A New Domain** → docroot **sama**
   (`/home/permatat/followtheline.id/jejaka500`). Nol downtime.
3. **SSL/TLS Status → Run AutoSSL** untuk domain baru.
4. **Rebuild SPA** dengan `api_base_url = https://jejaka500.id/api` — URL API
   ter-bake saat build, `.env` saja tidak cukup.
5. Redirect 301 setelah domain baru terverifikasi:
   ```apache
   RewriteCond %{HTTP_HOST} ^jejaka500\.followtheline\.id$ [NC]
   RewriteRule ^ https://jejaka500.id%{REQUEST_URI} [L,NE,R=301]
   ```
6. `.env`: `APP_URL=https://jejaka500.id`,
   `CORS_ALLOWED_ORIGINS=https://jejaka500.id` → `config:cache`.
7. Google Search Console + sitemap.
8. Biarkan redirect 30–90 hari agar SEO terbawa.

Pola sama untuk `gemma449.id` (folder `followtheline.id/gemma449`).

## Checklist

- [ ] PHP ≥ 8.3, ekstensi lengkap, `open_basedir` mencakup home
- [ ] Subdomain `jejaka500.followtheline.id` dibuat, docroot `jejaka500/`
- [ ] AutoSSL aktif (subdomain + root payung)
- [ ] Database `permatat_jejaka500` + user + ALL PRIVILEGES
- [ ] Root payung: `.htaccess` (force HTTPS + `-Indexes`) + `index.html`
- [ ] Root payung bukan `Index of /` lagi
- [ ] `jejaka500/api/` berisi Laravel lengkap + `vendor/`
- [ ] `.env` ada, `APP_KEY` terisi, `600`, `QUEUE_CONNECTION=sync`
- [ ] `migrate --force` + `db:seed --force` sukses
- [ ] `storage:link` sukses (foto tampil)
- [ ] SPA di `jejaka500/` + `.htaccess` routing Laravel
- [ ] `/up`, `/admin/login`, `/booking`, `/api/price-categories` benar
- [ ] Pendaftaran uji berhasil
- [ ] Backup database diunduh
- [ ] Render/Vercel hidup 7 hari sebagai rollback

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| 500 semua halaman | `.env` hilang / `APP_KEY` kosong / permission | Cek `api/storage/logs/laravel.log`, `chmod -R 775 storage bootstrap/cache` |
| 500 `open_basedir` | PHP membatasi path | Langkah 2 |
| 404 semua route SPA | `.htaccess` SPA tidak ada | Langkah 10 |
| 404 `/api/*` | Routing belum ditambah | Langkah 10 |
| 403/500 `/api/*` | LiteSpeed menolak PHP di subfolder | Catatan Langkah 10 (butuh persetujuan) |
| 404 `/admin` | Baris `^admin` hilang | Langkah 10 |
| Foto 404 | `storage:link`/symlink belum | Langkah 9/10 |
| `could not find driver` | `pdo_mysql` mati | Select PHP Version |
| 419 simpan admin | Cookie secure + akses HTTP | Pakai HTTPS |
| CORS error | `CORS_ALLOWED_ORIGINS` salah | Isi subdomain, `config:cache` |
| `.env` tak berefek | Config ter-cache | `php artisan config:cache` |
| `POST /api/register` 404 | `route:cache` | `php artisan route:clear` |
| SPA panggil `api.jejaka500.id` | Artefak `v1.0.0` dipakai | Rebuild (Langkah 6) |
| Job menumpuk di `jobs` | `QUEUE_CONNECTION=database` | Ganti `sync` |

Setelah ubah `.env`:

```bash
cd /home/permatat/followtheline.id/jejaka500/api \
  && php artisan config:cache && php artisan view:cache
```
