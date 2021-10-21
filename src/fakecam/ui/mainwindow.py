import configparser
import subprocess
import multiprocessing
from multiprocessing.queues import Queue

import gi
import os, sys

from .. import about, capture, lang
from ..types import CommandQueueDict

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gtk, Gst

CONFIG_FILE = os.path.expanduser("~/config.ini")
config = configparser.SafeConfigParser()

resolutions = {
      "640x480": {"width":  640, "height":  480, "description": "(works with most webcams)"},
      "720x480": {"width":  720, "height":  480, "description": "(NTSC)"},
      "720x576": {"width":  720, "height":  576, "description": "(PAL)"},
     "1280x720": {"width": 1280, "height":  720, "description": "(HD)"},
    "1920x1080": {"width": 1920, "height": 1080, "description": "(Full HD)"},
    "3840x2160": {"width": 3840, "height": 2160, "description": "(4k)"},
}

class MainWindow:
    p = None
    command_queue: "Queue[CommandQueueDict]" = multiprocessing.Queue()
    return_queue: "Queue[bool]" = multiprocessing.Queue()
    pipeline = None
    builder = None
    started = False
    cancel_timeout = False

    # movie_window_xid = None

    av_widget = None
    av_sink = None
    av_conv = None
    av_src = None

    camera = ""
    camera_is_set = False
    resolution = (1280, 720)
    background = None
    use_hologram = False
    use_mirror = False

    def __init__(self):
        self.player = None
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "fakecam.glade"))

        aboutDlg = builder.get_object("AboutDialog")
        aboutDlg.set_program_name(about.name)
        aboutDlg.set_version(about.version)
        aboutDlg.set_copyright(about.copyright)
        aboutDlg.set_comments(about.description)
        aboutDlg.set_license(about.license)
        aboutDlg.set_wrap_license(True)
        aboutDlg.set_authors(about.authors)
        aboutDlg.set_website(about.project_url)
        aboutDlg.set_website_label("{project} homepage".format(project=about.name))

        if os.path.isfile(CONFIG_FILE):
            config.read(CONFIG_FILE)

            if config.has_section("main"):
                try:
                    self.camera = config.get("main", "camera")
                except configparser.NoOptionError:
                    pass

                try:
                    resolution = resolutions[config.get("main", "resolution")]
                    self.resolution = (resolution["width"], resolution["height"])
                except configparser.NoOptionError:
                    pass

                try:
                    self.use_hologram = config.getboolean("main", "hologram")
                    builder.get_object("hologram_toggle").set_active(self.use_hologram)
                except configparser.NoOptionError:
                    pass

                try:
                    self.use_mirror = config.getboolean("main", "mirror")
                    builder.get_object("mirror_toggle").set_active(self.use_mirror)
                except configparser.NoOptionError:
                    pass

                try:
                    background = config.get("main", "background")
                    if background == "greenscreen":
                        self.background = background
                        builder.get_object("greenscreen_toggle").set_active(True)
                    elif os.path.isfile(background) and os.access(background, os.R_OK):
                        self.background = background
                        builder.get_object("background_chooser").set_filename(background)
                except configparser.NoOptionError:
                    pass

        if not config.has_section("main"):
            config.add_section("main")

        devices = []
        v4ldir = "/sys/class/video4linux"
        for file in os.listdir(v4ldir):
            if file == 'video20':
                continue
            device = os.path.join("/dev", file)
            if os.access(device, os.R_OK):
                devices.append(device)
        devices.sort()
        
        cameraList = Gtk.ListStore(str, str)
        if len(devices) == 0:
            self.camera = ""
            config.set("main", "camera", self.camera)
            devices.append("")
            cameraList.append(["", "No camera found"])
        else:
            for device in devices:
                with open(os.path.join(v4ldir, os.path.basename(device), "name")) as name_file:
                    device_name = name_file.readline().strip()
                    cameraList.append([device, "{name} ({device})".format(name=device_name, device=device)])
            if not self.camera in devices:
                self.camera = devices[0]
                config.set("main", "camera", self.camera)

        cameraRenderer = Gtk.CellRendererText()
        video_source = builder.get_object("video_source_combobox")
        video_source.set_model(cameraList)
        video_source.pack_start(cameraRenderer, True)
        video_source.add_attribute(cameraRenderer, "text", 1)
        video_source.set_active(devices.index(self.camera))

        resolutionList = Gtk.ListStore(str, str, str, int, int)
        index = 0
        for title, details in resolutions.items():
            resolutionList.append([title, title, details["description"], details["width"], details["height"]])
            index = index + 1
        resolutionRenderer = Gtk.CellRendererText()
        resolution_select = builder.get_object("resoution_combobox")
        resolution_select.set_model(resolutionList)
        resolution_select.pack_start(resolutionRenderer, True)
        resolution_select.add_attribute(resolutionRenderer, "text", 2)
        resolution_select.set_active(list(resolutions).index("x".join(map(str, self.resolution))))

        self.builder = builder

        # if not os.access(self.camera, os.R_OK):
        #     dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
        #                                Gtk.ButtonsType.OK, "Camera device not accessible")
        #     dialog.format_secondary_text(lang.CONNECT_INTERFACE + "\n\nThe fakecam app will now close.")
        #     dialog.run()
        #     dialog.destroy()
        #     self.on_quit()
        #     sys.exit(1)
        # el
        if not os.access("/dev/video20", os.W_OK):
            dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, "Fake camera device not accessible")
            dialog.format_secondary_text(lang.INSTRUCTIONS)
            dialog.run()
            dialog.destroy()
            sys.exit(1)
        else:
            handlers = {
                "onDestroy": self.on_quit,
                "onAbout": self.on_about,
                "onSelectedBackground": self.on_selected_background,
                "onResetBackground": self.on_reset_background,
                "onGreenscreenToggled": self.on_greenscreen_toggled,
                "onHologramToggled": self.on_hologram_toggled,
                "onMirrorToggled": self.on_mirror_toggled,
                "onStartButtonClicked": self.on_startbutton_clicked,
                "onDonateButtonClicked": self.on_donatebutton_clicked,
                "onCameraChanged": self.on_camera_changed,
                "onResolutionChanged": self.on_resolution_changed,
            }
            builder.connect_signals(handlers)
            builder.get_object("MainWindow").show_all()

    def on_donatebutton_clicked(self, bus):
        subprocess.call(["xdg-open", about.donate_url])

    def on_resolution_changed(self, selection):
        index = selection.get_active()
        model = selection.get_model()
        width, height = model[index][3], model[index][4]
        if self.resolution != (width, height):
            started = self.started
            if started:
                self.stop()
            self.resolution = (width, height)
            config.set("main", "resolution", "{width}x{height}".format(width=width, height=height))
            if started:
                self.start()

    def on_camera_changed(self, selection):
        index = selection.get_active()
        model = selection.get_model()
        device = model[index][0]
        if self.camera != device:
            started = self.started
            if started:
                self.stop()
            self.camera = device
            config.set("main", "camera", device)
            self.camera_is_set = True
            if started:
                self.start()

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            if not self.cancel_timeout:
                print("Error: {error}. Will retry in 1 second".format(error=err), debug)
                self.pipeline.set_state(Gst.State.NULL)
                GLib.timeout_add_seconds(1, self.try_start_viewer)

    # def on_sync_message(self, bus, message):
    #     struct = message.get_structure()
    #     if not struct:
    #         return
    #     message_name = struct.get_name()
    #     if message_name == "prepare-window-handle":
    #         # Assign the viewport
    #         imagesink = message.src
    #         GLib.idle_add(imagesink.set_property, "force-aspect-ratio", True)
    #         GLib.idle_add(imagesink.set_window_handle, self.movie_window_xid)

    def update_worker(self):
        if self.started is True:
            self.command_queue.put_nowait(CommandQueueDict(
                background=self.background,
                hologram=self.use_hologram,
                mirror=self.use_mirror,
                quit=False,
            ))

    def on_reset_background(self, widget, *args):
        self.background = None
        self.builder.get_object("background_chooser").unselect_all()
        config.remove_option("main", "background")
        self.update_worker()

    def set_background(self, background):
        self.background = background
        if background is not None:
            config.set("main", "background", background)
        else:
            config.set("main", "background", "")
        self.update_worker()

    def on_selected_background(self, widget, *args):
        self.set_background(widget.get_filename())

    def on_greenscreen_toggled(self, widget, *args):
        chooser = self.builder.get_object("background_chooser")
        reset_button = self.builder.get_object("reset_button")
        background = chooser.get_filename()
        if widget.get_active() is True:
            chooser.set_sensitive(False)
            reset_button.set_sensitive(False)
            self.set_background("greenscreen")
        else:
            chooser.set_sensitive(True)
            reset_button.set_sensitive(True)
            if background is not None and os.path.isfile(background) and os.access(background, os.R_OK):
                self.set_background(background)
            else:
                self.set_background(None)

    def on_hologram_toggled(self, widget, *args):
        self.use_hologram = widget.get_active()
        config.set("main", "hologram", str(self.use_hologram))
        self.update_worker()

    def on_mirror_toggled(self, widget, *args):
        self.use_mirror = widget.get_active()
        config.set("main", "mirror", str(self.use_mirror))
        self.update_worker()

    def on_startbutton_clicked(self, widget, *args):
        if self.started:
            self.stop()
            widget.set_label("Start Fakecam")
            self.started = False
        else:
            widget.set_label("Stop Fakecam")
            self.start()
            self.started = True

    def start(self):
        # movie_window = self.builder.get_object("movie_window")
        # self.movie_window_xid = movie_window.get_property("window").get_xid()
        self.stop()

        args = {
            "background": self.background,
            "camera": self.camera,
            "command_queue": self.command_queue,
            "resolution": self.resolution,
            "return_queue": self.return_queue,
            "use_hologram": self.use_hologram,
            "use_mirror": self.use_mirror,
        }
        p = multiprocessing.Process(target=capture.start, kwargs=args)
        p.start()
        self.p = p

        GLib.timeout_add(100, self.try_start_viewer)

    def try_start_viewer(self):
        if self.return_queue is None or self.return_queue.empty():
            return True
        self.return_queue.get(False)

        # window = self.builder.get_object("MainWindow")
        sink, widget = None, None
        # gtkglsink = Gst.ElementFactory.make("gtkglsink")
        # if gtkglsink is not None:
        #     print("Using GTKGLSink")
        #     glsinkbin = Gst.ElementFactory.make("glsinkbin")
        #     glsinkbin.set_property("sink", gtkglsink)
        #     widget = gtkglsink.get_property("widget")
        #     sink = glsinkbin
        # else:
        print("Using GTKSink")
        sink = Gst.ElementFactory.make("gtksink")
        widget = sink.get_property("widget")

        if sink is None:
            return True

        viewport = self.builder.get_object("camera_viewport")
        if self.av_widget is not None:
            viewport.remove(self.av_widget)

        viewport.add(widget)
        self.av_widget = widget
        viewport.show_all()

        try:
            pipeline = self.pipeline
            if pipeline is None:
                pipeline = Gst.Pipeline()
            else:
                pipeline.set_state(Gst.State.NULL)

            # src = Gst.parse_launch("v4l2src device=/dev/video20 ! video/x-raw ! videoconvert")
            src = Gst.ElementFactory.make("v4l2src")
            src.set_property("device", "/dev/video20")
            jpg = Gst.ElementFactory.make("jpegdec")
            conv = Gst.ElementFactory.make("videoconvert")
            caps = Gst.caps_from_string("video/x-raw")
            pipeline.add(src)
            pipeline.add(jpg)
            pipeline.add(conv)
            pipeline.add(sink)
            src.link(jpg)
            jpg.link_filtered(conv, caps)
            conv.link(sink)
            self.pipeline = pipeline
            self.av_src = src
            self.av_conv = conv
            self.av_sink = sink
        except:
            return True

        self.pipeline.set_state(Gst.State.PLAYING)
        return False

    def stop(self, *args):
        self.cancel_timeout = True
        viewport = self.builder.get_object("camera_viewport")
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
        if self.av_src is not None:
            self.pipeline.remove(self.av_src)
            self.av_src = None
        if self.av_conv is not None:
            self.pipeline.remove(self.av_conv)
            self.av_conv = None
        if self.av_widget is not None:
            self.av_widget.set_visible(False)
            viewport.remove(self.av_widget)
            self.av_widget = None
        if self.av_sink is not None:
            self.pipeline.remove(self.av_sink)
            self.av_sink = None

        self.pipeline = None

        if self.p is not None:
            self.command_queue.put(CommandQueueDict(
                quit=True,
            ))
            self.p.terminate()
            self.p.join()
            self.p = None

    def on_about(self, *args):
        dlg = self.builder.get_object("AboutDialog")
        dlg.run()
        dlg.hide()

    def on_quit(self, *args):
        self.stop()
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        Gtk.main_quit()
