import socket
import threading
import datetime
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import simpledialog
import signal

# Declare buttons_frame as a global variable
buttons_frame = None

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

# Add test menu for debugging menu bar visibility
test_menu = tk.Menu(menu_bar, tearoff=0)
test_menu.add_command(label="Test Item", command=lambda: print("Test clicked"))
menu_bar.add_cascade(label="Test", menu=test_menu)

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

    # Parse message to separate content and unique ID if present
    if "||" in message:
        content, _ = message.split("||", 1)  # Extract content before the unique ID
    else:
        content = message

    # Clean up private message format
    if content.startswith("[PM from") or content.startswith("[PM to"):
        content = content.replace(" (Online)", "")

    # Check if message is from bot "joker"
    if content.startswith("joker:") or content.startswith("[joker]:") or content.startswith("joker "):
        chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        chat_display.insert(tk.END, content + '\n', "bot_message")
    else:
        chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        chat_display.insert(tk.END, content + '\n')

    chat_display.config(state='disabled')
    chat_display.yview(tk.END)

    # Add tag configuration for bot messages
    chat_display.tag_configure("bot_message", foreground="blue", font=("Arial", 10, "italic"))

# Add a button to send message to bot
def send_message_to_bot():
    msg = entry.get()
    if msg:
        msg_to_send = f"@joker {msg}"
        display_message(f"{username} (to joker): {msg}")
        try:
            client.send(msg_to_send.encode('utf-8'))
        except Exception as e:
            print(f"Error sending message to bot: {e}")
            display_message("Failed to send message to bot.")
        entry.delete(0, tk.END)

# Add the button to the bottom frame after it is defined
def add_bot_button():
    bot_button = tk.Button(bottom_frame, text="Send to Bot", command=send_message_to_bot)
    bot_button.pack(padx=5, side=tk.LEFT)

root.after(100, add_bot_button)

# Modify send_message to detect if message is directed to bot and display accordingly
def send_message(event=None):
    msg = entry.get()
    print(f"send_message called with msg: {msg}")  # Debug print
    if msg:
        # Do not display private messages in global chat
        if msg.startswith("/pm "):
            # Extract recipient and message content for private messages
            try:
                _, rest = msg.split("/pm ", 1)
                recipient, private_msg = rest.split(" ", 1)
                if recipient in private_chat_windows:
                    private_chat_windows[recipient]['chat_display'].config(state='normal')
                    timestamp = datetime.datetime.now().strftime("%H:%M")
                    private_chat_windows[recipient]['chat_display'].insert(tk.END, f"[{timestamp}] You: {private_msg}\n")
                    private_chat_windows[recipient]['chat_display'].config(state='disabled')
                    private_chat_windows[recipient]['chat_display'].yview(tk.END)
                else:
                    open_private_chat_window(recipient)
                    private_chat_windows[recipient]['chat_display'].config(state='normal')
                    timestamp = datetime.datetime.now().strftime("%H:%M")
                    private_chat_windows[recipient]['chat_display'].insert(tk.END, f"[{timestamp}] You: {private_msg}\n")
                    private_chat_windows[recipient]['chat_display'].config(state='disabled')
                    private_chat_windows[recipient]['chat_display'].yview(tk.END)
            except ValueError:
                print("Invalid private message format.")
            return  # Exit function to prevent sending PM to public chat
        else:
            display_message(f"{username}: {msg}")

        try:
            client.send(msg.encode('utf-8'))
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

