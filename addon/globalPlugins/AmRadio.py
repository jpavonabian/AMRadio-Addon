# -*- coding: utf-8 -*-
# NVDA Add-on for amateur radio enthusiasts
# Copyright (C) 2024
# This file is covered by the GNU General Public License.

import globalPluginHandler
import scriptHandler
import ui
import addonHandler
import webbrowser
import wx
import time
from threading import Thread, Event
import tones

addonHandler.initTranslation()

TONE_WARNING_TIME = 160  # 2 minutes and 40 seconds
TIMER_DURATION = 180  # 3 minutes in seconds
TONE_2_40_FREQUENCY = 440
TONE_3_00_FREQUENCY = 600
TONE_DURATION = 300

class TimerThread(Thread):
    def __init__(self):
        super(TimerThread, self).__init__()
        self.stop_event = Event()
        self.timer_active = False
        self.daemon = True

    def start_timer(self):
        if self.timer_active:
            return
        self.timer_active = True

        def timer_logic():
            try:
                time.sleep(TONE_WARNING_TIME)
                tones.beep(TONE_2_40_FREQUENCY, TONE_DURATION)
                time.sleep(TIMER_DURATION - TONE_WARNING_TIME)
                tones.beep(TONE_3_00_FREQUENCY, TONE_DURATION)
            finally:
                self.timer_active = False

        Thread(target=timer_logic, daemon=True).start()

    def stop_timer(self):
        self.stop_event.set()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self.timer_thread = TimerThread()

    def show_callsign_dialog(self):
        """Open a dialog to enter the callsign and navigate to QRZ."""
        def open_dialog():
            dialog = wx.TextEntryDialog(None, _( "Enter Your Callsign"), _( "Please enter your callsign:"))
            if dialog.ShowModal() == wx.ID_OK:
                callsign = dialog.GetValue().strip().upper()
                if callsign:
                    webbrowser.open(f"https://www.qrz.com/db/{callsign}")
            dialog.Destroy()

        wx.CallAfter(open_dialog)

    @scriptHandler.script(description=_("Open the callsign dialog."), gesture=None, category=_("AM Radio Add-on"))
    def script_show_callsign_dialog(self, gesture):
        self.show_callsign_dialog()

    @scriptHandler.script(description=_("Start a 3-minute timer with tones."), gesture=None, category=_("AM Radio Add-on"))
    def script_start_timer(self, gesture):
        self.timer_thread.start_timer()
        ui.message(_("3-minute timer started."))
