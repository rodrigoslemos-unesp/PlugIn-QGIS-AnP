# -*- coding: utf-8 -*-
"""AnP — Fragmentação da Paisagem: launcher (menu principal, 2 estruturas)."""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt

from .comum.metadados import VERSAO_SUITE

DIR = os.path.dirname(__file__)

ESTRUTURAS = [
    {"id": "temporal", "img": "temporal.png",
     "titulo": "Fragmentação temporal da paisagem",
     "desc": ("Compara dois anos e mede a fragmentação em nível de classe e de "
              "paisagem via PyLandStats (CA, NP, TCA, CORE, MESH, LSI...), com "
              "áreas núcleo e distribuição por porte. Gera o paisagem.xlsx com "
              "métricas, variações (Δ) e distribuições.")},
    {"id": "fragmentos", "img": "fragmentos.png",
     "titulo": "Análise de fragmentos",
     "desc": ("Vetoriza cada fragmento de uma classe (patch-level) e calcula "
              "métricas por polígono: área, perímetro, área núcleo, índice de "
              "forma, fractal, circularidade e vizinho mais próximo. Gera "
              "shapefile + Excel-resumo (Fragmentos, Panorama).")},
]


class AnPFragLauncher(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface; self._dlg = None
        self.setWindowTitle("AnP — Fragmentação da Paisagem")
        self.setMinimumWidth(700)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16); root.setSpacing(12)
        cab = QLabel("AnP — Fragmentação da Paisagem")
        cab.setStyleSheet("font-size:17px;font-weight:bold;color:#00695C;")
        root.addWidget(cab)
        root.addWidget(QLabel("Selecione uma estrutura de análise."))
        for e in ESTRUTURAS:
            root.addWidget(self._card(e))
        rod = QLabel(f"v{VERSAO_SUITE}  ·  DGPA/IGCE — Unesp Rio Claro")
        rod.setStyleSheet("font-size:10px;color:#888;"); rod.setAlignment(Qt.AlignRight)
        root.addWidget(rod)

    def _card(self, e):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{border:1px solid #cfcfcf;border-radius:10px;background:#fafafa;}"
            "QFrame:hover{border:1px solid #00695C;background:#eef6f4;}")
        lay = QHBoxLayout(card); lay.setContentsMargins(12,12,12,12); lay.setSpacing(14)
        img = QLabel(); px = QPixmap(os.path.join(DIR, "img", e["img"]))
        if not px.isNull():
            img.setPixmap(px.scaled(84,84,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        img.setFixedSize(88,88); img.setAlignment(Qt.AlignCenter); lay.addWidget(img)
        col = QVBoxLayout(); col.setSpacing(4)
        tit = QLabel(e["titulo"])
        tit.setStyleSheet("font-size:14px;font-weight:bold;color:#222;border:none;")
        col.addWidget(tit)
        ds = QLabel(e["desc"]); ds.setWordWrap(True)
        ds.setStyleSheet("color:#555;border:none;"); col.addWidget(ds)
        lay.addLayout(col, 1)
        btn = QPushButton("Abrir"); btn.setFixedWidth(96)
        btn.setStyleSheet("QPushButton{background:#00695C;color:white;border-radius:6px;"
                          "padding:8px;font-weight:bold;}QPushButton:hover{background:#00544a;}")
        btn.clicked.connect(lambda _=False, eid=e["id"]: self._abrir(eid))
        wrap = QVBoxLayout(); wrap.addStretch(); wrap.addWidget(btn); wrap.addStretch()
        lay.addLayout(wrap)
        return card

    def _abrir(self, eid):
        # checagem CONTEXTUAL de dependências (sem pip automático)
        from .comum.deps import faltando, mensagem
        faltas = faltando(eid)
        if faltas:
            box = QMessageBox(self); box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("AnP — Dependências")
            box.setText("Faltam bibliotecas para esta estrutura.")
            box.setInformativeText(mensagem(faltas))
            box.setTextInteractionFlags(Qt.TextSelectableByMouse); box.exec_()
            return
        try:
            if eid == "temporal":
                from .temporal.dialog import AnPFragmentacaoDialog as Dlg
            else:
                from .fragmentos.dialog import AnPFragmentosDialog as Dlg
        except Exception as e:
            QMessageBox.critical(self, "AnP", f"Falha ao abrir a estrutura:\n{e}")
            return
        dlg = Dlg(self.iface)
        lay = dlg.layout()
        if lay is not None:
            voltar = QPushButton("\u25c0  Voltar ao menu AnP")
            voltar.setStyleSheet("QPushButton{background:#eeeeee;border:1px solid #ccc;"
                                 "border-radius:6px;padding:6px;}QPushButton:hover{background:#e0e0e0;}")
            voltar.clicked.connect(dlg.close); lay.insertWidget(0, voltar)
        dlg.finished.connect(lambda _=0: self.show())
        self._dlg = dlg; self.hide(); dlg.show(); dlg.raise_()