# Add button to open edit/delete messages window
def open_edit_delete_window():
    if hasattr(open_edit_delete_window, 'window') and open_edit_delete_window.window.winfo_exists():
        open_edit_delete_window.window.lift()
        return

    window = tk.Toplevel(root)
    window.title("Edit/Delete My Messages")
    window.geometry("400x300")

    listbox = tk.Listbox(window, width=60, height=15)
    listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Populate listbox with user's sent messages (show content only)
    for _, content in user_sent_messages[-50:]:  # Show last 50 messages
        listbox.insert(tk.END, content)

    def edit_selected():
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        message_id, old_content = user_sent_messages[-50 + index] if len(user_sent_messages) > 50 else user_sent_messages[index]
        new_content = simpledialog.askstring("Edit Message", "Enter new message content:", initialvalue=old_content, parent=window)
        if new_content and new_content != old_content:
            try:
                client.send(f"/edit {message_id} {new_content}".encode('utf-8'))
                # Update local list and listbox
                user_sent_messages[-50 + index if len(user_sent_messages) > 50 else index] = (message_id, new_content)
                listbox.delete(index)
                listbox.insert(index, new_content)
            except Exception as e:
                print(f"Error sending edit command: {e}")

    def delete_selected():
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        message_id, _ = user_sent_messages[-50 + index] if len(user_sent_messages) > 50 else user_sent_messages[index]
        confirm = tk.messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?", parent=window)
        if confirm:
            try:
                client.send(f"/delete {message_id}".encode('utf-8'))
                # Remove from local list and listbox
                del user_sent_messages[-50 + index if len(user_sent_messages) > 50 else index]
                listbox.delete(index)
            except Exception as e:
                print(f"Error sending delete command: {e}")

    btn_frame = tk.Frame(window)
    btn_frame.pack(pady=5)

    edit_btn = tk.Button(btn_frame, text="Edit", command=edit_selected)
    edit_btn.pack(side=tk.LEFT, padx=5)

    delete_btn = tk.Button(btn_frame, text="Delete", command=delete_selected)
    delete_btn.pack(side=tk.LEFT, padx=5)

    open_edit_delete_window.window = window

# Add Settings menu
settings_menu = tk.Menu(menu_bar, tearoff=0)
settings_menu.add_command(label="Theme", command=open_theme_settings)
settings_menu.add_command(label="Edit/Delete My Messages", command=open_edit_delete_window)

# Ensure group_window is properly defined and passed where needed
def open_group_settings():
    group_window = tk.Toplevel(root)
    group_window.title("Group Settings")
    group_window.geometry("400x300")

    def create_group():
        create_window = tk.Toplevel(group_window)
        create_window.title("Create Group")
        create_window.geometry("300x200")

        tk.Label(create_window, text="Group Name:").pack(pady=5)
        group_name_entry = tk.Entry(create_window)
        group_name_entry.pack(pady=5)

        def submit_group():
            group_name = group_name_entry.get()
            if group_name:
                try:
                    client.send(f"/create_group {group_name}".encode('utf-8'))
                    tk.messagebox.showinfo("Success", f"Group '{group_name}' created successfully!", parent=create_window)
                    create_window.destroy()
                except Exception as e:
                    tk.messagebox.showerror("Error", f"Failed to create group: {e}", parent=create_window)
            else:
                tk.messagebox.showerror("Error", "Group name cannot be empty.", parent=create_window)

        tk.Button(create_window, text="Create", command=submit_group).pack(pady=10)

    def invite_users():
        invite_window = tk.Toplevel(group_window)
        invite_window.title("Invite Users to Group")
        invite_window.geometry("300x200")
        tk.Label(invite_window, text="Group Name:").pack(pady=5)
        group_name_entry = tk.Entry(invite_window)
        group_name_entry.pack(pady=5)
        tk.Label(invite_window, text="User to Invite:").pack(pady=5)
        user_entry = tk.Entry(invite_window)
        user_entry.pack(pady=5)
        def send_invite():
            group_name = group_name_entry.get()
            user = user_entry.get()
            if group_name and user:
                try:
                    client.send(f"/invite_to_group {group_name} {user}".encode('utf-8'))
                    tk.messagebox.showinfo("Success", f"User '{user}' invited to group '{group_name}'!", parent=invite_window)
                    invite_window.destroy()
                except Exception as e:
                    tk.messagebox.showerror("Error", f"Failed to invite user: {e}", parent=invite_window)
            else:
                tk.messagebox.showerror("Error", "Group name and user cannot be empty.", parent=invite_window)
        tk.Button(invite_window, text="Invite", command=send_invite).pack(pady=10)
    def see_invites():
        invites_window = tk.Toplevel(group_window)
        invites_window.title("Group Invites")
        invites_window.geometry("300x200")
        tk.Label(invites_window, text="Pending Invites:").pack(pady=5)
        invites_listbox = tk.Listbox(invites_window, width=40, height=10)
        invites_listbox.pack(pady=5)
        def fetch_invites():
            try:
                client.send("/get_invites".encode('utf-8'))
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to fetch invites: {e}", parent=invites_window)
        fetch_invites()
    tk.Button(group_window, text="Create Group", command=create_group).pack(pady=5)
    tk.Button(group_window, text="Open Group Chat", command=open_group_chat_dialog).pack(pady=5)
    tk.Button(group_window, text="Invite Users to Group", command=invite_users).pack(pady=5)
    tk.Button(group_window, text="See Invites", command=see_invites).pack(pady=5)

