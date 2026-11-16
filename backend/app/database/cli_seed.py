from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.auto_migrate import auto_heal_schema
from app.database.base import Base
from app.database.seed import seed_initial_data
from app.database.session import SessionLocal, engine
import app.models  # noqa: F401


def main() -> None:
    auto_heal_schema(engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_initial_data(db)
    print("Database seeded successfully.")


if __name__ == "__main__":
    main()
