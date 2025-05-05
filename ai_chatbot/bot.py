import time
from network import NetworkClient
from chatterbot_bot import ChatterBotWrapper

class AIChatBot:
    def __init__(self, server_ip, port, username="AI_Bot"):
        self.bot = ChatterBotWrapper()
        self.bot.train_from_logs()
        self.network = NetworkClient(server_ip, port, username, self.handle_message)

    def handle_message(self, msg):
        if msg.startswith("__typing__") or msg.startswith("__user_list__") or msg == "__typing_stopped__":
            return
        if msg.startswith("[PM from ") or msg.startswith("[PM to "):
            return

        print(f"Received message: {msg}")
        response = self.bot.get_response(msg)

        if response:
            self.network.send_message(response)
            # Optionally, you can log messages here if needed

    def run(self):
        self.network.connect()
        print("AI ChatBot connected and running.")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    bot = AIChatBot("192.168.56.1", 5555)
    bot.run()