# Initialize latest_groups_list to store the list of groups
latest_groups_list = []

def open_group_chat_dialog():
    # Check if the window already exists and bring it to focus
    if hasattr(open_group_chat_dialog, 'group_chat_window') and open_group_chat_dialog.group_chat_window.winfo_exists():
        open_group_chat_dialog.group_chat_window.lift()
        return

    group_chat_window = tk.Toplevel(root)
    open_group_chat_dialog.group_chat_window = group_chat_window  # Store reference to the window
    group_chat_window.title("Open Group Chat")
    group_chat_window.geometry("300x300")

    tk.Label(group_chat_window, text="Your Groups:").pack(pady=5)

    global buttons_frame
    buttons_frame = tk.Frame(group_chat_window)
    buttons_frame.pack(pady=5, fill=tk.BOTH, expand=True)

    def open_group(group_name):
        try:
            print(f"Opening group chat for: {group_name}")  # Debug log
            # Send a command to the server to get group info
            command = f"/get_group_info {group_name}"
            print(f"[DEBUG] Sending command to server: {command}")
            client.send(command.encode('utf-8'))
            response = client.recv(1024).decode('utf-8')
            print(f"[DEBUG] Received response: {response}")

            if response.startswith("__group_info__:"):
                group_info = response[len("__group_info__:"):].split(":")
                if len(group_info) >= 3:
                    group_name, group_creator, group_members = group_info[0], group_info[1], group_info[2]
                    print(f"[DEBUG] Group Name: {group_name}, Creator: {group_creator}, Members: {group_members}")

                    # Check if the group chat window already exists
                    if hasattr(open_group, 'group_chat_windows') and group_name in open_group.group_chat_windows:
                        print(f"[DEBUG] Group chat window for '{group_name}' already exists. Bringing it to focus.")
                        open_group.group_chat_windows[group_name].lift()
                        return

                    # Create a new group chat window
                    group_chat_window = tk.Toplevel(root)
                    group_chat_window.title(f"Group Chat - {group_name}")
                    group_chat_window.geometry("400x400")

                    tk.Label(group_chat_window, text=f"Group: {group_name}").pack(pady=5)
                    tk.Label(group_chat_window, text=f"Creator: {group_creator}").pack(pady=5)
                    tk.Label(group_chat_window, text=f"Members: {group_members}").pack(pady=5)

                    # Store the window reference for reuse
                    if not hasattr(open_group, 'group_chat_windows'):
                        open_group.group_chat_windows = {}
                    open_group.group_chat_windows[group_name] = group_chat_window
                else:
                    print("[DEBUG] Incomplete group info received.")
                    tk.messagebox.showerror("Error", "Failed to open group chat. Incomplete group info received.", parent=group_chat_window)
            else:
                print("[DEBUG] Unexpected server response format.")
                tk.messagebox.showerror("Error", "Failed to open group chat. Unexpected response from server.", parent=group_chat_window)
        except Exception as e:
            print(f"Error opening group chat: {e}")  # Debug log
            tk.messagebox.showerror("Error", f"Failed to open group chat: {e}", parent=root)

    def fetch_groups():
        def fetch():
            try:
                command = f"/get_groups {username}"  # Include username in the command
                print(f"[DEBUG] Sending command to server: {command}")
                client.send(command.encode('utf-8'))
                response = client.recv(1024).decode('utf-8')
                print(f"[DEBUG] Received response: {response}")

                if response.startswith("__groups__:"):
                    global latest_groups_list
                    # Handle empty group list gracefully
                    groups_part = response[len("__groups__:"):]
                    if groups_part.strip() == "":
                        latest_groups_list = []
                    else:
                        latest_groups_list = [group.strip() for group in groups_part.split(",") if group.strip()]
                    print(f"[DEBUG] Updated latest_groups_list: {latest_groups_list}")

                    def update_ui():
                        global buttons_frame  # Ensure global declaration is at the top
                        if buttons_frame is None or not buttons_frame.winfo_exists():
                            print("[DEBUG] Initializing or reinitializing buttons_frame.")
                            buttons_frame = tk.Frame(group_chat_window)
                            buttons_frame.pack(pady=5, fill=tk.BOTH, expand=True)

                        print(f"[DEBUG] latest_groups_list: {latest_groups_list}")

                        for widget in buttons_frame.winfo_children():
                            widget.destroy()

                        if not latest_groups_list:
                            print("[DEBUG] No groups to display.")
                            tk.Label(buttons_frame, text="You don't have any group chats.").pack()
                        else:
                            for group in latest_groups_list:
                                print(f"[DEBUG] Adding group to UI: {group}")
                                tk.Button(buttons_frame, text=group, width=25, command=lambda g=group: open_group(g)).pack(pady=2, fill=tk.X)

                    group_chat_window.after(0, update_ui)
                else:
                    print("[DEBUG] Unexpected server response format.")
                    group_chat_window.after(0, lambda: tk.messagebox.showerror("Error", "Failed to fetch groups. Unexpected response from server.", parent=group_chat_window))
            except Exception as e:
                print(f"[DEBUG] Error fetching groups: {e}")
                group_chat_window.after(0, lambda: tk.messagebox.showerror("Error", f"Failed to fetch groups: {e}", parent=group_chat_window))

        threading.Thread(target=fetch, daemon=True).start()

    fetch_groups()

