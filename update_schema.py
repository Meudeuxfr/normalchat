import sqlite3

def update_group_members_schema():
    try:
        connection = sqlite3.connect('db.sqlite3')
        cursor = connection.cursor()

        # Drop the existing group_members table if it exists
        cursor.execute("DROP TABLE IF EXISTS group_members;")
        connection.commit()

        # Recreate the group_members table with the new schema
        cursor.execute('''
        CREATE TABLE group_members (
            group_id INTEGER,
            username TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(id)
        );
        ''')
        connection.commit()

        print("Database schema updated: Recreated group_members table with username column.")
    except Exception as e:
        print(f"Error updating group_members schema: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    update_group_members_schema()