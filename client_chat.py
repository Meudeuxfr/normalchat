import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import simpledialog, filedialog
import queue
import datetime
import signal
import time
import socket
import os
import threading
from plyer import notification
import re
from tkinter import PhotoImage, Label
import json
import ssl  # Add at the top with other imports

# Declare buttons_frame as a global variable
buttons_frame = None

# Initialize client socket variable
client = None

print("Client script started")  # Debug print at start

# ------ config ------

Server_IP = '192.168.56.1'
port = 5555

file_list_event = threading.Event()
file_list_result = None

file_download_event = threading.Event()
file_download_result = None
file_download_error = None

# ——————————————
# Estado global do download de ficheiro
file_download_in_progress = False
file_download_request     = None
file_download_buffer      = bytearray()
file_download_expected_size = 0
file_download_event       = threading.Event()
# ——————————————
selected_user_frame = None 

root = tk.Tk()

# SSL context for secure connection
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
# If you have a server certificate, you can load it here:
# ssl_context.load_verify_locations('server_cert.pem')
# To disable certificate verification (not recommended for production):
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# --- Registration/Login UI on root window ---
def build_login_ui():
    global status_label  # Declare status_label as global
    if not root.winfo_exists():
        # If root is destroyed, do nothing (or recreate root if needed)
        print("[ERROR] Root window has been destroyed. Cannot build login UI.")
        return
    for widget in root.winfo_children():
        try:
            widget.destroy()
        except Exception as e:
            print(f"[DEBUG] Could not destroy widget: {e}")
    root.title("Login or Register")
    root.geometry("300x250")
    tk.Label(root, text="Username:").pack(pady=5)
    username_entry = tk.Entry(root)
    username_entry.pack(pady=5)
    tk.Label(root, text="Password:").pack(pady=5)
    password_entry = tk.Entry(root, show='*')
    password_entry.pack(pady=5)
    status_label = tk.Label(root, text="")  # Initialize status_label
    status_label.pack(pady=5)

    def do_login():
        global username, password, client, status_label
        username = username_entry.get()
        password = password_entry.get()
        if not username or not password:
            status_label.config(text="Username and password required.")
            return
        try:
            if client:
                try:
                    client.close()
                except:
                    pass
            # Create a new socket and wrap with SSL
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client = ssl_context.wrap_socket(raw_sock, server_hostname=Server_IP)
            client.connect((Server_IP, port))
            client.send(f"{username}::{password}".encode())
            resp = client.recv(4096).decode('utf-8')
            if resp == "User does not exist":
                status_label.config(text="User does not exist")
                client.close()
                client = None
                return
            elif resp == "Password not correct":
                status_label.config(text="Password not correct")
                client.close()
                client = None
                return
            elif resp.startswith("Invalid"):
                status_label.config(text=resp)
                client.close()
                client = None
                return
            print(f"Username '{username}' sent to server.")  # Only print after successful login
            # Destroy login UI and show main chat UI
            for widget in root.winfo_children():
                widget.destroy()
            root.geometry("800x600")  # Make chat window larger
            show_main_chat_ui()
        except Exception as e:
            if status_label and status_label.winfo_exists():
                status_label.config(text=f"Login failed: {e}")
            else:
                print(f"Login failed: {e}")
            if client:
                client.close()
                client = None

    def do_register():
        global client
        uname = username_entry.get()
        pwd = password_entry.get()
        if not uname or not pwd:
            status_label.config(text="Username and password required.")
            return
        try:
            if client:
                try:
                    client.close()
                except:
                    pass
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((Server_IP, port))
            client.send(f"/register {uname} {pwd}".encode())
            resp = client.recv(4096).decode('utf-8')
            client.close()
            client = None
            if resp.startswith("__register_success__"):
                status_label.config(text="Registration successful! Please login.")
            else:
                status_label.config(text=resp)
        except Exception as e:
            status_label.config(text=f"Registration failed: {e}")

    tk.Button(root, text="Login", command=do_login).pack(pady=5)
    tk.Button(root, text="Register", command=do_register).pack(pady=5)


def open_server_settings_window():
    tk.messagebox.showinfo("Server Settings", "This feature is under development.")

