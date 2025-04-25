import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .plugin_dialog import MyPluginDialog

class MyPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        icon = QIcon(icon_path)
        self.action = QAction(icon, "RPA Footprints", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&RPA Footprints", self.action)

    def unload(self):
        self.iface.removePluginMenu("&RPA Footprints", self.action)
        self.iface.removeToolBarIcon(self.action)

    def show_dialog(self):
        if not self.dialog:
            self.dialog = MyPluginDialog()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
