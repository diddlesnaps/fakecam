import getopt
import multiprocessing
from multiprocessing.queues import Queue
import os
import sys

from . import capture
from . import lang
from .types import CommandQueueDict


def usage():
    print(lang.USAGE)


def main():
    background = None
    use_hologram = False
    use_mirror = False
    camera = "/dev/video0"
    resolution = None
    model = ""

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:r:b:mg", ["input=", "resolution=", "background=", "mirror", "hologram", "model="])
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
        elif opt in ("--model"):
            model = arg

    if not os.access(camera, os.R_OK):
        print(lang.CONNECT_INTERFACE + "\n\nIf you have multiple camera devices in /dev/video* then you may specify "
                                       "the correct device with the '-i' or '--input' parameter.\n")

    if not os.access("/dev/video20", os.W_OK):
        print(lang.INSTRUCTIONS)
        sys.exit(3)

    if not model in capture.models:
        print("The selected model is not available. Please choose one from the following list:\n")
        for m in capture.models:
            print("    {m}".format(m=m))
        sys.exit(4)

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

    command_queue: "Queue[CommandQueueDict]" = multiprocessing.Queue()

    args = {
        "background": background,
        "camera": camera,
        "command_queue": command_queue,
        "resolution": resolution,
        "use_hologram": use_hologram,
        "use_mirror": use_mirror,
        "model": model,
    }
    p = multiprocessing.Process(target=capture.start, kwargs=args)
    try:
        p.start()
        p.join()
    except KeyboardInterrupt:
        command_queue.put(CommandQueueDict(
            quit=True,
        ))
        p.terminate()
        p.join()
