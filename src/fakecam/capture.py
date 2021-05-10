import os
from typing import Tuple

import sys
import cv2
import numpy as np
from multiprocessing import Queue

from .pyfakewebcam import FakeWebcam
from .types import CommandQueueDict
from .bodypix_functions import BodypixScaler, to_mask_tensor

FHD = (1080, 1920)
HD = (720, 1280)
NTSC = (480, 720)


cvNet = cv2.dnn.readNetFromTensorflow(os.path.join(os.path.dirname(__file__), 'frozen_graph.pb'))


output_stride = 16
internal_resolution = 0.5
multiplier = 0.5


def get_mask(frame, scaler, dilation, height, width):
    ratio = 640 / height
    blob = cv2.dnn.blobFromImage(frame,
                                 size=(227, 227), scalefactor=(1/255)*ratio, mean=(1.0, 1.0, 1.0),
                                 swapRB=True, crop=False)
    cvNet.setInput(blob)
    results = cvNet.forward()[0][0]

    segment_logits = cv2.UMat(results)
    scaled_segment_scores = scaler.scale_and_crop_to_input_tensor_shape(
        segment_logits, True
    )
    mask = to_mask_tensor(scaled_segment_scores, 0.75)
    mask = cv2.dilate(mask, dilation, iterations=1)
    mask = cv2.blur(mask, (30, 30))
    return mask


def shift_image(img, dx, dy):
    img = np.roll(img, dy, axis=0)
    img = np.roll(img, dx, axis=1)
    if dy > 0:
        img[:dy, :] = 0
    elif dy < 0:
        img[dy:, :] = 0
    if dx > 0:
        img[:, :dx] = 0
    elif dx < 0:
        img[:, dx:] = 0
    return img


def hologram_effect(img):
    # add a blue tint
    holo = cv2.applyColorMap(img.get(), cv2.COLORMAP_WINTER)
    # add a halftone effect
    band_length, band_gap = 2, 3
    for y in range(holo.shape[0]):
        if y % (band_length + band_gap) < band_length:
            holo[y, :, :] = holo[y, :, :] * np.random.uniform(0.1, 0.3)
    # add some ghosting
    holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)
    # combine with the original color, oversaturated
    out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    return out


def get_frame(cap: object, scaler: BodypixScaler, ones, dilation, background: object = None, use_hologram: bool = False, height=0, width=0) -> object:
    if not cap.grab():
        print("ERROR: could not read from camera!")
        return None

    frame = cv2.UMat(cap.retrieve()[1])
    mask = get_mask(frame, scaler, dilation, height=height, width=width)

    if background is None:
        background = cv2.GaussianBlur(frame, (61, 61), sigmaX=20, sigmaY=20)

    if use_hologram:
        frame = hologram_effect(frame)

    # composite the foreground and background
    mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    inv_mask = cv2.subtract(ones, mask, dtype=cv2.CV_32F)

    mask_mult = cv2.multiply(frame, mask, dtype=cv2.CV_32F)
    inv_mask_mult = cv2.multiply(background, inv_mask, dtype=cv2.CV_32F)

    frame = cv2.add(mask_mult, inv_mask_mult)
    return frame


def start(command_queue: "Queue[CommandQueueDict]" = None, return_queue: "Queue[bool]" = None, camera: str = "/dev/video0", background: str = None,
          use_hologram: bool = False, use_mirror: bool = False, resolution: Tuple[int,int] = None):
    sys.stdout = sys.__stdout__

    if cv2.cuda.getCudaEnabledDeviceCount() > 0 and len(cv2.dnn.getAvailableTargets(cv2.dnn.DNN_BACKEND_CUDA)) > 0:
        print("Using CUDA for DNN")
        cvNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        cvNet.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    elif len(cv2.dnn.getAvailableTargets(cv2.dnn.DNN_BACKEND_VKCOM)) > 0:
        print("Using Vulkan for DNN")
        cv2.dnn.setPreferableBackend(cv2.dnn.DNN_BACKEND_VKCOM)
        cv2.dnn.setPreferableTarget(cv2.dnn.DNN_TARGET_VULKAN)
    elif cv2.ocl.haveOpenCL():
        print("Using OpenCL for DNN")
        cvNet.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)


    # setup access to the *real* webcam
    print("Starting capture using device: {camera}".format(camera=camera))
    cap = cv2.VideoCapture(camera, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("Failed to open {camera}".format(camera=camera))
        return

    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if resolution is not None:
        # resolution is supplied by user in width followed by height order
        (w, h) = resolution
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    else:
        width, height = orig_width, orig_height

    print("Resolution: {width}:{height}".format(width=width,height=height))

    scaler = BodypixScaler(width, height)
    ones = cv2.UMat(np.ones((height, width, 3)))
    dilation = cv2.UMat(np.ones((10, 10), np.uint8))

    # for (height, width) in [FHD, HD, NTSC, (orig_height, orig_width)]:
    #     # Attempt to set the camera resolution via brute force
    #     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    #     cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    #     if cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == height:
    #         break

    # setup the fake camera
    fake = FakeWebcam("/dev/video20", width, height)

    # load the virtual background
    background_scaled = None
    greenscreen_array = np.zeros((height, width, 3), np.uint8)
    greenscreen_array[:] = (0, 177, 64)
    greenscreen_image = cv2.UMat(greenscreen_array)
    if background == "greenscreen":
        background_scaled = greenscreen_image
    elif background is not None and os.path.isfile(background) and os.access(background, os.R_OK):
        background_data = cv2.UMat(cv2.imread(background))
        background_scaled = cv2.resize(background_data, (width, height))

    first_frame = True
    # frames forever
    while True:
        frame = get_frame(cap, scaler, ones, dilation, background=background_scaled, use_hologram=use_hologram, height=height, width=width)
        if frame is None:
            print("ERROR: could not read from camera!")
            break

        if use_mirror is True:
            frame = cv2.flip(frame, 1)
        # fake webcam expects RGB
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)
        if command_queue is not None and not command_queue.empty():
            data = command_queue.get(False)

            if data["background"] is None:
                background_scaled = None
            elif data["background"] == "greenscreen":
                background_scaled = greenscreen_image
            else:
                background = data["background"]
                background_data = cv2.UMat(cv2.imread(background))
                background_scaled = cv2.resize(background_data, (width, height))

            use_hologram = data["hologram"]
            use_mirror = data["mirror"]

        if first_frame and return_queue is not None:
            first_frame = False
            return_queue.put(True)
