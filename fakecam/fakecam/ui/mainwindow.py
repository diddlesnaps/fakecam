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
    p2 = None
    queue: "Queue[QueueDict]" = multiprocessing.Queue()
    pipeline = None
    builder = None
    started = False
    cancel_timeout = False

    # movie_window_xid = None

    av_widget = None
    av_sink = None
    av_src = None

    background = None
    use_hologram = False

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "fakecam.glade"))
        window = builder.get_object("MainWindow")

        handlers = {
            "onDestroy": self.on_quit,
            "onAbout": self.on_about,
            "onSelectedBackground": self.on_selected_background,
            "onResetBackground": self.on_reset_background,
            "onHologramToggled": self.on_hologram_toggled,
            "onStartButtonClicked": self.on_startbutton_clicked,
        }
        builder.connect_signals(handlers)

        if os.path.isfile(CONFIG_FILE):
            config.read(CONFIG_FILE)

            if config.has_section("main"):
                try:
                    self.use_hologram = config.getboolean("main", "hologram")
                    builder.get_object("hologram_toggle").set_active(self.use_hologram)
                except configparser.NoOptionError:
                    pass

                try:
                    background = config.get("main", "background")
                    if os.path.isfile(background):
                        self.background = background
                        builder.get_object("background_chooser").set_filename(background)
                except configparser.NoOptionError:
                    pass

        if not config.has_section("main"):
            config.add_section("main")

        self.builder = builder

        if not os.access("/dev/video0", os.R_OK):
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

    def setup_subprocess(self):
        if self.p is not None:
            self.p.terminate()
            self.p.join()
        if self.p2 is not None:
            self.p2.terminate()
            self.p2.join()

        if self.p2 is not None:
            self.p2.terminate()
            self.p2.join()

        self.p = multiprocessing.Process(target=capture.start, kwargs={'background': self.background,
                                                                       'use_hologram': self.use_hologram,
                                                                       'queue': self.queue})
        self.p2 = multiprocessing.Process(target=capture.start_bodypix)

    def update_worker(self):
        if self.started is True:
            self.queue.put_nowait(dict(background=self.background, hologram=self.use_hologram))

    def on_reset_background(self, widget):
        self.background = None
        self.builder.get_object("background_chooser").unselect_all()
        config.remove_option("main", "background")
        self.update_worker()

    def on_selected_background(self, widget):
        self.background = widget.get_filename()
        config.set("main", "background", self.background)
        self.update_worker()

    def on_hologram_toggled(self, widget, *args):
        self.use_hologram = widget.get_active()
        config.set("main", "hologram", str(self.use_hologram))
        self.update_worker()

    def on_startbutton_clicked(self, widget):
        if self.started:
            self.stop()
            # self.builder.get_object("hologram_toggle").set_sensitive(True)
            # self.builder.get_object("background_chooser").set_sensitive(True)
            # self.builder.get_object("reset_button").set_sensitive(True)
            widget.set_label("Start Fakecam")
            self.started = False
        else:
            # self.builder.get_object("hologram_toggle").set_sensitive(False)
            # self.builder.get_object("background_chooser").set_sensitive(False)
            # self.builder.get_object("reset_button").set_sensitive(False)
            widget.set_label("Stop Fakecam")
            self.start()
            self.started = True

    def start(self):
        # movie_window = self.builder.get_object('movie_window')
        # self.movie_window_xid = movie_window.get_property('window').get_xid()
        self.setup_subprocess()
        self.p2.start()
        self.p.start()
        GLib.timeout_add_seconds(5, self.try_start_viewer)

    def try_start_viewer(self):
        window = self.builder.get_object("MainWindow")

        sink, widget, name = gstreamer.create_gtk_widget()
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

            # src = Gst.parse_launch('v4l2src device=/dev/video20 ! video/x-raw ! videoconvert')
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
        if self.p2 is not None:
            self.p2.terminate()
            self.p2.join()
            self.p2 = None

    def on_about(self, *args):
        dlg = self.builder.get_object("AboutDialog")
        dlg.run()
        dlg.hide()

    def on_quit(self, *args):
        self.stop()
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
        Gtk.main_quit()
