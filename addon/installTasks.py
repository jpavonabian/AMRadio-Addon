# -*- coding: utf-8 -*-

# Este archivo está cubierto por la Licencia Pública General de GNU.
# Última actualización 2024
# Derechos de autor (C) 2024 Jesús Pavón Abián <galorasd@gmail.com>
# Idea y gran parte del código tomada de los complementos de Ángel Alcántar <rayoalcantar@gmail.com> ¡Gracias!

import addonHandler

addonHandler.initTranslation()

class donate:
    def open():
        import languageHandler
        import webbrowser
        webbrowser.open(f"https://www.paypal.com/paypalme/jpavonabian")

    def request():
        import wx
        import gui
        
        # Translators: The title of the dialog requesting donations from users.
        title = _("Please, donate")
        
        # Translators: The text of the donate dialog
        message = _("""NVDA Add-on for amateur radio enthusiasts.
You can make a donation to EA7LEE to help.
If you want, you'll redirected to Paypal.""")
        
        name = addonHandler.getCodeAddon().manifest['summary']
        if gui.messageBox(message.format(name=name), title, style=wx.YES_NO|wx.ICON_QUESTION) == wx.YES:
            donate.open()
            return True
        return False

def onInstall():
    import globalVars
    # This checks if NVDA is running in a secure mode (e.g., on the Windows login screen),
    # which would prevent the addon from performing certain actions.
    if not globalVars.appArgs.secure:
        donate.request()