import customtkinter as ctk
import threading
import queue
import time
import re
import paramiko

class ConnectionWorker:
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def log(self, msg):
        self.log_queue.put(msg)

    def read_until(self, shell, patterns, timeout=30):
        buffer = ""
        end_time = time.time() + timeout
        while time.time() < end_time:
            if shell.recv_ready():
                data = shell.recv(1024).decode('utf-8', errors='ignore')
                buffer += data
                for pat in patterns:
                    if re.search(pat, buffer):
                        return buffer
            else:
                time.sleep(0.1)
        return buffer

    def run(self, ip, ports, user, password, dev_user, dev_pass, cmds):
        for port in ports:
            try:
                # Prefix each selected port internally with '51' and zero-pad to 2 digits
                internal_port = int(f"51{port:02d}")
                self.log(f"[INFO] Connecting to {ip}:{internal_port}...")
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(ip, port=internal_port, username=user, password=password, timeout=10)
                shell = ssh.invoke_shell()
                time.sleep(1)
                self.log(f"[INFO] SSH connection established on port {internal_port}.")

                # Initial server prompt
                out = self.read_until(shell, [r">", r"#", r"login:", r"Password:"], timeout=10)
                self.log(f"server< {out.strip()}")

                # Proceed to device login
                shell.send("\r")
                self.log("server> <ENTER>")
                out = self.read_until(shell, [r"login:", r"Password:"], timeout=10)
                self.log(f"server< {out.strip()}")

                # Device login
                shell.send(dev_user + "\r")
                self.log(f"device> {dev_user}:******")
                out = self.read_until(shell, [r"Password:"], timeout=10)
                self.log(f"device< {out.strip()}")

                shell.send(dev_pass + "\r")
                out = self.read_until(shell, [r">", r"#"], timeout=10)
                self.log(f"device< {out.strip()}")

                # Execute each command
                for cmd in cmds:
                    shell.send(cmd + "\r")
                    self.log(f"device> {cmd}")
                    out = self.read_until(shell, [r"#", r">", r"y/n", r"confirm"], timeout=30)
                    self.log(f"device< {out.strip()}")

                ssh.close()
                self.log(f"[INFO] Connection closed on port {internal_port}.")
            except Exception as e:
                self.log(f"[ERROR] Port {internal_port}: {e}")

class ResetTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Device CLI Executor")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Log queue and worker
        self.log_queue = queue.Queue()
        self.worker = ConnectionWorker(self.log_queue)

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Form frame
        form = ctk.CTkFrame(self, fg_color="#2F3136")
        form.grid(row=0, column=0, sticky="nw", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)

        # Server Settings
        ctk.CTkLabel(form, text="Server Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0,8))
        ctk.CTkLabel(form, text="IP:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.ip_var = ctk.StringVar(value="10.253.77.131")
        self.ip_menu = ctk.CTkComboBox(
            form,
            values=["10.253.77.131", "10.253.77.132", "10.253.77.133"],
            variable=self.ip_var,
            width=200,
            fg_color="#36393F", border_width=1, border_color="#4F545C"
        )
        self.ip_menu.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Port selector grid: 48 ports
        ctk.CTkLabel(form, text="Select Ports:", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, columnspan=2, pady=(16,8))
        ports_frame = ctk.CTkFrame(form, fg_color="#2F3136")
        ports_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=2)
        self.port_buttons = {}
        for i in range(48):
            btn = ctk.CTkButton(
                ports_frame,
                text=str(i+1), width=30, height=30,
                fg_color="#36393F", hover_color="#4F545C",
                command=lambda p=i+1: self.toggle_port(p)
            )
            row, col = divmod(i, 8)
            btn.grid(row=row, column=col, padx=2, pady=2)
            self.port_buttons[i+1] = btn
        self.selected_ports = set()

        # Credentials and commands
        ctk.CTkLabel(form, text="Server User:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        self.user_entry = ctk.CTkEntry(
            form, width=200, fg_color="#36393F", border_width=1, border_color="#4F545C"
        )
        self.user_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(form, text="Server PW:").grid(row=5, column=0, sticky="e", padx=5, pady=2)
        self.pass_entry = ctk.CTkEntry(
            form, show="*", width=200, fg_color="#36393F", border_width=1, border_color="#4F545C"
        )
        self.pass_entry.grid(row=5, column=1, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(form, text="Device User:").grid(row=6, column=0, sticky="e", padx=5, pady=2)
        self.dev_user_entry = ctk.CTkEntry(
            form, placeholder_text="root", width=200, fg_color="#36393F", border_width=1, border_color="#4F545C"
        )
        self.dev_user_entry.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(form, text="Device PW:").grid(row=7, column=0, sticky="e", padx=5, pady=2)
        self.dev_pass_entry = ctk.CTkEntry(
            form, show="*", width=200, fg_color="#36393F", border_width=1, border_color="#4F545C"
        )
        self.dev_pass_entry.grid(row=7, column=1, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(form, text="Commands", font=ctk.CTkFont(size=14, weight="bold")).grid(row=8, column=0, columnspan=2, pady=(16,8))
        self.cmd_text = ctk.CTkTextbox(
            form, height=80, wrap="word",
            fg_color="#2F3136", text_color="#FFFFFF",
            border_width=1, border_color="#4F545C"
        )
        self.cmd_text.insert("0.0", "cli\nrequest system media zeroize\ny\n")
        self.cmd_text.grid(row=9, column=0, columnspan=2, padx=5, pady=2)

        # Execute Button inside form
        self.connect_btn = ctk.CTkButton(
            form, text="▶ Execute", fg_color="#5865F2", width=120, height=40, command=self.start
        )
        self.connect_btn.grid(row=10, column=1, sticky="e", padx=5, pady=(16,0))

        # Log Area
        self.log_text = ctk.CTkTextbox(
            self, fg_color="#2F3136", text_color="#DCDDDE",
            wrap="word", state="disabled", font=("Courier", 10)
        )
        self.log_text.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=8, pady=8)

        self.after(100, self._process_queue)

    def toggle_port(self, port):
        if port in self.selected_ports:
            self.selected_ports.remove(port)
            self.port_buttons[port].configure(fg_color="#36393F")
        else:
            self.selected_ports.add(port)
            self.port_buttons[port].configure(fg_color="#5865F2")

    def _process_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.configure(state="disabled")
            self.log_text.see("end")
        self.after(100, self._process_queue)

    def start(self):
        server_ip = self.ip_var.get()
        ports = sorted(self.selected_ports)
        user = self.user_entry.get()
        password = self.pass_entry.get()
        dev_user = self.dev_user_entry.get()
        dev_pass = self.dev_pass_entry.get()
        cmds = self.cmd_text.get("0.0", "end").strip().splitlines()

        if not ports:
            self.log_queue.put("[ERROR] Keine Ports ausgewählt.")
            return

        self.connect_btn.configure(state="disabled")
        threading.Thread(
            target=self.worker.run,
            args=(server_ip, ports, user, password, dev_user, dev_pass, cmds),
            daemon=True
        ).start()

if __name__ == "__main__":
    app = ResetTool()
    app.geometry("1400x800")
    app.mainloop()