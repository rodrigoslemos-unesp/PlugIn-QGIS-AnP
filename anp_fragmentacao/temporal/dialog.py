"""AnP Fragmentação — Interface principal v1.1"""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QLineEdit, QFileDialog, QTextEdit,
    QMessageBox, QProgressBar, QFrame, QSpinBox)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QFont
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel
from ..comum.legenda import COLECOES, info_borda
from ..comum.metadados import VERSAO_SUITE


class _Worker(QThread):
    progresso = pyqtSignal(str)
    concluido = pyqtSignal(object)
    erro      = pyqtSignal(str)

    def __init__(self, params):
        super().__init__(); self._p = params

    def run(self):
        try:
            from .processamento import processar_completo
            from .excel_saida   import exportar
            from .raster_nucleo import gerar_rasters_nucleo

            resultado = processar_completo(
                raster1      = self._p['raster1'],
                raster2      = self._p['raster2'],
                ano1         = self._p['ano1'],
                ano2         = self._p['ano2'],
                n_pixels_borda = self._p['n_pixels'],
                grupos_ids     = self._p.get('grupos_ids'),
                mascara_path = self._p.get('mascara_path'),
                campo_feicao = self._p.get('campo_feicao'),
                pixel_m_manual = self._p.get('pixel_m_manual'),
                classes_porte  = self._p.get('classes_porte'),
                progresso_fn = self.progresso.emit,
            )

            self.progresso.emit("Exportando Excel...")
            arquivos = exportar(
                resultado    = resultado,
                pasta        = self._p['pasta'],
                ano1         = self._p['ano1'],
                ano2         = self._p['ano2'],
                progresso_fn = self.progresso.emit,
            )

            self.progresso.emit("Gerando rasters de área núcleo...")
            arqs_r = gerar_rasters_nucleo(
                resultado    = resultado,
                pasta        = self._p['pasta'],
                ano1         = self._p['ano1'],
                ano2         = self._p['ano2'],
                grupos_ids   = self._p.get('grupos_ids'),
                progresso_fn = self.progresso.emit,
            )

            arqs_p = []
            if self._p.get('gerar_porte', True):
                self.progresso.emit(
                    "Gerando rasters classificados por porte (fragmento total + núcleo)...")
                from .raster_porte import gerar_rasters_porte
                arqs_p = gerar_rasters_porte(
                    resultado    = resultado,
                    pasta        = self._p['pasta'],
                    ano1         = self._p['ano1'],
                    ano2         = self._p['ano2'],
                    grupos_ids   = self._p.get('grupos_ids'),
                    classes_porte = resultado.get('_meta', {}).get('classes_porte'),
                    progresso_fn = self.progresso.emit,
                )

            self.concluido.emit(arquivos + arqs_r + arqs_p)

        except Exception as e:
            import traceback
            self.erro.emit(str(e) + '\n' + traceback.format_exc())


