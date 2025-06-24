import pyautogui
import ctypes
import time
import threading
import keyboard
import os
from mss import mss
import numpy as np

# Base resolution from 1440p system
BASE_WIDTH = 2560
BASE_HEIGHT = 1440

# Current screen resolution
screen_width, screen_height = pyautogui.size()
x_scale = screen_width / BASE_WIDTH
y_scale = screen_height / BASE_HEIGHT

def scale_point(x, y):
    return (int(x * x_scale), int(y * y_scale))

def click(x, y):
    ctypes.windll.user32.SetCursorPos(x, y)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    print(f"Clicked at ({x}, {y})")

base_gray_colors = [
    (156, 156, 156), (147, 147, 148), (164, 164, 163), (139, 140, 139),
    (132, 132, 132), (148, 147, 140), (160, 160, 144), (144, 160, 164)
]

TOLERANCE = 15

def color_in_range(pixel, base_colors, tolerance):
    for base in base_colors:
        if all(abs(p - b) <= tolerance for p, b in zip(pixel, base)):
            return True
    return False

original_point_pairs = [
    [(1066, 716), (1066, 698)],
    [(1155, 698), (1151, 715)],
    [(1238, 698), (1238, 715)],
    [(1318, 715), (1318, 698)],
    [(1408, 715), (1408, 698)],
    [(1496, 712), (1496, 701)]
]

point_pairs = [(scale_point(*a), scale_point(*b)) for a, b in original_point_pairs]

running = False

def worker():
    global running
    idx = 0
    with mss() as sct:
        while running:
            if idx >= len(point_pairs):
                print("Completed all pairs. Stopping and toggling off.")
                running = False
                return
            pair = point_pairs[idx]
            mon = {'top': 0, 'left': 0, 'width': screen_width, 'height': screen_height}
            img = np.array(sct.grab(mon))[:, :, :3]
            color1 = img[pair[0][1], pair[0][0]]
            color2 = img[pair[1][1], pair[1][0]]

            if color_in_range(color1, base_gray_colors, TOLERANCE) and color_in_range(color2, base_gray_colors, TOLERANCE):
                print(f"Detected gray colors at pair {idx+1}: {pair[0]}={color1}, {pair[1]}={color2}")
                print(f"Clicking at {pair[0]} for pair {idx+1}")
                click(*pair[0])
                idx += 1
                time.sleep(0.2)
            else:
                time.sleep(0.0001)

def toggle():
    global running
    running = not running
    if running:
        print("Script started")
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
    else:
        print("Script stopped")

if __name__ == "__main__":
    print("Press F6 to toggle the script ON/OFF.")
    keyboard.add_hotkey('f6', toggle)
    keyboard.wait()