# Add "Group" to the Settings menu
settings_menu.add_command(label="Group", command=open_group_settings)


menu_bar.add_cascade(label="Settings", menu=settings_menu)

chat_display = ScrolledText(root, wrap=tk.WORD, state='disabled', width=50, height=20)
# Create a frame for chat display and user list
main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

chat_display = ScrolledText(main_frame, wrap=tk.WORD, state='disabled', width=50, height=20)
chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Dictionary to map message_id to text widget indices for editing/deletion
message_id_to_index = {}

# List to store user's sent messages as tuples (message_id, message_content)
user_sent_messages = []

# Define a tag for small timestamp font
chat_display.tag_configure("timestamp", font=("Arial", 8), foreground="gray")

button_bar = tk.Frame(main_frame)
button_bar.pack(side=tk.TOP, fill=tk.X)
button_bar.pack_forget()  # Hide initially

edit_btn = tk.Button(button_bar, text="Edit", command=lambda: None)
delete_btn = tk.Button(button_bar, text="Delete", command=lambda: None)
edit_btn.pack(side=tk.LEFT, padx=5, pady=2)
delete_btn.pack(side=tk.LEFT, padx=5, pady=2)

current_hovered_message_id = None

def on_message_hover_enter(event):
    global current_hovered_message_id
    idx = chat_display.index(f"@{event.x},{event.y}")
    line = chat_display.index(f"{idx} linestart")
    msg_id = None; min_diff=None
    for mid, i in message_id_to_index.items():
        try: d=abs(int(float(i))-int(float(line)))
        except: d=None
        if d is not None and (min_diff is None or d<min_diff): min_diff, msg_id=d, mid
    if not msg_id: return
    text=chat_display.get(line, f"{line} lineend")
    if not text.startswith(f"{username}:"): return
    current_hovered_message_id=msg_id
    button_bar.pack(side=tk.TOP, fill=tk.X)

def on_message_hover_leave(event):
    global current_hovered_message_id
    current_hovered_message_id=None
    button_bar.pack_forget()


def edit_message():
    if current_hovered_message_id is None:
        return
    new_content = simpledialog.askstring("Edit Message", "Enter new message content:", parent=root)
    if new_content:
        try:
            client.send(f"/edit {current_hovered_message_id} {new_content}".encode('utf-8'))
        except Exception as e:
            print(f"Error sending edit command: {e}")

def delete_message():
    if current_hovered_message_id is None:
        return
    confirm = tk.messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?", parent=root)
    if confirm:
        try:
            client.send(f"/delete {current_hovered_message_id}".encode('utf-8'))
        except Exception as e:
            print(f"Error sending delete command: {e}")

