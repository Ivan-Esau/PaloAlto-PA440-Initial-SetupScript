import sys
import paramiko  # Bibliothek für SSH-Verbindungen
import time
import re  # Reguläre Ausdrücke
from PyQt5 import QtWidgets, QtGui, QtCore  # GUI-Bibliotheken
from PyQt5.QtWidgets import QMessageBox, QHBoxLayout, QLabel, QLineEdit, QComboBox, QVBoxLayout, QPushButton, QFrame, QProgressBar, QTextEdit
import qtawesome as qta  # Für Icons
import io  # Für die Umleitung von stdout

# Funktion zum Lesen der SSH-Shell bis zu einem bestimmten Prompt
def read_shell_until_prompt(shell, patterns, timeout=60):
    output = ""
    start_time = time.time()

    while time.time() - start_time < timeout:
        if shell.recv_ready():
            try:
                # Empfangene Daten dekodieren
                output += shell.recv(5000).decode('utf-8', errors='replace')
            except UnicodeDecodeError as e:
                print(f"Decoding error: {e}")
            print(output.strip())
            for pattern, action in patterns:
                # Überprüfen, ob eines der Muster im Output gefunden wurde
                if re.search(pattern, output, re.IGNORECASE):
                    return action, output
        else:
            time.sleep(1)
    raise TimeoutError("Timeout erreicht, ohne dass ein Prompt erkannt wurde.")

# Funktion für die interaktive Anmeldung und Konfiguration
def interactive_login_and_configure(shell, hostname, deviceTag):
    print("Starte interaktive Sitzung...")
    switched_credentials = False
    # Muster für verschiedene Prompts und entsprechende Aktionen
    patterns = [
        (r"login:", "send_username"),
        (r"password:", "send_password"),
        (r"login incorrect", "retry_login"),
        (r"enter old password", "send_old_password"),
        (r"enter new password", "send_new_password"),
        (r"confirm.*password", "confirm_new_password"),
        (r">", "continue_after_login")
    ]

    while True:
        try:
            # Warten auf einen Prompt und entsprechende Aktion
            action, output = read_shell_until_prompt(shell, patterns)
        except TimeoutError as e:
            print(e)
            break

        # Ausführen der entsprechenden Aktion basierend auf dem Prompt
        if action == "send_username":
            shell.send("admin\r\n")
        elif action == "send_password":
            shell.send("Rhenus2024\r\n" if switched_credentials else "admin\r\n")
        elif action == "retry_login":
            if not switched_credentials:
                switched_credentials = True
            else:
                break
        elif action == "send_old_password":
            shell.send("admin\r\n")
        elif action == "send_new_password":
            shell.send("Rhenus2024\r\n")
        elif action == "confirm_new_password":
            shell.send("Rhenus2024\r\n")
        elif action == "continue_after_login":
            return
        time.sleep(2)

# Funktion zum Überprüfen des ZTP-Status und Konfiguration
def check_ztp_status_and_configure(shell, hostname, deviceTag):
    print("Überprüfe, ob ZTP deaktiviert ist...")
    shell.send("show system setting ztp-status\r\n")
    time.sleep(2)
    # Empfangene Daten dekodieren und in Kleinbuchstaben umwandeln
    output = shell.recv(5000).decode('utf-8', errors='replace').lower()

    if "enabled" in output:
        # ZTP deaktivieren
        shell.send("set system ztp disable\r\n")
        time.sleep(2)
        shell.send("y\r\n")
        time.sleep(60)
    # Firewall-Kommandos konfigurieren
    configure_firewall_commands(shell, hostname, deviceTag)

# Funktion zum Senden der Konfigurationsbefehle an die Firewall
def configure_firewall_commands(shell, hostname, deviceTag):
    shell.send("set cli config-output-format set\r\n")
    time.sleep(1)
    shell.send("configure\r\n")
    time.sleep(1)

    # Liste der Konfigurationsbefehle
    commands = [
        "delete deviceconfig system ip-address",
        "delete deviceconfig system netmask",
        "delete network virtual-wire default-vwire",
        "delete rulebase security rules rule1",
        "delete zone trust",
        "delete zone untrust",
        "delete network interface ethernet ethernet1/1",
        "delete network interface ethernet ethernet1/2",
        "delete network virtual-router default",
        "set deviceconfig system panorama local-panorama panorama-server 212.202.64.26",
        f"set deviceconfig system hostname {hostname}",
        "set deviceconfig system type dhcp-client accept-dhcp-domain yes accept-dhcp-hostname yes send-client-id yes send-hostname yes",
        "set deviceconfig system secure-proxy-server proxy.net.rhs.zz",
        "set deviceconfig system secure-proxy-port 8080",
        f"set deviceconfig system snmp-setting snmp-system location {deviceTag}"
    ]

    # Senden der Befehle an die Firewall
    for cmd in commands:
        shell.send(f"{cmd}\r\n")
        time.sleep(1)
    shell.send("commit\r\n")  # Konfiguration übernehmen
    time.sleep(30)
    shell.send("exit\r\n")
    time.sleep(2)

# Hauptfunktion zur Konfiguration der Firewall
def configure_firewall(server_ip, username, password, ports, hostname, deviceTag):
    for port in ports:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # Verbindung zum Server herstellen
            ssh.connect(server_ip, username=username, password=password, port=port)

            shell = ssh.invoke_shell()
            time.sleep(2)
            shell.send("\r\n")
            time.sleep(2)

            # Interaktive Anmeldung und Konfiguration durchführen
            interactive_login_and_configure(shell, hostname, deviceTag)
            check_ztp_status_and_configure(shell, hostname, deviceTag)
        except Exception as e:
            print(f"Ein Fehler ist auf Port {port} aufgetreten: {e}")
        finally:
            ssh.close()
            print(f"Verbindung auf Port {port} geschlossen.")

