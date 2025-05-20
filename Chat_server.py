import socket
import threading
import datetime
import os
import sqlite3
import shutil
import hashlib

# ----------- config -----------
Host = '0.0.0.0'
Port = 5555
START_TIME = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"./logs/chat_log_{START_TIME}.txt"
SHARED_FILES_DIR = './shared_files'
os.makedirs(SHARED_FILES_DIR, exist_ok=True)
#------------------------------

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((Host, Port))
server.listen(5)

import uuid

clients = {}
usernames = {}
user_statuses = {} 
channels = {} 

pending_invites = {}

# Initialize SQLite database connection
db_connection = sqlite3.connect('db.sqlite3', check_same_thread=False)
db_cursor = db_connection.cursor()

# --- Add users and messages tables ---
db_cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
''')
db_cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    timestamp TEXT,
    content TEXT
);
''')
db_connection.commit()

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
    # Debug log to print all loaded groups and their members
    print("[DEBUG] Groups loaded into memory:", groups)

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
    # Save to database
    db_cursor.execute('INSERT INTO messages (username, timestamp, content) VALUES (?, ?, ?)', (username, timestamp, message))
    db_connection.commit()

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
    is_admin = False  # Always initialize is_admin
    try:
        credentials = client_socket.recv(4096).decode('utf-8')
        if credentials.startswith('/register '):
            _, reg_username, reg_password = credentials.strip().split(' ', 2)
            db_cursor.execute('SELECT username FROM users WHERE username = ?', (reg_username,))
            if db_cursor.fetchone():
                client_socket.send("__register_failed__:Username already exists".encode('utf-8'))
                client_socket.close()
                return
            password_hash = hash_password(reg_password)
            db_cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (reg_username, password_hash))
            db_connection.commit()
            client_socket.send("__register_success__".encode('utf-8'))
            client_socket.close()
            return
        # Login logic
        if '::' in credentials:
            username, password = credentials.split('::', 1)
        else:
            username = credentials
            password = None
        # Check user in users table
        db_cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
        row = db_cursor.fetchone()
        # Debug: Print all users and their password hashes
        db_cursor.execute('SELECT username, password_hash FROM users')
        all_users = db_cursor.fetchall()
        print("[DEBUG] Users in DB:")
        for u, ph in all_users:
            print(f"  - {u}: {ph}")
        print(f"[DEBUG] Login attempt: username='{username}', password='{password}'")
        if row:
            print(f"[DEBUG] DB password hash for '{username}': {row[0]}")
            if not password or not verify_password(password, row[0]):
                print(f"[DEBUG] Password check failed for '{username}'.")
                client_socket.send("Password not correct".encode('utf-8'))
                client_socket.close()
                return
            else:
                print(f"[DEBUG] Password check succeeded for '{username}'.")
        else:
            # Fallback to old admin logic if not in users table
            ADMIN_USERNAME = "meudeux"
            ADMIN_PASSWORD = "onlymeudeuxknows123"
            if username == ADMIN_USERNAME:
                if password != ADMIN_PASSWORD:
                    client_socket.send("Password not correct".encode('utf-8'))
                    client_socket.close()
                    return
                is_admin = True
            else:
                client_socket.send("User does not exist".encode('utf-8'))
                client_socket.close()
                return
                is_admin = False

        username_only = username.split("::")[0]
        usernames[client_socket] = username_only
        clients[username_only] = client_socket
        user_statuses[username_only] = "Online"  # Set initial status to Online
        print(f"[NEW USER] {username_only} connected from {address} {'(Admin)' if is_admin else ''}")
        log_message("Server", f"{username_only} has joined the chat.")
        broadcast(f"{username_only} has joined the chat.".encode('utf-8'), client_socket)
        send_user_list()

        # New: Buffer for receiving file data
        file_receiving = False
        file_info = {}
        file_write_handle = None  # File handle for writing incoming file
        received_file_bytes = 0   # Track bytes written
        file_buffer = b''  # Initialize file_buffer to avoid NameError
        file_write_progress = 0  # For debug progress output
        file_write_lock = threading.Lock()  # For thread safety
        file_write_thread = None

        def file_write_worker():
            nonlocal received_file_bytes, file_write_handle, file_info, file_write_progress, file_buffer
            while file_receiving and file_write_handle:
                with file_write_lock:
                    if file_buffer:
                        file_write_handle.write(file_buffer)
                        received_file_bytes += len(file_buffer)
                        file_buffer_len = len(file_buffer)
                        file_buffer = b''
                        # Print progress every 1MB or at the end
                        if received_file_bytes - file_write_progress >= 1024*1024 or received_file_bytes == file_info.get('size', 0):
                            print(f"[DEBUG] Background write: {received_file_bytes}/{file_info.get('size', 0)} bytes written.")
                            file_write_progress = received_file_bytes
                import time
                time.sleep(0.1)  # Sleep briefly to avoid busy loop

        # Send message history to client after connection
        try:
            import time
            time.sleep(0.5)  # Small delay to allow client to be ready
            # Send last 50 messages from DB
            db_cursor.execute('SELECT username, timestamp, content FROM messages ORDER BY id DESC LIMIT 50')
            rows = db_cursor.fetchall()[::-1]  # Reverse to send oldest first
            for uname, ts, content in rows:
                client_socket.send(f"__history__:[{ts}] {uname}: {content}\n".encode('utf-8'))
            client_socket.send("__history_end__\n".encode('utf-8'))
        except Exception as e:
            print(f"[ERROR] Failed to send message history: {e}")

        if is_admin:
            client_socket.send("__admin__".encode('utf-8'))

        username = username_only

    except Exception as e:
        print(f"Error during client connection setup: {e}")
        client_socket.close()
        return

    while True:
        try:
            # If receiving a file, read raw bytes until done
            if file_receiving:
                try:
                    chunk = client_socket.recv(min(4096, file_info['size'] - received_file_bytes))
                    if not chunk:
                        print(f"[ERROR] Connection closed by client during file upload. Received {received_file_bytes}/{file_info['size']} bytes.")
                        try:
                            client_socket.send(f"File upload failed: connection closed before complete file was received.".encode('utf-8'))
                        except Exception as send_err:
                            print(f"[ERROR] Could not send error to client: {send_err}")
                        file_receiving = False
                        continue

                    with file_write_lock:
                        file_buffer += chunk

                    print(f"[DEBUG] Received chunk: {len(chunk)} bytes | Total received: {received_file_bytes + len(file_buffer)}/{file_info['size']} bytes (buffered)")

                    if received_file_bytes + len(file_buffer) >= file_info['size']:
                        file_receiving = False
                        if file_write_thread:
                            file_write_thread.join(timeout=2)
                        print(f"[DEBUG] File transfer complete for: {file_info['filename']}")
                        try:
                            client_socket.send(f"File '{file_info['filename']}' uploaded successfully.".encode('utf-8'))
                        except Exception as send_err:
                            print(f"[ERROR] Could not send upload success to client: {send_err}")
                except Exception as e:
                    print(f"[ERROR] Exception during file receiving: {e}")
                    try:
                        client_socket.send(f"Error during file upload: {e}".encode('utf-8'))
                    except Exception as send_err:
                        print(f"[ERROR] Could not send error to client: {send_err}")
                    file_receiving = False
                    continue
            else:
                # If we have leftover buffer from file transfer, use it
                if file_buffer:
                    try:
                        msg = file_buffer.decode('utf-8')
                        print(f"[DEBUG] Decoded leftover buffer: {msg}")
                        file_buffer = b''
                    except Exception as e:
                        print(f"[ERROR] Error decoding buffered data: {e}")
                        # Instead of breaking, just clear buffer and continue
                        file_buffer = b''
                        continue
                else:
                    try:
                        msg = client_socket.recv(4096).decode('utf-8')
                    except OSError as e:
                        if hasattr(e, 'winerror') and e.winerror in (10038, 10054, 10053):
                            print(f"[ERROR] Socket error during recv: {e}. Cleaning up client.")
                            break
                        else:
                            print(f"[ERROR] Exception during recv: {e}")
                            continue
            if not msg:
                print(f"[DEBUG] Empty message received, breaking loop for {usernames.get(client_socket, address)}")
                break
            # Always strip whitespace from received message before parsing
            msg = msg.strip()
            print(f"[DEBUG] Received command: {msg}")  # Log the received command
            # --- File/image sharing support ---
            if msg.startswith("/send_file "):
                try:
                    print(f"[DEBUG] Raw command received (repr): {repr(msg)}")
                    _, filename, filesize_str = msg.split(" ", 2)
                    filename = filename.strip()
                    filesize = int(filesize_str)
                    print(f"[DEBUG] Received file transfer request: filename={filename}, size={filesize}")
                    # Prepare to receive file from client and save to shared_files
                    ack = f"ACK:{filename}\n".encode('utf-8')
                    client_socket.sendall(ack)
                    print(f"[DEBUG] ACK sent for file: {filename}")
                    # Receive file data from client
                    save_path = os.path.join(SHARED_FILES_DIR, filename)
                    received_bytes = 0
                    with open(save_path, 'wb') as f:
                        while received_bytes < filesize:
                            chunk = client_socket.recv(min(4096, filesize - received_bytes))
                            print(f"[DEBUG] Raw file chunk received (len={len(chunk)}): {repr(chunk[:32])} ...")
                            if not chunk:
                                print(f"[ERROR] Connection closed by client during upload. Received {received_bytes}/{filesize} bytes.")
                                break
                            f.write(chunk)
                            received_bytes += len(chunk)
                            print(f"[DEBUG] Received {received_bytes}/{filesize} bytes...")
                    if received_bytes == filesize:
                        print(f"[DEBUG] File upload complete: {filename}")
                        try:
                            client_socket.send(f"File '{filename}' uploaded successfully.".encode('utf-8'))
                        except Exception as send_err:
                            print(f"[ERROR] Could not send upload success to client: {send_err}")
                    else:
                        print(f"[ERROR] File upload incomplete: {received_bytes}/{filesize} bytes.")
                        try:
                            client_socket.send(f"File upload incomplete: {received_bytes}/{filesize} bytes.".encode('utf-8'))
                        except Exception as send_err:
                            print(f"[ERROR] Could not send upload error to client: {send_err}")
                except Exception as e:
                    try:
                        client_socket.send(f"Failed to initiate file transfer: {e}".encode('utf-8'))
                    except Exception as send_err:
                        print(f"[ERROR] Could not send error to client: {send_err}")
                    print(f"[ERROR] Failed to initiate file transfer: {e}")
                continue
            if msg.startswith("/get_file "):
                try:
                    import time
                    _, filename = msg.split(" ", 1)
                    file_path = os.path.join(SHARED_FILES_DIR, filename)
                    if os.path.exists(file_path):
                        # 1. Send ACK
                        ack = f"ACK:{filename}\n".encode('utf-8')
                        client_socket.sendall(ack)
                        print(f"[DEBUG] ACK sent for file: {filename}")
                        time.sleep(0.1)  # Optional: ensure client is ready
                        # 2. Send file start header
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                        file_header = f"__file_start__:{filename}:{len(file_data)}\n".encode('utf-8')
                        client_socket.sendall(file_header)
                        print(f"[DEBUG] Sent file header for: {filename}")
                        # 3. Send file content
                        client_socket.sendall(file_data)
                        print(f"[DEBUG] Sent file data: {len(file_data)} bytes")
                        # 4. Send file end marker
                        file_end = f"__file_end__:{filename}\n".encode('utf-8')
                        client_socket.sendall(file_end)
                        print(f"[DEBUG] Sent file end marker for: {filename}")
                    else:
                        client_socket.send(f"File '{filename}' not found.".encode('utf-8'))
                except Exception as e:
                    try:
                        client_socket.send(f"Error sending file: {e}".encode('utf-8'))
                    except Exception as send_err:
                        print(f"[ERROR] Could not send error to client: {send_err}")
                continue
            if msg == "/list_files":
                try:
                    files = os.listdir(SHARED_FILES_DIR)
                    files = [f for f in files if os.path.isfile(os.path.join(SHARED_FILES_DIR, f))]
                    file_list_str = "__file_list__:" + ",".join(files)
                    client_socket.send(file_list_str.encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Error listing files: {e}".encode('utf-8'))
                continue
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
                    print(f"[DEBUG] Received request for group info: {group_name}")  # Debug log
                    if group_name in groups:
                        print(f"[DEBUG] Group '{group_name}' found. Members: {groups[group_name]}")  # Log group details
                        members = groups[group_name]
                        creator = members[0] if members else ""
                        members_str = ",".join(members)
                        response = f"__group_info__:{group_name}:{creator}:{members_str}"
                        print(f"[DEBUG] Sending group info response: {response}")  # Debug log
                        client_socket.send(response.encode('utf-8'))
                    else:
                        print(f"[DEBUG] Group '{group_name}' not found in groups dictionary.")  # Log missing group
                        print(f"[ERROR] Group '{group_name}' does not exist.")  # Error log
                        client_socket.send(f"Group '{group_name}' does not exist.".encode('utf-8'))
                except Exception as e:
                    print(f"[ERROR] Exception while fetching group info: {e}")  # Error log
                    client_socket.send(f"Error fetching group info: {e}".encode('utf-8'))
            elif msg.startswith("/invite_to_group "):
                try:
                    _, group_name, user_to_invite = msg.split(" ", 2)
                    inviter = usernames[client_socket]
                    if group_name in groups:
                        if user_to_invite not in groups[group_name]:
                            # Add invite to pending_invites
                            if user_to_invite not in pending_invites:
                                pending_invites[user_to_invite] = []
                            if group_name not in pending_invites[user_to_invite]:
                                pending_invites[user_to_invite].append(group_name)
                                client_socket.send(f"Invite sent to {user_to_invite} for group '{group_name}'.".encode('utf-8'))
                            else:
                                client_socket.send(f"User '{user_to_invite}' already has a pending invite to '{group_name}'.".encode('utf-8'))
                        else:
                            client_socket.send(f"User '{user_to_invite}' is already in group '{group_name}'.".encode('utf-8'))
                    else:
                        client_socket.send(f"Group '{group_name}' does not exist.".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Invalid invite format. Use: /invite_to_group group_name username".encode('utf-8'))
            elif msg.startswith("/get_invites"):
                try:
                    user = usernames[client_socket]
                    invites = pending_invites.get(user, [])
                    client_socket.send(f"__invites__:{','.join(invites)}".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"__invites__:".encode('utf-8'))
            elif msg.startswith("/accept_invite "):
                try:
                    _, group_name = msg.split(" ", 1)
                    user = usernames[client_socket]
                    if user in pending_invites and group_name in pending_invites[user]:
                        pending_invites[user].remove(group_name)
                        if group_name in groups and user not in groups[group_name]:
                            groups[group_name].append(user)
                            save_group_member(group_name, user)
                            client_socket.send(f"You have joined the group: {group_name}".encode('utf-8'))
                        else:
                            client_socket.send(f"Group '{group_name}' does not exist or you are already a member.".encode('utf-8'))
                    else:
                        client_socket.send(f"No pending invite for group '{group_name}'.".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Failed to accept invite.".encode('utf-8'))
            elif msg.startswith("/group_msg "):
                try:
                    _, group_name, group_msg = msg.split(" ", 2)
                    sender = usernames[client_socket]
                    if group_name in groups and sender in groups[group_name]:
                        full_msg = f"[Group msg] {group_name} {sender}: {group_msg}"
                        for member in groups[group_name]:
                            if member in clients and clients[member] != client_socket:
                                clients[member].send(full_msg.encode('utf-8'))
                        # Optionally, echo the message back to the sender's group chat window
                        client_socket.send(full_msg.encode('utf-8'))
                        log_message(sender, f"Group {group_name}: {group_msg}")
                    else:
                        client_socket.send(f"You are not a member of group '{group_name}'.".encode('utf-8'))
                except Exception as e:
                    client_socket.send(f"Invalid group message format. Use: /group_msg group_name message".encode('utf-8'))
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
            print(f"[ERROR] Unexpected exception in main handler loop: {e}")
            import traceback
            traceback.print_exc()
            # Optionally, send error to client for debugging
            try:
                client_socket.send(f"[SERVER ERROR] {e}".encode('utf-8'))
            except:
                pass
            # Do not break; continue to next loop iteration
            continue

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

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password, password_hash):
    return hash_password(password) == password_hash

print("[STARTING] Server is running...")
while True:
    try:
        client_socket, client_address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {len(clients)}")
    except Exception as e:
        print(f"Error accepting connections: {e}")