edit_btn.config(command=edit_message)
delete_btn.config(command=delete_message)
chat_display.tag_bind("user_message","<Enter>",on_message_hover_enter)
chat_display.tag_bind("user_message","<Leave>",on_message_hover_leave)

# Context menu

chat_display.tag_bind("user_message", "<Enter>", on_message_hover_enter)
chat_display.tag_bind("user_message", "<Leave>", on_message_hover_leave)

# Add right-click context menu for edit/delete
def on_right_click(event):
    try:
        index = chat_display.index(f"@{event.x},{event.y}")
        line_start = chat_display.index(f"{index} linestart")
        line_end = chat_display.index(f"{index} lineend")
        # Find message_id for this line
        message_id = None
        for mid, idx in message_id_to_index.items():
            if idx == line_start:
                message_id = mid
                break
        if message_id is None:
            return  # No message_id found for this line

        # Create context menu
        menu = tk.Menu(root, tearoff=0)
        def edit_message():
            # Prompt for new message content
            new_content = simpledialog.askstring("Edit Message", "Enter new message content:", parent=root)
            if new_content:
                # Send edit command to server
                try:
                    client.send(f"/edit {message_id} {new_content}".encode('utf-8'))
                except Exception as e:
                    print(f"Error sending edit command: {e}")

        def delete_message():
            # Confirm deletion
            confirm = tk.messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?", parent=root)
            if confirm:
                try:
                    client.send(f"/delete {message_id}".encode('utf-8'))
                except Exception as e:
                    print(f"Error sending delete command: {e}")

        menu.add_command(label="Edit", command=edit_message)
        menu.add_command(label="Delete", command=delete_message)
        menu.tk_popup(event.x_root, event.y_root)
    except Exception as e:
        print(f"Error in right-click menu: {e}")

chat_display.bind("<Button-3>", on_right_click)  # Right-click binding for Windows/Linux
chat_display.bind("<Button-2>", on_right_click)  # Middle-click binding for Mac

# User list box
user_listbox = tk.Listbox(main_frame, width=20, height=20)
user_listbox.pack(side=tk.LEFT, fill=tk.Y, padx=5)

# Create a frame at the bottom for entry and emoji button
bottom_frame = tk.Frame(root)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

entry = tk.Entry(bottom_frame, width=50)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Add button to open edit/delete messages window
def open_edit_delete_window():
    if hasattr(open_edit_delete_window, 'window') and open_edit_delete_window.window.winfo_exists():
        open_edit_delete_window.window.lift()
        return

    window = tk.Toplevel(root)
    window.title("Edit/Delete My Messages")
    window.geometry("400x300")

    listbox = tk.Listbox(window, width=60, height=15)
    listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Populate listbox with user's sent messages (show content only)
    for _, content in user_sent_messages[-50:]:  # Show last 50 messages
        listbox.insert(tk.END, content)

    def edit_selected():
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        message_id, old_content = user_sent_messages[-50 + index] if len(user_sent_messages) > 50 else user_sent_messages[index]
        new_content = simpledialog.askstring("Edit Message", "Enter new message content:", initialvalue=old_content, parent=window)
        if new_content and new_content != old_content:
            try:
                client.send(f"/edit {message_id} {new_content}".encode('utf-8'))
                # Update local list and listbox
                user_sent_messages[-50 + index if len(user_sent_messages) > 50 else index] = (message_id, new_content)
                listbox.delete(index)
                listbox.insert(index, new_content)
            except Exception as e:
                print(f"Error sending edit command: {e}")

    def delete_selected():
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        message_id, _ = user_sent_messages[-50 + index] if len(user_sent_messages) > 50 else user_sent_messages[index]
        confirm = tk.messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?", parent=window)
        if confirm:
            try:
                client.send(f"/delete {message_id}".encode('utf-8'))
                # Remove from local list and listbox
                del user_sent_messages[-50 + index if len(user_sent_messages) > 50 else index]
                listbox.delete(index)
            except Exception as e:
                print(f"Error sending delete command: {e}")

    btn_frame = tk.Frame(window)
    btn_frame.pack(pady=5)

    edit_btn = tk.Button(btn_frame, text="Edit", command=edit_selected)
    edit_btn.pack(side=tk.LEFT, padx=5)

    delete_btn = tk.Button(btn_frame, text="Delete", command=delete_selected)
    delete_btn.pack(side=tk.LEFT, padx=5)

    open_edit_delete_window.window = window


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

