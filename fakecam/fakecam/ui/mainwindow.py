import gi
gi.require_version("Gtk", "3.0")
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GLib, Gtk, Gst, GdkX11, GstVideo
from multiprocessing import Process
import time
import os
from configparser import SafeConfigParser, NoOptionError

import fakecam.capture as capture
from fakecam.ui import gstreamer

CONFIG_FILE = os.path.expanduser('~/config.ini')
config = SafeConfigParser()

class MainWindow():
    p                = None
    p2               = None
    pipeline         = None
    builder          = None
    started          = False
    cancelTimeout    = False

    # movie_window_xid = None

    av_widget        = None
    av_sink          = None
    av_src           = None

    background       = None
    useHologram      = False

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "fakecam.glade"))
        window = builder.get_object("MainWindow")
 
        handlers = {
            "onDestroy":            self.on_quit,
            "onAbout":              self.on_about,
            "onSelectedBackground": self.on_selected_background,
            "onResetBackground":    self.on_reset_background,
            "onHologramToggled":    self.on_hologram_toggled,
            "onStartButtonClicked": self.on_startbutton_clicked,
        }
        builder.connect_signals(handlers)

        if os.path.isfile(CONFIG_FILE):
            config.read(CONFIG_FILE)

            if (config.has_section('main')):
                try:
                    self.useHologram = config.getboolean('main', 'hologram')
                    builder.get_object('hologram_toggle').set_active(self.useHologram)
                except NoOptionError:
                    pass

                try:
                    background = config.get('main', 'background')
                    if (os.path.isfile(background)):
                        self.background = background
                        builder.get_object('background_chooser').set_filename(background)
                except NoOptionError:
                    pass

        if not config.has_section('main'):
            config.add_section('main')

        self.builder = builder

        if not os.access('/dev/video0', os.R_OK):
            dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK, "Camera device not accessible")
            dialog.format_secondary_text("""
Your camera is not accessible. You need to manually run the following:
    snap connect fakecam:camera

The fakecam app will now close.
""")
            dialog.run()
            self.on_quit()

        if not os.access('/dev/video20', os.W_OK):
            dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK, "Fake camera device not accessible")
            dialog.format_secondary_text("""
The fake cemera device is not accessible. Make sure you have installed and
activated v4l2loopback-dkms. The module must be configured with the following
options:
    devices=1 video_nr=20 card_label="fakecam" exclusive_caps=1

To do this now and get going straight away run:
    modprobe -r v4l2loopback && modprobe v4l2loopback devices=1 \\
        video_nr=20 card_label="fakecam" exclusive_caps=1

This can be achieved by editing /etc/modprobe.d/fakecam.conf or
/etc/modprobe.conf to add the following line:
    options v4l2loopback devices=1 video_nr=20 \\
        card_label="fakecam" exclusive_caps=1

Once the configuration is set it will persist across reboots. If you haven't
run the modprobe commands above then you should now run:
    modprobe -r v4l2loopback && modprobe v4l2loopback

The fakecam app will now close.
""")
            dialog.run()
            self.on_quit()

        window.show_all()

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            if not self.cancelTimeout:
                print("Error: %s. Will retry in 1 second" % err, debug)
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

    def on_reset_background(self, widget):
        self.background = None
        self.builder.get_object('background_chooser').unselect_all()
        config.remove_option('main', 'background')

    def on_selected_background(self, widget):
        self.background = widget.get_filename()
        config.set('main', 'background', self.background)

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

        self.p = Process(target=capture.start, kwargs={'background': self.background, 'useHologram': self.useHologram})
        self.p2 = Process(target=capture.start_bodypix)

    def on_hologram_toggled(self, widget, *args):
        self.useHologram = widget.get_active()
        config.set('main', 'hologram', str(self.useHologram))

    def on_startbutton_clicked(self, widget):
        if (self.started):
            self.stop()
            self.builder.get_object('hologram_toggle').set_sensitive(True)
            self.builder.get_object('background_chooser').set_sensitive(True)
            self.builder.get_object('reset_button').set_sensitive(True)
            widget.set_label("Start Fakecam")
            self.started = False
        else:
            self.builder.get_object('hologram_toggle').set_sensitive(False)
            self.builder.get_object('background_chooser').set_sensitive(False)
            self.builder.get_object('reset_button').set_sensitive(False)
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

        viewport = self.builder.get_object('camera_viewport')
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
            src = Gst.ElementFactory.make('v4l2src')
            src.set_property('device', '/dev/video20')
            conv = Gst.ElementFactory.make('videoconvert')
            caps = Gst.caps_from_string('video/x-raw')
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
        self.cancelTimeout = True
        viewport = self.builder.get_object('camera_viewport')
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
        dlg = self.builder.get_object('AboutDialog')
        dlg.run()
        dlg.hide()

    def on_quit(self, *args):
        self.stop()
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        Gtk.main_quit()
