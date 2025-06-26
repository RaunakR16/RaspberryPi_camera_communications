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
    
        # Adjust other camera settings if necessary (e.g., brightness, ISO)
        # self.camera.brightness = 50  # set brightness level (0-100)
        # self.camera.iso = 800     
            
    
    def capture_image(self, apply_color_correction=True, byte_image=True, filename="bright_image.jpg"):
        """
        Capture an image with color correction option.
        
        Args:
            apply_color_correction (bool): Whether to apply color correction. Default is True.
            
        Returns:
            bytes: JPEG encoded image data
        """
        self.camera.start()
        
        try:
            preview = self.camera.capture_file("preview.jpg")
            preview = cv2.imread("preview.jpg")
            avg_brightness = np.mean(preview)
            print(f"Initial average brightness: {avg_brightness}")
            
            # Get current auto exposure settings
            metadata = self.camera.capture_metadata()
            current_exp = metadata.get('ExposureTime', 10000)
            current_gain = metadata.get('AnalogueGain', 1.0)
            
            print(f"Initial exposure: {current_exp}μs, gain: {current_gain}")
            
            # Calculate adaptive exposure multiplier based on image brightness
            # Target brightness around 128 (middle of 0-255 range)
            target_brightness = 97
            brightness_ratio = target_brightness / max(avg_brightness, 1)  # Avoid division by zero
            
            # Cap the multiplier to reasonable limits
            brightness_multiplier = min(max(brightness_ratio, 1.0), 8.0)
            
            # Calculate new exposure settings
            new_exp = int(current_exp * brightness_multiplier)
            new_gain = min(current_gain * (1 + (brightness_multiplier - 1) / 2), 8.0)
            
            print(f"Brightness multiplier: {brightness_multiplier:.2f}")
            
            # Apply the new exposure settings
            self.camera.set_controls({
                "ExposureTime": new_exp,
                "AnalogueGain": new_gain,
                "Brightness": 0.2,  # Add some brightness (range is -1.0 to 1.0)
                "Contrast": 1.1,    # Slight contrast increase
                "ColourGains": (1.54, 1.15)
            })
            
            # Wait for settings to take effect
            print(f"Applying adaptive settings - Exposure: {new_exp}μs, Gain: {new_gain}")
            time.sleep(2)
            
            # Capture the image
            image = self.camera.capture_array()
            
            # Verify final brightness
            final_brightness = np.mean(image)
            print(f"Final average brightness: {final_brightness}")
            
            # Close the camera
            self.camera.stop()
            
            # Apply color correction if requested
            if apply_color_correction:
                print("Applying color correction...")
                # Convert to float for processing
                image_float = image.astype(np.float32) / 255.0
                
                # Calculate the average color of the image
                avg_color = np.mean(image_float, axis=(0, 1))
                print(f"Average color channels before correction: R={avg_color[0]:.3f}, G={avg_color[1]:.3f}, B={avg_color[2]:.3f}")
                
                # Calculate scaling factors to balance the image colors
                scale = 1 / avg_color
                scale /= np.max(scale)
                
                # Apply the scaling factors
                corrected_image = image_float * scale
                corrected_image = np.clip(corrected_image, 0, 1) * 255
                corrected_image = corrected_image.astype(np.uint8)
                
                # Verify color correction effect
                avg_color_after = np.mean(corrected_image.astype(np.float32) / 255.0, axis=(0, 1))
                print(f"Average color channels after correction: R={avg_color_after[0]:.3f}, G={avg_color_after[1]:.3f}, B={avg_color_after[2]:.3f}")
                
                image = corrected_image
                
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(hsv)

                # Calculate current average brightness
                avg_v = np.mean(v)

                # Calculate scaling factor
                if avg_v == 0:
                    scale = 1
                else:
                    scale = target_brightness / avg_v

                # Apply scaling and clip to [0, 255]
                v = np.clip(v * scale, 0, 255).astype(np.uint8)

                # Merge and convert back to BGR
                normalized_hsv = cv2.merge((h, s, v))
                
                image = cv2.cvtColor(normalized_hsv, cv2.COLOR_HSV2BGR)
                
                # Save corrected version with a different name
                corrected_filename = filename.split('.')[0] + '_corrected.' + filename.split('.')[1]
                cv2.imwrite(corrected_filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                print(f"Color-corrected image saved as {corrected_filename}")
            
            # Save the original or corrected image
            cv2.imwrite(filename, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            print(f"Image saved as {filename}")
            
            if byte_image:
                # Create BytesIO object and write image
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
        """
        Get the size of the image in bytes.
        
        Args:
            image_bytes (bytes): The image data
            
        Returns:
            int: Size of the image in bytes
        """
        return len(image_bytes) if image_bytes else 0
    
    def close(self):
        """
        Clean up camera resources.
        """
        if hasattr(self, 'camera'):
            self.camera.stop()

    def __enter__(self):
        """
        Context manager entry point.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        """
        self.close()