typing_users = set()
typing_label = tk.Label(root, text="", fg="gray")
typing_label.pack(padx=10, pady=(0, 10))

def on_typing(event=None):
    # Send typing notification to server
    client.send(f"__typing__:{username}".encode())

    entry.bind("<KeyPress>", on_typing)

# Define group_chat_windows to manage group chat windows
group_chat_windows = {}

# Implement open_group_chat_window to handle opening group chat windows
def open_group_chat_window(group_name):
    if group_name in group_chat_windows:
        # If the window already exists, bring it to the front
        group_chat_windows[group_name]['window'].deiconify()
        group_chat_windows[group_name]['window'].lift()
        return

    # Create a new group chat window
    group_window = tk.Toplevel(root)
    group_window.title(f"Group Chat - {group_name}")
    group_window.geometry("500x350")

    chat_display = ScrolledText(group_window, wrap=tk.WORD, state='disabled', width=50, height=15)
    chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Add a frame on the right side for members list
    members_frame = tk.Frame(group_window, width=150)
    members_frame.pack(padx=5, pady=10, fill=tk.Y, side=tk.RIGHT)

    tk.Label(members_frame, text="Members:").pack(pady=5)

    members_listbox = tk.Listbox(members_frame, width=20, height=15)
    members_listbox.pack(pady=5, fill=tk.Y, expand=True)

    entry_frame = tk.Frame(group_window)
    entry_frame.pack(fill=tk.X, padx=10, pady=5)

    entry = tk.Entry(entry_frame, width=40)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def send_group_message(event=None):
        msg = entry.get()
        if msg:
            msg_to_send = f"/group_msg {group_name} {msg}"
            try:
                client.send(msg_to_send.encode('utf-8'))
                # Display the message in the group chat window
                chat_display.config(state='normal')
                timestamp = datetime.datetime.now().strftime("%H:%M")
                chat_display.insert(tk.END, f"[{timestamp}] You: {msg}\n")
                chat_display.config(state='disabled')
                chat_display.yview(tk.END)
                entry.delete(0, tk.END)
            except Exception as e:
                print(f"Error sending group message: {e}")
                tk.messagebox.showerror("Error", "Failed to send group message.", parent=group_window)

    entry.bind("<Return>", send_group_message)

    send_button = tk.Button(entry_frame, text="Send", command=send_group_message)
    send_button.pack(side=tk.LEFT, padx=5)

    def on_close():
        group_chat_windows.pop(group_name, None)
        group_window.destroy()

    group_window.protocol("WM_DELETE_WINDOW", on_close)

    group_chat_windows[group_name] = {'window': group_window, 'chat_display': chat_display}

cached_group_info = {}

