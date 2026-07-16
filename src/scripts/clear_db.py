from db import clear, session

if __name__ == "__main__":
    with session() as conn:
        clear(conn)
    print("Cleared all rows from conversations, feedback, rag_data_chunks, and rag_data.")
