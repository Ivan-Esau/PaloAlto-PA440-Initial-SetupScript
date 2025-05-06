import paramiko
from openpyxl import Workbook


def check_ports(server_ip, username, password, start_port, end_port):
    """
    Prüft die Ports auf einem Konsolenserver.
    """
    results = []
    try:
        # SSH-Verbindung zum Konsolenserver aufbauen
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username=username, password=password)

        for port in range(start_port, end_port + 1):
            command = f"show port status {port}"  # Beispielbefehl, an Konsolenserver anpassen
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode().strip()

            # Anpassen der Prüfung basierend auf der Ausgabe
            if "connected" in output.lower():
                results.append((port, "Ja"))
            else:
                results.append((port, "Nein"))

        ssh.close()
    except Exception as e:
        print(f"Fehler: {e}")
        results = [(port, "Fehler") for port in range(start_port, end_port + 1)]

    return results


def save_to_excel(results, filename="port_status.xlsx"):
    """
    Speichert die Ergebnisse in einer Excel-Datei.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Port Status"

    # Header hinzufügen
    ws.append(["Port", "Status"])

    # Ergebnisse hinzufügen
    for port, status in results:
        ws.append([port, status])

    # Datei speichern
    wb.save(filename)
    print(f"Ergebnisse gespeichert in {filename}")


if __name__ == "__main__":
    # Konsolenserver-Daten
    server_ip = "10.253.77.132"  # Konsolenserver-IP
    username = "ivan.esau"
    password = "Jenni19-"

    # Ports und Ergebnisse
    start_port = 5101
    end_port = 5132
    results = check_ports(server_ip, username, password, start_port, end_port)

    # Ergebnisse speichern
    save_to_excel(results)
