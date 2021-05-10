import os
import sys
import fcntl
import sys
import cv2
import numpy as np

import pyfakewebcam.v4l2 as _v4l2

class FakeWebcam:


    def __init__(self, video_device, width, height):

        if not os.path.exists(video_device):
            sys.stderr.write('\n--- Make sure the v4l2loopback kernel module is loaded ---\n')
            sys.stderr.write('sudo modprobe v4l2loopback devices=1\n\n')
            raise FileNotFoundError('device does not exist: {}'.format(video_device))

        self._video_device = os.open(video_device, os.O_WRONLY | os.O_SYNC)

        self._settings = _v4l2.v4l2_format()
        self._settings.type = _v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        self._settings.fmt.pix.width = width
        self._settings.fmt.pix.height = height
        self._settings.fmt.pix.field = _v4l2.V4L2_FIELD_NONE

        # JPEG
        self._settings.fmt.pix.colorspace = _v4l2.V4L2_COLORSPACE_JPEG
        self._settings.fmt.pix.pixelformat = _v4l2.V4L2_PIX_FMT_MJPEG

        if fcntl.ioctl(self._video_device, _v4l2.VIDIOC_S_FMT, self._settings) < 0:
            print("ERROR: unable to set video format!")


    def print_capabilities(self):

        capability = _v4l2.v4l2_capability()
        print(("get capabilities result", (fcntl.ioctl(self._video_device, _v4l2.VIDIOC_QUERYCAP, capability))))
        print(("capabilities", hex(capability.capabilities)))
        print(("v4l2 driver: {}".format(capability.driver)))


    def schedule_frame(self, frame):

        rv, buf = cv2.imencode('.jpg', frame)
        if not rv:
            print("ERROR: could not encode M-JPEG")
            return
        written = os.write(self._video_device, buf)

        if written < 0:
            print("ERROR: could not write to output device!")
            os.close(self._video_device)
            sys.exit(1)
