import re
import datetime
from difflib import SequenceMatcher

class KnowledgeBase:
    def __init__(self, log_file="chat_log.txt"):
        self.log_file = log_file
        self.pairs = []
        self.load_chat_log()
        self.pair_set = set(self.pairs)  # For faster lookup

    def load_chat_log(self):
        import glob
        self.pairs = []
        log_files = glob.glob("chat_log_*.txt")
        if not log_files:
            print("No chat log files found. Starting with empty knowledge base.")
            return
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for i in range(len(lines)-1):
                    current_line = lines[i].strip()
                    next_line = lines[i+1].strip()
                    match_current = re.match(r"\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} - (.+?): (.+)", current_line)
                    match_next = re.match(r"\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} - (.+?): (.+)", next_line)
                    if match_current and match_next:
                        user_current, msg_current = match_current.groups()
                        user_next, msg_next = match_next.groups()
                        if user_current != "Server" and user_next != "Server":
                            self.pairs.append((msg_current.lower(), msg_next))
                self.pair_set = set(self.pairs)
            except Exception as e:
                print(f"Error reading {log_file}: {e}")

    def add_pair(self, message, response):
        pair = (message.lower(), response)
        if pair not in self.pair_set:
            self.pairs.append(pair)
            self.pair_set.add(pair)
            self.log_message(message, sender="User")
            self.log_message(response, sender="AI_Bot")

    def remove_pair(self, message, response):
        pair = (message.lower(), response)
        if pair in self.pairs:
            self.pairs.remove(pair)
            # Optionally, update the log file or keep as is

    def log_message(self, message, sender="AI_Bot"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {sender}: {message}\n")

    def find_response(self, message):
        message = message.lower()
        best_ratio = 0
        best_response = None
        for question, response in self.pairs:
            ratio = SequenceMatcher(None, question, message).ratio()
            if ratio > best_ratio and ratio > 0.5:  # Lowered threshold for faster matching
                best_ratio = ratio
                best_response = response
        return best_response

    def save_pairs(self):
        # Save current pairs to the log file immediately to persist learning
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                for question, response in self.pairs:
                    f.write(f"{question}|||{response}\n")
        except Exception as e:
            print(f"Error saving pairs: {e}")
