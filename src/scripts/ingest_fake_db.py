from db import get_connection
from fixtures import seed

if __name__ == "__main__":
    connection = get_connection()
    try:
        seed(connection)
        print("Seeded fake conversations and feedback.")
    finally:
        connection.close()
