"""
Camera module for capturing images
Works with USB webcams or Raspberry Pi camera module
"""

import cv2
import base64
from io import BytesIO
from PIL import Image


class CameraCapture:
    """Handles camera input and image capture"""

    def __init__(self, camera_index=0):
        """Initialize camera"""
        self.camera_index = camera_index
        self.camera = None
        self.initialize_camera()

    def initialize_camera(self):
        """Set up the camera"""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise Exception(f"Could not open camera {self.camera_index}")
            print(f"Camera {self.camera_index} initialized successfully")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            print("Make sure a camera is connected")

    def capture_frame(self):
        """Capture a single frame from the camera"""
        if self.camera is None or not self.camera.isOpened():
            print("Camera not available")
            return None

        ret, frame = self.camera.read()
        if not ret:
            print("Failed to capture frame")
            return None

        return frame

    def capture_image_base64(self):
        """Capture an image and return it as base64 for API calls"""
        frame = self.capture_frame()
        if frame is None:
            return None

        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        image = Image.fromarray(frame_rgb)

        # Resize if too large (to save API costs)
        max_size = 1024
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert to base64
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return img_base64

    def save_image(self, filename):
        """Save current frame to a file"""
        frame = self.capture_frame()
        if frame is not None:
            cv2.imwrite(filename, frame)
            print(f"Image saved to {filename}")
            return True
        return False

    def release(self):
        """Release the camera"""
        if self.camera is not None:
            self.camera.release()
            print("Camera released")


# Test the camera module
if __name__ == "__main__":
    print("Testing camera...")
    cam = CameraCapture()
    cam.save_image("test_capture.jpg")
    cam.release()
