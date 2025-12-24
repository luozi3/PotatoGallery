#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from app import maintenance


def main() -> int:
    parser = argparse.ArgumentParser(description="Gallery maintenance tasks")
    parser.add_argument("--scan", action="store_true", help="Scan consistency and report")
    parser.add_argument("--clean", action="store_true", help="Cleanup staging/tmp/orphan thumbs")
    parser.add_argument("--vacuum", action="store_true", help="Run SQLite VACUUM")
    parser.add_argument("--backup", action="store_true", help="Backup SQLite database")
    parser.add_argument("--backup-dir", default=None, help="Backup directory")
    args = parser.parse_args()

    report = {}
    if args.scan or args.clean:
        report = maintenance.run_maintenance()
    if args.vacuum:
        maintenance.vacuum_db()
        report["vacuum"] = ["ok"]
    if args.backup:
        target_dir = Path(args.backup_dir) if args.backup_dir else None
        dst = maintenance.backup_db(target_dir) if target_dir else maintenance.backup_db()
        report["backup"] = [str(dst)]

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
