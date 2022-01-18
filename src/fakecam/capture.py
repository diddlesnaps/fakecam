import os
import sys
from typing import Tuple

import cv2
import numpy as np
from multiprocessing import Queue

from .pyfakewebcam import FakeWebcam
from .types import CommandQueueDict
from .bodypix_functions import BodypixScaler, to_mask_tensor

FHD = (1080, 1920)
HD = (720, 1280)
NTSC = (480, 720)

cvNet = cv2.dnn.readNetFromTensorflow(os.path.join(os.path.dirname(__file__), 'mobileNet/8/075/2/frozen_graph.pb'))

output_stride = 16
internal_resolution = 0.5
multiplier = 0.5

models = [
    # mobileNet
    "mobileNet/8/050/1/frozen_graph.pb",
    "mobileNet/8/050/2/frozen_graph.pb",
    "mobileNet/8/050/4/frozen_graph.pb",

    "mobileNet/8/075/1/frozen_graph.pb",
    "mobileNet/8/075/2/frozen_graph.pb",
    "mobileNet/8/075/4/frozen_graph.pb",

    "mobileNet/8/100/1/frozen_graph.pb",
    "mobileNet/8/100/2/frozen_graph.pb",
    "mobileNet/8/100/4/frozen_graph.pb",

    "mobileNet/16/050/1/frozen_graph.pb",
    "mobileNet/16/050/2/frozen_graph.pb",
    "mobileNet/16/050/4/frozen_graph.pb",

    "mobileNet/16/075/1/frozen_graph.pb",
    "mobileNet/16/075/2/frozen_graph.pb",
    "mobileNet/16/075/4/frozen_graph.pb",

    "mobileNet/16/100/1/frozen_graph.pb",
    "mobileNet/16/100/2/frozen_graph.pb",
    "mobileNet/16/100/4/frozen_graph.pb",

    # resNet
    "resNet/16/100/1/frozen_graph.pb",
    "resNet/16/100/2/frozen_graph.pb",
    "resNet/16/100/4/frozen_graph.pb",

    "resNet/32/100/1/frozen_graph.pb",
    "resNet/32/100/2/frozen_graph.pb",
    "resNet/32/100/4/frozen_graph.pb",
]


def get_mask(frame, scaler, dilation, height, width):
    ratio = 640 / height
    blob = cv2.dnn.blobFromImage(frame,
                                 size=(227, 227), scalefactor=(1/255)*ratio, mean=(1.0, 1.0, 1.0),
                                 swapRB=True, crop=False)
    cvNet.setInput(blob)
    results = cvNet.forward()[0][0]

    segment_logits = cv2.UMat(results)
    segment_logits.flags.writable = False
    scaled_segment_scores = scaler.scale_and_crop_to_input_tensor_shape(
        segment_logits, True
    )
    scaled_segment_scores.flags.writable = False
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
    frame.flags.writable = False

    mask = get_mask(frame, scaler, dilation, height=height, width=width)

    if background is None:
        background = cv2.resize(frame, (int(width/8), int(height/8)))
        background = cv2.GaussianBlur(background, (7, 7), sigmaX=20, sigmaY=20)
        background = cv2.resize(background, (width, height))

    if use_hologram:
        frame.flags.writable = True
        frame = hologram_effect(frame)
        frame.flags.writable = False

    # composite the foreground and background
    mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    mask.flags.writable = False

    inv_mask = cv2.subtract(ones, mask, dtype=cv2.CV_32F)

    mask_mult = cv2.multiply(frame, mask, dtype=cv2.CV_32F)
    inv_mask_mult = cv2.multiply(background, inv_mask, dtype=cv2.CV_32F)
    mask_mult.flags.writable = False
    inv_mask_mult.flags.writable = False

    frame.flags.writable = True
    frame = cv2.add(mask_mult, inv_mask_mult)
    return frame


def start(command_queue: "Queue[CommandQueueDict]" = None, return_queue: "Queue[bool]" = None, camera: str = "/dev/video0", background: str = None,
          use_hologram: bool = False, use_mirror: bool = False, resolution: Tuple[int,int] = None, model: str = ""):

    msg = ""
    try:
        if cv2.cuda.getCudaEnabledDeviceCount() > 0 and len(cv2.dnn.getAvailableTargets(cv2.dnn.DNN_BACKEND_CUDA)) > 0:
            msg += "Using CUDA for DNN\n"
            cvNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            cvNet.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        elif len(cv2.dnn.getAvailableTargets(cv2.dnn.DNN_BACKEND_VKCOM)) > 0:
            msg += "Using Vulkan for DNN\n"
            cvNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_VKCOM)
            cvNet.setPreferableTarget(cv2.dnn.DNN_TARGET_VULKAN)
    except cv2.error:
        if cv2.ocl.haveOpenCL() and cv2.ocl_Device().type() == cv2.ocl.Device_TYPE_GPU:
            msg += "Using OpenCL for DNN\n"
            cvNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            cvNet.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)

    if cv2.ocl.haveOpenCL():
        msg += "Using OpenCL for image manipulation\n"
        cv2.ocl.setUseOpenCL(True)

    sys.stdout = sys.__stdout__
    print(msg)

    if model in models:
        cv2.dnn.readNetFromTensorflow(os.path.join(os.path.dirname(__file__), model))

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
    ones.flags.writable = False
    dilation = cv2.UMat(np.ones((10, 10), np.uint8))
    dilation.flags.writable = False

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
    greenscreen_image.flags.writable = False

    if background == "greenscreen":
        background_scaled = greenscreen_image
    elif background is not None and os.path.isfile(background) and os.access(background, os.R_OK):
        background_data = cv2.UMat(cv2.imread(background))
        background_scaled = cv2.resize(background_data, (width, height))

    background_scaled.flags.writable = False

    first_frame = True
    # frames forever
    while cap.isOpened():
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

            if data["quit"]:
                break

            background_scaled.flags.writable = True
            if data["background"] is None:
                background_scaled = None
            elif data["background"] == "greenscreen":
                background_scaled = greenscreen_image
            else:
                background = data["background"]
                background_data = cv2.UMat(cv2.imread(background))
                background_scaled = cv2.resize(background_data, (width, height))
            background_scaled.flags.writable = False

            use_hologram = data["hologram"]
            use_mirror = data["mirror"]

        if first_frame and return_queue is not None:
            first_frame = False
            return_queue.put_nowait(True)

    fake.close()
