"""Δημιουργεί το pgvector extension και όλους τους πίνακες cp_*.

Τρέχει με ασφάλεια όσες φορές θες (create_all = μόνο ό,τι λείπει).
ΔΕΝ αγγίζει τους παλιούς πίνακες DentalPoint/Palatino.

Χρήση (τοπικά ή σε Render Shell):
    python migrations/migrate_to_multitenant.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from config.database import Base, get_engine
import models  # noqa: F401  — φορτώνει όλα τα models ώστε να τα δει το create_all


def run():
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    print("OK: pgvector extension + πίνακες cp_* έτοιμοι.")


if __name__ == "__main__":
    run()
