#========================================
#  Slave Raspberry Pi control over TCP
#========================================

import socket
import threading
import json
import time
import os
import signal
from camera_module_v4_3 import CameraModule

# Configuration - Change these for each slave
SLAVE_ID = 1  # Change this per slave (1, 2, 3, etc.)
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 8888  # Port to listen on
IMAGE_DIR = f"/home/rpiez1/images/slave{SLAVE_ID}"  # Directory to save images


class WiFiSlaveCamera:
    def __init__(self, slave_id, host='0.0.0.0', port=8888):
        self.slave_id = slave_id
        self.host = host
        self.port = port
        self.camera = CameraModule()
        self.server_socket = None
        self.running = False

        # Create image directory if it doesn't exist
        os.makedirs(IMAGE_DIR, exist_ok=True)
        print(f"[SLAVE {self.slave_id}] Image directory: {IMAGE_DIR}")

    def capture_image(self):
        """Capture an image using the camera module"""
        try:
            timestamp = int(time.time())
            filename = f"slave{self.slave_id}_image_{timestamp}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)

            print(f"[SLAVE {self.slave_id}] Capturing image: {filename}")
            self.camera.capture_image(filename=filepath)

            return {
                "status": "success",
                "message": f"Slave {self.slave_id} image captured successfully",
                "filename": filename,
                "filepath": filepath,
                "timestamp": timestamp
            }
        except Exception as e:
            error_msg = f"Failed to capture image: {str(e)}"
            print(f"[SLAVE {self.slave_id}] {error_msg}")
            return {
                "status": "error",
                "message": f"Slave {self.slave_id} image capture failed",
                "error": error_msg
            }

    def send_image_to_client(self, client_socket, filepath):
        """Send image file to client"""
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            file_size = len(file_data)
            client_socket.send(f"{file_size}\n".encode())

            ack = client_socket.recv(1024).decode().strip()
            if ack == "READY":
                client_socket.sendall(file_data)
                print(f"[SLAVE {self.slave_id}] Image sent successfully ({file_size} bytes)")
                return True
            else:
                print(f"[SLAVE {self.slave_id}] Client not ready to receive image")
                return False

        except Exception as e:
            print(f"[SLAVE {self.slave_id}] Error sending image: {e}")
            return False

    def handle_client(self, client_socket, client_address):
        """Handle incoming client connection"""
        try:
            print(f"[SLAVE {self.slave_id}] Client connected from {client_address}")

            data = client_socket.recv(1024).decode().strip()
            if not data:
                return

            command = json.loads(data)
            print(f"[SLAVE {self.slave_id}] Received command: {command}")

            if command.get('action') == 'capture':
                result = self.capture_image()

                response = json.dumps(result) + '\n'
                client_socket.send(response.encode())
                print(f"[SLAVE {self.slave_id}] Sent response to master")

                if result['status'] == 'success' and command.get('send_image', False):
                    print(f"[SLAVE {self.slave_id}] Preparing to send image...")
                    self.send_image_to_client(client_socket, result['filepath'])

            elif command.get('action') == 'status':
                status = {
                    "status": "success",
                    "message": f"Slave {self.slave_id} is running",
                    "slave_id": self.slave_id,
                    "uptime": time.time() - self.start_time
                }
                response = json.dumps(status) + '\n'
                client_socket.send(response.encode())

            else:
                error_response = {
                    "status": "error",
                    "message": f"Unknown command: {command.get('action', 'None')}"
                }
                response = json.dumps(error_response) + '\n'
                client_socket.send(response.encode())

        except json.JSONDecodeError:
            print(f"[SLAVE {self.slave_id}] Invalid JSON received from {client_address}")
        except Exception as e:
            print(f"[SLAVE {self.slave_id}] Error handling client {client_address}: {e}")
        finally:
            client_socket.close()

    def start_server(self):
        """Start the WiFi server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)

            self.running = True
            self.start_time = time.time()

            print(f"[SLAVE {self.slave_id}] WiFi Camera Server started on {self.host}:{self.port}")
            print(f"[SLAVE {self.slave_id}] Waiting for connections...")

            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except socket.error as e:
                    if self.running:
                        print(f"[SLAVE {self.slave_id}] Socket error: {e}")

        except Exception as e:
            print(f"[SLAVE {self.slave_id}] Server error: {e}")
        finally:
            self.cleanup()

    def stop_server(self):
        """Stop the WiFi server"""
        print(f"[SLAVE {self.slave_id}] Stopping server...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def cleanup(self):
        """Clean up resources"""
        if self.server_socket:
            self.server_socket.close()
        print(f"[SLAVE {self.slave_id}] Server stopped")


def signal_handler(signum, frame):
    """Handle interrupt signals"""
    print(f"\n[SLAVE {SLAVE_ID}] Interrupt received, shutting down...")
    if 'slave_camera' in globals():
        slave_camera.stop_server()
    exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"[SLAVE {SLAVE_ID}] WiFi Slave Camera Starting...")
    print(f"[SLAVE {SLAVE_ID}] Slave ID: {SLAVE_ID}")
    print(f"[SLAVE {SLAVE_ID}] Listening on: {HOST}:{PORT}")

    slave_camera = WiFiSlaveCamera(SLAVE_ID, HOST, PORT)

    try:
        slave_camera.start_server()
    except KeyboardInterrupt:
        print(f"\n[SLAVE {SLAVE_ID}] Keyboard interrupt received")
    finally:
        slave_camera.stop_server()
