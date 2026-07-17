from db import db_session
from ingestion.fixtures import seed

if __name__ == "__main__":
    with db_session() as conn:
        seed(conn)
    print("Seeded fake conversations and feedback.")
