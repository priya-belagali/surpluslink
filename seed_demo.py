"""Fill the database with demo accounts and eight weeks of history so every screen has data.

Run once:  python seed_demo.py
All demo accounts use the password demo123 and are labelled "(demo)". Re-running is safe.
"""
from core.db import init_db, session_scope
from core.demo import seed_if_empty


def main() -> None:
    init_db()
    with session_scope() as s:
        created = seed_if_empty(s)
    if created:
        print("Demo data created. Sign in as donor1@demo.com, ngo1@demo.com or vol1@demo.com (password demo123).")
    else:
        print("Demo data already exists: nothing to do.")


if __name__ == "__main__":
    main()
