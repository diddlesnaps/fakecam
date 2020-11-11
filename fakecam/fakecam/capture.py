import os
import signal

import cv2
import numpy as np
from multiprocessing import Queue

from .pyfakewebcam import FakeWebcam
from .types import QueueDict
from .bodypix_functions import scale_and_crop_to_input_tensor_shape, to_mask_tensor

FHD = (1080, 1920)
HD = (720, 1280)
NTSC = (480, 720)


# if cv2.ocl.haveOpenCL():
#     cv2.ocl.setUseOpenCL(True)

cvNet = cv2.dnn.readNetFromTensorflow(os.path.join(os.path.dirname(__file__), 'model.pb'))

output_stride = 16
internal_resolution = 0.5
multiplier = 0.5


def get_mask(frame, height, width):
    blob = cv2.dnn.blobFromImage(frame,
                                 size=(width, height), scalefactor=1/255, mean=(1.0, 1.0, 1.0),
                                 swapRB=True, crop=False)
    cvNet.setInput(blob)
    results = np.squeeze(cvNet.forward("float_segments/conv"))

    segment_logits = cv2.UMat(results)
    scaled_segment_scores = scale_and_crop_to_input_tensor_shape(
        segment_logits, height, width, True
    )
    mask = to_mask_tensor(scaled_segment_scores, 0.75)
    return mask


def post_process_mask(mask):
    mask = cv2.dilate(mask, np.ones((10, 10), np.uint8), iterations=1)
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


isOddFrame = True
lastMask = None
def get_frame(cap: object, background: object = None, use_hologram: bool = False, height=0, width=0) -> object:
    global isOddFrame, lastMask

    _, frame = cap.read()
    # fetch the mask with retries (the app needs to warmup and we're lazy)
    # e v e n t u a l l y c o n s i s t e n t
    if isOddFrame:
        isOddFrame = False
        frame = cv2.UMat(frame)
        mask = None
        while mask is None:
            try:
                mask = get_mask(frame, height=height, width=width)
            except:
                pass

        # post-process mask and frame
        mask = post_process_mask(mask)

        if background is None:
            background = cv2.GaussianBlur(frame, (221, 221), sigmaX=20, sigmaY=20)

        if use_hologram:
            frame = hologram_effect(frame)

        # composite the foreground and background
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        lastMask = mask
    else:
        isOddFrame = True
        mask = lastMask

    ones = np.ones((height, width, 3))
    inv_mask = cv2.subtract(ones, mask, dtype=cv2.CV_32F)

    mask_mult = cv2.multiply(frame, mask, dtype=cv2.CV_32F)
    inv_mask_mult = cv2.multiply(background, inv_mask, dtype=cv2.CV_32F)

    frame = cv2.add(mask_mult, inv_mask_mult)
    return frame


def start(queue: "Queue[QueueDict]" = None, camera: str = "/dev/video0", background: str = None,
          use_hologram: bool = False, use_mirror: bool = False, resolution: str = None):
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
        width, height = resolution[0], resolution[1]
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    else:
        width, height = orig_width, orig_height

    print("Resolution: {width}:{height}".format(width=width,height=height))

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

    # frames forever
    while True:
        frame = get_frame(cap, background=background_scaled, use_hologram=use_hologram, height=height, width=width)
        if use_mirror is True:
            frame = cv2.flip(frame, 1)
        # fake webcam expects RGB
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)
        if queue is not None and not queue.empty():
            data = queue.get(False)

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
