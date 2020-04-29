import cv2
import numpy as np
import os
import pyfakewebcam
import requests
import signal
import subprocess
from multiprocessing import Process


def get_mask(frame, bodypix_url='http://localhost:13165'):
    _, data = cv2.imencode(".jpg", frame)
    r = requests.post(
        url=bodypix_url,
        data=data.tobytes(),
        headers={'Content-Type': 'application/octet-stream'})
    mask = np.frombuffer(r.content, dtype=np.uint8)
    mask = mask.reshape((frame.shape[0], frame.shape[1]))
    return mask

def post_process_mask(mask):
    mask = cv2.dilate(mask, np.ones((10,10), np.uint8) , iterations=1)
    mask = cv2.blur(mask.astype(np.float32), (30,30))
    return mask

def shift_image(img, dx, dy):
    img = np.roll(img, dy, axis=0)
    img = np.roll(img, dx, axis=1)
    if dy>0:
        img[:dy, :] = 0
    elif dy<0:
        img[dy:, :] = 0
    if dx>0:
        img[:, :dx] = 0
    elif dx<0:
        img[:, dx:] = 0
    return img

def hologram_effect(img):
    # add a blue tint
    holo = cv2.applyColorMap(img, cv2.COLORMAP_WINTER)
    # add a halftone effect
    bandLength, bandGap = 2, 3
    for y in range(holo.shape[0]):
        if y % (bandLength+bandGap) < bandLength:
            holo[y,:,:] = holo[y,:,:] * np.random.uniform(0.1, 0.3)
    # add some ghosting
    holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)
    # combine with the original color, oversaturated
    out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    return out

def get_frame(cap, background=None, useHologram=False):
    _ret_, frame = cap.read()
    # fetch the mask with retries (the app needs to warmup and we're lazy)
    # e v e n t u a l l y c o n s i s t e n t
    mask = None
    while mask is None:
        try:
            mask = get_mask(frame)
        except:
            print("mask request failed, retrying")
    # post-process mask and frame
    mask = post_process_mask(mask)

    if (background is None):
        background = cv2.GaussianBlur(frame, (221, 221), sigmaX=20, sigmaY=20)

    if useHologram:
        frame = hologram_effect(frame)

    # composite the foreground and background
    inv_mask = 1-mask
    for c in range(frame.shape[2]):
        frame[:,:,c] = frame[:,:,c]*mask + background[:,:,c]*inv_mask
    return frame

def start(background=None, useHologram=False):
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # setup access to the *real* webcam
    cap = cv2.VideoCapture('/dev/video0')
    height, width = 720, 1280
    cap.set(3,width)
    cap.set(4,height)
    cap.set(cv2.CAP_PROP_FPS, 60)

    # setup the fake camera
    fake = pyfakewebcam.FakeWebcam('/dev/video20', width, height)

    # load the virtual background
    background_scaled = None
    if (background is not None):
        background_data = cv2.imread(background)
        background_scaled = cv2.resize(background_data, (width, height))

    # frames forever
    while True:
        frame = get_frame(cap, background=background_scaled, useHologram=useHologram)
        # fake webcam expects RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)

def start_bodypix():
    subprocess.run(['node', os.path.join(os.environ['SNAP'], 'app.js')])
