# =============================
# CAMERA MODULE CODE - FINAL VERSION
# =============================

import time
from picamera2 import Picamera2
import numpy as np
import imageio
import io
import cv2
import json
import os
import argparse

class CameraModule:
    def __init__(self):
        self.camera = Picamera2()
        config = self.camera.create_still_configuration(main={"size": (800, 600)})
        self.camera.configure(config)
        self.camera.options['quality'] = 95

        self.load_camera_settings()
        self.settings_file = "camera_settings.json"
        self._initialize_camera()

    def load_camera_settings(self):
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                self.saved_exposure = settings.get('exposure_time', 145660)
                self.saved_gain = settings.get('analogue_gain', 8.0)
                self.target_brightness = settings.get('target_brightness', 150)

                # fixed manual color gains
                self.colour_gains = (1.6, 1.0)  # RED, BLUE
                print(f"Loaded settings with fixed ColourGains: R={self.colour_gains[0]}, B={self.colour_gains[1]}")
            else:
                self.saved_exposure = 145660
                self.saved_gain = 8.0
                self.target_brightness = 150
                self.colour_gains = (1.6, 1.0)  # default fixed gains
                print("Using default camera settings with fixed ColourGains")
        except Exception as e:
            print(f"Error loading settings, using defaults: {e}")
            self.saved_exposure = 145660
            self.saved_gain = 8.0
            self.target_brightness = 150
            self.colour_gains = (1.6, 1.0)


    def save_camera_settings(self, exposure_time, analogue_gain, target_brightness):
        try:
            settings = {
                'exposure_time': int(exposure_time),
                'analogue_gain': float(analogue_gain),
                'target_brightness': int(target_brightness),
                'colour_gains': list(self.colour_gains)
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
            print(f"Settings saved: {settings}")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _initialize_camera(self):
        print("Initializing camera...")
        self.camera.start()
        self.camera.set_controls({
            "ExposureTime": self.saved_exposure,
            "AnalogueGain": self.saved_gain,
            "AeEnable": False,
            "AwbEnable": False,
            "ColourGains": self.colour_gains,
            "Brightness": 0.0,
            "Contrast": 1.0,
        })
        print("Camera warming up...")
        for i in range(5):
            _ = self.camera.capture_array()
            time.sleep(0.5)
            print(f"Warm-up frame {i+1}/5")
        print("Camera initialization complete")
        self.camera.stop()

    def capture_image(self, apply_color_correction=True, byte_image=True, filename="bright_image.jpg", auto_adjust=True, save_preview=True):
        self.load_camera_settings()
        self.camera.start()
        try:
            self.camera.set_controls({
                "ExposureTime": self.saved_exposure,
                "AnalogueGain": self.saved_gain,
                "AeEnable": False,
                "AwbEnable": False,
                "ColourGains": self.colour_gains,
                "Brightness": 0.0,
                "Contrast": 1.0,
            })
            time.sleep(1.0)
            test_image = self.camera.capture_array()
            current_brightness = np.mean(test_image)
            print(f"Current brightness: {current_brightness:.1f} (target: {self.target_brightness})")

            if save_preview:
                cv2.imwrite("preview.jpg", cv2.cvtColor(test_image, cv2.COLOR_RGB2BGR))
                print("Preview image saved as preview.jpg")

            if auto_adjust and abs(current_brightness - self.target_brightness) > 15:
                print("Auto-adjusting brightness...")
                brightness_ratio = self.target_brightness / max(current_brightness, 1)
                adjustment_factor = min(max(brightness_ratio, 0.3), 3.0)
                new_exposure = int(self.saved_exposure * adjustment_factor)
                new_gain = self.saved_gain
                if adjustment_factor > 2.0:
                    new_exposure = min(new_exposure, 100000)
                    remaining_adjustment = adjustment_factor / (new_exposure / self.saved_exposure)
                    new_gain = min(self.saved_gain * remaining_adjustment, 8.0)
                elif adjustment_factor < 0.5:
                    new_exposure = max(new_exposure, 1000)
                    remaining_adjustment = adjustment_factor / (new_exposure / self.saved_exposure)
                    new_gain = max(self.saved_gain * remaining_adjustment, 1.0)

                self.camera.set_controls({"ExposureTime": new_exposure, "AnalogueGain": new_gain})
                print(f"Adjusted: Exposure={new_exposure}us, Gain={new_gain:.2f}")
                time.sleep(1.0)
                #self.save_camera_settings(new_exposure, new_gain, self.target_brightness)
                self.saved_exposure = new_exposure
                self.saved_gain = new_gain

            image = self.camera.capture_array()
            final_brightness = np.mean(image)
            print(f"Final brightness: {final_brightness:.1f}")

            if apply_color_correction:
                image = self._apply_color_correction(image)
                corrected_filename = filename.replace('.jpg', '_corrected.jpg')
                cv2.imwrite(corrected_filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                print(f"Color-corrected image saved as {corrected_filename}")

            cv2.imwrite(filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            print(f"Image saved as {filename}")

            if byte_image:
                with io.BytesIO() as image_io:
                    imageio.imwrite(image_io, image, format='jpg')
                    return image_io.getvalue()
            return image
        except Exception as e:
            print(f"Error capturing image: {e}")
            return None
        finally:
            self.camera.stop()

    def _apply_color_correction(self, image):
        print("Applying color correction...")
        image_float = image.astype(np.float32) / 255.0
        avg_color = np.mean(image_float, axis=(0, 1))
        print(f"Average color channels: R={avg_color[0]:.3f}, G={avg_color[1]:.3f}, B={avg_color[2]:.3f}")
        gray_world_scale = np.mean(avg_color) / avg_color
        gray_world_scale = np.clip(gray_world_scale, 0.5, 2.0)
        corrected_image = image_float * gray_world_scale
        corrected_image = np.clip(corrected_image, 0, 1) * 255
        return corrected_image.astype(np.uint8)

    def close(self):
        if hasattr(self, 'camera'):
            try:
                self.camera.stop()
            except:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Raspberry Pi Camera Module")
#     parser.add_argument('--capture', action='store_true', help='Capture and save an image')
#     parser.add_argument('--filename', type=str, default='captured_image.jpg', help='Filename to save image')
#     parser.add_argument('--set-colour-gain', nargs=2, type=float, metavar=('RED_GAIN', 'BLUE_GAIN'), help='Set manual colour gains')
#     args = parser.parse_args()

#     with CameraModule() as cam:
#         if args.set_colour_gain:
#             red_gain, blue_gain = args.set_colour_gain
#             cam.colour_gains = (red_gain, blue_gain)
#             print(f"[INFO] Manually setting colour gains: R={red_gain}, B={blue_gain}")
#             cam.save_camera_settings(cam.saved_exposure, cam.saved_gain, cam.target_brightness)

#         if args.capture:
#             print("[INFO] Capturing image...")
#             cam.capture_image(filename=args.filename)