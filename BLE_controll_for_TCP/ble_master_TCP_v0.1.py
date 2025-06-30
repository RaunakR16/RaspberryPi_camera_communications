# master_wifi_controller.py
import socket
import time
import threading
import json
import os
from bluezero import peripheral
import cv2
import numpy as np
from motor_module import MotorModule
from collections import namedtuple

# === Brightness Level Detection Setup ===
BLevel = namedtuple("BLevel", ['brange', 'bval'])
_blevels = [
    BLevel(brange=range(0, 24), bval=0),
    BLevel(brange=range(23, 47), bval=1),
    BLevel(brange=range(46, 70), bval=2),
    BLevel(brange=range(69, 93), bval=3),
    BLevel(brange=range(92, 116), bval=4),
    BLevel(brange=range(115, 140), bval=5),
    BLevel(brange=range(139, 163), bval=6),
    BLevel(brange=range(162, 186), bval=7),
    BLevel(brange=range(185, 209), bval=8),
    BLevel(brange=range(208, 232), bval=9),
    BLevel(brange=range(231, 256), bval=10),
]

def detect_level(h_val):
    h_val = int(h_val)
    for blevel in _blevels:
        if h_val in blevel.brange:
            return blevel.bval
    raise ValueError("Brightness Level Out of Range")

