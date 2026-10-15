# -*- coding: utf-8 -*-
"""AnP — Fragmentação da Paisagem (plugin integrado) v1.1"""
import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
MENU = "AnP \u2013 An\u00e1lise da Paisagem"

class AnPFragmentacaoPlugin:
    def __init__(self, iface):
        self.iface = iface; self.action = None; self.launcher = None
    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "Fragmentação da Paisagem", self.iface.mainWindow())
        self.action.setToolTip("AnP — Fragmentação temporal e análise de fragmentos")
        self.action.triggered.connect(self._abrir)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)
    def unload(self):
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action); del self.action
    def _abrir(self):
        from .launcher import AnPFragLauncher
        if self.launcher is None:
            self.launcher = AnPFragLauncher(self.iface)
        self.launcher.show(); self.launcher.raise_()