def receive_messages():
    print("receive_messages thread started")  # Debug print
    history_buffer = ""
    receiving_history = False
    while True:
        try:
            msg = client.recv(4096).decode(errors='replace')
            print(f"Received message: {msg}")  # Debug log
            if not msg:
                print("Server closed connection.")
                display_message("Disconnected from server.")
                reconnect()
                break
            if msg.startswith("__group_info__:"):
                # Handle group info message
                try:
                    global cached_group_info
                    print(f"Debug: Received group info message: {msg}")  # Debug log
                    parts = msg.split(":", 3)
                    if len(parts) < 4:
                        print(f"Malformed group info message: {msg}")
                        return

                    _, group_name, creator, members_str = parts
                    print(f"Debug: Parsed group_name={group_name}, creator={creator}, members_str={members_str}")  # Debug log
                    members = members_str.split(",") if members_str.strip() else []

                    # Check if the group chat window already exists
                    if group_name in group_chat_windows:
                        group_chat_window = group_chat_windows[group_name]
                        chat_display = group_chat_window['chat_display']
                        chat_display.config(state='normal')
                        chat_display.insert(tk.END, f"Group Members: {', '.join(members)}\n")
                        chat_display.config(state='disabled')
                        chat_display.yview(tk.END)
                    else:
                        # Cache group info and open a new group chat window
                        cached_group_info[group_name] = members
                        open_group_chat_window(group_name)
                except Exception as e:
                    print(f"Error processing group info message: {e}")
            elif msg.startswith("__history__:") or receiving_history:
                receiving_history = True
                history_buffer += msg.replace("__history__:", "")
                if "__history_end__" in history_buffer:
                    full_history = history_buffer.replace("__history_end__", "")
                    for line in full_history.splitlines():
                        display_message(line)
                    history_buffer = ""
                    receiving_history = False
            elif msg.startswith("__typing__:"):
                typing_user = msg.split(":", 1)[1]
                typing_users.add(typing_user)
                typing_label.config(text=f"{', '.join(typing_users)} {'is' if len(typing_users) == 1 else 'are'} typing...")
                def clear_typing(user=typing_user):
                    typing_users.discard(user)
                    if not typing_users:
                        typing_label.config(text="")
                root.after(3000, clear_typing)
            elif msg == "__typing_stopped__":
                typing_users.discard(username)
                if not typing_users:
                    typing_label.config(text="")
            elif msg.startswith("__user_list__:"):
                user_list_str = msg[len("__user_list__:"):]
                users = user_list_str.split(",") if user_list_str else []
                user_listbox.delete(0, tk.END)
                for user_status in users:
                    if user_status:
                        parts = user_status.split("|")
                        user_name = parts[0]
                        status = parts[1] if len(parts) > 1 else "Online"
                        user_listbox.insert(tk.END, f"{user_name} ({status})")
            elif msg.startswith("[PM from"):
                # Extract sender and message content
                try:
                    sender = msg.split("[PM from ", 1)[1].split("]", 1)[0]
                    private_msg = msg.split("]", 1)[1].strip()
                    if sender not in private_chat_windows:
                        open_private_chat_window(sender)
                    private_chat_windows[sender]['chat_display'].config(state='normal')
                    timestamp = datetime.datetime.now().strftime("%H:%M")
                    private_chat_windows[sender]['chat_display'].insert(tk.END, f"[{timestamp}] {sender}: {private_msg}\n")
                    private_chat_windows[sender]['chat_display'].config(state='disabled')
                    private_chat_windows[sender]['chat_display'].yview(tk.END)
                except Exception as e:
                    print(f"Error processing private message: {e}")
            elif msg.startswith("[Group msg]"):
                # Format: [Group msg] group_name username: message
                try:
                    content = msg[len("[Group msg]"):].strip()
                    group_name, rest = content.split(" ", 1)
                    sender_name, message_text = rest.split(":", 1)
                    sender_name = sender_name.strip()
                    message_text = message_text.strip()
                    if group_name not in group_chat_windows:
                        # Optionally open the group chat window automatically
                        open_group_chat_window(group_name)
                    group_chat_windows[group_name]['chat_display'].config(state='normal')
                    timestamp = datetime.datetime.now().strftime("%H:%M")
                    group_chat_windows[group_name]['chat_display'].insert(tk.END, f"[{timestamp}] {sender_name}: {message_text}\n")
                    group_chat_windows[group_name]['chat_display'].config(state='disabled')
                    group_chat_windows[group_name]['chat_display'].yview(tk.END)
                except Exception as e:
                    print(f"Error processing group message: {e}")
            else:
                print(f"Displaying message: {msg}")  # Debug log
                display_message(msg)
        except Exception as e:
            print(f"Error receiving message: {e}")
            break

import time

time.sleep(0.5)  # Small delay before starting receive thread

def reconnect():
    global client
    global username
    global password

    display_message("Attempting to reconnect...")
    try:
        client.close()
    except:
        pass

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((Server_IP, port))
        if password:
            client.send(f"{username}::{password}".encode())
        else:
            client.send(username.encode())
        display_message("Reconnected to server.")
        threading.Thread(target=receive_messages, daemon=True).start()
    except Exception as e:
        display_message(f"Reconnect failed: {e}")
        # Retry after delay
        root.after(5000, reconnect)

threading.Thread(target=receive_messages, daemon=True).start()

entry.bind("<Return>", send_message)

def handle_exit(signal_received, frame):
    print("\n[INFO] Exiting program gracefully...")
    try:
        client.close()
    except Exception as e:
        print(f"[ERROR] Failed to close client socket: {e}")
    root.destroy()
    exit(0)

# Register signal handler for graceful shutdown
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

root.mainloop()