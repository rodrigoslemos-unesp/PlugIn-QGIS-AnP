"""AnP — Relatório de Cobertura da Terra v1.1 — Interface"""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QLineEdit, QFileDialog, QTextEdit,
    QMessageBox, QProgressBar, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget, QScrollArea,
    QAbstractItemView, QDoubleSpinBox)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QFont, QColor
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel

from ..comum.metadados import VERSAO_SUITE


class _Worker(QThread):
    progresso = pyqtSignal(str)
    concluido = pyqtSignal(str)
    erro      = pyqtSignal(str)

    def __init__(self, params):
        super().__init__(); self._p = params

    def run(self):
        try:
            from .processamento import processar_relatorio
            from .excel_saida   import exportar
            resultado = processar_relatorio(
                entradas        = self._p['entradas'],
                shapefile       = self._p.get('shapefile'),
                campo_id        = self._p.get('campo_id'),
                pixel_m_manual  = self._p.get('pixel_m'),
                gerar_tif       = self._p.get('gerar_tif', True),
                pasta_tif       = self._p['pasta'],
                progresso_fn    = self.progresso.emit,
            )
            arq = exportar(
                resultado    = resultado,
                pasta        = self._p['pasta'],
                nome_base    = self._p['nome_base'],
                progresso_fn = self.progresso.emit,
            )
            self.concluido.emit(arq)
        except Exception as e:
            import traceback
            self.erro.emit(str(e) + '\n' + traceback.format_exc())


