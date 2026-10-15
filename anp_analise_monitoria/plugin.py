# -*- coding: utf-8 -*-
"""AnP — Análise e Monitoria da Paisagem (plugin integrado) v1.1"""
import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

MENU = "AnP \u2013 An\u00e1lise da Paisagem"


class AnPIntegradoPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.launcher = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "Análise e Monitoria da Paisagem",
                              self.iface.mainWindow())
        self.action.setToolTip("AnP — Preparação, Relatório e Monitoria num só lugar")
        self.action.triggered.connect(self._abrir)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self):
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def _abrir(self):
        # checagem única e leve de dependências (sem pip automático)
        from .comum.deps import faltando, mensagem
        faltas = faltando()
        if faltas:
            from qgis.PyQt.QtWidgets import QMessageBox
            from qgis.PyQt.QtCore import Qt
            box = QMessageBox(self.iface.mainWindow())
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("AnP — Dependências")
            box.setText("Faltam bibliotecas para rodar o AnP.")
            box.setInformativeText(mensagem(faltas))
            box.setTextInteractionFlags(Qt.TextSelectableByMouse)
            box.exec_()
            return
        from .launcher import AnPLauncher
        if self.launcher is None:
            self.launcher = AnPLauncher(self.iface)
        self.launcher.show(); self.launcher.raise_()
