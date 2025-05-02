import socket
import threading
import datetime
import os

# ----------- config -----------
Host = '0.0.0.0'
Port = 5555
START_TIME = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"chat_log_{START_TIME}.txt"
#------------------------------

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((Host, Port))
server.listen(5)

clients = {}
usernames = {}

open(LOG_FILE, 'a').close()

def log_message(username, message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} - {username}: {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(entry)

def broadcast(message, sender_socket):
    disconnected_clients = []
    for client in clients.values():
        if client != sender_socket:
            try:
                client.send(message)
            except:
                client.close()
                disconnected_clients.append(client)
    for dc in disconnected_clients:
        username_to_remove = None
        for uname, sock in clients.items():
            if sock == dc:
                username_to_remove = uname
                break
        if username_to_remove:
            del clients[username_to_remove]
            del usernames[dc]

def send_user_list():
    user_list_message = "__user_list__:" + ",".join(clients.keys())
    disconnected_clients = []
    for client in clients.values():
        try:
            client.send(user_list_message.encode('utf-8'))
        except:
            client.close()
            disconnected_clients.append(client)
    for dc in disconnected_clients:
        username_to_remove = None
        for uname, sock in clients.items():
            if sock == dc:
                username_to_remove = uname
                break
        if username_to_remove:
            del clients[username_to_remove]
            del usernames[dc]

def broadcast_typing(username, sender_socket):
    disconnected_clients = []
    typing_message = f"__typing__:{username}"
    for client in clients.values():
        if client != sender_socket:
            try:
                client.send(typing_message.encode())
            except:
                client.close()
                disconnected_clients.append(client)
    for dc in disconnected_clients:
        username_to_remove = None
        for uname, sock in clients.items():
            if sock == dc:
                username_to_remove = uname
                break
        if username_to_remove:
            del clients[username_to_remove]
            del usernames[dc]

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
        print(f"[NEW USER] {username_only} connected from {address} {'(Admin)' if is_admin else ''}")
        log_message("Server", f"{username_only} has joined the chat.")
        broadcast(f"{username_only} has joined the chat.".encode('utf-8'), client_socket)
        send_user_list()

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
                        client_socket.send(f"[PM to {recipient}] {private_msg}".encode('utf-8'))
                        log_message(sender, f"Private to {recipient}: {private_msg}")
                    else:
                        client_socket.send(f"User {recipient} not found.".encode('utf-8'))
                except:
                    client_socket.send(f"Invalid private message format.".encode('utf-8'))
            else:
                log_message(usernames[client_socket], msg)
                broadcast(f"[{usernames[client_socket]}] {msg}".encode('utf-8'), client_socket)
        except Exception as e:
            print(f"Error receiving message from {usernames.get(client_socket, 'Unknown')}: {e}")
            break

    username = usernames.get(client_socket, "Unknown")
    print(f"[DISCONNECTED] {username} disconnected")
    log_message("Server", f"{username} has left the chat.")
    broadcast(f"{username} has left the chat.".encode(), client_socket)
    send_user_list()

    client_socket.close()
    if username in clients:
        del clients[username]
    if client_socket in usernames:
        del usernames[client_socket]

print("[STARTING] Server is running...")
while True:
    try:
        client_socket, client_address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {len(clients)}")
    except Exception as e:
        print(f"Error accepting connections: {e}")