class AnPRelatorioDialog(QDialog):

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface; self._worker = None
        self.setWindowTitle(f'AnP — Relatório de Cobertura da Terra  v{VERSAO_SUITE}')
        self.setMinimumWidth(800); self.setMinimumHeight(500)
        self.resize(860, 720); self.setSizeGripEnabled(True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        root.addWidget(self._header())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo)
        lay.setSpacing(10); lay.setContentsMargins(12,10,12,10)

        def sec(t):
            return self._sec_label(t)
        lay.addWidget(sec("1. Rasters MapBiomas — múltiplos anos"))
        lay.addWidget(self._bloco_rasters())
        lay.addWidget(sec("2. Desagregação por feições (opcional)"))
        lay.addWidget(self._bloco_feicoes())
        lay.addWidget(sec("3. Saída"))
        lay.addWidget(self._bloco_saida())
        lay.addWidget(self._bloco_log())
        lay.addStretch()
        scroll.setWidget(conteudo)
        root.addWidget(scroll, 1)

        barra = QWidget()
        barra.setStyleSheet("background:#F5F5F5;border-top:1px solid #CCCCCC;")
        bl = QHBoxLayout(barra); bl.setContentsMargins(12,8,12,8)
        btn_l = QPushButton("Limpar log"); btn_l.clicked.connect(self.log_box.clear)
        bl.addWidget(btn_l)
        btn_r = QPushButton("Resetar"); btn_r.clicked.connect(self._resetar)
        btn_r.setToolTip("Limpa todas as entradas e volta o formulário ao estado inicial.")
        bl.addWidget(btn_r)
        bl.addStretch()
        btn_f = QPushButton("Fechar"); btn_f.clicked.connect(self.close)
        bl.addWidget(btn_f)
        self.btn_exec = QPushButton("▶  Gerar Relatório")
        self.btn_exec.setDefault(True)
        self.btn_exec.setStyleSheet(
            "QPushButton{background:#1B5E20;color:white;font-weight:bold;"
            "padding:8px 24px;border-radius:5px;}"
            "QPushButton:hover{background:#2E7D32;}"
            "QPushButton:disabled{background:#AAAAAA;}")
        self.btn_exec.clicked.connect(self._executar)
        bl.addWidget(self.btn_exec)
        root.addWidget(barra)

    def _sec_label(self, txt):
        lbl = QLabel(f"  {txt}")
        lbl.setStyleSheet(
            "background:#1B5E20;color:white;font-weight:bold;"
            "font-size:12px;padding:6px;border-radius:4px;")
        return lbl

    def _header(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame{background-color:#1B5E20;}")
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
        txt = QVBoxLayout(); txt.setSpacing(3); txt.setAlignment(Qt.AlignVCenter)
        t1 = QLabel("AnP — Relatório de Cobertura da Terra")
        t1.setStyleSheet("color:white;font-size:15px;font-weight:bold;background:transparent;")
        txt.addWidget(t1)
        t2 = QLabel("Múltiplos anos · Todos os níveis N1–N4 · Planilha única tidy · Todos os níveis em colunas · Paleta oficial MapBiomas C10")
        t2.setStyleSheet("color:#A5D6A7;font-size:10px;font-style:italic;background:transparent;")
        t2.setWordWrap(True); txt.addWidget(t2)
        t3 = QLabel(f"Prof. Dr. Rodrigo Silva Lemos  ·  DGPA/IGCE — Unesp Rio Claro  ·  AnP v{VERSAO_SUITE}")
        t3.setStyleSheet("color:#81C784;font-size:10px;background:transparent;")
        txt.addWidget(t3)
        lay.addLayout(txt, 1); return frame

    def _grp(self):
        return ("QGroupBox{font-weight:bold;font-size:11px;"
                "border:1px solid #CCCCCC;border-radius:5px;"
                "margin-top:8px;padding-top:4px;}"
                "QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px;}")

    # ── Bloco rasters ─────────────────────────────────────────────────────────

    def _bloco_rasters(self):
        grp = QGroupBox("Rasters e anos"); grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp); lay.setSpacing(6)

        # Modo projeto ou pasta
        self.chk_projeto = QCheckBox(
            "Usar camadas raster já carregadas no projeto QGIS")
        self.chk_projeto.toggled.connect(self._toggle_modo)
        lay.addWidget(self.chk_projeto)

        self.frame_proj = QFrame()
        fp = QHBoxLayout(self.frame_proj); fp.setContentsMargins(0,0,0,0)
        fp.addWidget(QLabel("Adicionar camada:"))
        self.cb_raster = QgsMapLayerComboBox()
        self.cb_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cb_raster.setAllowEmptyLayer(True)
        fp.addWidget(self.cb_raster)
        btn_add = QPushButton("+ Adicionar"); btn_add.clicked.connect(self._add_projeto)
        fp.addWidget(btn_add)
        self.frame_proj.setVisible(False); lay.addWidget(self.frame_proj)

        sep = QLabel("— ou —"); self.sep_lbl = sep
        sep.setAlignment(Qt.AlignCenter); sep.setStyleSheet("color:#999;font-size:10px;")
        lay.addWidget(sep)
        row = QHBoxLayout()
        self.le_pasta = QLineEdit()
        self.le_pasta.setPlaceholderText("Selecione a pasta com os TIFs...")
        row.addWidget(self.le_pasta)
        btn_p = QPushButton("..."); btn_p.setFixedWidth(36)
        btn_p.clicked.connect(self._escolher_pasta); row.addWidget(btn_p)
        lay.addLayout(row)

        # Tabela
        info = QLabel("Preencha o ano de cada raster. Deixe em branco para ignorar.")
        info.setStyleSheet("font-size:10px;font-style:italic;color:#555;")
        lay.addWidget(info)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Incluir","Arquivo / Camada","Ano"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tabela.setColumnWidth(0, 54); self.tabela.setColumnWidth(2, 70)
        self.tabela.setMinimumHeight(160)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.tabela)

        btn_lay = QHBoxLayout()
        for lbl, fn in [("Marcar todos", lambda: self._marcar(True)),
                        ("Desmarcar todos", lambda: self._marcar(False)),
                        ("Remover selecionados", self._remover)]:
            b = QPushButton(lbl); b.clicked.connect(fn); btn_lay.addWidget(b)
        btn_lay.addStretch(); lay.addLayout(btn_lay)

        # CRS / pixel
        self.frame_crs = QFrame()
        self.frame_crs.setStyleSheet(
            "QFrame{background:#FFF3E0;border:1px solid #F9A825;"
            "border-radius:4px;padding:4px;}")
        crs_lay = QHBoxLayout(self.frame_crs); crs_lay.setContentsMargins(8,4,8,4)
        self.lbl_crs = QLabel(
            "⚠ Raster em coordenadas geográficas — informe o tamanho do pixel:")
        self.lbl_crs.setStyleSheet("font-size:10px;color:#BF360C;font-weight:bold;")
        crs_lay.addWidget(self.lbl_crs)
        self.cb_pixel = QComboBox()
        self.cb_pixel.addItems(["Landsat — 30m","Sentinel-2 — 10m",
                                "MODIS — 250m","MODIS — 500m","Outro"])
        self.cb_pixel.currentIndexChanged.connect(self._pixel_changed)
        crs_lay.addWidget(self.cb_pixel)
        self.le_pixel = QLineEdit("30"); self.le_pixel.setFixedWidth(60)
        self.le_pixel.setVisible(False); crs_lay.addWidget(self.le_pixel)
        crs_lay.addWidget(QLabel("m"))
        self.frame_crs.setVisible(False); lay.addWidget(self.frame_crs)
        return grp

    def _toggle_modo(self, on):
        self.frame_proj.setVisible(on)
        self.sep_lbl.setVisible(not on)
        self.le_pasta.setVisible(not on)

    def _add_projeto(self):
        layer = self.cb_raster.currentLayer()
        if not layer: return
        path  = layer.source().split('|')[0]
        fname = os.path.basename(path)
        for r in range(self.tabela.rowCount()):
            if self.tabela.item(r,1) and self.tabela.item(r,1).text()==fname:
                return
        self._inserir_linha(fname, path, verde=True)
        self._verificar_crs(path)

    def _escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(
            self,'Pasta com rasters',
            self.le_pasta.text() or os.path.expanduser('~'))
        if not pasta: return
        self.le_pasta.setText(pasta)
        import glob
        tifs = sorted(glob.glob(os.path.join(pasta,'*.tif')) +
                      glob.glob(os.path.join(pasta,'*.tiff')))
        self.tabela.setRowCount(0)
        for p in tifs:
            self._inserir_linha(os.path.basename(p), p)
        if tifs:
            self._verificar_crs(tifs[0])
        self._log(f"  {len(tifs)} arquivo(s) encontrado(s)")

    def _inserir_linha(self, fname, path, verde=False):
        row = self.tabela.rowCount(); self.tabela.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        chk.setData(Qt.UserRole, path)
        self.tabela.setItem(row, 0, chk)
        item_f = QTableWidgetItem(fname)
        item_f.setFlags(Qt.ItemIsEnabled)
        item_f.setToolTip(path)
        if verde: item_f.setForeground(QColor("#1B5E20"))
        self.tabela.setItem(row, 1, item_f)
        item_a = QTableWidgetItem("")
        item_a.setTextAlignment(Qt.AlignCenter)
        self.tabela.setItem(row, 2, item_a)

    def _verificar_crs(self, path):
        try:
            from osgeo import gdal, osr
            ds  = gdal.Open(path)
            if ds is None: return
            srs = osr.SpatialReference(); srs.ImportFromWkt(ds.GetProjection())
            ds  = None
            self.frame_crs.setVisible(not bool(srs.IsProjected()))
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"AnP: verificacao de CRS ignorada ({e})", "AnP", Qgis.Info)

    def _pixel_changed(self, idx):
        vals = [30, 10, 250, 500, None]
        v = vals[idx] if idx < len(vals) else None
        if v:
            self.le_pixel.setText(str(v)); self.le_pixel.setVisible(False)
        else:
            self.le_pixel.setVisible(True)

    def _marcar(self, on):
        for r in range(self.tabela.rowCount()):
            item = self.tabela.item(r,0)
            if item: item.setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _remover(self):
        rows = sorted({i.row() for i in self.tabela.selectedItems()}, reverse=True)
        for r in rows: self.tabela.removeRow(r)

    # ── Bloco feições ─────────────────────────────────────────────────────────

    def _bloco_feicoes(self):
        grp = QGroupBox("Desagregação por feições"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        self.chk_feic = QCheckBox(
            "Desagregar resultados por feição do shapefile")
        self.chk_feic.toggled.connect(self._toggle_feic)
        g.addWidget(self.chk_feic, 0, 0, 1, 3)

        g.addWidget(QLabel("Camada do projeto:"), 1, 0)
        self.cb_shp = QgsMapLayerComboBox()
        self.cb_shp.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_shp.setAllowEmptyLayer(True)
        self.cb_shp.layerChanged.connect(
            lambda lyr: self.cb_campo.setLayer(lyr) if lyr else None)
        self.cb_shp.setEnabled(False)
        g.addWidget(self.cb_shp, 1, 1)

        btn_shp = QPushButton("..."); btn_shp.setFixedWidth(36)
        btn_shp.clicked.connect(self._escolher_shp)
        btn_shp.setEnabled(False); self._btn_shp = btn_shp
        g.addWidget(btn_shp, 1, 2)

        self.le_shp = QLineEdit()
        self.le_shp.setPlaceholderText("Ou arquivo em disco...")
        self.le_shp.setEnabled(False)
        g.addWidget(self.le_shp, 2, 1, 1, 2)

        g.addWidget(QLabel("Campo identificador:"), 3, 0)
        self.cb_campo = QgsFieldComboBox(); self.cb_campo.setEnabled(False)
        g.addWidget(self.cb_campo, 3, 1, 1, 2)
        g.setColumnStretch(1, 1)
        return grp

    def _toggle_feic(self, on):
        for w in [self.cb_shp, self._btn_shp, self.le_shp, self.cb_campo]:
            w.setEnabled(on)
        if on and self.cb_shp.currentLayer():
            self.cb_campo.setLayer(self.cb_shp.currentLayer())

    def _escolher_shp(self):
        path, _ = QFileDialog.getOpenFileName(
            self,'Shapefile','','Shapefiles (*.shp);;GeoPackage (*.gpkg)')
        if path: self.le_shp.setText(path)

    def _shp_ativo(self):
        arq = self.le_shp.text().strip()
        if arq and os.path.exists(arq): return arq
        lyr = self.cb_shp.currentLayer()
        return lyr.source().split('|')[0] if lyr else None

    # ── Bloco saída ───────────────────────────────────────────────────────────

    def _bloco_saida(self):
        grp = QGroupBox("Configurações de saída"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)
        g.addWidget(QLabel("Nome base:"), 0, 0)
        self.le_nome = QLineEdit("relatorio")
        self.le_nome.setToolTip("Prefixo do arquivo Excel de saída")
        g.addWidget(self.le_nome, 0, 1)
        g.addWidget(QLabel("Pasta de saída:"), 1, 0)
        self.le_saida = QLineEdit()
        self.le_saida.setPlaceholderText("Pasta onde o Excel será salvo...")
        g.addWidget(self.le_saida, 1, 1)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_saida); g.addWidget(btn, 1, 2)

        self.chk_tif = QCheckBox(
            "Gerar TIF + QML (paleta MapBiomas) de cada paisagem analisada "
            "— Shape Completo e cada feição desagregada")
        self.chk_tif.setChecked(True)
        self.chk_tif.setToolTip(
            "Salva um GeoTIFF (com o mesmo recorte usado no cálculo) e um "
            "QML de estilo para cada unidade de análise, na pasta de saída.")
        g.addWidget(self.chk_tif, 2, 0, 1, 3)

        g.setColumnStretch(1, 1)
        return grp

    def _escolher_saida(self):
        p = QFileDialog.getExistingDirectory(
            self,'Pasta de saída',
            self.le_saida.text() or os.path.expanduser('~'))
        if p: self.le_saida.setText(p)

    # ── Log ───────────────────────────────────────────────────────────────────

    def _bloco_log(self):
        grp = QGroupBox("Log"); grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp)
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(100)
        self.log_box.setFont(QFont("Courier New", 9)); lay.addWidget(self.log_box)
        self.prog_bar = QProgressBar(); self.prog_bar.setRange(0,0)
        self.prog_bar.setVisible(False); lay.addWidget(self.prog_bar)
        return grp

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    def _resetar(self):
        """Volta o formulário ao estado inicial, sem precisar reinstalar."""
        resp = QMessageBox.question(
            self, 'AnP — Resetar',
            'Limpar todas as entradas e voltar o formulário ao estado inicial?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        # Rasters e origem
        self.tabela.setRowCount(0)
        self.chk_projeto.setChecked(False)      # dispara _toggle_modo → modo pasta
        self.le_pasta.clear()
        self.cb_raster.setCurrentIndex(0)

        # CRS / pixel
        self.frame_crs.setVisible(False)
        self.cb_pixel.setCurrentIndex(0)
        self.le_pixel.setText("30")
        self.le_pixel.setVisible(False)

        # Desagregação por feições
        self.chk_feic.setChecked(False)         # dispara _toggle_feic → desabilita
        self.cb_shp.setCurrentIndex(0)
        self.le_shp.clear()

        # Saída
        self.le_nome.setText("relatorio")
        self.le_saida.clear()
        self.chk_tif.setChecked(True)

        # Log e progresso
        self.log_box.clear()
        self.prog_bar.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log("Formulário resetado.")

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _coletar_entradas(self):
        entradas = []; erros = []
        for r in range(self.tabela.rowCount()):
            chk = self.tabela.item(r, 0)
            if not chk or chk.checkState() != Qt.Checked: continue
            fname = self.tabela.item(r, 1).text()
            ano_t = self.tabela.item(r, 2).text().strip()
            if not ano_t: continue
            try:
                ano = int(ano_t)
            except ValueError:
                erros.append(f"'{ano_t}' não é ano válido ({fname})")
                continue
            path = chk.data(Qt.UserRole)
            if not path:
                pasta = self.le_pasta.text().strip()
                path  = os.path.join(pasta, fname)
            entradas.append({'path': path, 'ano': ano})
        return entradas, erros

    def _pixel_m_ativo(self):
        if not self.frame_crs.isVisible():
            return None
        try:
            return float(self.le_pixel.text())
        except ValueError:
            return 30.0

    def _validar(self):
        erros = []
        entradas, erros_tab = self._coletar_entradas()
        erros.extend(erros_tab)
        if not entradas:
            erros.append("Nenhum raster marcado com ano preenchido.")
        if not self.le_saida.text().strip():
            erros.append("Selecione a pasta de saída.")
        if self.chk_feic.isChecked() and not self._shp_ativo():
            erros.append("Desagregação ativada: selecione o shapefile.")
        if self.chk_feic.isChecked() and not self.cb_campo.currentField():
            erros.append("Desagregação ativada: selecione o campo identificador.")
        return erros, entradas

    def _executar(self):
        erros, entradas = self._validar()
        if erros:
            QMessageBox.warning(self,'AnP — Campos incompletos',
                                '\n'.join(f'• {e}' for e in erros))
            return

        params = {
            'entradas' : entradas,
            'shapefile': self._shp_ativo() if self.chk_feic.isChecked() else None,
            'campo_id' : self.cb_campo.currentField() if self.chk_feic.isChecked() else None,
            'pixel_m'  : self._pixel_m_ativo(),
            'pasta'    : self.le_saida.text().strip(),
            'nome_base': self.le_nome.text().strip() or "relatorio",
            'gerar_tif': self.chk_tif.isChecked(),
        }

        self.btn_exec.setEnabled(False); self.prog_bar.setVisible(True)
        self.log_box.clear()
        anos = [e['ano'] for e in entradas]
        self._log(f"Iniciando  |  {len(entradas)} raster(s)  |  Anos: {anos}")

        self._worker = _Worker(params)
        self._worker.progresso.connect(self._log)
        self._worker.concluido.connect(self._concluido)
        self._worker.erro.connect(self._erro)
        self._worker.start()

    def _concluido(self, arq):
        self.prog_bar.setVisible(False); self.btn_exec.setEnabled(True)
        self._log(f"\n✓ Concluído: {arq}")
        resp = QMessageBox.question(
            self,'AnP — Concluído',
            f'Relatório gerado:\n{os.path.basename(arq)}\n\nAbrir pasta de saída?',
            QMessageBox.Yes|QMessageBox.No, QMessageBox.Yes)
        if resp == QMessageBox.Yes:
            from qgis.PyQt.QtGui import QDesktopServices
            from qgis.PyQt.QtCore import QUrl
            pasta = os.path.dirname(arq)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pasta))

    def _erro(self, msg):
        self.prog_bar.setVisible(False); self.btn_exec.setEnabled(True)
        self._log(f"\n⚠ ERRO:\n{msg}")
        QMessageBox.critical(self,'AnP — Erro', msg[:400])
