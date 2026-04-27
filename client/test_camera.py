import cv2

print("Testing camera...")
cam = cv2.VideoCapture(0)

if cam.isOpened():
    ret, frame = cam.read()
    if ret:
        print("SUCCESS: Camera is working!")
        print(f"Image size: {frame.shape}")
    else:
        print("FAILED: Could not read from camera")
else:
    print("FAILED: Could not open camera")

cam.release()
