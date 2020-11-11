import configparser
import multiprocessing
from multiprocessing.queues import Queue

import gi
import os, sys

from . import gstreamer
from .. import capture, lang
from ..types import QueueDict

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gtk, Gst

CONFIG_FILE = os.path.expanduser("~/config.ini")
config = configparser.SafeConfigParser()


class MainWindow:
    p = None
    queue: "Queue[QueueDict]" = multiprocessing.Queue()
    pipeline = None
    builder = None
    started = False
    cancel_timeout = False

    # movie_window_xid = None

    av_widget = None
    av_sink = None
    av_conv = None
    av_src = None

    camera = "/dev/video0"
    background = None
    use_hologram = False
    use_mirror = False

    def __init__(self):
        self.player = None
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "fakecam.glade"))
        window = builder.get_object("MainWindow")

        if os.path.isfile(CONFIG_FILE):
            config.read(CONFIG_FILE)

            if config.has_section("main"):
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

        self.builder = builder

        if not os.access(self.camera, os.R_OK):
            dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.OK, "Camera device not accessible")
            dialog.format_secondary_text(lang.CONNECT_INTERFACE + "\n\nThe fakecam app will now close.")
            dialog.run()
            dialog.destroy()
            self.on_quit()
            sys.exit(1)
        elif not os.access("/dev/video20", os.W_OK):
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
            }
            builder.connect_signals(handlers)
            window.show_all()

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
            self.queue.put_nowait(QueueDict(
                background=self.background,
                hologram=self.use_hologram,
                mirror=self.use_mirror,
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
            "camera": self.camera,
            "background": self.background,
            "use_hologram": self.use_hologram,
            "use_mirror": self.use_mirror,
            "queue": self.queue,
            "resolution": None
        }
        p = multiprocessing.Process(target=capture.start, kwargs=args)
        p.start()
        self.p = p

        GLib.timeout_add_seconds(5, self.try_start_viewer)

    def try_start_viewer(self):
        # window = self.builder.get_object("MainWindow")
        print("Starting gstreamer")
        sink, widget = None, None
        gtkglsink = Gst.ElementFactory.make("gtkglsink")
        if gtkglsink is not None:
            print("Using GTKGLSink")
            glsinkbin = Gst.ElementFactory.make("glsinkbin")
            glsinkbin.set_property("sink", gtkglsink)
            widget = gtkglsink.get_property("widget")
            sink = glsinkbin
        else:
            print("Using GTKSink")
            sink = Gst.ElementFactory.make("gtksink")
            widget = sink.get_property("widget")

        if sink is None:
            print("Could not set up gstreamer.")
            return False

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
            conv = Gst.ElementFactory.make("videoconvert")
            caps = Gst.caps_from_string("video/x-raw")
            pipeline.add(src)
            pipeline.add(conv)
            pipeline.add(sink)
            src.link_filtered(conv, caps)
            conv.link(sink)
            self.pipeline = pipeline
            self.av_src = src
            self.av_conv = conv
            self.av_sink = sink
        except GLib.Error:
            print("Error setting up video source")
            self.on_quit()

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
