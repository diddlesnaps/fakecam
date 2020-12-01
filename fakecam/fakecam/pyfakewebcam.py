import os
import sys
import fcntl
import timeit
import sys
import cv2
import numpy as np

import pyfakewebcam.v4l2 as _v4l2

class FakeWebcam:


    # TODO: add support for more pixfmts
    # TODO: add support for grayscale
    def __init__(self, video_device, width, height): #, channels=3, input_pixfmt='RGB'):

        # if channels != 3:
        #     raise NotImplementedError('Code only supports inputs with 3 channels right now. You tried to intialize with {} channels'.format(channels))

        # if input_pixfmt != 'RGB':
        #     raise NotImplementedError('Code only supports RGB pixfmt. You tried to intialize with {}'.format(input_pixfmt))

        if not os.path.exists(video_device):
            sys.stderr.write('\n--- Make sure the v4l2loopback kernel module is loaded ---\n')
            sys.stderr.write('sudo modprobe v4l2loopback devices=1\n\n')
            raise FileNotFoundError('device does not exist: {}'.format(video_device))

        # self._channels = channels
        self._video_device = os.open(video_device, os.O_WRONLY | os.O_SYNC)

        self._settings = _v4l2.v4l2_format()
        self._settings.type = _v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        self._settings.fmt.pix.pixelformat = _v4l2.V4L2_PIX_FMT_YUYV
        self._settings.fmt.pix.width = width
        self._settings.fmt.pix.height = height
        self._settings.fmt.pix.field = _v4l2.V4L2_FIELD_NONE
        self._settings.fmt.pix.bytesperline = width * 2
        self._settings.fmt.pix.sizeimage = width * height * 2
        self._settings.fmt.pix.colorspace = _v4l2.V4L2_COLORSPACE_JPEG

        self._buffer = np.zeros((self._settings.fmt.pix.height, 2*self._settings.fmt.pix.width), dtype=np.uint8)
        self._yuv = np.zeros((self._settings.fmt.pix.height, self._settings.fmt.pix.width, 3), dtype=np.uint8)

        if fcntl.ioctl(self._video_device, _v4l2.VIDIOC_S_FMT, self._settings) < 0:
            print("ERROR: unable to set video format!")


    def print_capabilities(self):

        capability = _v4l2.v4l2_capability()
        print(("get capabilities result", (fcntl.ioctl(self._video_device, _v4l2.VIDIOC_QUERYCAP, capability))))
        print(("capabilities", hex(capability.capabilities)))
        print(("v4l2 driver: {}".format(capability.driver)))


    # TODO: improve the conversion from RGB to YUV using cython when opencv is not available
    def schedule_frame(self, frame):

        # if frame.shape[0] != self._settings.fmt.pix.height:
        #     raise Exception('frame height does not match the height of webcam device: {}!={}\n'.format(self._settings.fmt.pix.height, frame.shape[0]))
        # if frame.shape[1] != self._settings.fmt.pix.width:
        #     raise Exception('frame width does not match the width of webcam device: {}!={}\n'.format(self._settings.fmt.pix.width, frame.shape[1]))
        # if frame.shape[2] != self._channels:
        #     raise Exception('num frame channels does not match the num channels of webcam device: {}!={}\n'.format(self._channels, frame.shape[2]))

        # t1 = timeit.default_timer()
        self._yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV).get().astype(np.uint8)
        # t2 = timeit.default_timer()
        # sys.stderr.write('conversion time: {}\n'.format(t2-t1))

        # t1 = timeit.default_timer()
        for i in range(self._settings.fmt.pix.height):
            self._buffer[i,::2] = self._yuv[i,:,0]
            self._buffer[i,1::4] = self._yuv[i,::2,1]
            self._buffer[i,3::4] = self._yuv[i,::2,2]
        # t2 = timeit.default_timer()
        # sys.stderr.write('pack time: {}\n'.format(t2-t1))

        written = os.write(self._video_device, self._buffer.tostring())
        # written = os.write(self._video_device, frame.get().astype(np.uint8).tostring())
        if written < 0:
            print("ERROR: could not write to output device!")
            os.close(self._video_device)
            sys.exit(1)