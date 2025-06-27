#==========================================
#  Master Raspberry Pi control over TCP
#==========================================

import socket
import time
import threading
import json
import os

# Replace with your actual slave Pi hostnames
SLAVE_HOSTS = {
    1: 'slcam01.local',
    2: 'slcam02.local', 
    3: 'slcam03.local',
    4: 'slcam04.local',
    5: 'slcam05.local',
    # Add more slaves as needed
}   

SLAVE_PORT = 8888  # Port that slaves will listen on
TIMEOUT = 30  # Timeout in seconds
MASTER_IMAGE_DIR = "/home/rpiez/received_images"  # Directory to save received images

# Create master image directory
os.makedirs(MASTER_IMAGE_DIR, exist_ok=True)

def receive_image_from_slave(sock, slave_id, response_data):
    """Receive image file from slave"""
    try:
        # Receive file size
        size_data = sock.recv(1024).decode().strip()
        file_size = int(size_data)
        print(f"[MASTER] Expecting image of {file_size} bytes from Slave {slave_id}")
        
        # Send acknowledgement
        sock.send("READY".encode())
        
        # Receive file data
        received_data = b""
        bytes_received = 0
        
        while bytes_received < file_size:
            chunk = sock.recv(min(4096, file_size - bytes_received))
            if not chunk:
                break
            received_data += chunk
            bytes_received += len(chunk)
            
            # Show progress for large files
            if file_size > 100000:  # Show progress for files > 100KB
                progress = (bytes_received / file_size) * 100
                print(f"[MASTER] Receiving from Slave {slave_id}: {progress:.1f}%")
        
        if bytes_received == file_size:
            # Save the image
            timestamp = int(time.time())
            filename = f"master_received_slave{slave_id}_{timestamp}.jpg"
            filepath = os.path.join(MASTER_IMAGE_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(received_data)
            
            print(f"[MASTER] Image saved from Slave {slave_id}: {filename}")
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "size": file_size
            }
        else:
            print(f"[MASTER] Incomplete image received from Slave {slave_id}")
            return {"success": False, "error": "Incomplete transfer"}
            
    except Exception as e:
        print(f"[MASTER] Error receiving image from Slave {slave_id}: {e}")
        return {"success": False, "error": str(e)}

def send_capture_command(slave_host, slave_id, receive_image=True):
    """Send capture command to a slave and optionally receive the image"""
    try:
        print(f"[MASTER] Connecting to Slave {slave_id} at {slave_host}:{SLAVE_PORT}...")
        
        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect((slave_host, SLAVE_PORT))
        
        print(f"[MASTER] Connected to Slave {slave_id}")
        
        # Send capture command
        command = {
            "action": "capture",
            "timestamp": time.time(),
            "send_image": receive_image
        }
        message = json.dumps(command) + '\n'
        sock.send(message.encode())
        print(f"[MASTER] Sent capture command to Slave {slave_id}")
        
        # Wait for response
        response = sock.recv(1024).decode().strip()
        response_data = json.loads(response)
        
        print(f"[MASTER] Response from Slave {slave_id}: {response_data['message']}")
        
        if response_data['status'] == 'success':
            print(f"[MASTER] Slave {slave_id} successfully captured image")
            
            # Receive image if requested, and capture was successful
            if receive_image:
                image_result = receive_image_from_slave(sock, slave_id, response_data)
                if image_result['success']:
                    print(f"[MASTER] Image successfully received from Slave {slave_id}")
                else:
                    print(f"[MASTER] Failed to receive image from Slave {slave_id}: {image_result.get('error')}")
        else:
            print(f"[MASTER] Slave {slave_id} failed to capture image: {response_data.get('error', 'Unknown error')}")
            
    except socket.timeout:
        print(f"[MASTER] Timeout waiting for Slave {slave_id}")
    except ConnectionRefusedError:
        print(f"[MASTER] Could not connect to Slave {slave_id} - service not running")
    except Exception as e:
        print(f"[MASTER] Error communicating with Slave {slave_id}: {e}")
    finally:
        try:
            sock.close()
        except:
            pass

def send_capture_to_all_slaves(receive_images=True):
    """Send capture command to all slaves simultaneously"""
    threads = []
    
    for slave_id, slave_host in SLAVE_HOSTS.items():
        thread = threading.Thread(
            target=send_capture_command, 
            args=(slave_host, slave_id, receive_images)
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()

def send_capture_sequential(receive_images=True):
    """Send capture command to slaves one by one"""
    for slave_id, slave_host in SLAVE_HOSTS.items():
        send_capture_command(slave_host, slave_id, receive_images)
        time.sleep(1)  # Small delay between slaves

def ping_slaves():
    """Check if all slaves are reachable"""
    print("[MASTER] Checking slave connectivity...")
    for slave_id, slave_host in SLAVE_HOSTS.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((slave_host, SLAVE_PORT))
            if result == 0:
                print(f"[MASTER] Slave {slave_id} ({slave_host}) is reachable")
                sock.close()
            else:
                print(f"[MASTER] Slave {slave_id} ({slave_host}) is not reachable")
        except Exception as e:
            print(f"[MASTER] Error checking Slave {slave_id}: {e}")

def capture_only_no_transfer():
    """Capture images on slaves without transferring to master"""
    print("\n[MASTER] Capturing images (no transfer)...")
    send_capture_to_all_slaves(receive_images=False)

def list_received_images():
    """List all images received from slaves"""
    try:
        images = [f for f in os.listdir(MASTER_IMAGE_DIR) if f.endswith('.jpg')]
        if images:
            print(f"\n[MASTER] Images in {MASTER_IMAGE_DIR}:")
            for img in sorted(images):
                filepath = os.path.join(MASTER_IMAGE_DIR, img)
                size = os.path.getsize(filepath)
                mtime = time.ctime(os.path.getmtime(filepath))
                print(f"  {img} - {size} bytes - {mtime}")
        else:
            print(f"[MASTER] No images found in {MASTER_IMAGE_DIR}")
    except Exception as e:
        print(f"[MASTER] Error listing images: {e}")

if __name__ == "__main__":
    print("[MASTER] WiFi Camera Controller Started")
    print(f"[MASTER] Configured slaves: {list(SLAVE_HOSTS.keys())}")
    
    # Check connectivity first
    ping_slaves()
  
    # Terminal Commands
    while True:
        print("\n[MASTER] Options:")
        print("1. Capture + receive images (simultaneous)")
        print("2. Capture + receive images (sequential)")
        print("3. Capture only (no image transfer)")
        print("4. Ping all slaves")
        print("5. List received images")
        print("6. Exit")
        
        choice = input("[MASTER] Enter choice (1-6): ").strip()
        
        if choice == '1':
            print("\n[MASTER] Starting simultaneous capture + image transfer...")
            send_capture_to_all_slaves(receive_images=True)
        elif choice == '2':
            print("\n[MASTER] Starting sequential capture + image transfer...")
            send_capture_sequential(receive_images=True)
        elif choice == '3':
            capture_only_no_transfer()
        elif choice == '4':
            ping_slaves()
        elif choice == '5':
            list_received_images()
        elif choice == '6':
            print("[MASTER] Exiting...")
            break
        else:
            print("[MASTER] Invalid choice")
        
        print("\n" + "="*50)
