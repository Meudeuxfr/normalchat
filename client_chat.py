import socket
import threading
import datetime
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import simpledialog

# ------ config ------

Server_IP = '192.168.56.1'
port = 5555

#---------------------

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((Server_IP, port))

root = tk.Tk()
root.withdraw()

username = simpledialog.askstring("Username", "Enter your username:", parent=root)
if not username:
    print("No username entered. Exiting.")
    exit()

password = None
if username == "meudeux":
    password = simpledialog.askstring("Password", "Enter admin password:", parent=root, show='*')
    if password is None:
        print("No password entered. Exiting.")
        exit()

root.deiconify()

try:
    if password:
        client.send(f"{username}::{password}".encode())  # Send username and password to server
    else:
        client.send(username.encode())  # Send username only
except Exception as e:
    print(f"Failed to send username: {e}")
    exit()

print(f"Username '{username}' sent to server.")
# ------- GUI --------

root.title(f"Chat Client - {username}")

# Add menu bar
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# Theme customization variables
theme_bg = "#ffffff"
theme_fg = "#000000"
theme_font_family = "Arial"
theme_font_size = 12

def apply_theme():
    chat_display.config(bg=theme_bg, fg=theme_fg, font=(theme_font_family, theme_font_size))
    entry.config(bg=theme_bg, fg=theme_fg, font=(theme_font_family, theme_font_size))
    root.config(bg=theme_bg)
    typing_label.config(bg=theme_bg, fg=theme_fg, font=(theme_font_family, theme_font_size))
    emoji_button.config(bg=theme_bg, fg=theme_fg, font=(theme_font_family, theme_font_size))

def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("chat_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp}: {message}\n")

def display_message(message):
    chat_display.config(state='normal')
    timestamp = datetime.datetime.now().strftime("%H:%M")
    chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
    chat_display.insert(tk.END, message + '\n')
    chat_display.config(state='disabled')
    chat_display.yview(tk.END)

def open_theme_settings():
    theme_window = tk.Toplevel(root)
    theme_window.title("Theme Settings")
    theme_window.geometry("300x250")

    tk.Label(theme_window, text="Background Color:").pack(pady=5)
    bg_entry = tk.Entry(theme_window)
    bg_entry.insert(0, theme_bg)
    bg_entry.pack()

    tk.Label(theme_window, text="Text Color:").pack(pady=5)
    fg_entry = tk.Entry(theme_window)
    fg_entry.insert(0, theme_fg)
    fg_entry.pack()

    tk.Label(theme_window, text="Font Family:").pack(pady=5)
    font_family_entry = tk.Entry(theme_window)
    font_family_entry.insert(0, theme_font_family)
    font_family_entry.pack()

    tk.Label(theme_window, text="Font Size:").pack(pady=5)
    font_size_entry = tk.Entry(theme_window)
    font_size_entry.insert(0, str(theme_font_size))
    font_size_entry.pack()

    def save_theme():
        global theme_bg, theme_fg, theme_font_family, theme_font_size
        theme_bg = bg_entry.get()
        theme_fg = fg_entry.get()
        theme_font_family = font_family_entry.get()
        try:
            theme_font_size = int(font_size_entry.get())
        except ValueError:
            theme_font_size = 12
        apply_theme()
        theme_window.destroy()

    save_button = tk.Button(theme_window, text="Apply", command=save_theme)
    save_button.pack(pady=10)

# Add Settings menu
settings_menu = tk.Menu(menu_bar, tearoff=0)
settings_menu.add_command(label="Theme", command=open_theme_settings)
menu_bar.add_cascade(label="Settings", menu=settings_menu)

chat_display = ScrolledText(root, wrap=tk.WORD, state='disabled', width=50, height=20)
# Create a frame for chat display and user list
main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

chat_display = ScrolledText(main_frame, wrap=tk.WORD, state='disabled', width=50, height=20)
chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Define a tag for small timestamp font
chat_display.tag_configure("timestamp", font=("Arial", 8), foreground="gray")

# User list box
user_listbox = tk.Listbox(main_frame, width=20, height=20)
user_listbox.pack(side=tk.LEFT, fill=tk.Y, padx=5)

# Create a frame at the bottom for entry and emoji button
bottom_frame = tk.Frame(root)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

entry = tk.Entry(bottom_frame, width=50)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Dictionary to keep track of private chat windows
private_chat_windows = {}

def open_private_chat_window(recipient):
    if recipient in private_chat_windows:
        # If window already exists, bring it to front
        private_chat_windows[recipient]['window'].deiconify()
        private_chat_windows[recipient]['window'].lift()
        return

    # Create new private chat window
    pm_window = tk.Toplevel(root)
    pm_window.title(f"Private Chat with {recipient}")
    pm_window.geometry("400x300")

    chat_display = ScrolledText(pm_window, wrap=tk.WORD, state='disabled', width=50, height=15)
    chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    entry_frame = tk.Frame(pm_window)
    entry_frame.pack(fill=tk.X, padx=10, pady=5)

    entry = tk.Entry(entry_frame, width=40)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def send_private_message(event=None):
        msg = entry.get()
        if msg:
            msg_to_send = f"/pm {recipient} {msg}"
            try:
                client.send(msg_to_send.encode('utf-8'))
                # Display message in private chat window
                chat_display.config(state='normal')
                timestamp = datetime.datetime.now().strftime("%H:%M")
                chat_display.insert(tk.END, f"[{timestamp}] You: {msg}\n")
                chat_display.config(state='disabled')
                chat_display.yview(tk.END)
                log_message(f"{username} to {recipient}: {msg}")
                entry.delete(0, tk.END)
            except Exception as e:
                print(f"Error sending private message: {e}")
                display_message("Failed to send private message.")
    entry.bind("<Return>", send_private_message)

    send_button = tk.Button(entry_frame, text="Send", command=send_private_message)
    send_button.pack(side=tk.LEFT, padx=5)

    def on_close():
        private_chat_windows.pop(recipient, None)
        pm_window.destroy()

    pm_window.protocol("WM_DELETE_WINDOW", on_close)

    private_chat_windows[recipient] = {'window': pm_window, 'chat_display': chat_display}