def show_main_chat_ui():
    global admins  # Ensure 'admins' is accessible

    # Initialize the admins list if not already done
    global admins
    if 'admins' not in globals():
        admins = []
    
    if username == "meudeux":
        admins.append(username)
    
    root.title(f"Chat Client - {username}")

    # Initialize bottom_frame before use
    global bottom_frame
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

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

    log_queue = queue.Queue()
    log_file_path = "chat_log.txt"
    log_bytes_written = 0
    log_thread_running = True

    def log_writer():
        global log_bytes_written
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            while log_thread_running or not log_queue.empty():
                try:
                    message = log_queue.get(timeout=0.5)
                    log_file.write(message)
                    log_file.flush()
                    log_bytes_written += len(message.encode("utf-8"))
                    print(f"[DEBUG] Written {log_bytes_written} bytes to log file.")
                    log_queue.task_done()
                except queue.Empty:
                    continue

    def log_message(message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}\n"
        log_queue.put(log_entry)

    # Start the background log writer thread
    log_thread = threading.Thread(target=log_writer, daemon=True)
    log_thread.start()

    def format_message(message):
        """Format message with bold, italics, and links."""
        message = re.sub(r"\*\*(.*?)\*\*", r"\1", message)  # Bold
        message = re.sub(r"\*(.*?)\*", r"\1", message)  # Italics
        message = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", message)  # Links
        return message

    # Update display_message to use format_message

    def display_message(message):
        formatted_message = format_message(message)
        chat_display.config(state='normal')
        timestamp = datetime.datetime.now().strftime("%H:%M")
        chat_display.insert(tk.END, f"[{timestamp}] {formatted_message}\n")
        chat_display.config(state='disabled')
        chat_display.yview(tk.END)

    # Add a button to send message to bot
    def send_message_to_bot():
        msg = entry.get()
        if msg:
            msg_to_send = f"@joker {msg}"
            display_message(f"{username} (to joker): {msg}")
            try:
                if client:
                    client.send(msg_to_send.encode('utf-8'))
                else:
                    print("Client socket is None, cannot send message to bot.")
                    display_message("Not connected to server.")
            except Exception as e:
                print(f"Error sending message to bot: {e}")
                display_message("Failed to send message to bot.")
            entry.delete(0, tk.END)

    # Add the button to the bottom frame after it is defined
    def add_bot_button():
        bot_button = tk.Button(bottom_frame, text="Send to Bot", command=send_message_to_bot)
        bot_button.pack(padx=5, side=tk.LEFT)

    root.after(100, add_bot_button)

    # --- Rate limiting state ---
    last_main_message_time = [0]  # Use list for mutability in nested functions
    last_group_message_times = {}  # group_name -> last send timestamp
    RATE_LIMIT_SECONDS = 1.0

    # Modify send_message to detect if message is directed to bot and display accordingly
    def send_message(event=None):
        import time
        now = time.time()
        if now - last_main_message_time[0] < RATE_LIMIT_SECONDS:
            display_message("You are sending messages too quickly. Please wait a moment.")
            return
        last_main_message_time[0] = now

        msg = entry.get()
        print(f"send_message called with msg: {msg}")  # Debug print
        if msg:
            global file_download_in_progress, file_download_request
            # Detect manual /get_file command and set download flags
            if msg.startswith("/get_file "):
                try:
                    _, filename = msg.split(" ", 1)
                    file_download_in_progress = True
                    file_download_request = filename.strip()
                    print(f"[DEBUG] Manual file download requested for: {file_download_request}")
                except Exception as e:
                    print(f"[ERROR] Failed to parse /get_file command: {e}")

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
                if client:
                    client.send(msg.encode('utf-8'))
                    print("Message sent to server")  # Debug print
                else:
                    print("Client socket is None, cannot send message.")
                    display_message("Not connected to server.")
            except Exception as e:
                print(f"Error sending message: {e}")
                display_message("Failed to send message.")
            entry.delete(0, tk.END)
        else:
            # If message is empty, send typing stopped notification
            try:
                if client:
                    client.send("__typing_stopped__".encode('utf-8'))
                else:
                    print("Client socket is None, cannot send typing stopped notification.")
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
                    # Update local list and listbox
                    user_sent_messages[-50 + index if len(user_sent_messages) > 50 else index] = (message_id, new_content)
                    listbox.delete(index)
                    listbox.insert(index, new_content)
                except Exception as e:
                    print(f"Error sending edit command: {e}")

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

        delete_btn = tk.Button(btn_frame, text="Delete", command=delete_selected)
        delete_btn.pack(side=tk.LEFT, padx=5)

        open_edit_delete_window.window = window

    # --- Group Management Panel ---
    def open_group_management_window():
        if hasattr(open_group_management_window, 'window') and open_group_management_window.window.winfo_exists():
            open_group_management_window.window.lift()
            return
        win = tk.Toplevel(root)
        win.title("Group Management")
        win.geometry("400x400")
        open_group_management_window.window = win

        tk.Label(win, text="Your Groups:").pack(pady=5)
        group_listbox = tk.Listbox(win, width=40, height=10)
        group_listbox.pack(pady=5)

        def refresh_groups():
            group_listbox.delete(0, tk.END)
            if latest_groups_list:
                for g in latest_groups_list:
                    group_listbox.insert(tk.END, g)
            else:
                group_listbox.insert(tk.END, "No groups found.")

        refresh_groups()

        def create_group():
            cg_win = tk.Toplevel(win)
            cg_win.title("Create Group")
            cg_win.geometry("250x120")
            tk.Label(cg_win, text="Group Name:").pack(pady=5)
            name_entry = tk.Entry(cg_win)
            name_entry.pack(pady=5)
            def submit():
                group_name = name_entry.get().strip()
                if group_name:
                    try:
                        client.send(f"/create_group {group_name}".encode('utf-8'))
                        log_message(f"[Analytics] Created group: {group_name}")
                        cg_win.destroy()
                    except Exception as e:
                        tk.messagebox.showerror("Error", f"Failed to create group: {e}", parent=cg_win)
            tk.Button(cg_win, text="Create", command=submit).pack(pady=5)

        def invite_user():
            inv_win = tk.Toplevel(win)
            inv_win.title("Invite User to Group")
            inv_win.geometry("250x150")
            tk.Label(inv_win, text="Group Name:").pack(pady=2)
            group_entry = tk.Entry(inv_win)
            group_entry.pack(pady=2)
            tk.Label(inv_win, text="Username:").pack(pady=2)
            user_entry = tk.Entry(inv_win)
            user_entry.pack(pady=2)
            def submit():
                group = group_entry.get().strip()
                user = user_entry.get().strip()
                if group and user:
                    try:
                        client.send(f"/invite_to_group {group} {user}".encode('utf-8'))
                        log_message(f"[Analytics] Invited {user} to group: {group}")
                        inv_win.destroy()
                    except Exception as e:
                        tk.messagebox.showerror("Error", f"Failed to invite: {e}", parent=inv_win)
            tk.Button(inv_win, text="Invite", command=submit).pack(pady=5)

        def leave_group():
            sel = group_listbox.curselection()
            if not sel:
                tk.messagebox.showinfo("Info", "Select a group to leave.", parent=win)
                return
            group = group_listbox.get(sel[0])
            if group == "No groups found.":
                return
            if tk.messagebox.askyesno("Leave Group", f"Leave group '{group}'?", parent=win):
                try:
                    client.send(f"/leave_group {group}".encode('utf-8'))
                    log_message(f"[Analytics] Left group: {group}")
                except Exception as e:
                    tk.messagebox.showerror("Error", f"Failed to leave group: {e}", parent=win)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Create Group", command=create_group).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Invite User", command=invite_user).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Leave Group", command=leave_group).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Refresh", command=refresh_groups).pack(side=tk.LEFT, padx=5)

    # Add to Settings menu
    settings_menu = tk.Menu(menu_bar, tearoff=0)
    settings_menu.add_command(label="Group Management", command=open_group_management_window)

    # Add Settings menu to the menu bar
    menu_bar.add_cascade(label="Settings", menu=settings_menu)

    # Ensure the menu bar is updated after adding all commands
    root.config(menu=menu_bar)

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
            invites_window = tk.Toplevel(root)
            invites_window.title("Group Invites")
            invites_window.geometry("300x200")

            tk.Label(invites_window, text="Pending Invites:").pack(pady=5)

            def fetch_invites():
                def fetch():
                    try:
                        # Send a command to fetch pending invites
                        client.send("/get_invites".encode('utf-8'))
                        response = client.recv(4096).decode('utf-8')
                        print(f"[DEBUG] Server response: {response}")  # Debug print to check server response
                        if response.startswith("__invites__:"):
                            invites = response[len("__invites__:"):].split(",")
                            invites = [invite.strip() for invite in invites if invite.strip()]
                            if invites:
                                if invites_window.winfo_exists():
                                    invites_window.after(0, lambda: populate_invites(invites))
                            else:
                                if invites_window.winfo_exists():
                                    invites_window.after(0, lambda: tk.Label(invites_window, text="No pending invites.").pack(pady=5))
                        else:
                            if invites_window.winfo_exists():
                                invites_window.after(0, lambda: tk.messagebox.showerror("Error", "Failed to fetch invites.", parent=invites_window))
                    except Exception as e:
                        print(f"Error fetching invites: {e}")
                        if invites_window.winfo_exists():
                            invites_window.after(0, lambda: tk.messagebox.showerror("Error", "Failed to fetch invites.", parent=invites_window))

                threading.Thread(target=fetch, daemon=True).start()

            def accept_invite(group_name):
                try:
                    # Send a command to accept the invite
                    client.send(f"/accept_invite {group_name}".encode('utf-8'))
                    tk.messagebox.showinfo("Success", f"You have joined the group: {group_name}", parent=invites_window)
                    for widget in invites_window.winfo_children():
                        if isinstance(widget, tk.Button) and widget.cget("text") == group_name:
                            widget.destroy()
                except Exception as e:
                    print(f"Error accepting invite: {e}")
                    tk.messagebox.showerror("Error", "Failed to accept invite.", parent=invites_window)

            def populate_invites(invites):
                for group_name in invites:
                    btn = tk.Button(invites_window, text=group_name, command=lambda g=group_name: accept_invite(g))
                    btn.pack(pady=2, fill=tk.X)

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

        def update_ui():
            nonlocal latest_groups_list
            global buttons_frame
            print("[DEBUG] update_ui called")  # Debug print to verify call
            if not hasattr(open_group_chat_dialog, 'group_chat_window') or not open_group_chat_dialog.group_chat_window.winfo_exists():
                print("[DEBUG] group_chat_window does not exist")  # Debug print
                return
            group_chat_window = open_group_chat_dialog.group_chat_window
            # Always (re)pack buttons_frame and set a visible border for debug
            if buttons_frame is None or not buttons_frame.winfo_exists():
                buttons_frame = tk.Frame(group_chat_window, bg="#e0e0e0", bd=2, relief="groove")
                buttons_frame.pack(pady=5, fill=tk.BOTH, expand=True)
            else:
                buttons_frame.pack(pady=5, fill=tk.BOTH, expand=True)            # Destroy all children before adding new ones
            for widget in buttons_frame.winfo_children():
                widget.destroy()

            print(f"[DEBUG] latest_groups_list at update_ui: {latest_groups_list}")
            if not latest_groups_list:
                tk.Label(buttons_frame, text="You don't have any group chats.").pack()
            else:
                print(f"[DEBUG] latest_groups_list before button creation: {latest_groups_list}")
                for group in latest_groups_list:
                    print(f"[DEBUG] Creating button for group: {group}")  # Debug print for each button
                    btn = tk.Button(buttons_frame, text=group, width=25, command=lambda g=group: open_group(g))
                    btn.pack(pady=2, fill=tk.X)
                    print(f"[DEBUG] Button '{group}' mapped: {btn.winfo_ismapped()}, viewable: {btn.winfo_viewable()}, size: {btn.winfo_width()}x{btn.winfo_height()}, fg: {btn.cget('fg')}, bg: {btn.cget('bg')}")
                    print(f"[DEBUG] Button '{group}' parent: {btn.master}, pack info: {btn.pack_info()}")
                print(f"[DEBUG] Number of buttons created: {len(buttons_frame.winfo_children())}")
                print(f"[DEBUG] buttons_frame mapped: {buttons_frame.winfo_ismapped()}, viewable: {buttons_frame.winfo_viewable()}, size: {buttons_frame.winfo_width()}x{buttons_frame.winfo_height()}")
                print(f"[DEBUG] Children of buttons_frame: {buttons_frame.winfo_children()}")
            buttons_frame.lift()
            buttons_frame.focus_set()
            group_chat_window.lift()
            group_chat_window.update_idletasks()
            group_chat_window.update()


        
        def open_group(group_name):
            try:
                print(f"[DEBUG] Sending command to open group: {group_name}")
                command = f"/get_group_info {group_name}"
                client.send(command.encode('utf-8'))
            except Exception as e:
                print(f"[ERROR] Exception occurred while sending open group command '{group_name}': {e}")
                tk.messagebox.showerror("Error", f"Failed to send open group command: {e}", parent=root)

        def fetch_groups():
            def fetch():
                if not ensure_connected(parent_window=group_chat_window):
                    return
                try:
                    client.send("/get_groups".encode('utf-8'))
                except Exception as e:
                    print(f"[DEBUG] Error sending /get_groups: {e}")
            threading.Thread(target=fetch, daemon=True).start()

        fetch_groups()
        # Call update_ui initially (in case latest_groups_list is already set)
        group_chat_window.after(0, update_ui)
        # Store update_ui for external call
        open_group_chat_dialog.update_ui = update_ui

    # Automatically open group chat dialog after login
    def open_group_chat_dialog_auto():
        open_group_chat_dialog()
        if hasattr(open_group_chat_dialog, 'update_ui'):
            open_group_chat_dialog.group_chat_window.after(0, open_group_chat_dialog.update_ui)

    # Schedule automatic opening of group chat dialog after login UI is destroyed
    root.after(2000, open_group_chat_dialog_auto)

    # Add "Group" to the Settings menu
    settings_menu.add_command(label="Group", command=open_group_settings)

    chat_display = ScrolledText(root, wrap=tk.WORD, state='disabled', width=50, height=20)
    # Create a frame for chat display and user list
    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    chat_display = ScrolledText(main_frame, wrap=tk.WORD, state='disabled', width=50, height=20)
    chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # --- Message Search/Filtering for Main Chat ---
    def search_main_chat():
        query = search_entry.get().strip().lower()
        chat_display.tag_remove('search_match', '1.0', tk.END)
        if not query:
            return
        start = '1.0'
        while True:
            pos = chat_display.search(query, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            chat_display.tag_add('search_match', pos, end)
            start = end
        chat_display.tag_config('search_match', background='yellow', foreground='black')
        # Scroll to first match
        first = chat_display.search(query, '1.0', stopindex=tk.END, nocase=True)
        if first:
            chat_display.see(first)

    search_frame = tk.Frame(main_frame)
    search_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
    search_entry = tk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=(0, 5))
    search_btn = tk.Button(search_frame, text="Search", command=search_main_chat)
    search_btn.pack(side=tk.LEFT)
    def clear_search():
        search_entry.delete(0, tk.END)
        chat_display.tag_remove('search_match', '1.0', tk.END)
    clear_btn = tk.Button(search_frame, text="Clear", command=clear_search)
    clear_btn.pack(side=tk.LEFT, padx=(5,0))

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
    user_listbox.pack(side=tk.LEFT, fill=tk.Y, padx=5, expand=True)

    # Create a frame at the bottom for entry and emoji button
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    entry = tk.Entry(bottom_frame, width=50)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    send_button = tk.Button(bottom_frame, text="Send", command=lambda: send_message())
    send_button.pack(side=tk.LEFT, padx=5)

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

        btn_frame = tk.Frame(window)
        btn_frame.pack(pady=5)

        edit_btn = tk.Button(btn_frame, text="Edit", command=edit_selected)
        edit_btn.pack(side=tk.LEFT, padx=5)

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
        try:
            if client:
                client.send(f"__typing__:{username}".encode())
        except Exception as e:
            print(f"Error sending typing notification: {e}")

    entry.bind("<KeyPress>", on_typing)

    # Define group_chat_windows to manage group chat windows
    group_chat_windows = {}

    # Implement open_group_chat_window to handle opening group chat windows
    def open_group_chat_window(group_name):
        if group_name in group_chat_windows:
            group_chat_windows[group_name]['window'].deiconify()
            group_chat_windows[group_name]['window'].lift()
            return

        # Create a new group chat window
        group_window = tk.Toplevel(root)
        group_window.title(f"Group Chat - {group_name}")
        group_window.geometry("500x350")
        group_window.minsize(400, 250)

        # Configure grid layout
        group_window.grid_rowconfigure(0, weight=1)
        group_window.grid_columnconfigure(0, weight=4)
        group_window.grid_columnconfigure(1, weight=1)

        # --- Group Chat Search ---
        group_search_frame = tk.Frame(group_window)
        group_search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 2))
        group_search_entry = tk.Entry(group_search_frame, width=30)
        group_search_entry.pack(side=tk.LEFT, padx=(0, 5))
        def group_search():
            query = group_search_entry.get().strip().lower()
            chat_display.tag_remove('search_match', '1.0', tk.END)
            if not query:
                return
            start = '1.0'
            while True:
                pos = chat_display.search(query, start, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(query)}c"
                chat_display.tag_add('search_match', pos, end)
                start = end
            chat_display.tag_config('search_match', background='yellow', foreground='black')
            first = chat_display.search(query, '1.0', stopindex=tk.END, nocase=True)
            if first:
                chat_display.see(first)
        group_search_btn = tk.Button(group_search_frame, text="Search", command=group_search)
        group_search_btn.pack(side=tk.LEFT)
        def group_clear_search():
            group_search_entry.delete(0, tk.END)
            chat_display.tag_remove('search_match', '1.0', tk.END)
        group_clear_btn = tk.Button(group_search_frame, text="Clear", command=group_clear_search)
        group_clear_btn.pack(side=tk.LEFT, padx=(5,0))

        # Chat display in the main area
        chat_display = ScrolledText(group_window, wrap=tk.WORD, state='disabled', width=50, height=15)
        chat_display.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Members list on the right side
        members_frame = tk.Frame(group_window, width=150)
        members_frame.grid(row=0, column=1, padx=5, pady=10, sticky="ns")

        tk.Label(members_frame, text="Members:").pack(pady=5)

        members_listbox = tk.Listbox(members_frame, width=20, height=15)
        members_listbox.pack(pady=5, fill=tk.Y, expand=True)

        # Entry frame at the bottom
        entry_frame = tk.Frame(group_window)
        entry_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        entry_frame.grid_columnconfigure(0, weight=1)
        entry = tk.Entry(entry_frame)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        send_button = tk.Button(entry_frame, text="Send", command=lambda: send_group_message())
        send_button.pack(side=tk.RIGHT, padx=5, pady=0)

        # Typing indicator label for group chat
        group_typing_label = tk.Label(entry_frame, text="", fg="gray")
        group_typing_label.pack(side=tk.LEFT, padx=5)

        # Track users currently typing in this group
        group_typing_users = set()

        # Function to update the typing label
        def update_group_typing_label():
            if group_typing_users:
                users_typing = ', '.join(group_typing_users)
                group_typing_label.config(text=f"{users_typing} typing...")
            else:
                group_typing_label.config(text="")

        def send_group_typing(event=None):
            try:
                if client:
                    client.send(f"__group_typing__:{group_name}:{username}".encode('utf-8'))
            except Exception as e:
                print(f"Error sending group typing notification: {e}")

        entry.bind("<KeyPress>", send_group_typing)

        def send_group_message(event=None):
            import time
            now = time.time()
            last_time = last_group_message_times.get(group_name, 0)
            if now - last_time < RATE_LIMIT_SECONDS:
                # Use the group chat window's typing label for feedback
                if group_name in group_chat_windows:
                    group_chat_windows[group_name]['group_typing_label'].config(text="You are sending messages too quickly. Please wait.")
                    group_chat_windows[group_name]['window'].after(1500, group_chat_windows[group_name]['update_group_typing_label'])
                return
            last_group_message_times[group_name] = now
            if not ensure_connected(parent_window=group_window):
                return
            msg = entry.get()
            if msg:
                msg_to_send = f"/group_msg {group_name} {msg}"
                try:
                    client.send(msg_to_send.encode('utf-8'))
                    entry.delete(0, tk.END)
                except Exception as e:
                    print(f"Error sending group message: {e}")
                    tk.messagebox.showerror("Error", "Failed to send group message.", parent=group_window)

        entry.bind("<Return>", send_group_message)

        def on_close():
            group_chat_windows.pop(group_name, None)
            group_window.destroy()

        group_window.protocol("WM_DELETE_WINDOW", on_close)

        group_chat_windows[group_name] = {
            'window': group_window,
            'chat_display': chat_display,
            'members_listbox': members_listbox,
            'group_typing_label': group_typing_label,
            'group_typing_users': group_typing_users,
            'update_group_typing_label': update_group_typing_label
        }

    cached_group_info = {}

    # Synchronization primitives for file transfer handshake
    file_transfer_event = threading.Event()
    file_transfer_ack = None
    file_transfer_confirm = None

    def send_file():
        global file_transfer_ack, file_transfer_confirm
        file_transfer_ack = None
        file_transfer_confirm = None
        file_transfer_event.clear()

        file_path = filedialog.askopenfilename(title="Select file to send")
        if not file_path:
            print("[DEBUG] No file selected for upload.")
            return
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        print(f"[DEBUG] Preparing to send file: {filename} | Size: {filesize} bytes")
        try:
            print(f"[DEBUG] Sending file transfer request: /send_file {filename} {filesize}")
            cmd = f"/send_file {filename} {filesize}"
            print(f"[DEBUG] Raw command sent (repr): {repr(cmd)}")
            if client:
                client.send(cmd.encode('utf-8'))
            else:
                print("Client socket is None, cannot send file transfer request.")
                display_message("Not connected to server.")

            # Wait for ACK from receive_messages thread
            print("[DEBUG] Waiting for ACK from server...")
            if not file_transfer_event.wait(timeout=10):
                print(f"[ERROR] File transfer handshake timed out waiting for ACK.")
                display_message("File transfer handshake timed out.")
                return

            print(f"[DEBUG] Received file_transfer_ack: {repr(file_transfer_ack)}")
            if not file_transfer_ack or not file_transfer_ack.startswith(f"ACK:{filename}"):
                display_message(f"Server error: {file_transfer_ack}")
                return

            print(f"[DEBUG] Starting file transfer: {filename}")
            sent_bytes = 0
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    print(f"[DEBUG] Raw file chunk sent (len={len(chunk)}): {repr(chunk[:32])} ...")
                    client.sendall(chunk)
                    sent_bytes += len(chunk)
                    print(f"[DEBUG] Sent {sent_bytes}/{filesize} bytes...")

            # Wait for confirmation from receive_messages thread
            file_transfer_event.clear()
            print("[DEBUG] Waiting for file transfer confirmation from server...")
            if not file_transfer_event.wait(timeout=10):
                print(f"[ERROR] File transfer confirmation timed out.")
                display_message("File transfer confirmation timed out.")
                return

            if file_transfer_confirm:
                print(f"[DEBUG] Server confirmation: {file_transfer_confirm}")
                display_message(file_transfer_confirm)
            else:
                display_message("No confirmation received from server.")

        except Exception as e:
            print(f"[ERROR] Failed to send file: {e}")
            display_message(f"Failed to send file: {e}")
 
 

    def request_file():
        def fetch_list():
            try:
                # Limpa e envia o comando
                file_list_event.clear()
                client.send("/list_files".encode('utf-8'))

                # Espera até 10s pelo receive_messages definir file_list_result
                if not file_list_event.wait(timeout=10):
                    raise TimeoutError("Timeout a aguardar lista de ficheiros")

                files = file_list_result
                if not files:
                    raise ValueError("O servidor retornou lista vazia")

                # Chama GUI-thread
                root.after(0, lambda: show_file_buttons(files))

            except Exception as e:
                root.after(0, lambda:
                    tk.messagebox.showerror("Error",
                        f"Não foi possível obter lista de ficheiros:\n{e}"))
        threading.Thread(target=fetch_list, daemon=True).start()

    file_get_btn = tk.Button(bottom_frame, text="Get File", command=request_file)
    file_get_btn.pack(side=tk.LEFT, padx=5)

    def show_file_buttons(file_list):
        file_window = tk.Toplevel(root)
        file_window.title("Download Shared File")
        file_window.geometry("300x400")
        tk.Label(file_window, text="Select a file to download:").pack(pady=10)
        for fname in file_list:
            btn = tk.Button(
                file_window,
                text=fname,
                width=30,
                command=lambda f=fname: download_file_direct(f, file_window)
            )
            btn.pack(pady=2)
    
    def download_file_direct(filename, file_window):
        def _download():
            global file_download_in_progress
            file_download_header_parsed = False
            file_download_event.clear()
            file_download_request = filename
            file_download_in_progress = True

            client.send(f"/get_file {filename}".encode())

            if file_download_event.wait(timeout=30):
                save = filedialog.asksaveasfilename(initialfile=filename)
                if save:
                    with open(save, "wb") as f:
                        f.write(bytes(file_download_buffer))
                        print(f" saved {len(file_download_buffer)} bytes")  # Corrected debug print statement
                    root.after(0, lambda:
                        tk.messagebox.showinfo("Sucesso", f"'{filename}' guardado."))
            else:
                root.after(0, lambda:
                    tk.messagebox.showerror("Erro", "Timeout no download"))
            file_window.destroy()

        threading.Thread(target=_download, daemon=True).start()

    # Add file sharing buttons to the bottom frame
    file_send_btn = tk.Button(bottom_frame, text="Send File", command=send_file)
    file_send_btn.pack(side=tk.LEFT, padx=5)

    time.sleep(0.5)  # Small delay before starting receive thread

    def reconnect():
        global client
        global username
        global password

        display_message("Attempting to reconnect...")
        try:
            if client:
                client.close()
        except:
            pass

        # Create a new socket and wrap with SSL
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = ssl_context.wrap_socket(raw_sock, server_hostname=Server_IP)
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

    def notify_user(title, message):
        """Show a desktop notification."""
        notification.notify(
            title=title,
            message=message,
            app_name="Chat Application",
            timeout=5  # Notification duration in seconds
        )

    # List of admin users
    admins = ["meudeux"]  # Replace "admin" with the default admin username

    # Function to grant admin privileges
    def grant_admin(username):
        if username not in admins:
            admins.append(username)
            display_message(f"{username} has been granted admin privileges.")
        else:
            display_message(f"{username} is already an admin.")

    # Add a button to open a dialog to grant admin privileges
    def open_grant_admin_dialog():
        def submit():
            user_to_grant = entry.get().strip()
            if user_to_grant:
                try:
                    client.send(f"/grant_admin {user_to_grant}".encode('utf-8'))
                    grant_admin(user_to_grant)
                    dialog.destroy()
                except Exception as e:
                    display_message(f"Failed to send grant admin command: {e}")
            else:
                display_message("Username cannot be empty.")

        dialog = tk.Toplevel(root)
        dialog.title("Grant Admin Privileges")
        dialog.geometry("300x120")
        tk.Label(dialog, text="Enter username to grant admin:").pack(pady=10)
        entry = tk.Entry(dialog)
        entry.pack(pady=5)
        tk.Button(dialog, text="Grant", command=submit).pack(pady=5)

    # Add the grant admin button to the bottom frame if user is admin
    if username in admins:
        grant_admin_button = tk.Button(bottom_frame, text="Grant Admin", command=open_grant_admin_dialog)
        grant_admin_button.pack(side=tk.LEFT, padx=5)


    # Helper to ensure client is connected before sending/receiving
    def ensure_connected(parent_window=None):
        global client, username, password
        if client is None:
            try:
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client = ssl_context.wrap_socket(raw_sock, server_hostname=Server_IP)
                client.connect((Server_IP, port))
                if password:
                    client.send(f"{username}::{password}".encode())
                else:
                    client.send(username.encode())
                # Optionally, start receive_messages thread if not running
                threading.Thread(target=receive_messages, daemon=True).start()
                return True
            except Exception as e:
                if parent_window:
                    tk.messagebox.showerror("Connection Error", f"Could not connect to server: {e}", parent=parent_window)
                else:
                    print(f"[ERROR] Could not connect to server: {e}")
                return False
        return True

    # Initial connection (before show_main_chat_ui is called)
    # Replace any direct socket creation with SSL-wrapped socket
    # Example:
    # client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # client.connect((Server_IP, port))
    # Should become:
    # raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # client = ssl_context.wrap_socket(raw_sock, server_hostname=Server_IP)
    # client.connect((Server_IP, port))

    def receive_messages():
        global file_download_in_progress, file_download_buffer
        global file_download_expected_size, file_download_request
        global file_download_event
        nonlocal cached_group_info  # Fix scoping for group info cache
        global file_download_in_progress, file_download_request, file_download_event, file_download_result, file_download_error
        global file_download_buffer, file_download_header_parsed, file_download_filename, file_download_expected_size
        print("receive_messages thread started")  # Debug print
        history_buffer = ""
        receiving_history = False
        global file_list_event, file_list_result

        while True:
            try:
                data = client.recv(4096)
                print(f"[DEBUG] Raw data received ({len(data)} bytes): {repr(data[:100])} ...")
                if not data:
                    print("Server closed connection.")
                    display_message("Disconnected from server.")
                    reconnect()
                    break
                try:
                    msg = data.decode('utf-8')
                except UnicodeDecodeError:
                    msg = None
                if not msg:
                    continue
                # --- Group typing indicator handling ---
                if msg.startswith("__group_typing__:"):
                    # Format: __group_typing__:<group_name>:<username>
                    try:
                        _, group_name, typing_user = msg.strip().split(":", 2)
                        if group_name in group_chat_windows:
                            group_chat_window = group_chat_windows[group_name]
                            group_typing_users = group_chat_window['group_typing_users']
                            group_typing_users.add(typing_user)
                            group_chat_window['update_group_typing_label']()
                            def clear_group_typing(user=typing_user, gname=group_name):
                                if gname in group_chat_windows:
                                    group_typing_users = group_chat_windows[gname]['group_typing_users']
                                    group_typing_users.discard(user)
                                    group_chat_windows[gname]['update_group_typing_label']()
                            root.after(3000, clear_group_typing)
                    except Exception as e:
                        print(f"Error processing __group_typing__: {e}")
                    continue
                if msg.startswith("__group_typing_stopped__:"):
                    # Format: __group_typing_stopped__:<group_name>:<username>
                    try:
                        _, group_name, typing_user = msg.strip().split(":", 2)
                        if group_name in group_chat_windows:
                            group_typing_users = group_chat_windows[group_name]['group_typing_users']
                            group_typing_users.discard(typing_user)
                            group_chat_windows[group_name]['update_group_typing_label']()
                    except Exception as e:
                        print(f"Error processing __group_typing_stopped__: {e}")
                    continue

                # Handle file download state machine
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    text = None
                if text and text.startswith("ACK:") and file_download_in_progress:
                    # Sinaliza ao download thread que começou a receber
                    file_download_event.set()
                    # descarta este pedaço do buffer
                    continue

                # Agora sim, entra no state‐machine de download
                if file_download_in_progress and file_download_request:
                    try:
                        # Append received data directly to file_download_buffer
                        if not file_download_header_parsed:
                            # Parse header if not already done
                            header_end = data.find(b'\n')
                            if header_end != -1:
                                header_line = data[:header_end].decode('utf-8', errors='replace')
                                if header_line.startswith("__file_start__:"):
                                    _, fname, fsize = header_line.strip().split(":", 2)
                                    file_download_filename = fname
                                    file_download_expected_size = int(fsize)
                                    file_download_header_parsed = True
                                    file_download_buffer.extend(data[header_end + 1:])
                                else:
                                    raise ValueError("Unexpected header format")
                            else:
                                # Accumulate file data
                                file_download_buffer.extend(data)
                        else:
                            # Accumulate file data
                            file_download_buffer.extend(data)

                        # Check if the file is complete
                        if file_download_header_parsed and len(file_download_buffer) >= file_download_expected_size:
                            # Save file to disk
                            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                            os.makedirs(downloads_path, exist_ok=True)
                            save_path = os.path.join(downloads_path, file_download_filename)
                            with open(save_path, "wb") as f:
                                f.write(file_download_buffer[:file_download_expected_size])

                            print(f"[DEBUG] File download complete: {file_download_filename}")

                            # Reset state
                            file_download_in_progress = False
                            file_download_header_parsed = False
                            file_download_buffer = bytearray()
                            file_download_event.set()
                    except Exception as e:
                        print(f"[ERROR] Exception during file download: {e}")
                        file_download_in_progress = False
                        file_download_header_parsed = False
                        file_download_buffer = bytearray()
                        file_download_event.set()
                    continue

                # Handle normal message processing
                try:
                    msg = data.decode('utf-8')
                except UnicodeDecodeError:
                    # This is likely file data, skip displaying
                    continue

                # Notify user for new messages or mentions
                if msg.startswith("[PM from") or msg.startswith("[Group msg]"):
                    try:
                        if msg.startswith("[PM from"):
                            sender = msg.split("[PM from ", 1)[1].split("]", 1)[0]
                            notify_user("New Private Message", f"Message from {sender}")
                        elif msg.startswith("[Group msg]"):
                            content = msg[len("[Group msg]"):].strip()
                            group_name, rest = content.split(" ", 1)
                            sender, message_text = rest.split(":", 1)
                            if username in message_text:
                                notify_user("Mention in Group Chat", f"{sender} mentioned you in {group_name}")
                            else:
                                notify_user("New Group Message", f"Message in {group_name} from {sender}")
                    except Exception as e:
                        print(f"Error processing notification: {e}")

                # Ignore all file transfer protocol messages
                if (
                    msg.startswith("Ready to receive file ") or
                    (msg.startswith("File '") and "uploaded successfully" in msg) or
                    msg.startswith("__file_start__:") or
                    msg.startswith("__file_end__:")
                ):
                    continue  # Do NOT display in chat

                # If this is likely binary data (file content), skip it
                if not msg or any(ord(c) < 32 and c not in '\r\n\t' for c in msg):
                    continue

                print(f"Received message: {msg}")  # Debug log

                if msg.startswith("__file_list__:"):
                    lst = msg[len("__file_list__:"):].split(",")
                    file_list_result = [f.strip() for f in lst if f.strip()]
                    file_list_event.set()
                    continue

                if msg.startswith("__group_info__:"):
                    # Handle group info message
                    try:
                        nonlocal cached_group_info
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
                            # Update the members_listbox if it exists
                            if 'members_listbox' in group_chat_window:
                                members_listbox = group_chat_window['members_listbox']
                                members_listbox.delete(0, tk.END)
                                for member in members:
                                    member_name = member.strip().split(' (')[0]
                                    if member_name:
                                        members_listbox.insert(tk.END, member_name)
                        else:
                            # Cache group info and open a new group chat window
                            cached_group_info[group_name] = members
                            open_group_chat_window(group_name)
                            # After opening, update the members_listbox if possible
                            if group_name in group_chat_windows:
                                group_chat_window = group_chat_windows[group_name]
                                if 'members_listbox' in group_chat_window:
                                    members_listbox = group_chat_window['members_listbox']
                                    members_listbox.delete(0, tk.END)
                                    for member in members:
                                        member_name = member.strip().split(' (')[0]
                                        if member_name:
                                            members_listbox.insert(tk.END, member_name)
                    except Exception as e:
                        print(f"Error processing group info message: {e}")
                elif msg.startswith("__groups__:"):
                    # Update latest_groups_list and refresh group UI if open
                    groups_str = msg[len("__groups__:"):]
                    print(f"[DEBUG] __groups__ message received: {groups_str}")
                    nonlocal latest_groups_list
                    latest_groups_list = [g.strip() for g in groups_str.split(",") if g.strip()]
                    print(f"[DEBUG] latest_groups_list after update: {latest_groups_list}")
                    # If group chat dialog is open, update its UI if open
                    if hasattr(open_group_chat_dialog, 'group_chat_window') and open_group_chat_dialog.group_chat_window.winfo_exists():
                        if hasattr(open_group_chat_dialog, 'update_ui'):
                            print(f"[DEBUG] Calling update_ui with latest_groups_list: {latest_groups_list}")
                            open_group_chat_dialog.group_chat_window.after(0, open_group_chat_dialog.update_ui)
                    continue
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
                    # Format: [Group msg] <group_name> <sender>: <message>
                    try:
                        content = msg[len("[Group msg]"):].strip()
                        # Split into group_name + rest, then sender + message
                        group_name, rest = content.split(" ", 1)
                        sender, message_text = rest.split(":", 1)
                        sender = sender.strip()
                        message_text = message_text.strip()

                        # Auto-open the window if needed
                        if group_name not in group_chat_windows:
                            open_group_chat_window(group_name)

                        chat_disp = group_chat_windows[group_name]['chat_display']
                        chat_disp.config(state='normal')
                        timestamp = datetime.datetime.now().strftime("%H:%M")
                        display_sender = "You" if sender == username else sender
                        chat_disp.insert(tk.END, f"[{timestamp}] {display_sender}: {message_text}\n")
                        chat_disp.config(state='disabled')
                        chat_disp.yview(tk.END)

                    except Exception as e:
                        print(f"Error processing group message: {e}")
                elif msg.startswith("__file_shared__:"):
                    # Format: __file_shared__:filename:sender
                    try:
                        _, filename, sender = msg.split(":", 2)
                        display_message(f"File shared: {filename} (by {sender}) - Use 'Get File' to download.")
                    except Exception as e:
                        display_message(f"File shared, but error parsing notification: {e}")
                elif msg.strip() == "__close_app__":
                    print("[DEBUG] Received __close_app__ from server. Closing app.")
                    def close_app():
                        print("You have been kicked by an admin. The app will now close.")
                        root.quit()
                        root.destroy()
                        import os
                        os._exit(0)
                    root.after(0, close_app)
                elif msg.strip().startswith("[") and "] /close_app " in msg:
                    # Handles messages like: [admin] /close_app username||id
                    try:
                        prefix, rest = msg.split("] /close_app ", 1)
                        target = rest.strip()
                        if target.startswith(username):
                            print(f"[DEBUG] Received bracketed close_app for user {username}. Closing app.")
                            def close_app():
                                print("You have been kicked by an admin. The app will now close.")
                                root.quit()
                                root.destroy()
                                import os
                                os._exit(0)
                            root.after(0, close_app)
                            continue
                    except Exception as e:
                        print(f"[ERROR] Error processing bracketed close_app message: {e}")
                elif msg.strip().startswith("[") and "] /kick " in msg:
                    # Handles messages like: [admin] /kick username||id
                    try:
                        prefix, rest = msg.split("] /kick ", 1)
                        target = rest.strip()
                        if target.startswith(username):
                            print(f"[DEBUG] Received bracketed kick for user {username}. Closing app.")
                            def close_app():
                                print("You have been kicked by an admin. The app will now close.")
                                root.quit()
                                root.destroy()
                                os._exit(0)
                            root.after(0, close_app)
                            continue
                    except Exception as e:
                        print(f"[ERROR] Error processing bracketed kick message: {e}")
                elif msg.strip().startswith("[") and "] /ban " in msg:
                    # Handles messages like: [admin] /ban username||id
                    try:
                        prefix, rest = msg.split("] /ban ", 1)
                        target = rest.strip()
                        if target.startswith(username):
                            print(f"[DEBUG] Received bracketed ban for user {username}. Deleting account and closing app.")
                            def ban_and_close():
                                # Delete cached user data files
                                cached_files = [
                                   
                                    'cached_group_info.py',
                                    'chat_log.txt',
                                ]
                                for fname in cached_files:
                                    try:
                                        if os.path.exists(fname):
                                            os.remove(fname)
                                            print(f"[DEBUG] Deleted cached file: {fname}")
                                    except Exception as e:
                                        print(f"[ERROR] Failed to delete cached file {fname}: {e}")
                                # Delete user from database
                                try:
                                    import sqlite3
                                    db_path = 'db.sqlite3'
                                    if os.path.exists(db_path):
                                        conn = sqlite3.connect(db_path)
                                        cur = conn.cursor()
                                        cur.execute("DELETE FROM users WHERE username = ?", (username,))
                                        conn.commit()
                                        cur.close()
                                        conn.close()
                                        print(f"[DEBUG] Deleted user {username} from database.")
                                    else:
                                        print(f"[DEBUG] Database file {db_path} does not exist.")
                                except Exception as e:
                                    print(f"[ERROR] Failed to delete user from database: {e}")
                                print("You have been banned by an admin. Your account will be deleted and the app will now close.")
                                root.quit()
                                root.destroy()
                                os._exit(0)
                            root.after(0, ban_and_close)
                            continue
                    except Exception as e:
                        print(f"[ERROR] Error processing bracketed ban message: {e}")
                protocol_prefixes = [
                    "__file_list__:", "__file_start__:", "__file_end__:",
                    "ACK:", "Ready to receive file ", "File '", "uploaded successfully",
                    "Error sending file:", "Error listing files:", "__group_info__:", "__groups__:", "__history__:", "__typing__:", "__user_list__:", "[PM from", "[Group msg]", "__file_shared__:",
                ]
                code_like_prefixes = [
                    "pattern = r", "match = re.match", "if not match:", "import re", "def ", "class ", "print(", "print ", "try:", "except ", "return ", "continue", "break", "global ", "client.send", "client.recv", "def send_", "def open_", "def on_", "def handle_", "def request_", "def fetch_", "def download_", "def accept_", "def populate_", "def clear_", "def edit_", "def delete_", "def send_message", "def receive_messages", "def reconnect", "def handle_exit"
                ]
                msg_stripped = msg.strip()
                if any(msg_stripped.startswith(prefix) for prefix in protocol_prefixes):
                    continue  # Do NOT display protocol/debug messages
                if any(msg_stripped.startswith(prefix) for prefix in code_like_prefixes):
                    continue  # Do NOT display code-like messages
                # Also filter out messages that look like debug logs or contain debug markers
                debug_markers = ["[DEBUG]", "[INFO]", "[ERROR]", "[WARNING]", "[TRACE]"]
                if any(marker in msg for marker in debug_markers):
                    continue
                # Only now display the message
                display_message(msg)
                # At the end of all protocol checks, before the except block:
                print(f"[DEBUG] Unmatched message in receive_messages: {repr(msg)}")
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    threading.Thread(target=receive_messages, daemon=True).start()

    entry.bind("<Return>", send_message)

    def handle_exit(signal_received, frame):
        global log_thread_running
        print("\n[INFO] Exiting program gracefully...")
        try:
            client.close()
        except Exception as e:
            print(f"[ERROR] Failed to close client socket: {e}")
        # Stop the log thread gracefully
        log_thread_running = False
        log_thread.join(timeout=2)
        root.destroy()
        exit(0)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    WINDOW_STATE_FILE = 'window_state.json'
    
    def save_window_state(window, key):
        state = {}
        if os.path.exists(WINDOW_STATE_FILE):
            try:
                with open(WINDOW_STATE_FILE, 'r') as f:
                    state = json.load(f)
            except Exception:
                state = {}
        state[key] = window.geometry()
        with open(WINDOW_STATE_FILE, 'w') as f:
            json.dump(state, f)
    
    def load_window_state(window, key, default_geometry=None):
        if os.path.exists(WINDOW_STATE_FILE):
            try:
                with open(WINDOW_STATE_FILE, 'r') as f:
                    state = json.load(f)
                if key in state:
                    window.geometry(state[key])
                    return
            except Exception:
                pass
        if default_geometry:
            window.geometry(default_geometry)
    
    # In show_main_chat_ui, after root is created:
    load_window_state(root, 'main', default_geometry='800x600')
    
    # When closing main window, save state
    old_handle_exit = handle_exit
    
    def handle_exit(signal_received, frame):
        save_window_state(root, 'main')
        old_handle_exit(signal_received, frame)
    
    # Patch signal handlers to use new handle_exit
    import signal
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # In open_group_chat_window, restore and save geometry
    old_open_group_chat_window = open_group_chat_window

    def open_group_chat_window(group_name):
        if group_name in group_chat_windows:
            group_chat_windows[group_name]['window'].deiconify()
            group_chat_windows[group_name]['window'].lift()
            return

        # Create a new group chat window
        group_window = tk.Toplevel(root)
        load_window_state(group_window, f'group_{group_name}', default_geometry='500x350')
        group_window.title(f"Group Chat - {group_name}")
    
        group_window.geometry("500x350")
        group_window.minsize(400, 250)
    
        # Configure grid layout
        group_window.grid_rowconfigure(0, weight=1)
        group_window.grid_columnconfigure(0, weight=4)
        group_window.grid_columnconfigure(1, weight=1)
    
        # --- Group Chat Search ---
        group_search_frame = tk.Frame(group_window)
        group_search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 2))
        group_search_entry = tk.Entry(group_search_frame, width=30)
        group_search_entry.pack(side=tk.LEFT, padx=(0, 5))
        def group_search():
            query = group_search_entry.get().strip().lower()
            chat_display.tag_remove('search_match', '1.0', tk.END)
            if not query:
                return
            start = '1.0'
            while True:
                pos = chat_display.search(query, start, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(query)}c"
                chat_display.tag_add('search_match', pos, end)
                start = end
            chat_display.tag_config('search_match', background='yellow', foreground='black')
            first = chat_display.search(query, '1.0', stopindex=tk.END, nocase=True)
            if first:
                chat_display.see(first)
        group_search_btn = tk.Button(group_search_frame, text="Search", command=group_search)
        group_search_btn.pack(side=tk.LEFT)
        def group_clear_search():
            group_search_entry.delete(0, tk.END)
            chat_display.tag_remove('search_match', '1.0', tk.END)
        group_clear_btn = tk.Button(group_search_frame, text="Clear", command=group_clear_search)
        group_clear_btn.pack(side=tk.LEFT, padx=(5,0))

        # Chat display in the main area
        chat_display = ScrolledText(group_window, wrap=tk.WORD, state='disabled', width=50, height=15)
        chat_display.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Members list on the right side
        members_frame = tk.Frame(group_window, width=150)
        members_frame.grid(row=0, column=1, padx=5, pady=10, sticky="ns")

        tk.Label(members_frame, text="Members:").pack(pady=5)

        members_listbox = tk.Listbox(members_frame, width=20, height=15)
        members_listbox.pack(pady=5, fill=tk.Y, expand=True)

        # Entry frame at the bottom
        entry_frame = tk.Frame(group_window)
        entry_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        entry_frame.grid_columnconfigure(0, weight=1)
        entry = tk.Entry(entry_frame)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        send_button = tk.Button(entry_frame, text="Send", command=lambda: send_group_message())
        send_button.pack(side=tk.RIGHT, padx=5, pady=0)

        # Typing indicator label for group chat
        group_typing_label = tk.Label(entry_frame, text="", fg="gray")
        group_typing_label.pack(side=tk.LEFT, padx=5)

        # Track users currently typing in this group
        group_typing_users = set()

        # Function to update the typing label
        def update_group_typing_label():
            if group_typing_users:
                users_typing = ', '.join(group_typing_users)
                group_typing_label.config(text=f"{users_typing} typing...")
            else:
                group_typing_label.config(text="")

        def send_group_typing(event=None):
            try:
                if client:
                    client.send(f"__group_typing__:{group_name}:{username}".encode('utf-8'))
            except Exception as e:
                print(f"Error sending group typing notification: {e}")

        entry.bind("<KeyPress>", send_group_typing)

        def send_group_message(event=None):
            import time
            now = time.time()
            last_time = last_group_message_times.get(group_name, 0)
            if now - last_time < RATE_LIMIT_SECONDS:
                # Use the group chat window's typing label for feedback
                if group_name in group_chat_windows:
                    group_chat_windows[group_name]['group_typing_label'].config(text="You are sending messages too quickly. Please wait.")
                    group_chat_windows[group_name]['window'].after(1500, group_chat_windows[group_name]['update_group_typing_label'])
                return
            last_group_message_times[group_name] = now
            if not ensure_connected(parent_window=group_window):
                return
            msg = entry.get()
            if msg:
                msg_to_send = f"/group_msg {group_name} {msg}"
                try:
                    client.send(msg_to_send.encode('utf-8'))
                    entry.delete(0, tk.END)
                except Exception as e:
                    print(f"Error sending group message: {e}")
                    tk.messagebox.showerror("Error", "Failed to send group message.", parent=group_window)

        entry.bind("<Return>", send_group_message)

        def on_close():
            group_chat_windows.pop(group_name, None)
            group_window.destroy()

        group_window.protocol("WM_DELETE_WINDOW", on_close)

        group_chat_windows[group_name] = {
            'window': group_window,
            'chat_display': chat_display,
            'members_listbox': members_listbox,
            'group_typing_label': group_typing_label,
            'group_typing_users': group_typing_users,
            'update_group_typing_label': update_group_typing_label
        }

    # Automatically open the group chat window for the default group (if any)
    if latest_groups_list and len(latest_groups_list) == 1:
        def open_default_group():
            open_group_chat_window(latest_groups_list[0])
            if hasattr(open_group_chat_dialog, 'update_ui'):
                open_group_chat_dialog.group_chat_window.after(0, open_group_chat_dialog.update_ui)
        root.after(1000, open_default_group)

    # Synchronize file transfer state
    def sync_file_transfer_state():
        global file_download_in_progress, file_download_request
        if file_download_in_progress and file_download_request:
            try:
                client.send(f"/get_file {file_download_request}".encode())
            except Exception as e:
                print(f"Error resending file download request: {e}")
        root.after(5000, sync_file_transfer_state)

    # Start syncing file transfer state
    sync_file_transfer_state()

def main():
    build_login_ui()
    root.mainloop()

if __name__ == "__main__":
    main()