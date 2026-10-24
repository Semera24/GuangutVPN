#!/usr/bin/env python3
"""GuangutVPN Desktop System Tray Applet (Status Pill with 1-Click Quick Connect/Disconnect Menu)."""

from __future__ import annotations
import os
import signal
import subprocess
import sys
import threading
import time

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk
    HAS_GTK = True
except Exception:
    HAS_GTK = False

from guangut.tunnel import disconnect_vpn, get_active_tun_iface, running_pid


class GuangutTrayApp:
    def __init__(self):
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_title("GuangutVPN")
        self.status_icon.connect("popup-menu", self.on_popup_menu)
        self.status_icon.connect("activate", self.on_activate)

        self.update_status()
        GLib.timeout_add_seconds(3, self.update_status)

    def update_status(self) -> bool:
        pid = running_pid()
        tun = get_active_tun_iface()
        if pid and tun:
            self.status_icon.set_from_icon_name("security-high")
            self.status_icon.set_tooltip_text(f"GuangutVPN: CONNECTED ({tun})")
        else:
            self.status_icon.set_from_icon_name("security-low")
            self.status_icon.set_tooltip_text("GuangutVPN: Disconnected")
        return True

    def on_activate(self, icon):
        # Open Web GUI on left click
        subprocess.Popen(["xdg-open", "http://127.0.0.1:8765"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_popup_menu(self, icon, button, time):
        menu = Gtk.Menu()

        title_item = Gtk.MenuItem(label="🛡️ GuangutVPN Control")
        title_item.set_sensitive(False)
        menu.append(title_item)
        menu.append(Gtk.SeparatorMenuItem())

        # Web GUI item
        gui_item = Gtk.MenuItem(label="Open Web Dashboard")
        gui_item.connect("activate", lambda w: subprocess.Popen(["xdg-open", "http://127.0.0.1:8765"]))
        menu.append(gui_item)

        # Quick connect US-West
        us_west_item = Gtk.MenuItem(label="Connect: US-West (CA / CO)")
        us_west_item.connect("activate", lambda w: subprocess.Popen(["sudo", "guangut", "connect", "--us-region", "west"]))
        menu.append(us_west_item)

        # Quick connect US-Central
        us_central_item = Gtk.MenuItem(label="Connect: US-Central (TX)")
        us_central_item.connect("activate", lambda w: subprocess.Popen(["sudo", "guangut", "connect", "--us-region", "central"]))
        menu.append(us_central_item)

        # Disconnect item
        disc_item = Gtk.MenuItem(label="Disconnect VPN")
        disc_item.connect("activate", lambda w: disconnect_vpn())
        menu.append(disc_item)

        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit Tray Icon")
        quit_item.connect("activate", lambda w: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, self.status_icon, button, time)


def run_tray():
    if not HAS_GTK:
        print("GTK3 bindings not found. System tray requires python3-gi and libgtk-3.")
        return 1
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = GuangutTrayApp()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(run_tray())