def on_user_double_click(event):
    selected_indices = user_listbox.curselection()
    if selected_indices:
        recipient = user_listbox.get(selected_indices[0])
        if recipient != username:
            open_private_chat_window(recipient)

user_listbox.bind("<Double-Button-1>", on_user_double_click)

# Remove old private chat mode variables and toggle button

def open_emoji_picker():
    emoji_window = tk.Toplevel(root)
    emoji_window.title("Emoji Picker")
    emojis = [
        "😀", "😂", "😍", "😎", "😊", "😢", "😡", "👍", "🙏", "🎉",
        "❤️", "🔥", "🌟", "💯", "🎶", "🍕", "🍔", "🍎", "⚽", "🏆"
    ]
    def insert_emoji(emoji):
        current_pos = entry.index(tk.INSERT)
        entry.insert(current_pos, emoji)
        emoji_window.destroy()
    row = 0
    col = 0
    for emoji in emojis:
        button = tk.Button(emoji_window, text=emoji, font=("Arial", 14), width=3, command=lambda e=emoji: insert_emoji(e))
        button.grid(row=row, column=col, padx=3, pady=3)
        col += 1
        if col > 4:
            col = 0
            row += 1

emoji_button = tk.Button(bottom_frame, text="😊", font=("Arial", 14), command=open_emoji_picker)
emoji_button.pack(padx=5, side=tk.LEFT)

def send_message(event=None):
    msg = entry.get()
    print(f"send_message called with msg: {msg}")  # Debug print
    if msg:
        # Do not display private messages in global chat
        if msg.startswith("/pm "):
            # Just send the private message, do not display globally
            msg_to_send = msg
        else:
            msg_to_send = msg
            display_message(f"{username}: {msg}")

        try:
            client.send(msg_to_send.encode('utf-8'))
            print("Message sent to server")  # Debug print
        except Exception as e:
            print(f"Error sending message: {e}")
            display_message("Failed to send message.")
        entry.delete(0, tk.END)
    else:
        # If message is empty, send typing stopped notification
        try:
            client.send("__typing_stopped__".encode('utf-8'))
        except Exception as e:
            print(f"Error sending typing stopped notification: {e}")

def on_user_double_click(event):
    selected_indices = user_listbox.curselection()
    if selected_indices:
        recipient = user_listbox.get(selected_indices[0])
        if recipient != username:
            open_private_chat_window(recipient)

user_listbox.bind("<Double-Button-1>", on_user_double_click)

typing_users = set()
typing_label = tk.Label(root, text="", fg="gray")
typing_label.pack(padx=10, pady=(0, 10))

def on_typing(event=None):
    # Send typing notification to server
    client.send(f"__typing__:{username}".encode())

    entry.bind("<KeyPress>", on_typing)

def receive_messages():
    while True:
        try:
            msg = client.recv(1024).decode()
            if not msg:
                print("Server closed connection.")
                break
            if msg.startswith("__typing__:"):
                typing_user = msg.split(":", 1)[1]
                typing_users.add(typing_user)
                # Update typing label with all users typing
                typing_label.config(text=f"{', '.join(typing_users)} {'is' if len(typing_users) == 1 else 'are'} typing...")
                # Remove typing notification after 3 seconds
                def clear_typing(user=typing_user):
                    typing_users.discard(user)
                    if not typing_users:
                        typing_label.config(text="")
                root.after(3000, clear_typing)
            elif msg == "__typing_stopped__":
                # Remove user from typing users set
                if username in typing_users:
                    typing_users.discard(username)
                if not typing_users:
                    typing_label.config(text="")
            elif msg.startswith("__user_list__:"):
                # Update user list
                user_list_str = msg[len("__user_list__:"):]
                users = user_list_str.split(",") if user_list_str else []
                user_listbox.delete(0, tk.END)
                for user in users:
                    if user != username:
                        user_listbox.insert(tk.END, user)
            elif msg.startswith("[PM from "):
                # Private message received
                try:
                    print(f"Debug: Received private message: {msg}")  # Debug print
                    # Extract sender username
                    end_idx = msg.find("]")
                    sender = msg[9:end_idx]
                    # Extract message content
                    private_msg = msg[end_idx+2:]
                    if sender not in private_chat_windows:
                        open_private_chat_window(sender)
                    pm_window = private_chat_windows[sender]
                    chat_display = pm_window['chat_display']
                    if chat_display:
                        chat_display.config(state='normal')
                        timestamp = datetime.datetime.now().strftime("%H:%M")
                        chat_display.insert(tk.END, f"[{timestamp}] {sender}: {private_msg}\n")
                        chat_display.config(state='disabled')
                        chat_display.yview(tk.END)
                except Exception as e:
                    print(f"Error handling private message: {e}")
            elif msg.startswith("[PM to "):
                # Ignore private message confirmation to avoid cluttering main chat
                pass
            else:
                display_message(msg)
                log_message(msg)
        except OSError as e:
            print(f"Connection error: {e}")
            display_message("Disconnected from server.")
            break
        except Exception as e:
            print(f"Error receiving message: {e}")

threading.Thread(target=receive_messages, daemon=True).start()

entry.bind("<Return>", send_message)

root.mainloop()