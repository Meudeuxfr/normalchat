import sqlite3

def clear_all_groups():
    try:
        connection = sqlite3.connect('db.sqlite3')
        cursor = connection.cursor()
        cursor.execute("DELETE FROM groups;")
        cursor.execute("DELETE FROM group_members;")
        connection.commit()
        print("All groups and their members have been cleared.")
    except Exception as e:
        print(f"Error clearing groups: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    clear_all_groups()