def get_img_avg_brightness(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, _, v = cv2.split(hsv)
    return int(np.average(v.flatten()))

def process(img_path):
    c = 1
    l = []
    b_val = []
    n = 0
    while c < 3:
        bb = cv2.imread(img_path)
        bb_1 = cv2.cvtColor(bb, cv2.COLOR_RGB2BGR)
        prt_1 = bb_1[:, :400]
        prt_2 = bb_1[:, 400:]
        if c == 1:
            check_img = prt_1[0:100, 100:200]
            b_value = detect_level(get_img_avg_brightness(check_img))
            b_val.append(b_value)
            if b_value < 3:
                cnt = 0
                l.extend([c, cnt])
                c += 1
                continue
            else:
                prt_11 = prt_1[:300, 100:240]
        elif c == 2:
            check_img = prt_2[0:100, 100:200]
            b_value = detect_level(get_img_avg_brightness(check_img))
            b_val.append(b_value)
            if b_val[0] == b_val[1] <= 2:
                cnt = 0
                l.extend([c, cnt])
                c += 1
                break
            elif b_val[0] < b_val[1] <= 2:
                prt_11 = prt_2[:300, 100:230]
            elif b_val[0] > b_val[1] <= 2:
                prt_11 = prt_1[:300, 100:240]
                n = 1
            else:
                prt_11 = prt_2[:300, 100:230]
        prt_11_1 = prt_11[:140]
        prt_11_2 = prt_11[140:280]
        i = 10
        ini_sum = np.sum(prt_11_1[0:10])
        count_t = 0
        while i + 10 < len(prt_11_1):
            m = np.sum(prt_11_1[i:i + 10])
            s_t = np.subtract(ini_sum.astype(np.int64), m.astype(np.int64))
            if s_t > 1000:
                count_t += 1
                break
            else:
                ini_sum = np.sum(prt_11_1[i:i + 10])
                i += 2
        i = 10
        ini_sum = np.sum(prt_11_2[0:10])
        count_c = 0
        while i + 10 < len(prt_11_2):
            m = np.sum(prt_11_2[i:i + 10])
            s_c = np.subtract(ini_sum.astype(np.int64), m.astype(np.int64))
            if s_c > -1000:
                count_c += 1
                break
            else:
                ini_sum = np.sum(prt_11_2[i:i + 10])
                i += 2
        if count_c == 1 and count_t == 0:
            cnt = 1
        elif count_c == 1 and count_t == 1:
            cnt = 2
        elif count_t == 1 and count_c == 0:
            cnt = 0
        else:
            cnt = 0
        l.extend([c, cnt])
        c += 1
        if n == 1:
            l = [1, cnt, 2, 0]
    return l


# === BLE and Networking Setup ===
motor = MotorModule()

folder_path = '/home/rpiez/received_images'
def clear_image_folder(folder_path=folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
clear_image_folder()

ADAPTER_ADDR = 'B8:27:EB:11:A5:AA'
my_device = peripheral.Peripheral(adapter_address=ADAPTER_ADDR, local_name='master')
result = "master Ready"
processing_complete = False

def write_callback(value, options):
    global processing_complete
    command = value.decode()
    print(f"Received command: {command}")
    if command.strip() == "capture":
        processing_complete = False
        motor.rotate_anticlockwise()
        time.sleep(2)
        threading.Thread(target=send_capture_to_all_slaves).start()
    if command.strip() == "cw":
        print("Received command to rotate clockwise")
        motor.rotate_clockwise()

def read_callback(options):
    global result
    return result.encode('utf-8')

SLAVE_HOSTS = {
    1: 'slcam01.local',
    2: 'slcam02.local',
    3: 'slcam03.local',
    4: 'slcam04.local',
    5: 'slcam05.local',
}
SLAVE_PORT = 8888
TIMEOUT = 30
MASTER_IMAGE_DIR = folder_path
os.makedirs(MASTER_IMAGE_DIR, exist_ok=True)

def update_ble_result(new_result):
    global result, processing_complete
    result = new_result
    processing_complete = True
    try:
        my_device.update_characteristic_value(1, 2, result.encode('utf-8'))
        print(f"BLE characteristic updated with result: {result}")
    except Exception as e:
        print(f"Error updating BLE characteristic: {e}")

def process_image_data(device=None, folder_path=folder_path):
    process_results = []
    try:
        image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            update_ble_result("No images to process")
            return []
        for filename in image_files:
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                try:
                    result = process(file_path)
                    process_results.append(result)
                    print(f"Processed {filename}: {result}")
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
        if process_results:
            update_ble_result(json.dumps({"results": process_results, "status": "complete"}))
        else:
            update_ble_result("No valid results")
    except Exception as e:
        update_ble_result(json.dumps({"error": str(e), "status": "error"}))
    finally:
        clear_image_folder(folder_path)
    return process_results

# === TCP Communication ===
def receive_image_from_slave(sock, slave_id, response_data):
    try:
        size_data = sock.recv(1024).decode().strip()
        file_size = int(size_data)
        sock.send("READY".encode())
        received_data = b""
        bytes_received = 0
        while bytes_received < file_size:
            chunk = sock.recv(min(4096, file_size - bytes_received))
            if not chunk:
                break
            received_data += chunk
            bytes_received += len(chunk)
        if bytes_received == file_size:
            timestamp = int(time.time())
            filename = f"master_received_slave{slave_id}_{timestamp}.jpg"
            filepath = os.path.join(MASTER_IMAGE_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(received_data)
            time.sleep(1)
            return {"success": True, "filepath": filepath, "filename": filename, "size": file_size}
        else:
            return {"success": False, "error": "Incomplete transfer"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_capture_command(slave_host, slave_id, receive_image=True):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((slave_host, SLAVE_PORT))
        command = {
            "action": "capture",
            "timestamp": time.time(),
            "send_image": receive_image
        }
        sock.send((json.dumps(command) + '\n').encode())
        response = sock.recv(1024).decode().strip()
        response_data = json.loads(response)
        if response_data['status'] == 'success':
            if receive_image:
                return receive_image_from_slave(sock, slave_id, response_data)
            else:
                return {"success": True, "message": "Command sent, no image requested"}
        else:
            return {"success": False, "error": response_data.get('error', 'Unknown error')}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try: sock.close()
        except: pass

def send_capture_to_all_slaves(receive_images=True):
    threads = []
    results = {}
    update_ble_result("Processing started...")
    def capture_with_result(slave_host, slave_id, receive_images):
        result = send_capture_command(slave_host, slave_id, receive_images)
        results[slave_id] = result
    for slave_id, slave_host in SLAVE_HOSTS.items():
        thread = threading.Thread(target=capture_with_result, args=(slave_host, slave_id, receive_images))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    successful_transfers = [r for r in results.values() if r.get('success', False)]
    if successful_transfers:
        update_ble_result("Images received, processing...")
        time.sleep(1)
        process_image_data(device=my_device, folder_path=MASTER_IMAGE_DIR)
    else:
        update_ble_result("No images received")

# === BLE Start ===
if __name__ == "__main__":
    print("[MASTER] Starting BLE WiFi Camera Controller")
    print(f"[MASTER] Using Bluetooth adapter: {ADAPTER_ADDR}")
    my_device.add_service(srv_id=1, uuid='12345678-1234-5678-1234-56789abcdef0', primary=True)
    my_device.add_characteristic(
        srv_id=1, chr_id=1,
        uuid='abcd1234-5678-4321-1234-fedcba987654',
        value=result.encode(), notifying=False,
        flags=['write'], write_callback=write_callback)
    my_device.add_characteristic(
        srv_id=1, chr_id=2,
        uuid='abcd1234-5678-4321-1234-fedcba987655',
        value=result.encode(), notifying=True,
        flags=['read', 'notify'], read_callback=read_callback)
    print("Master BLE advertising started...")
    my_device.publish()
