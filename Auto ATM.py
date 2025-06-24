import easyocr
import pyautogui
import numpy as np
import cv2
import keyboard
import threading
import ctypes
import time
import os
from mss import mss

# Initialize EasyOCR
reader = easyocr.Reader(['en'], gpu=False)

# Base resolution (from 1440p system)
BASE_WIDTH = 2560
BASE_HEIGHT = 1440

# Current screen resolution
screen_width, screen_height = pyautogui.size()
x_scale = screen_width / BASE_WIDTH
y_scale = screen_height / BASE_HEIGHT

# Auto-scale helper
def scale(x, y, w=0, h=0):
    return (int(x * x_scale), int(y * y_scale), int(w * x_scale), int(h * y_scale))

# Scaled Regions
reference_region = scale(1330, 488, 107, 64)
detection_region = scale(950, 583, 656, 325)

PIXEL_OFFSETS = [int(p * x_scale) for p in [45, 50, 60]]
TOLERANCE = 30
CONFIDENCE_THRESHOLD = 0.80

running = False
reference_text = ""
matched_text_center = None
click_count = 0
MAX_CLICKS = 5

def click(x, y):
    ctypes.windll.user32.SetCursorPos(x, y)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    print(f"Clicked at ({x}, {y})")

normalize_map = {
    'o': '0', 'O': '0', 'D': '0',
    'i': '1', 'I': '1', 'l': '1', '|': '1',
    'A': '4',
    's': '5', 'S': '5',
    'B': '8',
    'Z': '2', 'z': '2',
    'g': '9', 'q': '9',
    'G': '6',
    'E': '3'
}

def normalize(text):
    return ''.join(normalize_map.get(char, char) for char in text if char.isalnum())

def extract_reference_text(region):
    with mss() as sct:
        monitor = {'left': region[0], 'top': region[1], 'width': region[2], 'height': region[3]}
        img = np.array(sct.grab(monitor))[:, :, :3]
    results = reader.readtext(img)

    best_conf = 0.0
    best_text = ""

    for bbox, text, conf in results:
        raw_text = text.strip()
        if not raw_text or len(raw_text) > 3:
            continue
        if conf >= CONFIDENCE_THRESHOLD:
            norm_text = normalize(raw_text.upper())
            if norm_text:
                print(f"[Reference Area] Found (≥{CONFIDENCE_THRESHOLD:.2f}): '{norm_text}' (raw: '{raw_text}', conf: {conf:.4f})")
                return norm_text

        if conf > best_conf:
            best_conf = conf
            best_text = raw_text

    if best_text:
        norm_text = normalize(best_text.upper())
        print(f"[Reference Area] Fallback to best confidence '{norm_text}' (raw: '{best_text}', conf: {best_conf:.4f})")
        return norm_text

    print("No valid reference text found.")
    return ""

def is_black_or_gray(pixel):
    r, g, b = pixel
    return abs(r - g) <= TOLERANCE and abs(g - b) <= TOLERANCE and r <= 100

def check_pixels_around(img_rgb, center):
    if center is None:
        return False
    x_center, y_center = center
    h, w, _ = img_rgb.shape

    for offset in PIXEL_OFFSETS:
        for dx in [-offset, offset]:
            check_x = x_center + dx
            check_y = y_center
            if 0 <= check_x < w and 0 <= check_y < h:
                pixel = img_rgb[check_y, check_x]
                if not is_black_or_gray(pixel):
                    print(f"Pixel at ({check_x}, {check_y}) is NOT black/gray: {pixel}")
                    return True
    return False

def scan_for_match():
    global matched_text_center, reference_text
    with mss() as sct:
        monitor = {'left': detection_region[0], 'top': detection_region[1], 'width': detection_region[2], 'height': detection_region[3]}
        img = np.array(sct.grab(monitor))[:, :, :3]
    results = reader.readtext(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))

    for bbox, text, conf in results:
        raw_text = text.strip()
        if not raw_text or len(raw_text) > 3 or conf < CONFIDENCE_THRESHOLD:
            continue
        norm_text = normalize(raw_text.upper())
        print(f"[Detection Area] Found: '{norm_text}' (raw: '{raw_text}', conf: {conf:.4f})")
        if norm_text == reference_text:
            x_center = int(np.mean([pt[0] for pt in bbox]))
            y_center = int(np.mean([pt[1] for pt in bbox]))
            matched_text_center = (x_center, y_center)
            print(f"Matched text center at pixel coordinates: {matched_text_center}")
            return True
    matched_text_center = None
    return False

def worker():
    global running, reference_text, matched_text_center, click_count
    print("Detection thread started.")
    scanning = True

    while running:
        current_reference = extract_reference_text(reference_region)
        if current_reference != reference_text:
            print(f"Reference text changed from '{reference_text}' to '{current_reference}'")
            reference_text = current_reference
            matched_text_center = None
            scanning = True

        if not reference_text:
            print("No reference text currently found. Waiting and retrying...")
            time.sleep(1)
            continue

        if scanning:
            found = scan_for_match()
            if found:
                scanning = False
            else:
                time.sleep(0.01)
        else:
            with mss() as sct:
                monitor = {'left': detection_region[0], 'top': detection_region[1], 'width': detection_region[2], 'height': detection_region[3]}
                img = np.array(sct.grab(monitor))[:, :, :3]

            if matched_text_center and check_pixels_around(img, matched_text_center):
                screen_x = detection_region[0] + matched_text_center[0]
                screen_y = detection_region[1] + matched_text_center[1]
                click(screen_x, screen_y)
                click_count += 1
                if click_count >= MAX_CLICKS:
                    print(f"Reached max clicks ({MAX_CLICKS}). Turning script OFF.")
                    running = False
                    return
                matched_text_center = None
                scanning = True
            else:
                time.sleep(0.0001)

def toggle():
    global running, reference_text, matched_text_center, click_count
    running = not running
    if running:
        print("Script ON")
        reference_text = extract_reference_text(reference_region)
        if not reference_text:
            print("No reference text detected initially; will retry.")
        matched_text_center = None
        click_count = 0
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
    else:
        print("Script OFF")

if __name__ == "__main__":
    print("Press F6 to toggle script ON/OFF.")
    keyboard.add_hotkey('f6', toggle)
    keyboard.wait()
