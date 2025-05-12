import socket
import threading
import datetime
import os
import sqlite3

# ----------- config -----------
Host = '0.0.0.0'
Port = 5555
START_TIME = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"./logs/chat_log_{START_TIME}.txt"
#------------------------------

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((Host, Port))
server.listen(5)

import uuid

clients = {}
usernames = {}
user_statuses = {}  # New dictionary to track user statuses (Online/Away)
channels = {}  # Initialize channels dictionary

# Initialize SQLite database connection
db_connection = sqlite3.connect('db.sqlite3', check_same_thread=False)
db_cursor = db_connection.cursor()

# Update database schema to include username when saving groups
db_cursor.execute('''
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    creator_username TEXT NOT NULL
);
''')
db_cursor.execute('''
CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER,
    username TEXT,
    FOREIGN KEY(group_id) REFERENCES groups(id)
);
''')
db_connection.commit()

# Load groups from the database into memory
# Add debug logs to verify group loading
def load_groups():
    global groups
    groups = {}
    print("Loading groups from database...")  # Debug log
    db_cursor.execute('SELECT id, name FROM groups')
    for group_id, group_name in db_cursor.fetchall():
        db_cursor.execute('SELECT username FROM group_members WHERE group_id = ?', (group_id,))
        members = [username for (username,) in db_cursor.fetchall()]

        groups[group_name] = members
        print(f"Loaded group: {group_name} with members: {members}")  # Debug log
    print("Finished loading groups.")  # Debug log

load_groups()

# Update save_group to include username
def save_group(group_name, creator_username, member_usernames):
    try:
        db_cursor.execute('INSERT INTO groups (name, creator_username) VALUES (?, ?)', (group_name, creator_username))
        group_id = db_cursor.lastrowid
        for username in member_usernames:
            db_cursor.execute('INSERT INTO group_members (group_id, username) VALUES (?, ?)', (group_id, username))
        db_connection.commit()
        print(f"Group '{group_name}' created with members: {member_usernames}")  # Debug log
    except Exception as e:
        print(f"Error saving group '{group_name}': {e}")

# Save group member to the database
def save_group_member(group_name, username):
    db_cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
    group_id = db_cursor.fetchone()[0]
    db_cursor.execute('INSERT INTO group_members (group_id, username) VALUES (?, ?)', (group_id, username))
    db_connection.commit()

# Remove group member from the database
def remove_group_member(group_name, username):
    db_cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
    group_id = db_cursor.fetchone()[0]
    db_cursor.execute('DELETE FROM group_members WHERE group_id = ? AND username = ?', (group_id, username))
    db_connection.commit()

# Remove group from the database
def remove_group(group_name):
    db_cursor.execute('DELETE FROM groups WHERE name = ?', (group_name,))
    db_cursor.execute('DELETE FROM group_members WHERE group_id = (SELECT id FROM groups WHERE name = ?)', (group_name,))
    db_connection.commit()

def fetch_user_groups(username):
    try:
        db_cursor.execute('SELECT g.name FROM groups g JOIN group_members gm ON g.id = gm.group_id WHERE gm.username = ?', (username,))
        user_groups = [group_name for (group_name,) in db_cursor.fetchall()]
        print(f"Groups for user '{username}': {user_groups}")  # Debug log
        return user_groups
    except Exception as e:
        print(f"Error fetching groups for user '{username}': {e}")
        return []

# Store recent messages with unique IDs: {message_id: {username, timestamp, content}}
recent_messages = {}

open(LOG_FILE, 'a').close()

