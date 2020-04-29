import os
import sys
import getopt
import signal
from multiprocessing import Process

import fakecam.capture as capture


def main():
    if not os.access('/dev/video0', os.R_OK):
        print("""
Your camera is not accessible. You need to manually run the following:
    snap connect fakecam:camera
""")

    if not os.access('/dev/video20', os.W_OK):
        print("""
The fake cemera device is not accessible. Make sure you have installed and
activated v4l2loopback-dkms. The module must be configured with the following
options:
    devices=1 video_nr=20 card_label="fakecam" exclusive_caps=1

To do this now and get going straight away run:
    modprobe -r v4l2loopback && modprobe v4l2loopback devices=1 \\
        video_nr=20 card_label="fakecam" exclusive_caps=1

This can be achieved by editing /etc/modprobe.d/fakecam.conf or
/etc/modprobe.conf to add the following line:

options v4l2loopback devices=1 video_nr=20 card_label="fakecam" exclusive_caps=1

Once the configuration is set it will persist across reboots. If you haven't
run the modprobe commands above then you should now run:
    modprobe -r v4l2loopback && modprobe v4l2loopback
""")
        sys.exit(3)

    background = None
    useHologram = False

    try:
        opts, args = getopt.getopt(sys.argv[1:],"hb:m",["background=","hologram"])
    except getopt.GetoptError:
        print('fakecam [--background <backgroundfile>] [--hologram]')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print('fakecam [--background=<backgroundfile>] [--hologram]')
            sys.exit()
        elif opt in ("-b", "--background"):
            background = arg
        elif opt in ("-m", "--hologram"):
            useHologram = True

    if (useHologram):
        print("Using the hologram effect")

    if (background is not None and background != '' and os.path.isfile(background)):
        print("Using background image {}".format(background))
    else:
        print("No background specified, will blur your background instead")
        background = None

    p = Process(target=capture.start, kwargs={'background': background, 'useHologram': useHologram})
    p2 = Process(target=capture.start_bodypix)
    try:
        p2.start()
        p.start()
        p.join()
        p2.join()
    except KeyboardInterrupt:
        p.terminate()
        p.join()
        p2.terminate()
        p2.join()
