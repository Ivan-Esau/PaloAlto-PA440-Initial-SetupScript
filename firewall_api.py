import tkinter as tk
from tkinter import messagebox, ttk
from ttkthemes import ThemedTk
import urllib3
import xml.etree.ElementTree as ET
import time
from PIL import Image, ImageTk

# Deaktiviert SSL-Warnungen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class FirewallAPI:
    def __init__(self, firewall_ip, username, password):
        self.firewall_ip = firewall_ip
        self.username = username
        self.password = password
        self.api_key = None

    def get_api_key(self):
        url = f"https://{self.firewall_ip}/api/?type=keygen"
        data = f'user={self.username}&password={self.password}'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        try:
            http = urllib3.PoolManager(cert_reqs='CERT_NONE')
            response = http.request('POST', url, body=data, headers=headers, retries=False)
            if response.status == 200:
                root = ET.fromstring(response.data.decode('utf-8'))
                self.api_key = root.find(".//key").text
                return self.api_key
            else:
                print("Error while fetching API key:", response.status)
                return None
        except Exception as e:
            print("Connection error:", e)
            return None

    def list_available_software_versions(self):
        headers = {'X-PAN-KEY': self.api_key}
        url_check = f"https://{self.firewall_ip}/api/?type=op&cmd=<request><system><software><check></check></software></system></request>"
        try:
            http = urllib3.PoolManager(cert_reqs='CERT_NONE')
            response = http.request('GET', url_check, headers=headers, retries=False)
            if response.status == 200:
                root = ET.fromstring(response.data.decode('utf-8'))
                versions = root.findall(".//entry")
                available_versions = [version.find("version").text for version in versions]
                return available_versions
            else:
                print("Error while listing software versions:", response.status)
                return []
        except Exception as e:
            print("Connection error while listing software versions:", e)
            return []

    def software_update_install(self, version):
        if not self.api_key:
            print("API key is not set. Call get_api_key() first.")
            return None

        headers = {'X-PAN-KEY': self.api_key}
        url_install = f"https://{self.firewall_ip}/api/?type=op&cmd=<request><system><software><install><version>{version}</version></install></software></system></request>"
        try:
            http = urllib3.PoolManager(cert_reqs='CERT_NONE')
            response = http.request('GET', url_install, headers=headers, retries=False)
            if response.status == 200:
                root = ET.fromstring(response.data.decode('utf-8'))
                job = root.find(".//job")
                if job is not None:
                    job_id = job.text
                    print(f"Software version {version} installation started, job ID: {job_id}")
                    return True
                else:
                    print("Job ID not found in response. Full response:")
                    print(response.data.decode('utf-8'))
                    return False
            else:
                print("Error while installing software version:", response.status)
                return False
        except Exception as e:
            print("Connection error during software installation:", e)
            return False

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Firewall Update Tool")
        self.api = None
        self.software_versions = []

        # Styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", foreground="white", background="#2C2F33", font=("Arial", 10))
        style.configure("TEntry", foreground="white", background="#23272A", padding=5, relief="flat")
        style.configure("TCombobox", fieldbackground="#23272A", background="#23272A", foreground="white")
        style.configure("TButton", background="#7289DA", foreground="white", padding=6, font=("Arial", 10, "bold"))
        style.map("TButton", background=[("active", "#5b6eae")])

        # Haupt-Layout
        self.root.configure(bg="#2C2F33")
        self.create_widgets()

    def create_widgets(self):
        # Header
        header = tk.Label(self.root, text="Firewall Update Tool", bg="#2C2F33", fg="white", font=("Arial", 18, "bold"))
        header.grid(row=0, column=0, columnspan=3, pady=(10, 5))

        # Trennlinie
        line = tk.Frame(self.root, height=2, bd=1, relief="solid", bg="#7289DA")
        line.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 15), padx=10)

        # Firewall IP-Adresse Eingabefeld mit Icon
        self.add_icon_field("Firewall IP:", "Geben Sie die Firewall-IP ein", row=2, icon_path="icons/server.png", field_name='firewall_ip_entry')

        # Benutzername Eingabefeld mit Icon
        self.add_icon_field("Username:", "Geben Sie den Benutzernamen ein", row=3, icon_path="icons/user.png", field_name='username_entry')

        # Passwort Eingabefeld mit Icon
        self.add_icon_field("Password:", "Geben Sie das Passwort ein", row=4, icon_path="icons/lock.png", show="*", field_name='password_entry')

        # Software Version Dropdown mit Icon
        self.add_icon_field("Software Version:", "Wählen Sie eine Version aus", row=5, icon_path="icons/version.png", combo=True, field_name='software_version_combo')

        # Schaltfläche für API-Verbindung
        self.connect_button = ttk.Button(self.root, text="Connect and Load Versions", command=self.connect_to_firewall, style="TButton")
        self.connect_button.grid(row=6, column=0, columnspan=3, pady=(20, 5))

        # Schaltfläche zum Starten des Software-Updates
        self.update_button = ttk.Button(self.root, text="Update Software", command=self.start_update, state="disabled", style="TButton")
        self.update_button.grid(row=7, column=0, columnspan=3, pady=10)

    def add_icon_field(self, label_text, placeholder, row, icon_path, field_name, combo=False, show=None):
        # Versucht, das Icon zu laden, falls die Datei vorhanden ist
        try:
            icon = Image.open(icon_path).resize((20, 20), Image.ANTIALIAS)
            icon = ImageTk.PhotoImage(icon)
            icon_label = tk.Label(self.root, image=icon, bg="#2C2F33")
            icon_label.image = icon
            icon_label.grid(row=row, column=0, sticky="w", padx=5)
        except FileNotFoundError:
            print(f"Icon '{icon_path}' nicht gefunden. Es wird kein Icon angezeigt.")

        # Label
        ttk.Label(self.root, text=label_text).grid(row=row, column=1, sticky="w", padx=5)

        # Eingabefeld oder Kombinationsbox
        if combo:
            combo_box = ttk.Combobox(self.root, style="TCombobox")
            combo_box.grid(row=row, column=2, padx=5, pady=5)
            combo_box.set(placeholder)
            setattr(self, field_name, combo_box)
        else:
            entry = ttk.Entry(self.root, style="TEntry", show=show)
            entry.grid(row=row, column=2, padx=5, pady=5)
            entry.insert(0, placeholder)
            entry.bind("<FocusIn>", lambda event: self.clear_placeholder(entry, placeholder))
            setattr(self, field_name, entry)

    def clear_placeholder(self, widget, placeholder):
        """Clears the placeholder text when the user clicks into the entry."""
        if widget.get() == placeholder:
            widget.delete(0, tk.END)

    def connect_to_firewall(self):
        firewall_ip = self.firewall_ip_entry.get()
        username = self.username_entry.get()
        password = self.password_entry.get()

        self.api = FirewallAPI(firewall_ip, username, password)

        api_key = self.api.get_api_key()
        if not api_key:
            messagebox.showerror("Error", "Failed to connect to firewall or get API key.")
            return

        self.software_versions = self.api.list_available_software_versions()
        if not self.software_versions:
            messagebox.showerror("Error", "No software versions found.")
            return

        self.software_version_combo['values'] = self.software_versions
        self.update_button["state"] = "normal"
        messagebox.showinfo("Success", "Connected to firewall and loaded available versions.")

    def start_update(self):
        selected_version = self.software_version_combo.get()
        if not selected_version:
            messagebox.showwarning("Warning", "Please select a software version to install.")
            return

        success = self.api.software_update_install(selected_version)
        if success:
            messagebox.showinfo("Success", f"Software version {selected_version} installed successfully.")
        else:
            messagebox.showerror("Error", f"Failed to install software version {selected_version}.")

def main():
    root = ThemedTk(theme="arc")
    root.configure(bg="#2C2F33")
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
