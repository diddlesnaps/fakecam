import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst

from .ui.mainwindow import MainWindow


def main():
    Gst.init(None)
    MainWindow()
    Gtk.main()


if __name__ == "__main__":
    main()
