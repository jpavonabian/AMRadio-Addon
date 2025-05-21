# -*- coding: utf-8 -*-
# NVDA Add-on for amateur radio enthusiasts
# Copyright (C) 2024
# This file is covered by the GNU General Public License.

import globalPluginHandler
import scriptHandler
import ui
import addonHandler
import logHandler
import webbrowser
import wx
import requests
from bs4 import BeautifulSoup
import time
from threading import Thread, Event
import tones
from datetime import datetime, timezone
try:
    addonHandler.initTranslation()
except Exception as e:
    logHandler.error(f"The translation can't be initialiced due the following error: {e}")

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

    def scrape_qrz_data(self, callsign):
        # This is a stub function. It will be implemented later.
        # For now, it returns placeholder data.
        # logHandler.debug(f"Scraping data for callsign: {callsign}")
        # return {"callsign": callsign, "name": "Placeholder Name", "location": "Placeholder Location"}
        url = f"https://www.qrz.com/db/{callsign}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        data = {"callsign": callsign}

        try:
            logHandler.info(f"Fetching data for {callsign} from {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logHandler.error(f"Error fetching data for {callsign}: Status code {response.status_code}")
                # Check for common qrz.com 'not found' message
                if "record not found" in response.text.lower() or "Invalid Request" in response.text:
                     logHandler.info(f"Callsign {callsign} not found in QRZ.com database.")
                return None

            soup = BeautifulSoup(response.content, 'html.parser')

            # --- Data Extraction ---
            # This part is highly dependent on qrz.com's HTML structure and might need adjustments.
            # We'll try to find data in tables, as that's common.

            # Example: Find by text label in a <td> and get the next <td>
            # Looking for specific field names in <td> elements
            fields_to_extract = {
                "Name": None, # Actual field name on qrz might be different e.g. "fname" or in a specific td
                "Address": None, # Often split into multiple fields
                "Grid Sq": None, # Often "Grid Square"
                "Country": None,
                "License Class": None, # Might not be explicitly labeled
                "Email": None, # Rarely public
            }
            
            # General approach: iterate through <td> elements that might contain labels
            # QRZ.com uses a table with id="tabCallsignDetail" for some details
            detail_table = soup.find('table', id='tabCallsignDetail')
            if detail_table:
                rows = detail_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2: # Expecting Label: Value pairs
                        label = cells[0].get_text(strip=True).replace(':', '')
                        value = cells[1].get_text(strip=True)
                        
                        if "Trusteeship" in label or "Trustee" in label: # Skip trustee details for now
                            continue

                        if "fname" in cells[0].get('id', '') or "fullname" in cells[0].get('id', ''):
                             data["Name"] = value
                        elif "addr1" in cells[0].get('id', '') and value: # first line of address
                            data["Address"] = value
                        elif "addr2" in cells[0].get('id', '') and value: # city, state often here
                            if data.get("Address"):
                                data["Address"] += f", {value}"
                            else:
                                data["Address"] = value
                        elif "country" in cells[0].get('id', ''):
                            data["Country"] = value
                        elif "grid" in cells[0].get('id', '') :
                            data["Grid Sq"] = value
                        elif "class" in cells[0].get('id', ''): # License class
                            data["License Class"] = value
                        elif "email" in cells[0].get('id', '') : # Email
                            data["Email"] = value
            
            # Fallback or additional search for name if not found in the detailed table
            if not data.get("Name"):
                name_tag = soup.find('font', {'size': '+2', 'color': 'green'})
                if name_tag:
                    data["Name"] = name_tag.get_text(strip=True)
            
            # Look for other common data points like grid square
            # This is a guess, qrz.com structure can be complex
            grid_square_td = soup.find('td', string=lambda t: t and "Grid Square" in t)
            if grid_square_td and grid_square_td.find_next_sibling('td'):
                data["Grid Sq"] = grid_square_td.find_next_sibling('td').get_text(strip=True)
            
            # Extracting address details can be tricky.
            # QRZ often lists address in multiple '<td>' elements.
            # We'll try to find the section with address info.
            # Example: <td class="addrdet">Address Line 1</td>
            # <td class="addrdet">City, State Zip</td>
            # <td class="addrdet">Country</td>
            address_parts = []
            address_labels = ["Address", "City", "State", "Zip Code", "Country"] # Common labels
            
            for label_text in address_labels:
                label_td = soup.find('td', string=lambda t: t and label_text in t)
                if label_td:
                    value_td = label_td.find_next_sibling('td')
                    if value_td:
                        part = value_td.get_text(strip=True)
                        if part:
                            address_parts.append(part)
            
            if address_parts:
                if not data.get("Address"): # If not already populated by the id search
                     data["Address (Combined)"] = ", ".join(address_parts)
                elif not data.get("Country") and any(country_label in str(address_parts) for country_label in ["USA", "Canada"]): # Basic country detection
                    # Try to find country if not set by ID
                    for part in address_parts:
                        # This is a very rough way to find country.
                        if part.upper() == part and len(part) > 3 and not any(char.isdigit() for char in part): 
                            data["Country"] = part
                            break


            if len(data) == 1 and data["callsign"] == callsign : # Only callsign was added
                logHandler.info(f"No detailed data extracted for {callsign}. Page structure might have changed or data is not available.")
                # Check if it's a "callsign not found" page more definitively
                title_tag = soup.find('title')
                if title_tag and ("not found" in title_tag.get_text().lower() or "error" in title_tag.get_text().lower()):
                    logHandler.info(f"Callsign {callsign} does not appear to be in the QRZ.com database (based on page title).")
                    return None # Return None if it seems like a "not found" page

            logHandler.info(f"Successfully extracted data for {callsign}: {data}")
            return data

        except requests.exceptions.Timeout:
            logHandler.error(f"Timeout while fetching data for {callsign} from QRZ.com.")
            return None
        except requests.exceptions.RequestException as e:
            logHandler.error(f"Network error fetching data for {callsign} from QRZ.com: {e}")
            return None
        except Exception as e:
            logHandler.error(f"Error parsing data for {callsign}: {e}")
            return None

    def display_callsign_data_dialog(self, data, callsign):
        if not data:
            ui.message(_("Callsign {} not found or an error occurred while fetching data.").format(callsign))
            return

        # Ensure this runs in the main wx thread if called from elsewhere
        # However, show_callsign_dialog already uses wx.CallAfter for this.

        class CallsignDataDialog(wx.Dialog):
            def __init__(self, parent, title, content_data):
                super(CallsignDataDialog, self).__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
                
                panel = wx.Panel(self)
                vbox = wx.BoxSizer(wx.VERTICAL)

                text_content = ""
                if isinstance(content_data, dict):
                    for key, value in content_data.items():
                        if value: # Only display if value is not None or empty
                            text_content += f"{key.replace('_', ' ').title()}: {value}\n"
                else:
                    text_content = str(content_data) # Fallback if data is not a dict

                if not text_content:
                    text_content = _("No detailed information available for {}.").format(callsign)

                text_ctrl = wx.TextCtrl(panel, value=text_content, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
                # Make text_ctrl expand with the dialog
                vbox.Add(text_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

                # OK Button
                ok_button = wx.Button(panel, wx.ID_OK, label=_("OK"))
                ok_button.SetDefault() # Make OK the default button
                
                # Button sizer for right alignment (common practice)
                button_sizer = wx.BoxSizer(wx.HORIZONTAL)
                button_sizer.AddStretchSpacer()
                button_sizer.Add(ok_button, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
                
                vbox.Add(button_sizer, flag=wx.EXPAND | wx.BOTTOM | wx.RIGHT, border=5)

                panel.SetSizer(vbox)
                
                # Set initial size (optional, but good for usability)
                # Attempt to make it reasonably sized based on content, but not too big.
                # This is a rough estimate.
                lines = text_content.count('\n') + 1
                width = max(350, min(600, max(len(line) for line in text_content.split('\n')) * 9)) # estimate width
                height = max(200, min(500, lines * 20)) # estimate height
                self.SetSize((width, height))

                self.CentreOnParent()

        # Create and show the dialog
        dialog_title = _("QRZ.com Data for {}").format(callsign)
        dlg = CallsignDataDialog(None, dialog_title, data)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

    def show_callsign_dialog(self):
        """Open a dialog to enter the callsign, fetch data, and display it."""
        def open_dialog():
            dialog = wx.TextEntryDialog(None, _( "Enter Your Callsign"), _( "Please enter your callsign:"))
            try:
                if dialog.ShowModal() == wx.ID_OK:
                    callsign = dialog.GetValue().strip().upper()
                    if callsign:
                        # Call scrape_qrz_data to get the data
                        data = self.scrape_qrz_data(callsign)
                        # Call display_callsign_data_dialog to show the data
                        # Ensure UI operations are done in the main thread
                        # Pass both data and callsign
                        wx.CallAfter(self.display_callsign_data_dialog, data, callsign)
                        # The case where 'data' is None is handled by display_callsign_data_dialog itself.
            except Exception as e:
                logHandler.error(f"An error occurred in show_callsign_dialog: {e}")
            finally:
                dialog.Destroy()

        wx.CallAfter(open_dialog)

    @scriptHandler.script(description=_("Open the callsign dialog."), gesture=None, category=_("AM Radio Add-on"))
    def script_show_callsign_dialog(self, gesture):
        self.show_callsign_dialog()

    @scriptHandler.script(description=_("Start a 3-minute timer with tones."), gesture=None, category=_("AM Radio Add-on"))
    def script_start_timer(self, gesture):
        self.timer_thread.start_timer()
        ui.message(_("3-minute timer started."))
        
    @scriptHandler.script(description=_("Announce the current UTC time (hour and minute)."), gesture=None, category=_("AM Radio Add-on")
    )
    def script_announce_utc_time(self, gesture):
        """Gets the current UTC time and announces it."""
        current_utc = datetime.now(timezone.utc)
        hour = current_utc.hour
        minute = current_utc.minute

        # Format the time in HH:MM format
        formatted_time = f"{hour:02d}:{minute:02d}"

        ui.message(_("The current UTC time is ") + formatted_time)

    @scriptHandler.script(description=_("Open the brand meister hoseline"), gesture=None, category=_("AM Radio Add-on"))
    def script_open_brand_meister(self, gesture):
        """Opens brand meister hoseline to hear dmr radio talk grops"""
        #Try-except to verify if the webbrouser execution works good
        try:
            webbrowser.open("https://hose.brandmeister.network/")
            #If execution can't be finished due an error, print into the nvda log
        except Exception as e:
            logHandler.error(f"An exception ocured wen opens Brand Meister. Exception: {e}")
