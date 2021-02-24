INSTRUCTIONS = "The fake cemera device is not accessible. Make sure you have installed and activated " \
               "v4l2loopback-dkms. On debian and Ubuntu derivative distributions, this is done with the following " \
               "command - for other systems check your provider's documentation and package repositories for a " \
               "similar package:\n\n" \
               "    sudo apt install v4l2loopback-dkms\n\n" \
               "The module must be configured with the following options:\n\n" \
               "    devices=1 video_nr=20 card_label=\"fakecam\" exclusive_caps=1\n\n" \
               "To do this now and get going straight away run:\n\n" \
               "    modprobe -r v4l2loopback && modprobe v4l2loopback devices=1 video_nr=20 card_label=\"fakecam\" " \
               "exclusive_caps=1\n\n" \
               "This can be achieved by editing /etc/modprobe.d/fakecam.conf or /etc/modprobe.conf to add the " \
               "following line:\n\n" \
               "    options v4l2loopback devices=1 video_nr=20 card_label=\"fakecam\" exclusive_caps=1\n\n" \
               "You can do this easily with the following command:\n\n" \
               "    echo options v4l2loopback devices=1 video_nr=20 card_label=\"fakecam\" exclusive_caps=1 | " \
               "sudo tee -a /etc/modprobe.d/fakecam.conf\n\n" \
               "The module is not automatically reloaded on bootup so we need to add an entry into either " \
               "/etc/modules or a new file in /etc/modules-load.d named fakecam.conf. It simply requires the word " \
               "v4l2loopback on a new line in one of these places:\n\n" \
               "    echo v4l2loopback | sudo tee -a /etc/modules-load.d/fakecam.conf\n\n" \
               "Once the configuration is set it will persist across reboots. If you haven't run the modprobe " \
               "commands above then you should now either reboot, or run:\n\n" \
               "    sudo modprobe -r v4l2loopback && sudo modprobe v4l2loopback\n"

CONNECT_INTERFACE = "Your camera is not accessible. You need to manually run the following:\n\n" \
                    "    snap connect fakecam:camera\n"

USAGE = """
USAGE:
    fakecam [--input=<camera-device>] [--resolution=<width>x<height>] [--background=<background-file>] [--hologram]

PARAMETERS:
  --help:       display this help document.
  --input:      specify the camera device to use. The default is /dev/video0.
  --resolution: override your camera's default resolution. Must be width and
                height as numbers separated by an 'x', e.g. '640x480'. May not
                work reliably.
  --background: replace your camera background with an image. The default is
                to blur your existing background that your camera sees. Use the
                special value of 'greenscreen' to replace the background with a
                solid green colour so that you can cut yourself out of the image
                with chroma-key software such as is built-into OBS.
  --hologram:   overlay a Star Wars style hologram effect onto your likeness.
  --mirror:     flip the image.
"""

USING_MIRROR = "Mirroring the camera image."
USING_HOLOGRAM = "Using the hologram effect."
USING_GREENSCREEN = "Replacing your background with a greenscreen."
USING_BACKGROUND_IMAGE = "Using background image {background}."
USING_BACKGROUND_BLUR = "No background specified. will blur your background instead."
BACKGROUND_UNREADABLE = "The background image cannot be read. Will blur your background instead."
