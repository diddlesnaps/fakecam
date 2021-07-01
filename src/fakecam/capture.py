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

mlmodel = os.path.join(os.path.dirname(__file__), 'frozen_graph.pb')
cvNet = cv2.dnn.readNetFromTensorflow(mlmodel)

output_stride = 16
internal_resolution = 0.5
multiplier = 0.5

pkgs = [
    ('ocl'    , cv2.gapi.core.ocl.kernels()),
    ('cpu'    , cv2.gapi.core.cpu.kernels()),
]

def get_pipeline(background=None, use_hologram=False, mirror=False):
    g_in   = cv2.GMat()
    inputs = cv2.GInferInputs()
    inputs.setInput('data', g_in)

    ml_out   = cv2.gapi.infer("net", inputs)
    segments = ml_out.at("float_segments")

    unscaled = cv2.gapi.resize(segments, g_in.size())

    ## <sigmoid activation>
    sig_sub = cv2.gapi.subRC(0, unscaled)
    sig_exp = cv2.gapi.exp(sig_sub, sig_sub)
    gid_add = cv2.gapi.addC(1, sig_exp)
    sigmoid = cv2.gapi.divRC(1, gid_add)
    ## </sigmoid activation>

    thresh   = cv2.gapi.threshold(sigmoid, 0.75, 1, cv2.THRESH_BINARY)

    dilate = cv2.gapi.dilate(thresh, cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10)), iterations=1)
    mask   = cv2.gapi.blur(dilate, (30, 30))

    ## <background>
    if background is None:
        small_bg = cv2.gapi.resize(g_in, 0, fx=1/8, fy=1/8)
        blur_bg  = cv2.gapi.gaussianBlur(small_bg, (7, 7))
        bg_in    = cv2.gapi.resize(blur_bg, g_in.size())
    else:
        bg_in = cv2.GMat()
    ## </background>

    ## <hologram>
    # add a blue tint
    # holo = cv2.applyColorMap(img.get(), cv2.COLORMAP_WINTER)
    # # add a halftone effect
    # band_length, band_gap = 2, 3
    # for y in range(holo.shape[0]):
    #     if y % (band_length + band_gap) < band_length:
    #         holo[y, :, :] = holo[y, :, :] * np.random.uniform(0.1, 0.3)
    # # add some ghosting
    # holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    # holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)
    # # combine with the original color, oversaturated
    # out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    ## </hologram>

    inv_mask     = cv2.gapi.subRC(1, mask)
    frame_masked = cv2.gapi.mulC(g_in, mask)
    bg_masked    = cv2.gapi.mul(bg_in, inv_mask)

    frame = cv2.gapi.add(frame_masked, bg_masked)

    if mirror is True:
        return cv2.GComputation(cv2.GIn(g_in), cv2.GOut(cv2.gapi.flip(frame)))

    return cv2.GComputation(cv2.GIn(g_in), cv2.GOut(frame))


def start(command_queue: "Queue[CommandQueueDict]" = None, return_queue: "Queue[bool]" = None, camera: str = "/dev/video0", background: str = None,
          use_hologram: bool = False, use_mirror: bool = False, resolution: Tuple[int,int] = None):
    sys.stdout = sys.__stdout__

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

    pipeline = get_pipeline(background=background_scaled, use_hologram=use_hologram)

    # frames forever
    while True:
        frame = cap.grab()
        if frame is None:
            print("ERROR: could not read from camera!")
            break

        if background_scaled is not None:
            fake.schedule_frame(pipeline.apply(cv2.gin(cap.retrieve()[1], background_scaled)))
        else:
            fake.schedule_frame(pipeline.apply(cv2.gin(cap.retrieve()[1])))

        if command_queue is not None and not command_queue.empty():
            data = command_queue.get(False)

            if data["quit"]:
                break
            elif data["background"] is None:
                background_scaled = None
            elif data["background"] == "greenscreen":
                background_scaled = greenscreen_image
            else:
                background = data["background"]
                background_data = cv2.UMat(cv2.imread(background))
                background_scaled = cv2.resize(background_data, (width, height))

            use_hologram = data["hologram"]
            use_mirror = data["mirror"]

            pipeline = get_pipeline()

        if first_frame and return_queue is not None:
            first_frame = False
            return_queue.put_nowait(True)

    fake.close()
