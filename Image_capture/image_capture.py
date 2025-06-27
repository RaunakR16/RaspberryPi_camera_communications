#=============================
# CAMERA MODULE CODE
#=============================

import time
from picamera2 import Picamera2
import numpy as np
import imageio
import io
import cv2

class CameraModule:
    def __init__(self):
        """
        Initialize the camera module.
        """
        self.camera = Picamera2()
        config = self.camera.create_still_configuration(main={"size": (800, 600)})
        self.camera.configure(config)
        self.camera.options['quality'] = 95 

        self.camera.exposure_mode = 'auto'
        self.camera.automatic_gain_control = True  # Enable AGC

    def capture_image(self, apply_color_correction=True, byte_image=True, filename="bright_image.jpg"):
        """
        Capture an image with color correction option.

        Args:
            apply_color_correction (bool): Whether to apply color correction. Default is True.
            byte_image (bool): Whether to return JPEG encoded image data as bytes. Default is True.
            filename (str): Filename to save the image.

        Returns:
            bytes or np.ndarray: JPEG encoded image data or raw image array
        """
        self.camera.start()

        try:
            preview = self.camera.capture_file("Image.jpg")
            preview = cv2.imread("Image.jpg")
            avg_brightness = np.mean(preview)
            print(f"Initial average brightness: {avg_brightness}")

            metadata = self.camera.capture_metadata()
            current_exp = metadata.get('ExposureTime', 10000)
            current_gain = metadata.get('AnalogueGain', 1.0)

            print(f"Initial exposure: {current_exp}μs, gain: {current_gain}")

            target_brightness = 97
            brightness_ratio = target_brightness / max(avg_brightness, 1)
            brightness_multiplier = min(max(brightness_ratio, 1.0), 8.0)

            new_exp = int(current_exp * brightness_multiplier)
            new_gain = min(current_gain * (1 + (brightness_multiplier - 1) / 2), 8.0)

            print(f"Brightness multiplier: {brightness_multiplier:.2f}")

            self.camera.set_controls({
                "ExposureTime": new_exp,
                "AnalogueGain": new_gain,
                "Brightness": 0.2,
                "Contrast": 1.1,
                "ColourGains": (1.54, 1.0)
            })

            print(f"Applying adaptive settings - Exposure: {new_exp}μs, Gain: {new_gain}")
            time.sleep(2)

            image = self.camera.capture_array()

            final_brightness = np.mean(image)
            print(f"Final average brightness: {final_brightness}")

            self.camera.stop()

            if apply_color_correction:
                print("Applying color correction...")
                image_float = image.astype(np.float32) / 255.0
                avg_color = np.mean(image_float, axis=(0, 1))
                print(f"Average color channels before correction: R={avg_color[0]:.3f}, G={avg_color[1]:.3f}, B={avg_color[2]:.3f}")

                scale = 1 / avg_color
                scale /= np.max(scale)
                corrected_image = image_float * scale
                corrected_image = np.clip(corrected_image, 0, 1) * 255
                corrected_image = corrected_image.astype(np.uint8)

                avg_color_after = np.mean(corrected_image.astype(np.float32) / 255.0, axis=(0, 1))
                print(f"Average color channels after correction: R={avg_color_after[0]:.3f}, G={avg_color_after[1]:.3f}, B={avg_color_after[2]:.3f}")

                image = corrected_image

                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(hsv)
                avg_v = np.mean(v)
                scale = target_brightness / avg_v if avg_v != 0 else 1
                v = np.clip(v * scale, 0, 255).astype(np.uint8)
                normalized_hsv = cv2.merge((h, s, v))
                image = cv2.cvtColor(normalized_hsv, cv2.COLOR_HSV2BGR)

                corrected_filename = filename.split('.')[0] + '_corrected.' + filename.split('.')[1]
                cv2.imwrite(corrected_filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                print(f"Color-corrected image saved as {corrected_filename}")

            cv2.imwrite(filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            print(f"Image saved as {filename}")

            if byte_image:
                with io.BytesIO() as image_io:
                    imageio.imwrite(image_io, image, format='jpg')
                    image_bytes = image_io.getvalue()
                    print(f"Image captured successfully. Size: {len(image_bytes)} bytes")
                    return image_bytes

            return image

        except Exception as e:
            print(f"Error capturing image: {e}")
            return None
        finally:
            self.camera.stop()

    def get_image_size(self, image_bytes):
        return len(image_bytes) if image_bytes else 0

    def close(self):
        if hasattr(self, 'camera'):
            self.camera.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==============================
# CLI Entry Point for SSH Use
# ==============================

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Camera Module CLI")
    parser.add_argument("--capture", action="store_true", help="Capture and save an image")
    parser.add_argument("--filename", type=str, default="captured_via_ssh.jpg", help="Filename to save the image")
    parser.add_argument("--no-correction", action="store_true", help="Skip color correction")
    parser.add_argument("--no-bytes", action="store_true", help="Do not return bytes (just save image)")

    args = parser.parse_args()

    cam = CameraModule()

    if args.capture:
        print("[SSH Command] Capturing image...")
        cam.capture_image(
            apply_color_correction=not args.no_correction,
            byte_image=not args.no_bytes,
            filename=args.filename
        )
        print(f"[SSH Command] Image saved as {args.filename}")
    else:
        print("No action specified. Use --capture to capture an image.")

    cam.close()
