"""
AnP — Interface principal: Monitoria de Cobertura da Terra.
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSpinBox,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QLineEdit, QFileDialog, QTextEdit,
    QMessageBox, QProgressBar, QFrame)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QFont
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel

from ..comum.legenda import COLECOES
from ..comum.metadados import VERSAO_SUITE


class _Worker(QThread):
    progresso = pyqtSignal(str)
    concluido = pyqtSignal(object)
    erro      = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self._p = params

    def run(self):
        try:
            from .processamento import processar_completo
            from .excel_saida   import exportar
            from .raster_saida  import exportar_rasters
            import os

            resultado = processar_completo(
                raster1      = self._p['raster1'],
                raster2      = self._p['raster2'],
                ano1         = self._p['ano1'],
                ano2         = self._p['ano2'],
                colecao_nome   = self._p['colecao'],
                nivel_legenda  = self._p.get('nivel', 4),
                mascara_path = self._p.get('mascara_path'),
                campo_feicao = self._p.get('campo_feicao'),
                progresso_fn = self.progresso.emit,
            )

            arquivos = exportar(
                resultado    = resultado,
                pasta        = self._p['pasta_saida'],
                ano1         = self._p['ano1'],
                ano2         = self._p['ano2'],
                modo         = self._p['modo'],
                progresso_fn = self.progresso.emit,
            )

            self.progresso.emit("Gerando rasters de apoio...")
            arqs_r = exportar_rasters(
                resultado                = resultado,
                pasta                    = self._p['pasta_saida'],
                ano1                     = self._p['ano1'],
                ano2                     = self._p['ano2'],
                gerar_mudanca_codigos    = self._p.get('gerar_mudanca_codigos', True),
                gerar_mudanca_categorias = self._p.get('gerar_mudanca_categorias', True),
                progresso_fn             = self.progresso.emit,
            )

            self.concluido.emit(arquivos + arqs_r)

        except Exception as e:
            import traceback
            self.erro.emit(str(e) + '\n' + traceback.format_exc())


class AnPMonitoriaDialog(QDialog):

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface   = iface
        self._worker = None
        self._is_projected = True   # atualizado ao detectar CRS
        self.setWindowTitle(f'AnP — Monitoria de Cobertura da Terra  v{VERSAO_SUITE}')
        self.setMinimumWidth(740)
        self._build_ui()

    # ── Interface ───────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)
        root.addWidget(self._header())
        root.addWidget(self._bloco_rasters())
        root.addWidget(self._bloco_feicoes())
        root.addWidget(self._bloco_config())
        root.addWidget(self._bloco_saida())
        root.addWidget(self._bloco_log())
        root.addLayout(self._barra_botoes())

    def _header(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background-color:#1B5E20;border-radius:8px;}")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(14)

        logo = os.path.join(os.path.dirname(__file__), 'unesp_logo.png')
        if os.path.exists(logo):
            lbl = QLabel()
            pix = QPixmap(logo).scaledToHeight(60, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            lbl.setStyleSheet("background:white;border-radius:5px;padding:4px;")
            lbl.setFixedSize(pix.width()+10, 70)
            lay.addWidget(lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#2E7A3A;")
        lay.addWidget(sep)

        txt = QVBoxLayout()
        txt.setSpacing(3); txt.setAlignment(Qt.AlignVCenter)

        t1 = QLabel("AnP — Monitoria de Cobertura da Terra")
        t1.setStyleSheet("color:white;font-size:15px;font-weight:bold;"
                         "background:transparent;")
        txt.addWidget(t1)

        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color:#2E7A3A;"); txt.addWidget(div)

        t2 = QLabel("Grupo de Pesquisa: Planejamento Ambiental e Dinâmicas "
                    "da Paisagem  •  DGPA / IGCE — Unesp Rio Claro")
        t2.setStyleSheet("color:#A5D6A7;font-size:10px;font-style:italic;"
                         "background:transparent;")
        t2.setWordWrap(True); txt.addWidget(t2)

        t3 = QLabel("Prof. Dr. Rodrigo Silva Lemos  •  "
                    f"rodrigo.s.lemos@unesp.br  •  AnP v{VERSAO_SUITE}")
        t3.setStyleSheet("color:#81C784;font-size:10px;background:transparent;")
        txt.addWidget(t3)

        lay.addLayout(txt, 1)
        return frame

    def _grp(self):
        return ("QGroupBox{font-weight:bold;font-size:11px;"
                "border:1px solid #CCCCCC;border-radius:5px;"
                "margin-top:8px;padding-top:4px;}"
                "QGroupBox::title{subcontrol-origin:margin;"
                "left:8px;padding:0 4px;}")

    def _bloco_rasters(self):
        grp = QGroupBox("1. Rasters MapBiomas")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        g.addWidget(QLabel("Coleção / Sensor:"), 0, 0)
        self.cb_colecao = QComboBox()
        self.cb_colecao.addItems(list(COLECOES.keys()))
        self.cb_colecao.currentIndexChanged.connect(
            self._atualizar_info_colecao)
        g.addWidget(self.cb_colecao, 0, 1, 1, 3)

        self.lbl_col_info = QLabel("")
        self.lbl_col_info.setStyleSheet(
            "color:#555;font-size:10px;font-style:italic;")
        g.addWidget(self.lbl_col_info, 1, 1, 1, 3)

        g.addWidget(QLabel("Raster Ano 1:"), 2, 0)
        self.cb_r1 = QgsMapLayerComboBox()
        self.cb_r1.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cb_r1.layerChanged.connect(self._verificar_crs)
        g.addWidget(self.cb_r1, 2, 1, 1, 2)
        self.le_ano1 = QLineEdit("1985")
        self.le_ano1.setFixedWidth(60)
        g.addWidget(self.le_ano1, 2, 3)

        g.addWidget(QLabel("Raster Ano 2:"), 3, 0)
        self.cb_r2 = QgsMapLayerComboBox()
        self.cb_r2.setFilters(QgsMapLayerProxyModel.RasterLayer)
        g.addWidget(self.cb_r2, 3, 1, 1, 2)
        self.le_ano2 = QLineEdit("2024")
        self.le_ano2.setFixedWidth(60)
        g.addWidget(self.le_ano2, 3, 3)

        # Aviso CRS
        self.lbl_crs = QLabel("")
        self.lbl_crs.setStyleSheet(
            "color:#BF360C;font-size:10px;font-weight:bold;")
        self.lbl_crs.setWordWrap(True)
        self.lbl_crs.setVisible(False)
        g.addWidget(self.lbl_crs, 4, 0, 1, 4)

        g.setColumnStretch(1, 1)
        self._atualizar_info_colecao(0)
        return grp

    def _atualizar_info_colecao(self, idx=None):
        nome = self.cb_colecao.currentText()
        info = COLECOES.get(nome, {})
        self.lbl_col_info.setText(info.get('descricao', ''))
        # Atualizar níveis disponíveis conforme a coleção
        nivel_max = info.get('nivel_max', 4)
        if hasattr(self, 'cb_nivel'):
            self._popular_niveis(nivel_max)

    def _verificar_crs(self, layer):
        """Verifica CRS do raster e adapta opções de unidade."""
        if layer is None:
            return
        try:
            from .processamento import detectar_crs
            info = detectar_crs(layer.source())
            self._is_projected = info['is_projected']
            if not info['is_projected']:
                col  = COLECOES.get(self.cb_colecao.currentText(), {})
                res  = col.get('resolucao_m', 30)
                px   = col.get('px_m2', 900)
                self.lbl_crs.setText(
                    f"⚠ Raster sem coordenadas projetadas (unidade em graus). "
                    f"Áreas calculadas com pixel padrão de {res}m × {res}m "
                    f"({px} m²). As unidades ha e km² são estimativas; "
                    f"o percentual é o dado mais confiável.")
                self.lbl_crs.setVisible(True)
                # Forçar percentual
                self.cb_unidade.setCurrentIndex(
                    self.cb_unidade.findText('Apenas percentual'))
                self.cb_unidade.setEnabled(False)
            else:
                self.lbl_crs.setVisible(False)
                self.cb_unidade.setEnabled(True)
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"AnP: verificacao de CRS ignorada ({e})", "AnP", Qgis.Info)

    def _bloco_feicoes(self):
        grp = QGroupBox("2. Desagregação por feições (opcional)")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        self.chk_feicoes = QCheckBox(
            "Desagregar resultados por feição de um shapefile")
        self.chk_feicoes.setChecked(False)
        self.chk_feicoes.toggled.connect(self._toggle_feicoes)
        g.addWidget(self.chk_feicoes, 0, 0, 1, 3)

        self.lbl_mask = QLabel("Shape de unidades:")
        self.lbl_mask.setEnabled(False)
        g.addWidget(self.lbl_mask, 1, 0)
        self.cb_mask = QgsMapLayerComboBox()
        self.cb_mask.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_mask.setEnabled(False)
        g.addWidget(self.cb_mask, 1, 1, 1, 2)

        self.lbl_campo = QLabel("Campo identificador:")
        self.lbl_campo.setEnabled(False)
        g.addWidget(self.lbl_campo, 2, 0)
        self.cb_campo = QgsFieldComboBox()
        self.cb_campo.setEnabled(False)
        g.addWidget(self.cb_campo, 2, 1, 1, 2)
        self.cb_mask.layerChanged.connect(
            lambda lyr: self.cb_campo.setLayer(lyr)
            if self.chk_feicoes.isChecked() else None)

        g.setColumnStretch(2, 1)
        return grp

    def _toggle_feicoes(self, on):
        """Habilita/desabilita campos de feição conforme checkbox."""
        for w in [self.lbl_mask, self.cb_mask,
                  self.lbl_campo, self.cb_campo]:
            w.setEnabled(on)
        if on and self.cb_mask.currentLayer():
            self.cb_campo.setLayer(self.cb_mask.currentLayer())

    def _bloco_config(self):
        grp = QGroupBox("3. Configurações")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(8)

        # Nível de legenda
        g.addWidget(QLabel("Nível de legenda:"), 0, 0)
        self.cb_nivel = QComboBox()
        self.cb_nivel.currentIndexChanged.connect(self._atualizar_nivel_info)
        g.addWidget(self.cb_nivel, 0, 1)

        self.lbl_nivel_info = QLabel("")
        self.lbl_nivel_info.setStyleSheet(
            "color:#555;font-size:10px;font-style:italic;")
        self.lbl_nivel_info.setWordWrap(True)
        g.addWidget(self.lbl_nivel_info, 1, 0, 1, 3)

        # Unidade de área
        g.addWidget(QLabel("Unidade de saída:"), 2, 0)
        self.cb_unidade = QComboBox()
        self.cb_unidade.addItems([
            "Hectares (ha)",
            "Quilômetros quadrados (km²)",
            "Hectares e km²",
            "Apenas percentual",
        ])
        g.addWidget(self.cb_unidade, 2, 1)
        g.setColumnStretch(2, 1)

        self._popular_niveis(4)  # padrão nível 4
        return grp

    def _popular_niveis(self, nivel_max=4):
        """Popula o ComboBox de nível conforme a coleção selecionada."""
        from ..comum.legenda import descricao_nivel
        self.cb_nivel.blockSignals(True)
        self.cb_nivel.clear()
        for n in range(1, nivel_max + 1):
            self.cb_nivel.addItem(descricao_nivel(n), n)
        self.cb_nivel.setCurrentIndex(nivel_max - 1)  # default = máximo
        self.cb_nivel.blockSignals(False)
        self._atualizar_nivel_info(nivel_max - 1)

    def _atualizar_nivel_info(self, idx):
        nivel = self.cb_nivel.itemData(idx)
        if nivel is None:
            return
        msgs = {
            1: "Comparação de grandes grupos — ideal para visão geral.",
            2: "Nível recomendado para comparar Landsat e Sentinel.",
            3: "Desagrega lavouras temporárias e perenes.",
            4: "Máximo detalhe — culturas específicas (Soja, Cana, Café…).",
        }
        self.lbl_nivel_info.setText(msgs.get(nivel, ""))

    def _bloco_saida(self):
        grp = QGroupBox("4. Pasta de saída")
        grp.setStyleSheet(self._grp())
        lay_v = QVBoxLayout(grp); lay_v.setSpacing(6)

        lay = QHBoxLayout(); lay.setSpacing(6)
        self.le_pasta = QLineEdit()
        self.le_pasta.setPlaceholderText(
            "Selecione a pasta onde os arquivos serão salvos...")
        lay.addWidget(self.le_pasta)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_pasta)
        lay.addWidget(btn)
        lay_v.addLayout(lay)

        self.chk_mud_codigos = QCheckBox(
            "Raster de mudança com códigos originais das classes "
            "(ex: identificar Soja→Cana especificamente)")
        self.chk_mud_codigos.setChecked(True)
        lay_v.addWidget(self.chk_mud_codigos)

        self.chk_mud_categorias = QCheckBox(
            "Raster de mudança por categoria ecológica "
            "(6 categorias: natural↔antrópico)")
        self.chk_mud_categorias.setChecked(True)
        lay_v.addWidget(self.chk_mud_categorias)

        return grp

    def _escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(
            self, 'Selecionar pasta de saída',
            self.le_pasta.text() or os.path.expanduser('~'))
        if pasta:
            self.le_pasta.setText(pasta)

    def _bloco_log(self):
        grp = QGroupBox("Log de processamento")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(130)
        self.log_box.setFont(QFont("Courier New", 9))
        lay.addWidget(self.log_box)
        self.prog = QProgressBar()
        self.prog.setRange(0, 0); self.prog.setVisible(False)
        lay.addWidget(self.prog)
        return grp

    def _barra_botoes(self):
        lay = QHBoxLayout()
        btn_lim = QPushButton("Limpar log")
        btn_lim.clicked.connect(self.log_box.clear)
        lay.addWidget(btn_lim)
        lay.addStretch()
        btn_f = QPushButton("Fechar")
        btn_f.clicked.connect(self.close)
        lay.addWidget(btn_f)
        self.btn_exec = QPushButton("▶  Calcular")
        self.btn_exec.setDefault(True)
        self.btn_exec.setStyleSheet(
            "QPushButton{background:#1B5E20;color:white;font-weight:bold;"
            "padding:8px 24px;border-radius:5px;}"
            "QPushButton:hover{background:#2E7D32;}"
            "QPushButton:disabled{background:#AAAAAA;}")
        self.btn_exec.clicked.connect(self._executar)
        lay.addWidget(self.btn_exec)
        return lay

    # ── Lógica ──────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    def _modo(self):
        txt = self.cb_unidade.currentText()
        if 'km²' in txt and 'Hectare' in txt: return 'ha_km2_pct'
        if 'km²' in txt:  return 'km2'
        if 'percent' in txt.lower(): return 'pct'
        return 'ha'

    def _validar(self):
        erros = []
        if not self.cb_r1.currentLayer():
            erros.append("Selecione o raster do Ano 1.")
        if not self.cb_r2.currentLayer():
            erros.append("Selecione o raster do Ano 2.")
        elif (self.cb_r1.currentLayer() and
              self.cb_r1.currentLayer().source() == self.cb_r2.currentLayer().source()):
            erros.append("O raster do Ano 1 e o do Ano 2 são o mesmo arquivo — "
                         "selecione rasters de anos diferentes.")
        if self.le_ano1.text().strip() == self.le_ano2.text().strip():
            erros.append("O Ano 1 e o Ano 2 são iguais.")
        if not self.le_ano1.text().strip().isdigit():
            erros.append("Informe um ano válido para o Ano 1.")
        if not self.le_ano2.text().strip().isdigit():
            erros.append("Informe um ano válido para o Ano 2.")
        if not self.le_pasta.text().strip():
            erros.append("Selecione a pasta de saída.")
        elif not os.path.isdir(self.le_pasta.text().strip()):
            erros.append("A pasta de saída não existe.")
        if self.chk_feicoes.isChecked():
            if not self.cb_mask.currentLayer():
                erros.append("Desagregação ativada: selecione o shape de unidades.")
            elif not self.cb_campo.currentField():
                erros.append("Desagregação ativada: selecione o campo identificador.")
        return erros

    def _executar(self):
        erros = self._validar()
        if erros:
            QMessageBox.warning(self, 'AnP — Campos incompletos',
                                '\n'.join(f'• {e}' for e in erros))
            return

        mask = self.cb_mask.currentLayer()
        use_f = self.chk_feicoes.isChecked() and mask

        params = {
            'raster1'     : self.cb_r1.currentLayer().source(),
            'raster2'     : self.cb_r2.currentLayer().source(),
            'ano1'        : int(self.le_ano1.text().strip()),
            'ano2'        : int(self.le_ano2.text().strip()),
            'colecao'     : self.cb_colecao.currentText(),
            'mascara_path': mask.source().split('|')[0] if use_f else None,
            'campo_feicao': self.cb_campo.currentField() if use_f else None,
            'nivel'       : self.cb_nivel.itemData(self.cb_nivel.currentIndex()) or 4,
            'modo'        : self._modo(),
            'pasta_saida' : self.le_pasta.text().strip(),
            'gerar_mudanca_codigos'   : self.chk_mud_codigos.isChecked(),
            'gerar_mudanca_categorias': self.chk_mud_categorias.isChecked(),
        }

        self.btn_exec.setEnabled(False)
        self.prog.setVisible(True)
        self.log_box.clear()
        self._log("Iniciando processamento...")

        self._worker = _Worker(params)
        self._worker.progresso.connect(self._log)
        self._worker.concluido.connect(self._concluido)
        self._worker.erro.connect(self._erro)
        self._worker.start()

    def _concluido(self, arquivos):
        self.prog.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log("\n✓ Processamento concluído!")
        for a in arquivos:
            self._log(f"  → {a}")

        resp = QMessageBox.question(
            self, 'AnP — Concluído',
            'Arquivos gerados com sucesso!\n\n'
            + '\n'.join(os.path.basename(a) for a in arquivos)
            + '\n\nDeseja abrir a pasta de saída?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

        if resp == QMessageBox.Yes:
            from qgis.PyQt.QtGui import QDesktopServices
            from qgis.PyQt.QtCore import QUrl
            pasta = os.path.dirname(arquivos[0])
            QDesktopServices.openUrl(QUrl.fromLocalFile(pasta))

    def _erro(self, msg):
        self.prog.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log(f"\n⚠ ERRO:\n{msg}")
        QMessageBox.critical(self, 'AnP — Erro', msg[:400])
