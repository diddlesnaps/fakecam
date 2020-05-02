import getopt
import multiprocessing
import os
import sys

from . import capture
from . import lang


def usage():
    print(lang.USAGE)


def main():
    background = None
    use_hologram = False
    use_mirror = False
    camera = "/dev/video0"
    resolution = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:r:b:mg", ["input=", "resolution=", "background=", "mirror", "hologram"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt in ("-i", "--input"):
            camera = arg
        elif opt in ("-r", "--resolution"):
            res = str.split(arg, 'x', 2)
            resolution = (int(res[0]), int(res[1]))
        elif opt in ("-b", "--background"):
            background = arg
        elif opt in ("-m", "--mirror"):
            use_mirror = True
        elif opt in ("-g", "--hologram"):
            use_hologram = True

    if not os.access(camera, os.R_OK):
        print(lang.CONNECT_INTERFACE + "\n\nIf you have multiple camera devices in /dev/video* then you may specify "
                                       "the correct device with the '-i' or '--input' parameter.")

    if not os.access("/dev/video20", os.W_OK):
        print(lang.INSTRUCTIONS)
        sys.exit(3)

    if use_hologram:
        print(lang.USING_HOLOGRAM)

    if background is not None and background != "" and os.path.isfile(background):
        print(lang.USING_BACKGROUND_IMAGE.format(background=background))
    else:
        print(lang.USING_BACKGROUND_BLUR)
        background = None

    args = {
        background: background,
        use_hologram: use_hologram,
        use_mirror: use_mirror,
        resolution: resolution
    }
    p = multiprocessing.Process(target=capture.start, kwargs=args)
    p2 = multiprocessing.Process(target=capture.start_bodypix)
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
