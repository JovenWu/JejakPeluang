import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth import password_helper  # noqa: E402
from app.db import engine  # noqa: E402
from app.models.auth import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Create an invite-only moderator account.')
    parser.add_argument('email')
    parser.add_argument('--password', default=None,
        help='Set an explicit password instead of a generated one.')
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = args.password or secrets.token_urlsafe(18)
    with Session(engine()) as session:
        existing = session.execute(select(User).where(
            func.lower(User.email) == email)).scalar_one_or_none()
        if existing is not None:
            print(f'moderator {email} already exists', file=sys.stderr)
            return 1
        session.add(User(email=email,
            hashed_password=password_helper.hash(password),
            is_active=True, is_verified=True, role='moderator'))
        session.commit()

    print(f'created moderator {email}')
    if args.password is None:
        print(f'password: {password}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