def log_message(username, message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} - {username}: {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(entry)

def broadcast(message, sender_socket):
    print(f"Broadcasting message: {message}")  # Debug log
    disconnected_clients = []
    for client in clients.values():
        if client != sender_socket:
            try:
                client.send(message)
            except Exception as e:
                print(f"Error sending message to client: {e}")  # Debug log
                disconnected_clients.append(client)
    for dc in disconnected_clients:
        remove_disconnected_client(dc)

def remove_disconnected_client(client_socket):
    username_to_remove = None
    for uname, sock in clients.items():
        if sock == client_socket:
            username_to_remove = uname
            break
    if username_to_remove:
        del clients[username_to_remove]
        del usernames[client_socket]
        del user_statuses[username_to_remove]
        send_user_list()  # Update user list

def send_user_list():
    print("Sending updated user list...")  # Debug log
    user_list_with_status = []
    for user in clients.keys():
        status = user_statuses.get(user, "Online")
        user_list_with_status.append(f"{user}|{status}")
    user_list_message = "__user_list__:" + ",".join(user_list_with_status)
    print(f"User list message: {user_list_message}")  # Debug log
    disconnected_clients = []
    for client in clients.values():
        try:
            client.send(user_list_message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending user list to client: {e}")  # Debug log
            client.close()
            disconnected_clients.append(client)
    for dc in disconnected_clients:
        remove_disconnected_client(dc)

def broadcast_typing(username, sender_socket):
    disconnected_clients = []
    typing_message = f"__typing__:{username}"
    for client in clients.values():
        if client != sender_socket:
            try:
                client.send(typing_message.encode())
            except:
                disconnected_clients.append(client)
    for dc in disconnected_clients:
        remove_disconnected_client(dc)

def handle_client(client_socket, address):
    try:
        credentials = client_socket.recv(1024).decode('utf-8')
        ADMIN_USERNAME = "meudeux"
        ADMIN_PASSWORD = "onlymeudeuxknows123"

        if "::" in credentials:
            username, password = credentials.split("::", 1)
        else:
            username = credentials
            password = None

        if username.split("::")[0] == ADMIN_USERNAME:
            if password != ADMIN_PASSWORD:
                client_socket.send("Invalid password for admin.".encode('utf-8'))
                client_socket.close()
                return
            is_admin = True
        else:
            is_admin = False

        username_only = username.split("::")[0]
        usernames[client_socket] = username_only
        clients[username_only] = client_socket
        user_statuses[username_only] = "Online"  # Set initial status to Online
        print(f"[NEW USER] {username_only} connected from {address} {'(Admin)' if is_admin else ''}")
        log_message("Server", f"{username_only} has joined the chat.")
        broadcast(f"{username_only} has joined the chat.".encode('utf-8'), client_socket)
        send_user_list()

        # Send message history to client after connection
        try:
            import time
            time.sleep(0.5)  # Small delay to allow client to be ready
            print(f"Sending message history from log file: {LOG_FILE}")
            with open(LOG_FILE, "r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
                # Send last 100 lines or all if less
                history_lines = lines[-100:] if len(lines) > 100 else lines
                print(f"Number of history lines to send: {len(history_lines)}")
                history_message = "__history__:" + "".join(history_lines)
                # Send entire history message at once
                client_socket.send(history_message.encode('utf-8'))
                # Send delimiter to indicate end of history message
                client_socket.send("__history_end__".encode('utf-8'))
                import time
                time.sleep(0.1)  # Small delay to flush send buffer
                print("Finished sending message history")
        except Exception as e:
            print(f"Error sending message history: {e}")

        if is_admin:
            client_socket.send("__admin__".encode('utf-8'))

        username = username_only

    except Exception as e:
        print(f"Error during client connection setup: {e}")
        client_socket.close()
        return

    while True:
        try:
            msg = client_socket.recv(1024).decode('utf-8')
            if not msg:
                break
            if msg.startswith("__typing__:") or msg == "__typing_stopped__":
                if msg.startswith("__typing__:"):
                    typing_user = msg.split(":", 1)[1]
                    broadcast_typing(typing_user, client_socket)
                elif msg == "__typing_stopped__":
                    broadcast_typing("__typing_stopped__", client_socket)
            elif msg.startswith("/pm "):
                try:
                    _, rest = msg.split(" ", 1)
                    recipient, private_msg = rest.split(" ", 1)
                    if recipient in clients:
                        sender = usernames[client_socket]
                        full_msg = f"[PM from {sender}] {private_msg}"
                        clients[recipient].send(full_msg.encode('utf-8'))
                        log_message(sender, f"Private to {recipient}: {private_msg}")
                    else:
                        client_socket.send(f"User {recipient} not found.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid private message format.".encode('utf-8'))
            elif msg.startswith("/create_channel "):
                try:
                    _, channel_name = msg.split(" ", 1)
                    if channel_name not in channels:
                        channels[channel_name] = []
                        client_socket.send(f"Channel '{channel_name}' created successfully.".encode('utf-8'))
                    else:
                        client_socket.send(f"Channel '{channel_name}' already exists.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid channel creation format.".encode('utf-8'))
            elif msg.startswith("/join_channel "):
                try:
                    _, channel_name = msg.split(" ", 1)
                    if channel_name in channels:
                        if client_socket not in channels[channel_name]:
                            channels[channel_name].append(client_socket)
                            client_socket.send(f"Joined channel '{channel_name}'.".encode('utf-8'))
                        else:
                            client_socket.send(f"Already in channel '{channel_name}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"Channel '{channel_name}' does not exist.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid join channel format.".encode('utf-8'))
            elif msg.startswith("/leave_channel "):
                try:
                    _, channel_name = msg.split(" ", 1)
                    if channel_name in channels and client_socket in channels[channel_name]:
                        channels[channel_name].remove(client_socket)
                        client_socket.send(f"Left channel '{channel_name}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"Not in channel '{channel_name}'.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid leave channel format.".encode('utf-8'))
            elif msg.startswith("/channel_msg "):
                try:
                    _, rest = msg.split(" ", 1)
                    channel_name, channel_msg = rest.split(" ", 1)
                    if channel_name in channels and client_socket in channels[channel_name]:
                        sender = usernames[client_socket]
                        full_msg = f"[Channel {channel_name}] {sender}: {channel_msg}"
                        for member in channels[channel_name]:
                            if member != client_socket:
                                member.send(full_msg.encode('utf-8'))
                        log_message(sender, f"Channel {channel_name}: {channel_msg}")
                    else:
                        client_socket.send(f"Not in channel '{channel_name}'.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid channel message format.".encode('utf-8'))
            elif msg.startswith("/create_group "):
                try:
                    _, group_name = msg.split(" ", 1)
                    if group_name not in groups:
                        groups[group_name] = [usernames[client_socket]]  # Add the creator to the group
                        save_group(group_name, usernames[client_socket], [usernames[client_socket]])  # Save with username
                        client_socket.send(f"Group '{group_name}' created successfully.".encode('utf-8'))
                    else:
                        client_socket.send(f"Group '{group_name}' already exists.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid group creation format.".encode('utf-8'))
            elif msg.startswith("/get_groups"):
                try:
                    username = usernames[client_socket]  # Get the username of the client
                    print(f"Fetching groups for username: {username}")  # Debug log

                    user_groups = fetch_user_groups(username)
                    print(f"Groups for username {username}: {user_groups}")  # Debug log
                    client_socket.send(f"__groups__:{','.join(user_groups)}".encode('utf-8'))
                except Exception as e:
                    print(f"Error fetching groups for username {username}: {e}")  # Debug log
                    client_socket.send(f"Error fetching groups: {e}".encode('utf-8'))
            elif msg.startswith("/join_group "):
                try:
                    _, group_name = msg.split(" ", 1)
                    if group_name in groups:
                        if usernames[client_socket] not in groups[group_name]:
                            groups[group_name].append(usernames[client_socket])
                            save_group_member(group_name, usernames[client_socket])
                            client_socket.send(f"Joined group '{group_name}'.".encode('utf-8'))
                        else:
                            client_socket.send(f"Already in group '{group_name}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"Group '{group_name}' does not exist.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid join group format.".encode('utf-8'))
            elif msg.startswith("/leave_group "):
                try:
                    _, group_name = msg.split(" ", 1)
                    if group_name in groups and usernames[client_socket] in groups[group_name]:
                        groups[group_name].remove(usernames[client_socket])
                        remove_group_member(group_name, usernames[client_socket])
                        if not groups[group_name]:  # Remove group if it becomes empty
                            del groups[group_name]
                            remove_group(group_name)
                        client_socket.send(f"Left group '{group_name}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"Not in group '{group_name}'.".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Error leaving group: {e}".encode('utf-8'))
            elif msg.startswith("/get_group_info "):
                try:
                    _, group_name = msg.split(" ", 1)
                    if group_name in groups:
                        members = groups[group_name]
                        creator = members[0] if members else ""
                        members_str = ",".join(members)
                        response = f"__group_info__:{group_name}:{creator}:{members_str}"
                        client_socket.send(response.encode('utf-8'))
                    else:
                        client_socket.send(f"Group '{group_name}' does not exist.".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Error fetching group info: {e}".encode('utf-8'))
            else:
                # Check if message is an edit or delete command
                if msg.startswith("/edit "):
                    try:
                        # Format: /edit message_id new message content
                        _, message_id, new_content = msg.split(" ", 2)
                        if message_id in recent_messages:
                            old_message = recent_messages[message_id]
                            if old_message['username'] == usernames[client_socket]:
                                recent_messages[message_id]['content'] = new_content
                                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                recent_messages[message_id]['timestamp'] = timestamp
                                edit_broadcast = f"__edit__:{message_id}:{new_content}"
                                broadcast(edit_broadcast.encode('utf-8'), None)
                                log_message(usernames[client_socket], f"Edited message {message_id}: {new_content}")
                            else:
                                client_socket.send("You can only edit your own messages.".encode('utf-8'))
                        else:
                            client_socket.send("Message ID not found.".encode('utf-8'))
                    except Exception as e:
                        client_socket.send(f"Invalid edit command format. Use: /edit message_id new_content".encode('utf-8'))
                elif msg.startswith("/delete "):
                    try:
                        # Format: /delete message_id
                        _, message_id = msg.split(" ", 1)
                        if message_id in recent_messages:
                            old_message = recent_messages[message_id]
                            if old_message['username'] == usernames[client_socket]:
                                del recent_messages[message_id]
                                delete_broadcast = f"__delete__:{message_id}"
                                broadcast(delete_broadcast.encode('utf-8'), None)
                                log_message(usernames[client_socket], f"Deleted message {message_id}")
                            else:
                                client_socket.send("You can only delete your own messages.".encode('utf-8'))
                        else:
                            client_socket.send("Message ID not found.".encode('utf-8'))
                    except Exception as e:
                        client_socket.send(f"Invalid delete command format. Use: /delete message_id".encode('utf-8'))
                else:
                    # Assign unique ID to message
                    message_id = str(uuid.uuid4())
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    recent_messages[message_id] = {
                        'username': usernames[client_socket],
                        'timestamp': timestamp,
                        'content': msg
                    }
                    log_message(usernames[client_socket], msg)
                    broadcast_msg = f"[{usernames[client_socket]}] {msg}||{message_id}"
                    broadcast(broadcast_msg.encode('utf-8'), client_socket)
        except Exception as e:
            print(f"Error receiving message from {usernames.get(client_socket, 'Unknown')}: {e}")
            break

    username = usernames.get(client_socket, "Unknown")
    print(f"[DISCONNECTED] {username} disconnected")
    user_statuses[username] = "Away"  # Set status to Away on disconnect
    log_message("Server", f"{username} has left the chat.")
    broadcast(f"{username} has left the chat.".encode(), client_socket)
    send_user_list()

    client_socket.close()
    if username in clients:
        del clients[username]
    if client_socket in usernames:
        del usernames[client_socket]
    if username in user_statuses:
        del user_statuses[username]

print("[STARTING] Server is running...")
while True:
    try:
        client_socket, client_address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {len(clients)}")
    except Exception as e:
        print(f"Error accepting connections: {e}")
