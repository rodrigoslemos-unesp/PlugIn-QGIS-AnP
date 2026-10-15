# -*- coding: utf-8 -*-
"""
AnP Integrado — Launcher (menu principal).

Mostra um card por módulo (imagem + título + descrição + botão). Ao abrir
um módulo, o launcher se esconde; ao fechar o módulo (pelo X ou pelo botão
"Voltar ao menu"), o launcher reaparece. O botão "Voltar" é injetado no topo
do diálogo do módulo, sem precisar editar cada módulo.
"""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt

from .comum.metadados import VERSAO_SUITE

DIR = os.path.dirname(__file__)

MODULOS = [
    {
        "id": "preparacao",
        "img": "preparacao.png",
        "titulo": "Preparação de Dados",
        "desc": ("Alinha, recorta e reprojeta os rasters MapBiomas. Recorte por "
                 "shapefile com desagregação por campo (regionalização) e "
                 "geração de TIF + QML. Ponto de partida: reprojete aqui para "
                 "um CRS projetado (ex.: EPSG:31983) antes das análises."),
    },
    {
        "id": "relatorio",
        "img": "relatorio.png",
        "titulo": "Relatório de Cobertura",
        "desc": ("Composição de cobertura multi-ano e multi-unidade numa "
                 "planilha única (níveis N1–N4 em colunas). Desagrega por "
                 "shapefile + campo e gera TIF + QML por paisagem."),
    },
    {
        "id": "monitoria",
        "img": "monitoria.png",
        "titulo": "Monitoria de Cobertura",
        "desc": ("Compara dois anos: cobertura, alterações e matriz de "
                 "transição. Gera rasters de mudança (códigos originais e "
                 "categorias ecológicas) e as planilhas monitoria.xlsx e "
                 "Matriz.xlsx."),
    },
]


class AnPLauncher(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self._dlg = None
        self.setWindowTitle("AnP — Análise e Monitoria da Paisagem")
        self.setMinimumWidth(680)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16); root.setSpacing(12)

        cab = QLabel("AnP — Análise e Monitoria da Paisagem")
        cab.setStyleSheet("font-size:17px;font-weight:bold;color:#1B5E20;")
        root.addWidget(cab)
        sub = QLabel("Selecione um módulo para começar.")
        sub.setStyleSheet("color:#555;")
        root.addWidget(sub)

        for m in MODULOS:
            root.addWidget(self._card(m))

        rod = QLabel(f"v{VERSAO_SUITE}  ·  DGPA/IGCE — Unesp Rio Claro")
        rod.setStyleSheet("font-size:10px;color:#888;")
        rod.setAlignment(Qt.AlignRight)
        root.addWidget(rod)

    def _card(self, m):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{border:1px solid #cfcfcf;border-radius:10px;background:#fafafa;}"
            "QFrame:hover{border:1px solid #2E7D32;background:#f2f8f2;}")
        lay = QHBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(14)

        img = QLabel()
        px = QPixmap(os.path.join(DIR, "img", m["img"]))
        if not px.isNull():
            img.setPixmap(px.scaled(84, 84, Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation))
        img.setFixedSize(88, 88); img.setAlignment(Qt.AlignCenter)
        lay.addWidget(img)

        col = QVBoxLayout(); col.setSpacing(4)
        tit = QLabel(m["titulo"])
        tit.setStyleSheet("font-size:14px;font-weight:bold;color:#222;border:none;")
        col.addWidget(tit)
        desc = QLabel(m["desc"]); desc.setWordWrap(True)
        desc.setStyleSheet("color:#555;border:none;")
        col.addWidget(desc)
        lay.addLayout(col, 1)

        btn = QPushButton("Abrir")
        btn.setFixedWidth(96)
        btn.setStyleSheet(
            "QPushButton{background:#2E7D32;color:white;border-radius:6px;"
            "padding:8px;font-weight:bold;}QPushButton:hover{background:#256628;}")
        btn.clicked.connect(lambda _=False, mid=m["id"]: self._abrir(mid))
        wrap = QVBoxLayout(); wrap.addStretch(); wrap.addWidget(btn); wrap.addStretch()
        lay.addLayout(wrap)
        return card

    def _abrir(self, mid):
        try:
            if mid == "preparacao":
                from .preparacao.dialog import AnPPreparacaoDialog as Dlg
            elif mid == "monitoria":
                from .monitoria.dialog import AnPMonitoriaDialog as Dlg
            else:
                from .relatorio.dialog import AnPRelatorioDialog as Dlg
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(self, "AnP", f"Falha ao abrir o módulo:\n{e}")
            return

        dlg = Dlg(self.iface)
        # injeta um botão "Voltar ao menu" no topo do diálogo do módulo
        lay = dlg.layout()
        if lay is not None:
            voltar = QPushButton("\u25c0  Voltar ao menu AnP")
            voltar.setStyleSheet(
                "QPushButton{background:#eeeeee;border:1px solid #ccc;"
                "border-radius:6px;padding:6px;}QPushButton:hover{background:#e0e0e0;}")
            voltar.clicked.connect(dlg.close)
            lay.insertWidget(0, voltar)
        dlg.finished.connect(lambda _=0: self.show())
        self._dlg = dlg
        self.hide()
        dlg.show(); dlg.raise_()
