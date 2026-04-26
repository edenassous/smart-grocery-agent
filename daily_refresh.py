"""
רענון יומי של מאגר המחירים.

הרצה ידנית:
    python daily_refresh.py

הרצה כ-cron יומי (ב-2:30 בלילה):
    crontab -e
    30 2 * * * cd /Users/edenassous/Downloads/veggie-agent && /opt/anaconda3/bin/python daily_refresh.py >> logs/refresh.log 2>&1
"""
import sys
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from il_supermarket_scarper import ScarpingTask, ScraperFactory
from il_supermarket_scarper.utils import FileTypesFilters

import parser as parser_module

CHAINS = [
    ScraperFactory.RAMI_LEVY.name,
    ScraperFactory.SHUFERSAL.name,
    ScraperFactory.VICTORY.name,
]

FILES_PER_CHAIN = 10
DUMPS_DIR = Path("dumps")
LOGS_DIR = Path("logs")
RETENTION_DAYS = 7   # לאחר כמה ימים למחוק קבצים ישנים


def log(message: str) -> None:
    """כותב הודעה ל-stdout עם timestamp. ה-cron יקלוט את זה ל-log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def cleanup_old_files() -> int:
    """מוחק קבצי XML ישנים מ-RETENTION_DAYS ימים. מחזיר כמה נמחקו."""
    if not DUMPS_DIR.exists():
        return 0

    cutoff = time.time() - (RETENTION_DAYS * 86400)
    deleted = 0

    for xml_file in DUMPS_DIR.rglob("*.xml"):
        if xml_file.stat().st_mtime < cutoff:
            xml_file.unlink()
            deleted += 1

    if deleted > 0:
        log(f"🗑️  ניקיתי {deleted} קבצים ישנים (יותר מ-{RETENTION_DAYS} ימים)")

    return deleted


def download_with_idempotency() -> dict:
    """
    מוריד נתונים. הספרייה כבר עושה idempotency - בדיקת status DB
    שמונעת הורדה כפולה של אותם קבצים.
    """
    log(f"📥 מוריד עד {FILES_PER_CHAIN} קבצים מכל רשת ({len(CHAINS)} רשתות)")

    start = time.time()
    scraper = ScarpingTask(
        enabled_scrapers=CHAINS,
        files_types=[FileTypesFilters.PRICE_FULL_FILE.name],
    )
    scraper.start(limit=FILES_PER_CHAIN)
    scraper.join()

    elapsed = time.time() - start
    log(f"✓ הורדה הסתיימה ב-{elapsed:.0f} שניות")

    # סיכום מה ירד
    summary = {}
    if DUMPS_DIR.exists():
        for chain_dir in DUMPS_DIR.iterdir():
            if chain_dir.is_dir() and chain_dir.name != "status":
                files = [f for f in chain_dir.glob("*.xml") if "Price" in f.name]
                size_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
                summary[chain_dir.name] = {"files": len(files), "size_mb": size_mb}
                log(f"   {chain_dir.name}: {len(files)} קבצים, {size_mb:.1f} MB")

    return summary


def parse_to_db() -> dict:
    """פרסר את כל הקבצים שב-dumps ל-DB."""
    log("📦 פורס קבצים ל-DB...")
    start = time.time()

    counts = parser_module.load_all_dumps()

    elapsed = time.time() - start
    total = sum(counts.values())
    log(f"✓ פרסור הסתיים ב-{elapsed:.0f} שניות. סה״כ {total:,} שורות מחיר.")
    for chain, count in counts.items():
        log(f"   {chain}: {count:,} שורות")

    return counts


def main() -> int:
    """החזרת exit code: 0 = הצלחה, 1 = כשלון."""
    LOGS_DIR.mkdir(exist_ok=True)

    log("=" * 60)
    log("🚀 מתחיל רענון יומי")
    log("=" * 60)

    try:
        # 1. ניקוי
        cleanup_old_files()

        # 2. הורדה
        download_with_idempotency()

        # 3. פרסור
        counts = parse_to_db()

        # 4. בדיקת תקינות בסיסית
        total = sum(counts.values())
        if total < 10000:
            log(f"⚠️  אזהרה: רק {total} שורות נטענו - חשוד")
            return 1

        log("=" * 60)
        log(f"✅ רענון יומי הסתיים בהצלחה - {total:,} שורות")
        log("=" * 60)
        return 0

    except Exception as e:
        log(f"❌ שגיאה: {type(e).__name__}: {e}")
        import traceback
        log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
