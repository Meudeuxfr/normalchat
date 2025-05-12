import glob
import re

class ChatterBotWrapper:
    def __init__(self, name="AI_Bot"):
        from chatterbot.logic import BestMatch
        from chatterbot.trainers import ListTrainer
        from chatterbot import ChatBot
        import os

        db_path = os.path.join(os.path.dirname(__file__), 'chatterbot_db.sqlite3')

        self.bot = ChatBot(
            name,
            storage_adapter='chatterbot.storage.SQLStorageAdapter',
            database_uri=f'sqlite:///{db_path}',
            logic_adapters=[
                {
                    'import_path': 'chatterbot.logic.BestMatch',
                    'default_response': "I'm not sure how to respond to that yet.",
                    'maximum_similarity_threshold': 0.75
                }
            ],
            read_only=True,
        )
        self.trainer = ListTrainer(self.bot)

    def train_from_logs(self, log_pattern="chat_log_*.txt"):
        log_files = glob.glob(log_pattern)
        for log_file in log_files:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                conversation = []
                for line in lines:
                    match = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - (.+?): (.+)", line)
                    if match:
                        user, message = match.groups()
                        # Filter out system messages and user join/leave messages
                        if user.lower() in ["server", "ai_bot"]:
                            continue
                        if any(keyword in message.lower() for keyword in ["has joined", "has left", "typing"]):
                            continue
                        conversation.append(message.strip())
                        # Train in pairs (user message, bot response)
                        if len(conversation) == 2:
                            self.trainer.train(conversation)
                            conversation = []

    def get_response(self, message):
        # Custom handling for greetings and farewells
        greetings = ["hello", "hi", "hey", "greetings"]
        farewells = ["bye", "goodbye", "see you", "farewell"]

        if any(greet in message.lower() for greet in greetings):
            base_response = "Hello!"
        elif any(farewell in message.lower() for farewell in farewells):
            base_response = "Goodbye! Have a great day."
        else:
            # If message looks like an explanation or teaching, learn from it
            if any(phrase in message.lower() for phrase in ["i mean", "let me explain", "what i mean", "to clarify", "for example"]):
                # Teach the bot this message as a response to the previous user input if available
                # This requires storing last user input and pairing it with this explanation
                if hasattr(self, 'last_user_message') and self.last_user_message:
                    self.trainer.train([self.last_user_message, message])
                    self.last_user_message = None
                    return "Thanks for explaining, I've learned something new!"
            
            # Store current message as last user message for possible learning
            self.last_user_message = message

            base_response = str(self.bot.get_response(message))

        # Add joker personality style
        personality_response = f"{base_response} Why so serious? 😈"

        return personality_response

if __name__ == "__main__":
    chatbot = ChatterBotWrapper()
    chatbot.train_from_logs()
    print("ChatterBot trained and ready.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        response = chatbot.get_response(user_input)
        print("Bot:", response)
