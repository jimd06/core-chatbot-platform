"""Pre-flight έλεγχος πριν από deploy: env vars + σύνδεση βάσης.

Χρήση:  python config_check.py
"""
import sys

from config import Config


def run():
    ok = True

    missing = Config.missing_required()
    if missing:
        print(f"ΛΕΙΠΟΥΝ env vars: {', '.join(missing)}")
        ok = False
    else:
        print("OK: όλα τα υποχρεωτικά env vars υπάρχουν.")

    if Config.OPENAI_API_KEY and not Config.OPENAI_API_KEY.startswith("sk-"):
        print("ΠΡΟΣΟΧΗ: το OPENAI_API_KEY δεν μοιάζει με κλειδί OpenAI (sk-...).")
        ok = False

    if Config.DATABASE_URL:
        try:
            from sqlalchemy import create_engine, text
            url = Config.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("OK: σύνδεση με τη βάση.")
        except Exception as exc:
            print(f"ΑΠΟΤΥΧΙΑ σύνδεσης βάσης: {exc}")
            ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    run()
