# Backup and Restore

## Backup layout
- Database snapshots: `/opt/PotatoGallery/storage/backups/gallery_YYYYMMDD_HHMMSS.db`
- Storage mirrors: `/opt/PotatoGallery/storage/backups/raw_mirror/`, `/opt/PotatoGallery/storage/backups/www_mirror/`
- Daily task: `/opt/PotatoGallery/bin/cron_daily.sh`

The maintenance task uses `rsync` when available; otherwise it falls back to a full copy.

## Restore steps (quick runbook)
1. Stop services:
   - `systemctl stop gallery-worker gallery-upload`
2. Restore SQLite:
   - `cp /opt/PotatoGallery/storage/backups/gallery_YYYYMMDD_HHMMSS.db /opt/PotatoGallery/db/gallery.db`
3. Restore raw + www:
   - `rsync -a --delete /opt/PotatoGallery/storage/backups/raw_mirror/ /opt/PotatoGallery/storage/raw/`
   - `rsync -a --delete /opt/PotatoGallery/storage/backups/www_mirror/ /opt/PotatoGallery/storage/www/`
4. Fix permissions if needed:
   - `chown -R gallery:www-data /opt/PotatoGallery/storage /opt/PotatoGallery/db`
5. Restart services:
   - `systemctl start gallery-upload gallery-worker`
6. Optional: rebuild static if you restored only raw or templates:
   - `/opt/PotatoGallery/bin/refresh_static.sh`
