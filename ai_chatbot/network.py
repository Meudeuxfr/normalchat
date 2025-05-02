import socket
import threading

class NetworkClient:
    def __init__(self, server_ip, port, username, message_handler):
        self.server_ip = server_ip
        self.port = port
        self.username = username
        self.message_handler = message_handler
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        self.client.connect((self.server_ip, self.port))
        self.client.send(self.username.encode())
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def receive_messages(self):
        while True:
            try:
                msg = self.client.recv(1024).decode()
                if not msg:
                    print("Server closed connection.")
                    break
                self.message_handler(msg)
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    def send_message(self, message):
        try:
            self.client.send(message.encode())
        except Exception as e:
            print(f"Error sending message: {e}")
