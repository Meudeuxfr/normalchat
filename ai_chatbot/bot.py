import time
from network import NetworkClient
from chatterbot_bot import ChatterBotWrapper

class AIChatBot:
    def __init__(self, server_ip, port, username="joker"):
        self.bot = ChatterBotWrapper()
        self.bot.train_from_logs()
        self.network = NetworkClient(server_ip, port, username, self.handle_message)

    def handle_message(self, msg):
        import time

        if msg.startswith("__typing__") or msg.startswith("__user_list__") or msg == "__typing_stopped__":
            return
        if msg.startswith("[PM from ") or msg.startswith("[PM to "):
            return

        print(f"Received message: {msg}")
        response = self.bot.get_response(msg)

        if response:
            max_chunk_size = 500
            # Split response into chunks if too long
            chunks = [response[i:i+max_chunk_size] for i in range(0, len(response), max_chunk_size)]
            for chunk in chunks:
                self.network.send_message(chunk)
                time.sleep(0.5)  # short delay between chunks
            # Optionally, you can log messages here if needed

    def run(self):
        import threading
        import random
        import time

        def send_periodic_messages():
            greetings = ["Hello everyone!", "How's it going?", "I'm here if you need me.", "Hi all!"]
            recent_messages = []
            while True:
                time.sleep(random.randint(60, 180))  # check every 1 to 3 minutes
                # Only send message if chat is quiet (e.g., less than 2 messages in last 30 seconds)
                if len(recent_messages) < 2:
                    message = random.choice(greetings)
                    self.network.send_message(message)
                # Clear recent messages periodically
                recent_messages.clear()

        def handle_message(self, msg):
            if msg.startswith("__typing__") or msg.startswith("__user_list__") or msg == "__typing_stopped__":
                return
            if msg.startswith("[PM from ") or msg.startswith("[PM to "):
                return

            # Track recent messages for periodic message logic
            if not hasattr(self, 'recent_messages'):
                self.recent_messages = []
            import time as _time
            now = _time.time()
            self.recent_messages.append({'message': msg, 'timestamp': now})
            # Keep only messages from last 30 seconds
            self.recent_messages = [m for m in self.recent_messages if now - m['timestamp'] < 30]

            # Check if bot is mentioned in message
            if "joker" in msg.lower() or "@ai_bot" in msg.lower():
                response = self.bot.get_response(msg)
                if response:
                    self.network.send_message(response)
            else:
                # Normal message handling
                print(f"Received message: {msg}")
                response = self.bot.get_response(msg)
                if response:
                    self.network.send_message(response)

        # Replace original handle_message with this new one
        self.handle_message = handle_message

        self.network.connect()
        print("AI ChatBot (joker) connected and running.")

        # Start background thread to send periodic messages
        threading.Thread(target=send_periodic_messages, daemon=True).start()

        while True:
            time.sleep(1)

if __name__ == "__main__":
    bot = AIChatBot("192.168.56.1", 5555, username="joker")
    bot.run()
