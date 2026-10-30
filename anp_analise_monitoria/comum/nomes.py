# -*- coding: utf-8 -*-
"""Nome da unidade de análise que representa a área total (sem recorte).

O padrão é "Shape Completo", mas o usuário pode dar outro nome no diálogo
de cada módulo (ex.: "Quadrilátero Ferrífero", "APA Jundiaí") — ele é usado
nas planilhas, nos nomes dos rasters e, depois, nos gráficos.
"""
import re
from qgis.PyQt.QtWidgets import QLabel, QLineEdit

NOME_TOTAL_PADRAO = "Shape Completo"


def limpar_nome_total(texto):
    """Nome sem espaços sobrando; vazio volta ao padrão."""
    nome = re.sub(r"\s+", " ", str(texto or "")).strip()
    return nome or NOME_TOTAL_PADRAO


def campo_nome_total(grid, linha, col_label=0, col_campo=1, span=2):
    """Acrescenta ao QGridLayout o campo 'Nome da área total' e o devolve."""
    lbl = QLabel("Nome da área total:")
    lbl.setToolTip("Nome da unidade que representa toda a área analisada "
                   "(sem recorte). Aparece nas planilhas e nos gráficos.")
    le = QLineEdit(NOME_TOTAL_PADRAO)
    le.setPlaceholderText(NOME_TOTAL_PADRAO)
    le.setToolTip(lbl.toolTip())
    grid.addWidget(lbl, linha, col_label)
    grid.addWidget(le, linha, col_campo, 1, span)
    return le
