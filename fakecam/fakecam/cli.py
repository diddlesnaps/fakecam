import getopt
import os
import sys
from multiprocessing import Process

from fakecam.capture import start, start_bodypix


def usage():
    print("""
USAGE:
  fakecam [--input=<camera-device>] [--resolution=<width>x<height>] [--background=<background-file>] [--hologram]

PARAMETERS:
  --input:      specify the camera device to use. The default is /dev/video0.
  --resolution: override your camera's default resolution. Must be width and height as numbers separated by an 'x', e.g. '640x480'. May not work reliably.
  --background: replace your camera background with an image. The default is to
                blur your existing background that your camera sees.
  --hologram:   overlay a Star Wars style hologram effect onto your likeness.
""")


def main():
    background = None
    use_hologram = False
    camera = "/dev/video0"
    resolution = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:r:b:m", ["input=", "resolution=", "background=", "hologram"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt in ("-i", "--input"):
            camera = arg
        elif opt in ("-r", "--resolution"):
            res = str.split(arg, 'x', 2)
            resolution = (int(res[0]), int(res[1]))
        elif opt in ("-b", "--background"):
            background = arg
        elif opt in ("-m", "--hologram"):
            use_hologram = True

    if not os.access(camera, os.R_OK):
        print("""
Your camera is not accessible. You need to manually run the following:
    snap connect fakecam:camera
    
If you have multiple camera devices in /dev/video* then you may specify the
correct device with the '-i' or '--input' parameter.
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

    if use_hologram:
        print("Using the hologram effect")

    if background is not None and background != '' and os.path.isfile(background):
        print("Using background image {}".format(background))
    else:
        print("No background specified, will blur your background instead")
        background = None

    p = Process(target=start, kwargs=dict(background=background, use_hologram=use_hologram, resolution=resolution))
    p2 = Process(target=start_bodypix)
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
