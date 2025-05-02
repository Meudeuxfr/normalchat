import socket
import threading
import datetime
import re

# AI Chatbot client that connects to the chat server and interacts with users
# It learns from chat_log.txt and responds based on simple pattern matching

SERVER_IP = '192.168.56.1'  # Change if needed
PORT = 5555
USERNAME = "AI_Bot"

# Load chat log and build a simple knowledge base of message-response pairs
def load_chat_log(filename="chat_log.txt"):
    knowledge_base = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Parse lines to extract user messages (skip server messages)
        for i in range(len(lines)-1):
            current_line = lines[i].strip()
            next_line = lines[i+1].strip()
            # Extract user and message from current line
            match_current = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - (.+?): (.+)", current_line)
            match_next = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - (.+?): (.+)", next_line)
            if match_current and match_next:
                user_current, msg_current = match_current.groups()
                user_next, msg_next = match_next.groups()
                # Only consider user messages, ignore server messages
                if user_current != "Server" and user_next != "Server":
                    knowledge_base.append((msg_current.lower(), msg_next))
    except FileNotFoundError:
        print("Chat log file not found. Starting with empty knowledge base.")
    return knowledge_base

# Find a response from knowledge base based on input message
def find_response(message, knowledge_base):
    message = message.lower()
    for question, response in knowledge_base:
        if question in message or message in question:
            return response
    return None

def log_message(message, filename="chat_log.txt"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {USERNAME}: {message}\n")

def receive_messages(client, knowledge_base):
    while True:
        try:
            msg = client.recv(1024).decode()
            if not msg:
                print("Server closed connection.")
                break
            # Ignore typing notifications and user list updates
            if msg.startswith("__typing__") or msg.startswith("__user_list__") or msg == "__typing_stopped__":
                continue
            # Ignore private messages for now
            if msg.startswith("[PM from ") or msg.startswith("[PM to "):
                continue
            print(f"Received message: {msg}")
            # Find a response
            response = find_response(msg, knowledge_base)
            if response:
                send_message(client, response)
                log_message(response)
                knowledge_base.append((msg.lower(), response))
        except Exception as e:
            print(f"Error receiving message: {e}")
            break

def send_message(client, message):
    try:
        client.send(message.encode())
        print(f"Sent message: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((SERVER_IP, PORT))
    client.send(USERNAME.encode())

    knowledge_base = load_chat_log()

    thread = threading.Thread(target=receive_messages, args=(client, knowledge_base), daemon=True)
    thread.start()

    # Keep the bot running
    while True:
        pass

if __name__ == "__main__":
    main()
