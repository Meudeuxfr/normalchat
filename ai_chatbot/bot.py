import time
from knowledge_base import KnowledgeBase
from responder import Responder
from network import NetworkClient

class AIChatBot:
    def __init__(self, server_ip, port, username="AI_Bot"):
        self.kb = KnowledgeBase()
        self.responder = Responder(self.kb)
        self.network = NetworkClient(server_ip, port, username, self.handle_message)

    def handle_message(self, msg):
        # Ignore typing notifications and user list updates
        if msg.startswith("__typing__") or msg.startswith("__user_list__") or msg == "__typing_stopped__":
            return
        # Ignore private messages for now
        if msg.startswith("[PM from ") or msg.startswith("[PM to "):
            return
        print(f"Received message: {msg}")
        response = self.responder.generate_response(msg)
        if response:
            self.network.send_message(response)
            self.kb.add_pair(msg.lower(), response)

    def run(self):
        self.network.connect()
        print("AI ChatBot connected and running.")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    bot = AIChatBot("192.168.56.1", 5555)
    bot.run()
