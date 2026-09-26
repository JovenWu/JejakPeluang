import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.services.retention import sweep_expired  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Delete expired uploads, redact purged submission PII, '
            'close stale screening work, and remove staging orphans.')
    parser.add_argument('--stale-hours', type=int, default=None,
        help='Override STALE_HOURS (default 72).')
    parser.add_argument('--staging-max-age-hours', type=int, default=None,
        help='Override STAGING_MAX_AGE_HOURS (default 24).')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
        format='%(levelname)s %(name)s: %(message)s')
    with Session(engine()) as session:
        counts = sweep_expired(session, stale_hours=args.stale_hours,
            staging_max_age_hours=args.staging_max_age_hours)
    print(' '.join(f'{key}={value}' for key, value in counts.items()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
