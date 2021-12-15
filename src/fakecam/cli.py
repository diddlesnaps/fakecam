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
    camera_input = "/dev/video0"
    camera_output = "/dev/video20"
    resolution = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:r:b:mg", ["input=", "output=", "resolution=", "background=", "mirror", "hologram"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt in ("-i", "--input"):
            camera_input = arg
        elif opt in ("-o", "--output"):
            camera_output = arg
        elif opt in ("-r", "--resolution"):
            res = str.split(arg, 'x', 2)
            resolution = (int(res[0]), int(res[1]))
        elif opt in ("-b", "--background"):
            background = arg
        elif opt in ("-m", "--mirror"):
            use_mirror = True
        elif opt in ("-g", "--hologram"):
            use_hologram = True

    if not os.access(camera_input, os.R_OK):
        print(lang.CONNECT_INTERFACE + "\n\nIf you have multiple camera devices in /dev/video* then you may specify "
                                       "the correct device with the '-i' or '--input' parameter.\n")

    if not os.access(camera_output, os.W_OK):
        print(lang.INSTRUCTIONS)
        sys.exit(3)

    if use_hologram:
        print(lang.USING_HOLOGRAM)

    if background is not None:
        background = os.path.expanduser(background)
        if background == "greenscreen":
            print(lang.USING_GREENSCREEN)
        elif os.path.isfile(background) and os.access(background, os.R_OK):
            print(lang.USING_BACKGROUND_IMAGE.format(background=background))
        else:
            print(lang.BACKGROUND_UNREADABLE)
            background = None
    else:
        print(lang.USING_BACKGROUND_BLUR)
        background = None

    args = {
        "camera_input": camera_input,
        "camera_output": camera_output,
        "background": background,
        "use_hologram": use_hologram,
        "use_mirror": use_mirror,
        "resolution": resolution,
    }
    p = multiprocessing.Process(target=capture.start, kwargs=args)
    try:
        p.start()
        p.join()
    except KeyboardInterrupt:
        p.terminate()
        p.join()