class AnPFragmentacaoDialog(QDialog):

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface; self._worker = None
        self.setWindowTitle(f'AnP — Fragmentação e Conectividade  v{VERSAO_SUITE}')
        self.setMinimumWidth(760)
        self._build_ui()

    # ── Interface ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10); root.setContentsMargins(12,12,12,12)
        root.addWidget(self._header())
        root.addWidget(self._bloco_rasters())
        root.addWidget(self._bloco_borda())
        root.addWidget(self._bloco_grupos())
        root.addWidget(self._bloco_feicoes())
        root.addWidget(self._bloco_saida())
        root.addWidget(self._bloco_log())
        root.addLayout(self._barra_botoes())
        # Inicializar display de borda APÓS todos os widgets criados
        self._atualizar_borda_info()

    def _header(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background-color:#1A237E;border-radius:8px;}")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16,10,16,10); lay.setSpacing(14)
        logo = os.path.join(os.path.dirname(__file__), 'unesp_logo.png')
        if os.path.exists(logo):
            lbl = QLabel()
            pix = QPixmap(logo).scaledToHeight(60, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            lbl.setStyleSheet("background:white;border-radius:5px;padding:4px;")
            lbl.setFixedSize(pix.width()+10, 70)
            lay.addWidget(lbl)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#283593;"); lay.addWidget(sep)
        txt = QVBoxLayout(); txt.setSpacing(3)
        txt.setAlignment(Qt.AlignVCenter)
        t1 = QLabel("AnP — Fragmentação e Conectividade da Paisagem")
        t1.setStyleSheet("color:white;font-size:15px;font-weight:bold;"
                         "background:transparent;")
        txt.addWidget(t1)
        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color:#283593;"); txt.addWidget(div)
        t2 = QLabel("Grupo de Pesquisa: Planejamento Ambiental e Dinâmicas "
                    "da Paisagem  •  DGPA / IGCE — Unesp Rio Claro")
        t2.setStyleSheet("color:#C5CAE9;font-size:10px;font-style:italic;"
                         "background:transparent;")
        t2.setWordWrap(True); txt.addWidget(t2)
        t3 = QLabel("Prof. Dr. Rodrigo Silva Lemos  •  "
                    f"rodrigo.s.lemos@unesp.br  •  AnP v{VERSAO_SUITE}")
        t3.setStyleSheet("color:#9FA8DA;font-size:10px;background:transparent;")
        txt.addWidget(t3)
        lay.addLayout(txt, 1); return frame

    def _grp(self):
        return ("QGroupBox{font-weight:bold;font-size:11px;"
                "border:1px solid #CCCCCC;border-radius:5px;"
                "margin-top:8px;padding-top:4px;}"
                "QGroupBox::title{subcontrol-origin:margin;"
                "left:8px;padding:0 4px;}")

    def _bloco_rasters(self):
        grp = QGroupBox("1. Rasters MapBiomas"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        g.addWidget(QLabel("Coleção / Sensor:"), 0, 0)
        self.cb_col = QComboBox()
        self.cb_col.addItems(list(COLECOES.keys()))
        self.cb_col.currentIndexChanged.connect(self._atualizar_borda_info)
        g.addWidget(self.cb_col, 0, 1, 1, 3)

        self.lbl_col = QLabel("")
        self.lbl_col.setStyleSheet("color:#555;font-size:10px;font-style:italic;")
        g.addWidget(self.lbl_col, 1, 1, 1, 3)

        g.addWidget(QLabel("Raster Ano 1:"), 2, 0)
        self.cb_r1 = QgsMapLayerComboBox()
        self.cb_r1.setFilters(QgsMapLayerProxyModel.RasterLayer)
        g.addWidget(self.cb_r1, 2, 1, 1, 2)
        self.le_ano1 = QLineEdit("1985"); self.le_ano1.setFixedWidth(60)
        g.addWidget(self.le_ano1, 2, 3)

        g.addWidget(QLabel("Raster Ano 2:"), 3, 0)
        self.cb_r2 = QgsMapLayerComboBox()
        self.cb_r2.setFilters(QgsMapLayerProxyModel.RasterLayer)
        g.addWidget(self.cb_r2, 3, 1, 1, 2)
        self.le_ano2 = QLineEdit("2024"); self.le_ano2.setFixedWidth(60)
        g.addWidget(self.le_ano2, 3, 3)

        g.setColumnStretch(1, 1)
        return grp

    def _bloco_borda(self):
        grp = QGroupBox("2. Distância de borda (área núcleo)")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(8)

        g.addWidget(QLabel("Distância em pixels:"), 0, 0)
        self.sb_pixels = QSpinBox()
        self.sb_pixels.setMinimum(1); self.sb_pixels.setMaximum(50)
        self.sb_pixels.setValue(3)
        self.sb_pixels.valueChanged.connect(self._atualizar_borda_info)
        self.sb_pixels.setFixedWidth(70)
        g.addWidget(self.sb_pixels, 0, 1)

        self.lbl_borda = QLabel("")
        self.lbl_borda.setStyleSheet(
            "color:#1A237E;font-size:10px;font-weight:bold;")
        self.lbl_borda.setWordWrap(True)
        g.addWidget(self.lbl_borda, 1, 0, 1, 4)

        self.lbl_aviso_borda = QLabel(
            "ℹ  Para comparar Landsat e Sentinel usando a mesma distância "
            "real em metros, o número de pixels deve ser diferente entre as duas coleções.")
        self.lbl_aviso_borda.setStyleSheet(
            "color:#555;font-size:10px;font-style:italic;")
        self.lbl_aviso_borda.setWordWrap(True)
        g.addWidget(self.lbl_aviso_borda, 2, 0, 1, 4)
        g.setColumnStretch(3, 1)
        return grp

    def _atualizar_borda_info(self):
        nome = self.cb_col.currentText()
        info = COLECOES.get(nome, {})
        res  = info.get('resolucao_m', 30)
        n    = self.sb_pixels.value() if hasattr(self, 'sb_pixels') else 3
        self.lbl_col.setText(info.get('descricao',''))
        dist_m, equiv = info_borda(res, n)
        linhas = [f"→  {n} pixel(s) × {res}m = <b>{dist_m}m</b> de distância de borda"]
        for nome_c, px_equiv in equiv.items():
            linhas.append(
                f"     equivale a <b>{px_equiv:.1f} pixel(s)</b> em {nome_c}")
        self.lbl_borda.setText("  |  ".join(linhas))

    def _bloco_grupos(self):
        from ..comum.legenda import GRUPOS_FRAG
        grp = QGroupBox("3. Grupos de cobertura a analisar")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp); lay.setSpacing(8)

        info = QLabel(
            "Análise restrita à cobertura NATURAL (Floresta e Vegetação "
            "Herbácea). Corpos d'água não são analisados neste módulo.")
        info.setStyleSheet("font-size:10px;font-style:italic;color:#555;")
        info.setWordWrap(True)
        lay.addWidget(info)

        row = QHBoxLayout()
        self._chk_grupos = {}
        for g in GRUPOS_FRAG:
            chk = QCheckBox(g['nome'])
            chk.setChecked(True)   # todos marcados por padrão
            chk.setProperty('grupo_id', g['id'])
            row.addWidget(chk)
            self._chk_grupos[g['id']] = chk
        row.addStretch()
        lay.addLayout(row)

        self.chk_porte = QCheckBox(
            "Gerar rasters classificados por porte de fragmento "
            "(fragmento total + área núcleo)")
        self.chk_porte.setChecked(True)
        lay.addWidget(self.chk_porte)

        # ── Limiares de tamanho — configuráveis por bioma/escala ────────────
        from .raster_porte import PRESETS_PORTE
        row_porte = QHBoxLayout()
        row_porte.addWidget(QLabel("Escala de tamanhos:"))
        self.cb_preset_porte = QComboBox()
        for nome_preset in PRESETS_PORTE.keys():
            self.cb_preset_porte.addItem(nome_preset)
        self.cb_preset_porte.addItem("Personalizado (informar abaixo)")
        self.cb_preset_porte.currentIndexChanged.connect(
            self._atualizar_preset_porte)
        row_porte.addWidget(self.cb_preset_porte)
        row_porte.addStretch()
        lay.addLayout(row_porte)

        info_porte = QLabel(
            "O limiar de \"fragmento grande\" varia muito por bioma: 200 ha "
            "já é grande na Mata Atlântica fragmentada de SP, mas é "
            "minúsculo diante dos blocos contínuos da Amazônia. Escolha a "
            "escala mais adequada à área analisada, ou digite pontos de "
            "corte próprios (em hectares, separados por vírgula).")
        info_porte.setStyleSheet("font-size:10px;color:#666;font-style:italic;")
        info_porte.setWordWrap(True)
        lay.addWidget(info_porte)

        row_custom = QHBoxLayout()
        row_custom.addWidget(QLabel("Pontos de corte (ha):"))
        self.le_pontos_porte = QLineEdit()
        self.le_pontos_porte.setPlaceholderText(
            "ex: 1, 10, 20, 30, 50, 100, 200")
        self.le_pontos_porte.setEnabled(False)
        row_custom.addWidget(self.le_pontos_porte)
        lay.addLayout(row_custom)

        self.lbl_preview_porte = QLabel("")
        self.lbl_preview_porte.setStyleSheet(
            "font-size:9px;color:#1B5E20;font-family:Courier New;")
        self.lbl_preview_porte.setWordWrap(True)
        lay.addWidget(self.lbl_preview_porte)
        self.le_pontos_porte.textChanged.connect(self._atualizar_preview_custom)
        self._atualizar_preset_porte(0)

        return grp

    def _atualizar_preset_porte(self, idx):
        from .raster_porte import PRESETS_PORTE, construir_classes_porte
        nomes = list(PRESETS_PORTE.keys())
        personalizado = (idx == len(nomes))
        self.le_pontos_porte.setEnabled(personalizado)

        if personalizado:
            self.lbl_preview_porte.setText(
                "→ digite os pontos de corte acima para ver o preview")
            return

        pontos = PRESETS_PORTE[nomes[idx]]
        self.le_pontos_porte.setText(", ".join(str(p) for p in pontos))
        classes = construir_classes_porte(pontos)
        rotulos = " · ".join(c[3] for c in classes)
        self.lbl_preview_porte.setText(f"→ {rotulos}")

    def _atualizar_preview_custom(self):
        if not self.le_pontos_porte.isEnabled():
            return
        from .raster_porte import construir_classes_porte
        pontos = self._pontos_corte_ativos()
        if not pontos:
            self.lbl_preview_porte.setText("→ pontos de corte inválidos")
            return
        classes = construir_classes_porte(pontos)
        rotulos = " · ".join(c[3] for c in classes)
        self.lbl_preview_porte.setText(f"→ {rotulos}")

    def _pontos_corte_ativos(self):
        """Lê e valida os pontos de corte digitados/selecionados (ha)."""
        txt = self.le_pontos_porte.text().strip()
        if not txt:
            return None
        try:
            pontos = [float(item.strip()) for item in txt.split(",")
                     if item.strip()]
            pontos = sorted(set(p for p in pontos if p > 0))
            return pontos if pontos else None
        except ValueError:
            return None

    def _bloco_feicoes(self):
        grp = QGroupBox("4. Desagregação por feições (opcional)")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        self.chk_f = QCheckBox("Desagregar resultados por feição do shapefile")
        self.chk_f.setChecked(False)
        self.chk_f.toggled.connect(self._toggle_f)
        g.addWidget(self.chk_f, 0, 0, 1, 3)

        self.lbl_mask = QLabel("Shape de unidades:"); self.lbl_mask.setEnabled(False)
        g.addWidget(self.lbl_mask, 1, 0)
        self.cb_mask = QgsMapLayerComboBox()
        self.cb_mask.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_mask.setEnabled(False)
        g.addWidget(self.cb_mask, 1, 1, 1, 2)

        self.lbl_campo = QLabel("Campo identificador:"); self.lbl_campo.setEnabled(False)
        g.addWidget(self.lbl_campo, 2, 0)
        self.cb_campo = QgsFieldComboBox(); self.cb_campo.setEnabled(False)
        g.addWidget(self.cb_campo, 2, 1, 1, 2)
        self.cb_mask.layerChanged.connect(
            lambda lyr: self.cb_campo.setLayer(lyr)
            if self.chk_f.isChecked() else None)
        g.setColumnStretch(2, 1); return grp

    def _toggle_f(self, on):
        for w in [self.lbl_mask, self.cb_mask,
                  self.lbl_campo, self.cb_campo]:
            w.setEnabled(on)
        if on and self.cb_mask.currentLayer():
            self.cb_campo.setLayer(self.cb_mask.currentLayer())

    def _bloco_saida(self):
        grp = QGroupBox("5. Pasta de saída"); grp.setStyleSheet(self._grp())
        lay = QHBoxLayout(grp); lay.setSpacing(6)
        self.le_pasta = QLineEdit()
        self.le_pasta.setPlaceholderText(
            "Selecione a pasta onde os arquivos serão salvos...")
        lay.addWidget(self.le_pasta)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_pasta); lay.addWidget(btn)
        return grp

    def _escolher_pasta(self):
        p = QFileDialog.getExistingDirectory(
            self, 'Pasta de saída',
            self.le_pasta.text() or os.path.expanduser('~'))
        if p: self.le_pasta.setText(p)

    def _bloco_log(self):
        grp = QGroupBox("Log de processamento"); grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True); self.log_box.setMaximumHeight(130)
        self.log_box.setFont(QFont("Courier New", 9)); lay.addWidget(self.log_box)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0,0); self.prog_bar.setVisible(False)
        lay.addWidget(self.prog_bar); return grp

    def _barra_botoes(self):
        lay = QHBoxLayout()
        btn_l = QPushButton("Limpar log"); btn_l.clicked.connect(self.log_box.clear)
        lay.addWidget(btn_l); lay.addStretch()
        btn_f = QPushButton("Fechar"); btn_f.clicked.connect(self.close)
        lay.addWidget(btn_f)
        self.btn_exec = QPushButton("▶  Calcular")
        self.btn_exec.setDefault(True)
        self.btn_exec.setStyleSheet(
            "QPushButton{background:#1A237E;color:white;font-weight:bold;"
            "padding:8px 24px;border-radius:5px;}"
            "QPushButton:hover{background:#283593;}"
            "QPushButton:disabled{background:#AAAAAA;}")
        self.btn_exec.clicked.connect(self._executar); lay.addWidget(self.btn_exec)
        return lay

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    def _validar(self):
        erros = []
        if not self.cb_r1.currentLayer():
            erros.append("Selecione o raster do Ano 1.")
        if not self.cb_r2.currentLayer():
            erros.append("Selecione o raster do Ano 2.")
        if not self.le_ano1.text().strip().isdigit():
            erros.append("Informe um ano válido para o Ano 1.")
        if not self.le_ano2.text().strip().isdigit():
            erros.append("Informe um ano válido para o Ano 2.")
        if not self.le_pasta.text().strip():
            erros.append("Selecione a pasta de saída.")
        elif not os.path.isdir(self.le_pasta.text().strip()):
            erros.append("A pasta de saída não existe.")
        if self.chk_f.isChecked():
            if not self.cb_mask.currentLayer():
                erros.append("Selecione o shape de unidades.")
            elif not self.cb_campo.currentField():
                erros.append("Selecione o campo identificador.")
        return erros

    def _executar(self):
        erros = self._validar()
        if erros:
            QMessageBox.warning(self, 'AnP — Campos incompletos',
                                '\n'.join(f'• {e}' for e in erros))
            return

        mask = self.cb_mask.currentLayer()
        use_f = self.chk_f.isChecked() and mask

        classes_porte = None
        pontos = self._pontos_corte_ativos()
        if pontos:
            from .raster_porte import construir_classes_porte
            classes_porte = construir_classes_porte(pontos)

        params = {
            'raster1'     : self.cb_r1.currentLayer().source(),
            'raster2'     : self.cb_r2.currentLayer().source(),
            'ano1'        : int(self.le_ano1.text()),
            'ano2'        : int(self.le_ano2.text()),
            'n_pixels'    : self.sb_pixels.value(),
            'grupos_ids'  : [gid for gid, chk in self._chk_grupos.items()
                             if chk.isChecked()],
            'mascara_path': mask.source().split('|')[0] if use_f else None,
            'campo_feicao': self.cb_campo.currentField() if use_f else None,
            'pasta'       : self.le_pasta.text().strip(),
            'gerar_porte' : self.chk_porte.isChecked(),
            'classes_porte': classes_porte,
        }
        self.btn_exec.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.log_box.clear(); self._log("Iniciando processamento...")

        self._worker = _Worker(params)
        self._worker.progresso.connect(self._log)
        self._worker.concluido.connect(self._concluido)
        self._worker.erro.connect(self._erro)
        self._worker.start()

    def _concluido(self, arquivos):
        self.prog_bar.setVisible(False); self.btn_exec.setEnabled(True)
        self._log("\n✓ Concluído!")
        for a in arquivos:
            self._log(f"  → {a}")

        resp = QMessageBox.question(
            self, 'AnP — Concluído',
            'Processamento concluído!\n\n'
            + '\n'.join(os.path.basename(a) for a in arquivos
                        if not a.endswith('.qml'))
            + '\n\nAbrir a pasta de saída?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

        if resp == QMessageBox.Yes:
            import subprocess, sys
            pasta = os.path.dirname(arquivos[0])
            if sys.platform == 'win32':
                os.startfile(pasta)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', pasta])
            else:
                subprocess.Popen(['xdg-open', pasta])

    def _erro(self, msg):
        self.prog_bar.setVisible(False); self.btn_exec.setEnabled(True)
        self._log(f"\n⚠ ERRO:\n{msg}")
        QMessageBox.critical(self, 'AnP — Erro', msg[:400])
