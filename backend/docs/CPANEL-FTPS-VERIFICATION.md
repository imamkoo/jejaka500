# Log verifikasi deploy cPanel via FTPS

Catatan uji untuk memastikan rantai `push main → CI → Deploy (cPanel via FTPS)`
benar-benar berjalan setelah kredensial FTPS dipasang.

## Kondisi sebelum uji

| Item | Nilai |
|---|---|
| Commit `main` | `6e95722` |
| Workflow | `.github/workflows/deploy-cpanel.yml` (trigger: `workflow_run` CI `main` sukses + `workflow_dispatch`) |
| Variables | `CPANEL_FTP_HOST`, `CPANEL_FTP_USERNAME`, `CPANEL_FTP_PORT` terpasang |
| Secret | `CPANEL_FTP_PASSWORD` terpasang |
| FTPS | Terverifikasi `openssl s_client -starttls ftp` → TLSv1.3, `Verify return code: 0 (ok)` |
| Root FTP | `/home/permatat/followtheline.id/jejaka500` (berisi `api/`, `index.html`, `.htaccess`) |

Baseline HTTP sebelum deploy (dipakai untuk pembanding pasca-deploy):

```
/                         200  last-modified Wed, 18 Nov 2026 16:08:07 GMT
/up                       200
/admin/login              200
/api/price-categories     200
```

## Cara membaca hasil

- **Sukses** bila job `Build & deploy ke cPanel (FTPS)` berjalan (bukan `skipped`)
  dan langkah Smoke test lolos.
- **Gagal di autentikasi** berarti kredensial FTPS atau batasan path akun perlu
  diperiksa; perubahan tidak terkirim.
- **Gagal di Smoke test** berarti upload berhasil tetapi hasil live belum sesuai;
  periksa mapping direktori dan konfigurasi routing, bukan kredensial.

Workflow bersifat aditif: tidak menghapus file server, tidak menyentuh `.env`,
`storage/`, maupun `.htaccess` docroot. Migrasi database dan cache Artisan tetap
manual — lihat `backend/docs/CPANEL-DEPLOY.md` §6.