# Klasse zum Umleiten von stdout in die QTextEdit-Konsole
class EmittingStream(QtCore.QObject):
    text_written = QtCore.pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass

# GUI-Anwendungsklasse für den Firewall-Konfigurator
class FirewallConfiguratorApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

        # Umleitung von stdout in die Konsole
        sys.stdout = EmittingStream()
        sys.stdout.text_written.connect(self.update_console)

    def init_ui(self):
        # Einstellungen des Hauptfensters
        self.setWindowTitle("Firewall Configurator")
        self.setFixedSize(500, 600)  # Höhe angepasst, um Platz für die Konsole zu schaffen
        self.setStyleSheet("""
            QWidget {
                background-color: #2C2F33;
                color: white;
                font-family: Arial;
            }
            QLineEdit, QComboBox {
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px;
                background-color: #23272A;
                color: #FFFFFF;
            }
            QLineEdit:hover, QComboBox:hover {
                border: 1px solid #7289DA;
            }
            QPushButton {
                background-color: #7289DA;
                border-radius: 8px;
                padding: 10px;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5b6eae;
            }
            QLabel {
                font-size: 12pt;
            }
            QTextEdit {
                background-color: #23272A;
                color: #FFFFFF;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px;
            }
        """)

        # Layout und Widgets
        layout = QtWidgets.QVBoxLayout()
        header = QLabel("Firewall Configurator")
        header.setFont(QtGui.QFont("Arial", 18, QtGui.QFont.Bold))
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #7289DA;")
        layout.addWidget(line)

        form_layout = QVBoxLayout()

        # Server IP
        self.server_ip_combo = self.add_icon_field(form_layout, "Server IP:", qta.icon('fa.server'), QComboBox, "Server IP auswählen", ["10.253.77.131", "10.253.77.132", "10.253.77.133"])

        # Benutzername
        self.username_input = self.add_icon_field(form_layout, "Username:", qta.icon('fa.user'), QLineEdit, "Geben Sie den Benutzernamen (RadiusAcc) ein")

        # Passwort
        self.password_input = self.add_icon_field(form_layout, "Password:", qta.icon('fa.lock'), QLineEdit, "Geben Sie das Passwort ein")
        self.password_input.setEchoMode(QLineEdit.Password)

        # Ports
        self.ports_input = self.add_icon_field(form_layout, "Ports:", qta.icon('fa.plug'), QLineEdit, "Port (z.B. 5118)")

        # Hostname
        self.hostname_input = self.add_icon_field(form_layout, "Hostname:", qta.icon('fa.desktop'), QLineEdit, "Geben Sie den Hostname ein")

        # Device Tag
        self.device_tag_input = self.add_icon_field(form_layout, "Device Tag:", qta.icon('fa.tag'), QLineEdit, "Geben Sie das Device Tag ein")

        layout.addLayout(form_layout)

        # Fortschrittsanzeige
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Ausführen-Button
        self.run_button = QPushButton("Run Configuration")
        self.run_button.clicked.connect(self.run_configuration)
        layout.addWidget(self.run_button)

        # Konsolenfenster für CLI-Ausgaben
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        layout.addWidget(self.console_output)

        self.setLayout(layout)

    # Hilfsfunktion zum Hinzufügen von Eingabefeldern mit Icons
    def add_icon_field(self, layout, label_text, icon, field_type, placeholder, items=None):
        field_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        field_layout.addWidget(icon_label)

        field = field_type()
        field.setPlaceholderText(placeholder)
        field.setToolTip(placeholder)

        if isinstance(field, QComboBox) and items:
            field.addItems(items)

        field_layout.addWidget(field)
        layout.addLayout(field_layout)

        return field

    # Funktion, die beim Klicken des Ausführen-Buttons aufgerufen wird
    def run_configuration(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Startet den unbestimmten Fortschritt

        # Blockieren des Buttons während der Ausführung
        self.run_button.setEnabled(False)

        # Starten der Konfiguration in einem separaten Thread
        self.thread = QtCore.QThread()
        self.worker = ConfigurationWorker(
            self.server_ip_combo.currentText(),
            self.username_input.text(),
            self.password_input.text(),
            self.ports_input.text(),
            self.hostname_input.text(),
            self.device_tag_input.text()
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.configuration_finished)
        self.thread.start()

    def configuration_finished(self, success, message):
        self.progress_bar.setRange(0, 1)  # Fortschrittsbalken zurücksetzen
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)  # Button wieder aktivieren

        if success:
            QMessageBox.information(self, "Erfolg", "Konfiguration erfolgreich abgeschlossen.")
        else:
            QMessageBox.critical(self, "Fehler", f"Ein Fehler ist aufgetreten: {message}")

    # Aktualisiert die Konsole mit neuen Texten
    def update_console(self, text):
        self.console_output.append(text)

# Worker-Klasse für die Konfiguration in einem separaten Thread
class ConfigurationWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool, str)

    def __init__(self, server_ip, username, password, ports_text, hostname, device_tag):
        super().__init__()
        self.server_ip = server_ip
        self.username = username
        self.password = password
        self.ports_text = ports_text
        self.hostname = hostname
        self.device_tag = device_tag

    def run(self):
        try:
            ports = list(map(int, self.ports_text.split(',')))
            # Firewall konfigurieren
            configure_firewall(self.server_ip, self.username, self.password, ports, self.hostname, self.device_tag)
            self.finished.emit(True, "Success")
        except Exception as e:
            self.finished.emit(False, str(e))

# Start des Programms
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    configurator = FirewallConfiguratorApp()
    configurator.show()
    sys.exit(app.exec_())
