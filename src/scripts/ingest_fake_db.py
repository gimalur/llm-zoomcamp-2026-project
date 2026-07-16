from db import session
from ingestion.fixtures import seed

if __name__ == "__main__":
    with session() as conn:
        seed(conn)
    print("Seeded fake conversations and feedback.")
