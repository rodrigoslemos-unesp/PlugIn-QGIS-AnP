"""AnP — Preparação de Dados v1.1 — Interface reestruturada"""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QLineEdit, QFileDialog, QTextEdit,
    QMessageBox, QProgressBar, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget,
    QScrollArea, QSizePolicy, QAbstractItemView, QDialogButtonBox)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QFont, QColor
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel

from ..comum.metadados import VERSAO_SUITE
from .processamento import ALBERS_BR


class _Worker(QThread):
    progresso = pyqtSignal(str)
    concluido = pyqtSignal(object)
    erro      = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self._p = params

    def run(self):
        try:
            from .processamento import preparar_rasters
            arquivos = preparar_rasters(
                entradas       = self._p['entradas'],
                pasta_saida    = self._p['pasta_saida'],
                op_alinhar     = self._p['op_alinhar'],
                op_recortar    = self._p['op_recortar'],
                gerar_qml      = self._p.get('gerar_qml', False),
                op_reprojetar  = self._p['op_reprojetar'],
                shapefile      = self._p.get('shapefile'),
                epsg_saida     = self._p.get('epsg_saida', 31983),
                desagregar     = self._p.get('desagregar', False),
                campo_id       = self._p.get('campo_id'),
                progresso_fn   = self.progresso.emit,
            )
            self.concluido.emit(arquivos)
        except Exception as e:
            import traceback
            self.erro.emit(str(e) + '\n' + traceback.format_exc())


class AnPPreparacaoDialog(QDialog):

    FUSOS = [
        ("SIRGAS 2000 / UTM Zona 18S (EPSG:31978)", 31978),
        ("SIRGAS 2000 / UTM Zona 19S (EPSG:31979)", 31979),
        ("SIRGAS 2000 / UTM Zona 20S (EPSG:31980)", 31980),
        ("SIRGAS 2000 / UTM Zona 21S (EPSG:31981)", 31981),
        ("SIRGAS 2000 / UTM Zona 22S (EPSG:31982)", 31982),
        ("SIRGAS 2000 / UTM Zona 23S (EPSG:31983)", 31983),
        ("SIRGAS 2000 / UTM Zona 24S (EPSG:31984)", 31984),
        ("SIRGAS 2000 / UTM Zona 25S (EPSG:31985)", 31985),
        ("SIRGAS 2000 / UTM Zona 18N (EPSG:31972)", 31972),
        ("SIRGAS 2000 / UTM Zona 19N (EPSG:31973)", 31973),
        ("SIRGAS 2000 / UTM Zona 20N (EPSG:31974)", 31974),
        ("SIRGAS 2000 / UTM Zona 21N (EPSG:31975)", 31975),
        ("SIRGAS 2000 / UTM Zona 22N (EPSG:31976)", 31976),
        ("WGS 84 / UTM Zona 17S (EPSG:32717)", 32717),
        ("WGS 84 / UTM Zona 18S (EPSG:32718)", 32718),
        ("WGS 84 / UTM Zona 19S (EPSG:32719)", 32719),
        ("WGS 84 / UTM Zona 20S (EPSG:32720)", 32720),
        ("WGS 84 / UTM Zona 21S (EPSG:32721)", 32721),
        ("WGS 84 / UTM Zona 22S (EPSG:32722)", 32722),
        ("WGS 84 / UTM Zona 23S (EPSG:32723)", 32723),
        ("WGS 84 / UTM Zona 24S (EPSG:32724)", 32724),
        ("WGS 84 / UTM Zona 25S (EPSG:32725)", 32725),
        ("SIRGAS 2000 / Cônica Equivalente de Albers — Brasil (IBGE)", ALBERS_BR),
        ("Outro — informar EPSG manualmente", 0),
    ]

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface; self._worker = None
        self._pasta_rasters = ""
        self.setWindowTitle(f'AnP — Preparação de Dados  v{VERSAO_SUITE}')
        self.setMinimumWidth(780)
        self.setMinimumHeight(520)
        self.resize(840, 740)
        self.setSizeGripEnabled(True)
        self._build_ui()

    # ── Interface ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._header())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo)
        lay.setSpacing(10); lay.setContentsMargins(12, 10, 12, 10)

        # ── SEÇÃO 1 — ORIGEM ──────────────────────────────────────────────────
        sec1 = QLabel("  1. Origem dos rasters")
        sec1.setStyleSheet(
            "background:#37474F;color:white;font-weight:bold;"
            "font-size:12px;padding:6px;border-radius:4px;")
        lay.addWidget(sec1)
        lay.addWidget(self._bloco_pasta())
        lay.addWidget(self._bloco_tabela())

        # ── SEÇÃO 2 — OPERAÇÕES ───────────────────────────────────────────────
        sec2 = QLabel("  2. Operações a executar")
        sec2.setStyleSheet(
            "background:#37474F;color:white;font-weight:bold;"
            "font-size:12px;padding:6px;border-radius:4px;")
        lay.addWidget(sec2)
        lay.addWidget(self._bloco_op_alinhar())
        lay.addWidget(self._bloco_op_recortar())
        lay.addWidget(self._bloco_op_reprojetar())

        # ── SEÇÃO 3 — SAÍDA ───────────────────────────────────────────────────
        sec3 = QLabel("  3. Saída")
        sec3.setStyleSheet(
            "background:#37474F;color:white;font-weight:bold;"
            "font-size:12px;padding:6px;border-radius:4px;")
        lay.addWidget(sec3)
        lay.addWidget(self._bloco_qml())
        lay.addWidget(self._bloco_saida())
        lay.addWidget(self._bloco_log())
        lay.addStretch()
        scroll.setWidget(conteudo)
        root.addWidget(scroll, 1)

        # Barra de botões fixa
        barra = QWidget()
        barra.setStyleSheet(
            "background:#F5F5F5;border-top:1px solid #CCCCCC;")
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(12, 8, 12, 8)
        btn_l = QPushButton("Limpar log")
        btn_l.clicked.connect(self.log_box.clear)
        bl.addWidget(btn_l)
        bl.addStretch()
        btn_f = QPushButton("Fechar")
        btn_f.clicked.connect(self.close)
        bl.addWidget(btn_f)
        self.btn_exec = QPushButton("▶  Executar")
        self.btn_exec.setDefault(True)
        self.btn_exec.setStyleSheet(
            "QPushButton{background:#37474F;color:white;font-weight:bold;"
            "padding:8px 24px;border-radius:5px;}"
            "QPushButton:hover{background:#455A64;}"
            "QPushButton:disabled{background:#AAAAAA;}")
        self.btn_exec.clicked.connect(self._executar)
        bl.addWidget(self.btn_exec)
        root.addWidget(barra)

    def _header(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame{background-color:#37474F;border-radius:0px;}")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10); lay.setSpacing(14)
        logo = os.path.join(os.path.dirname(__file__), 'unesp_logo.png')
        if os.path.exists(logo):
            lbl = QLabel()
            pix = QPixmap(logo).scaledToHeight(60, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            lbl.setStyleSheet(
                "background:white;border-radius:5px;padding:4px;")
            lbl.setFixedSize(pix.width()+10, 70)
            lay.addWidget(lbl)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#546E7A;"); lay.addWidget(sep)
        txt = QVBoxLayout(); txt.setSpacing(3)
        txt.setAlignment(Qt.AlignVCenter)
        t1 = QLabel("AnP — Preparação de Dados")
        t1.setStyleSheet("color:white;font-size:15px;font-weight:bold;"
                         "background:transparent;")
        txt.addWidget(t1)
        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color:#546E7A;"); txt.addWidget(div)
        t2 = QLabel(
            "Alinhar grades  ·  Recortar por shapefile  ·  Reprojetar  "
            "—  execute uma, duas ou as três operações")
        t2.setStyleSheet("color:#B0BEC5;font-size:10px;font-style:italic;"
                         "background:transparent;")
        t2.setWordWrap(True); txt.addWidget(t2)
        t3 = QLabel("Prof. Dr. Rodrigo Silva Lemos  ·  "
                    f"DGPA/IGCE — Unesp Rio Claro  ·  AnP v{VERSAO_SUITE}")
        t3.setStyleSheet(
            "color:#90A4AE;font-size:10px;background:transparent;")
        txt.addWidget(t3)
        lay.addLayout(txt, 1)
        return frame

    def _grp(self):
        return ("QGroupBox{font-weight:bold;font-size:11px;"
                "border:1px solid #CCCCCC;border-radius:5px;"
                "margin-top:8px;padding-top:4px;}"
                "QGroupBox::title{subcontrol-origin:margin;"
                "left:8px;padding:0 4px;}")

    # ── Bloco pasta / origem ──────────────────────────────────────────────────

    def _bloco_pasta(self):
        grp = QGroupBox("Origem dos rasters")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp); lay.setSpacing(6)

        self.chk_do_projeto = QCheckBox(
            "Usar camadas raster já carregadas no projeto QGIS")
        self.chk_do_projeto.toggled.connect(self._toggle_modo_origem)
        lay.addWidget(self.chk_do_projeto)

        self.frame_projeto = QFrame()
        fp_lay = QHBoxLayout(self.frame_projeto)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.addWidget(QLabel("Adicionar camada:"))
        self.cb_raster_proj = QgsMapLayerComboBox()
        self.cb_raster_proj.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cb_raster_proj.setAllowEmptyLayer(True)
        fp_lay.addWidget(self.cb_raster_proj)
        btn_add = QPushButton("+ Adicionar à lista")
        btn_add.clicked.connect(self._adicionar_raster_projeto)
        fp_lay.addWidget(btn_add)
        self.frame_projeto.setVisible(False)
        lay.addWidget(self.frame_projeto)

        sep = QLabel("— ou —")
        self.sep_lbl = sep
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet("color:#999;font-size:10px;")
        lay.addWidget(sep)

        row = QHBoxLayout()
        self.le_pasta_r = QLineEdit()
        self.le_pasta_r.setPlaceholderText(
            "Selecione a pasta onde estão os arquivos .tif...")
        row.addWidget(self.le_pasta_r)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_pasta_rasters)
        row.addWidget(btn)
        lay.addLayout(row)
        return grp

    def _toggle_modo_origem(self, on):
        self.frame_projeto.setVisible(on)
        self.sep_lbl.setVisible(not on)
        self.le_pasta_r.setVisible(not on)
        if self.tabela.rowCount() > 0:
            resp = QMessageBox.question(
                self, 'AnP — Limpar tabela?',
                'Ao trocar o modo de origem a lista sera limpa. Deseja continuar?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if resp == QMessageBox.Yes:
                self.tabela.setRowCount(0)
                self._log("  Tabela limpa.")
            else:
                self.chk_do_projeto.blockSignals(True)
                self.chk_do_projeto.setChecked(not on)
                self.chk_do_projeto.blockSignals(False)
                self._toggle_modo_origem(not on)

    def _adicionar_raster_projeto(self):
        layer = self.cb_raster_proj.currentLayer()
        if not layer:
            return
        path  = layer.source().split('|')[0]
        fname = os.path.basename(path)
        for row in range(self.tabela.rowCount()):
            if self.tabela.item(row, 1) and \
               self.tabela.item(row, 1).text() == fname:
                self._log(f"  Camada já na lista: {fname}")
                return
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        chk.setData(Qt.UserRole, path)
        self.tabela.setItem(row, 0, chk)
        item_f = QTableWidgetItem(fname)
        item_f.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item_f.setToolTip(path)
        item_f.setForeground(QColor("#1B5E20"))
        self.tabela.setItem(row, 1, item_f)
        item_a = QTableWidgetItem("")
        item_a.setTextAlignment(Qt.AlignCenter)
        self.tabela.setItem(row, 2, item_a)
        nome_base = os.path.splitext(fname)[0]
        self.tabela.setItem(row, 3, QTableWidgetItem(nome_base))
        self._log(f"  + Adicionado: {fname}")

    def _escolher_pasta_rasters(self):
        pasta = QFileDialog.getExistingDirectory(
            self, 'Pasta com rasters',
            self.le_pasta_r.text() or os.path.expanduser('~'))
        if pasta:
            self.le_pasta_r.setText(pasta)
            self._pasta_rasters = pasta
            self._popular_tabela(pasta)

    # ── Bloco tabela ─────────────────────────────────────────────────────────

    def _bloco_tabela(self):
        grp = QGroupBox("Rasters — informe o ano de cada imagem")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp)

        info = QLabel(
            "Preencha o ano de cada arquivo. Deixe em branco para ignorar. "
            "Desmarcados são ignorados sem ser removidos da lista.")
        info.setStyleSheet("font-size:10px;font-style:italic;color:#555;")
        info.setWordWrap(True); lay.addWidget(info)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(
            ["Incluir", "Arquivo", "Ano", "Nome base (saída)"])
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        self.tabela.setColumnWidth(0, 54)
        self.tabela.setColumnWidth(2, 70)
        self.tabela.setMinimumHeight(160)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.tabela)

        btn_lay = QHBoxLayout()
        for label, fn in [
            ("Marcar todos",   lambda: self._marcar_todos(True)),
            ("Desmarcar todos",lambda: self._marcar_todos(False)),
            ("Limpar anos",    self._limpar_anos),
            ("Remover selecionados", self._remover_selecionados),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            btn_lay.addWidget(btn)
        btn_lay.addStretch()
        lay.addLayout(btn_lay)
        return grp

    def _popular_tabela(self, pasta):
        from .processamento import listar_tifs
        tifs = listar_tifs(pasta)
        self.tabela.setRowCount(0)
        for fname in tifs:
            row = self.tabela.rowCount()
            self.tabela.insertRow(row)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked)
            self.tabela.setItem(row, 0, chk)
            item_f = QTableWidgetItem(fname)
            item_f.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item_f.setToolTip(os.path.join(pasta, fname))
            self.tabela.setItem(row, 1, item_f)
            item_a = QTableWidgetItem("")
            item_a.setTextAlignment(Qt.AlignCenter)
            self.tabela.setItem(row, 2, item_a)
            nome_base = os.path.splitext(fname)[0]
            self.tabela.setItem(row, 3, QTableWidgetItem(nome_base))
        self._log(f"  {len(tifs)} arquivo(s) encontrado(s) em {pasta}")

    def _marcar_todos(self, estado):
        check = Qt.Checked if estado else Qt.Unchecked
        for row in range(self.tabela.rowCount()):
            item = self.tabela.item(row, 0)
            if item: item.setCheckState(check)

    def _limpar_anos(self):
        for row in range(self.tabela.rowCount()):
            item = self.tabela.item(row, 2)
            if item: item.setText("")

    def _remover_selecionados(self):
        # Coleta as linhas selecionadas de forma robusta: usa o modelo de
        # seleção (funciona mesmo clicando em células não-selecionáveis, como
        # o checkbox ou o nome do arquivo) e, como reforço, os itens selecionados.
        rows = set()
        sel_model = self.tabela.selectionModel()
        if sel_model is not None:
            for idx in sel_model.selectedRows():
                rows.add(idx.row())
        for it in self.tabela.selectedItems():
            rows.add(it.row())
        if not rows:
            self._log("  Nenhuma linha selecionada. "
                      "Clique sobre a linha (na coluna do arquivo ou do ano) "
                      "antes de remover.")
            return
        for r in sorted(rows, reverse=True):
            self.tabela.removeRow(r)
        self._log(f"  {len(rows)} linha(s) removida(s).")

    # ── Blocos de operações ───────────────────────────────────────────────────

    def _bloco_op_alinhar(self):
        grp = QGroupBox("Operação A — Alinhamento de grade")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp); lay.setSpacing(6)

        self.chk_alinhar = QCheckBox(
            "Alinhar todos os rasters à grade do raster de referência")
        self.chk_alinhar.setChecked(True)
        lay.addWidget(self.chk_alinhar)

        self.lbl_alinhar_info = QLabel(
            "  O raster de menor ano será usado como referência de grade. "
            "Os demais serão reamostrados (vizinho mais próximo) para "
            "compartilhar exatamente a mesma origem, resolução e dimensões.")
        self.lbl_alinhar_info.setStyleSheet(
            "font-size:10px;color:#555;font-style:italic;")
        self.lbl_alinhar_info.setWordWrap(True)
        lay.addWidget(self.lbl_alinhar_info)

        self.chk_alinhar.toggled.connect(
            lambda on: self.lbl_alinhar_info.setVisible(on))
        return grp

    def _bloco_op_recortar(self):
        grp = QGroupBox("Operação B — Recorte por shapefile")
        grp.setStyleSheet(self._grp())
        g = QVBoxLayout(grp); g.setSpacing(6)

        self.chk_recortar = QCheckBox(
            "Recortar os rasters pelo shapefile da área de estudo")
        self.chk_recortar.setChecked(True)
        self.chk_recortar.toggled.connect(self._toggle_recortar)
        g.addWidget(self.chk_recortar)

        # Painel de configuração do shapefile
        self.frame_shp = QFrame()
        shp_lay = QGridLayout(self.frame_shp)
        shp_lay.setSpacing(6)

        shp_lay.addWidget(QLabel("Camada do projeto:"), 0, 0)
        self.cb_shp_projeto = QgsMapLayerComboBox()
        self.cb_shp_projeto.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_shp_projeto.setAllowEmptyLayer(True)
        self.cb_shp_projeto.layerChanged.connect(self._shp_projeto_mudou)
        shp_lay.addWidget(self.cb_shp_projeto, 0, 1, 1, 2)

        sep = QLabel("— ou —")
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet("color:#999;font-size:10px;")
        shp_lay.addWidget(sep, 1, 0, 1, 3)

        shp_lay.addWidget(QLabel("Arquivo em disco:"), 2, 0)
        self.le_shp = QLineEdit()
        self.le_shp.setPlaceholderText(
            "Ou selecione um shapefile em disco...")
        self.le_shp.textChanged.connect(self._shp_arquivo_mudou)
        shp_lay.addWidget(self.le_shp, 2, 1)
        btn_shp = QPushButton("..."); btn_shp.setFixedWidth(36)
        btn_shp.clicked.connect(self._escolher_shp)
        shp_lay.addWidget(btn_shp, 2, 2)

        self.lbl_shp_info = QLabel("")
        self.lbl_shp_info.setStyleSheet(
            "font-size:10px;font-style:italic;color:#555;")
        shp_lay.addWidget(self.lbl_shp_info, 3, 0, 1, 3)

        # Desagregação por feição (regionalização por campo)
        self.chk_desagregar = QCheckBox(
            "Gerar também um TIF recortado para cada feição (regionalização)")
        self.chk_desagregar.setToolTip(
            "Além do recorte pela área total, gera um raster para cada feição "
            "do shapefile, identificado pelo valor do campo escolhido abaixo "
            "(mesma lógica de desagregação do Relatório de Cobertura).")
        self.chk_desagregar.toggled.connect(self._toggle_desagregar)
        shp_lay.addWidget(self.chk_desagregar, 4, 0, 1, 3)

        self.lbl_campo = QLabel("Campo de regionalização:")
        self.lbl_campo.setEnabled(False)
        shp_lay.addWidget(self.lbl_campo, 5, 0)
        self.cb_campo = QComboBox()
        self.cb_campo.setEnabled(False)
        self.cb_campo.setToolTip(
            "Campo da base de referência cujos valores nomeiam cada recorte "
            "(ex.: NOME, Grupo, bioma).")
        shp_lay.addWidget(self.cb_campo, 5, 1, 1, 2)

        shp_lay.setColumnStretch(1, 1)

        g.addWidget(self.frame_shp)
        return grp

    def _toggle_recortar(self, on):
        self.frame_shp.setVisible(on)

    def _toggle_desagregar(self, on):
        self.lbl_campo.setEnabled(on)
        self.cb_campo.setEnabled(on)
        if on:
            self._popular_campos()

    def _popular_campos(self):
        """Lê os campos da base de referência ativa e preenche o combo."""
        self.cb_campo.clear()
        shp = self._shapefile_ativo()
        if not shp:
            return
        try:
            from osgeo import ogr
            ds   = ogr.Open(shp)
            lyr  = ds.GetLayer(0)
            defn = lyr.GetLayerDefn()
            campos = [defn.GetFieldDefn(i).GetName()
                      for i in range(defn.GetFieldCount())]
            ds = None
            self.cb_campo.addItems(campos)
        except Exception as e:
            self._log(f"  ⚠ Não foi possível ler os campos do shapefile: {e}")

    def _shp_projeto_mudou(self, layer):
        if layer:
            self.le_shp.blockSignals(True)
            self.le_shp.clear()
            self.le_shp.blockSignals(False)
            n   = layer.featureCount()
            srs = layer.crs().description()
            self.lbl_shp_info.setText(
                f"{n} feição(ões)  ·  CRS: {srs}  ·  [camada do projeto]")
        if self.chk_desagregar.isChecked():
            self._popular_campos()

    def _shp_arquivo_mudou(self, path):
        if path:
            self.cb_shp_projeto.blockSignals(True)
            self.cb_shp_projeto.setCurrentIndex(0)
            self.cb_shp_projeto.blockSignals(False)
        if self.chk_desagregar.isChecked():
            self._popular_campos()

    def _escolher_shp(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Shapefile', '',
            'Shapefiles (*.shp);;GeoPackage (*.gpkg);;Todos (*)')
        if path:
            self.le_shp.setText(path)
            try:
                from osgeo import ogr
                ds  = ogr.Open(path)
                lyr = ds.GetLayer(0)
                n   = lyr.GetFeatureCount()
                srs = lyr.GetSpatialRef()
                nome_srs = srs.GetName() if srs else "CRS desconhecido"
                self.lbl_shp_info.setText(
                    f"{n} feição(ões)  ·  CRS: {nome_srs}  ·  [arquivo em disco]")
                ds = None
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"AnP: leitura de CRS do shapefile ignorada ({e})",
                    "AnP", Qgis.Info)

    def _shapefile_ativo(self):
        arq = self.le_shp.text().strip()
        if arq and os.path.exists(arq):
            return arq
        layer = self.cb_shp_projeto.currentLayer()
        if layer:
            return layer.source().split('|')[0]
        return None

    def _bloco_op_reprojetar(self):
        grp = QGroupBox("Operação C — Reprojeção")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp); lay.setSpacing(6)

        self.chk_reproj = QCheckBox(
            "Reprojetar os rasters para outro sistema de coordenadas")
        self.chk_reproj.setChecked(False)
        self.chk_reproj.toggled.connect(self._toggle_reproj)
        lay.addWidget(self.chk_reproj)

        # Painel de fuso (oculto por padrão)
        self.frame_reproj = QFrame()
        r_lay = QHBoxLayout(self.frame_reproj)
        r_lay.setContentsMargins(0, 0, 0, 0); r_lay.setSpacing(8)

        r_lay.addWidget(QLabel("Projeção de destino:"))
        self.cb_fuso = QComboBox()
        for nome, _ in self.FUSOS:
            self.cb_fuso.addItem(nome)
        # Padrão: 23S (busca por EPSG)
        for idx, (_, epsg) in enumerate(self.FUSOS):
            if epsg == 31983:
                self.cb_fuso.setCurrentIndex(idx); break
        self.cb_fuso.currentIndexChanged.connect(self._toggle_epsg_manual)
        r_lay.addWidget(self.cb_fuso)

        self.lbl_epsg = QLabel("EPSG manual:")
        self.lbl_epsg.setVisible(False)
        r_lay.addWidget(self.lbl_epsg)
        self.le_epsg = QLineEdit()
        self.le_epsg.setPlaceholderText("Ex: 32633")
        self.le_epsg.setFixedWidth(80)
        self.le_epsg.setVisible(False)
        r_lay.addWidget(self.le_epsg)
        r_lay.addStretch()

        self.frame_reproj.setVisible(False)
        lay.addWidget(self.frame_reproj)

        # Aviso CRS detectado
        self.lbl_crs_orig = QLabel(
            "  Selecione os rasters para detectar o CRS automaticamente.")
        self.lbl_crs_orig.setStyleSheet(
            "font-size:10px;color:#555;font-style:italic;")
        self.lbl_crs_orig.setWordWrap(True)
        lay.addWidget(self.lbl_crs_orig)
        return grp

    def _toggle_reproj(self, on):
        self.frame_reproj.setVisible(on)

    def _toggle_epsg_manual(self, idx):
        visivel = (self.FUSOS[idx][1] == 0)
        self.lbl_epsg.setVisible(visivel)
        self.le_epsg.setVisible(visivel)
        if self.FUSOS[idx][1] == ALBERS_BR:
            self._aviso_albers()

    def _aviso_albers(self):
        QMessageBox.information(
            self, 'AnP — Projeção de Albers',
            "<b>Cônica Equivalente de Albers — Brasil (SIRGAS 2000)</b><br><br>"
            "É uma projeção <b>equivalente</b>: preserva as <b>áreas</b> em todo "
            "o território nacional. As métricas de área (hectares, percentuais "
            "de cobertura, matriz de transição) ficam corretas, mesmo quando a "
            "área de estudo abrange mais de um fuso UTM.<br><br>"
            "Ela <b>não preserva distâncias nem formas</b>: a escala linear varia "
            "conforme a posição no mapa. Isso prejudica as análises e funções "
            "de <b>fragmentação florestal</b>, que dependem de distâncias e "
            "perímetros — densidade de borda, profundidade de borda da área "
            "núcleo, distância entre fragmentos e índices de forma.<br><br>"
            "Para fragmentação, prefira o fuso UTM SIRGAS 2000 da área de estudo.")

    # ── Bloco estilo QML ──────────────────────────────────────────────────────
    # O nome de cada TIF de saída é o "Nome base (saída)" da tabela.

    def _bloco_qml(self):
        grp = QGroupBox("Estilo de cores")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp); g.setSpacing(6)

        # Opção QML
        self.chk_qml = QCheckBox(
            "Gerar arquivo QML MapBiomas (estilo de cores) junto com cada TIF de saída")
        self.chk_qml.setChecked(True)
        self.chk_qml.setToolTip(
            "O QML tem o mesmo nome-base do TIF e é aplicado automaticamente "
            "ao importar o arquivo no QGIS. Paleta: MapBiomas Coleção 10 completa (N1–N4).")
        lay2 = QHBoxLayout()
        lay2.addWidget(self.chk_qml)

        btn_prev = QPushButton("Pré-visualizar paleta")
        btn_prev.setFixedWidth(150)
        btn_prev.clicked.connect(self._previsualizar_paleta)
        lay2.addWidget(btn_prev)
        lay2.addStretch()

        g.addLayout(lay2, 0, 0)
        return grp

    def _previsualizar_paleta(self):
        """Mostra as cores MapBiomas em uma caixa de informação."""
        from .qml_mapbiomas import PALETA_C10
        linhas = ["Paleta MapBiomas Coleção 10 — códigos e cores:\n"]
        grupos = {
            "Floresta": [3,4,5,6,49],
            "Veg. Herbácea": [11,12,32,29,50],
            "Agropecuária": [15,18,9,21,19,36,39,20,40,62,41,46,47,35,48],
            "Área não Vegetada": [23,24,30,75,25],
            "Corpo D'água": [33,31],
        }
        for grupo, cods in grupos.items():
            linhas.append(f"── {grupo}")
            for cod in cods:
                if cod in PALETA_C10:
                    nome, cor, _ = PALETA_C10[cod]
                    linhas.append(f"   {cod:>3}  #{cor}  {nome}")
        QMessageBox.information(
            self, "Paleta MapBiomas Coleção 10",
            "\n".join(linhas))

    def _bloco_saida(self):
        grp = QGroupBox("Pasta de saída")
        grp.setStyleSheet(self._grp())
        lay_v = QVBoxLayout(grp); lay_v.setSpacing(6)

        lay = QHBoxLayout(); lay.setSpacing(6)
        self.le_saida = QLineEdit()
        self.le_saida.setPlaceholderText(
            "Pasta onde os rasters processados serão salvos...")
        lay.addWidget(self.le_saida)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_saida)
        lay.addWidget(btn)
        lay_v.addLayout(lay)
        return grp

    def _escolher_saida(self):
        p = QFileDialog.getExistingDirectory(
            self, 'Pasta de saída',
            self.le_saida.text() or os.path.expanduser('~'))
        if p: self.le_saida.setText(p)

    def _bloco_log(self):
        grp = QGroupBox("Log de processamento")
        grp.setStyleSheet(self._grp())
        lay = QVBoxLayout(grp)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(100)
        self.log_box.setFont(QFont("Courier New", 9))
        lay.addWidget(self.log_box)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setVisible(False)
        lay.addWidget(self.prog_bar)
        return grp

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    def _coletar_entradas(self):
        pasta   = self.le_pasta_r.text().strip()
        entradas = []; erros = []
        for row in range(self.tabela.rowCount()):
            chk = self.tabela.item(row, 0)
            if chk and chk.checkState() != Qt.Checked:
                continue
            fname = self.tabela.item(row, 1).text()
            ano_t = self.tabela.item(row, 2).text().strip()
            nome  = self.tabela.item(row, 3).text().strip()
            if not ano_t:
                continue
            try:
                ano = int(ano_t)
            except ValueError:
                erros.append(f"Linha ({fname}): '{ano_t}' não é um ano válido.")
                continue
            if not nome:
                nome = os.path.splitext(fname)[0]
            path_completo = chk.data(Qt.UserRole)
            if not path_completo:
                path_completo = os.path.join(pasta, fname)
            entradas.append({'path': path_completo, 'ano': ano, 'nome_base': nome})
        return entradas, erros

    def _validar(self):
        erros = []
        op_al = self.chk_alinhar.isChecked()
        op_re = self.chk_recortar.isChecked()
        op_rp = self.chk_reproj.isChecked()

        if not op_al and not op_re and not op_rp:
            erros.append(
                "Selecione ao menos uma operação (A, B ou C).")

        modo_projeto = self.chk_do_projeto.isChecked()
        if not modo_projeto and not self.le_pasta_r.text().strip():
            erros.append(
                "Selecione a pasta com os rasters ou use camadas do projeto.")

        if op_re and not self._shapefile_ativo():
            erros.append(
                "Operação B ativada: selecione o shapefile de recorte.")

        if op_re and self.chk_desagregar.isChecked() \
                and not self.cb_campo.currentText():
            erros.append(
                "Desagregação ativada: selecione o campo de regionalização.")

        if op_rp:
            fuso_idx = self.cb_fuso.currentIndex()
            if self.FUSOS[fuso_idx][1] == 0:
                try:
                    int(self.le_epsg.text().strip())
                except ValueError:
                    erros.append(
                        "Operação C ativada: informe um EPSG válido.")

        if not self.le_saida.text().strip():
            erros.append("Selecione a pasta de saída.")

        entradas, erros_tab = self._coletar_entradas()
        erros.extend(erros_tab)
        if not entradas:
            erros.append("Nenhum raster marcado com ano preenchido.")

        # O nome base vira o nome do TIF: dois rasters com o mesmo nome se
        # sobrescreveriam, e um nome igual ao do arquivo de entrada na
        # mesma pasta apagaria o original durante o processamento.
        pasta_saida = self.le_saida.text().strip()
        vistos = set()
        for e in entradas:
            nome_tif = e['nome_base']
            if not nome_tif.lower().endswith('.tif'):
                nome_tif += '.tif'
            if nome_tif.lower() in vistos:
                erros.append(
                    f"Nome base repetido: '{e['nome_base']}'. "
                    "Cada raster precisa de um nome de saída diferente.")
            vistos.add(nome_tif.lower())
            if pasta_saida and os.path.normcase(os.path.abspath(
                    os.path.join(pasta_saida, nome_tif))) ==                     os.path.normcase(os.path.abspath(e['path'])):
                erros.append(
                    f"'{nome_tif}' sobrescreveria o arquivo de entrada. "
                    "Altere o nome base ou a pasta de saída.")

        return erros, entradas

    def _executar(self):
        erros, entradas = self._validar()
        if erros:
            QMessageBox.warning(
                self, 'AnP — Campos incompletos',
                '\n'.join(f'• {e}' for e in erros))
            return

        fuso_idx = self.cb_fuso.currentIndex()
        epsg_out = self.FUSOS[fuso_idx][1]
        if epsg_out == 0:
            epsg_out = int(self.le_epsg.text().strip())

        op_al = self.chk_alinhar.isChecked()
        op_re = self.chk_recortar.isChecked()
        op_rp = self.chk_reproj.isChecked()

        ops_desc = []
        if op_al: ops_desc.append("Alinhar grade")
        if op_re: ops_desc.append("Recortar")
        if op_rp:
            ops_desc.append("Reprojetar (Albers — Brasil)" if epsg_out == ALBERS_BR
                            else f"Reprojetar (EPSG:{epsg_out})")

        gerar_qml = self.chk_qml.isChecked()
        params = {
            'entradas'     : entradas,
            'pasta_saida'  : self.le_saida.text().strip(),
            'op_alinhar'   : op_al,
            'op_recortar'  : op_re,
            'op_reprojetar': op_rp,
            'shapefile'    : self._shapefile_ativo() if op_re else None,
            'epsg_saida'   : epsg_out,
            'gerar_qml'    : gerar_qml,
            'desagregar'   : op_re and self.chk_desagregar.isChecked(),
            'campo_id'     : (self.cb_campo.currentText()
                              if op_re and self.chk_desagregar.isChecked()
                              else None),
        }

        self.btn_exec.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.log_box.clear()
        self._log(
            f"Iniciando  |  {len(entradas)} raster(s)  |  "
            f"Operações: {', '.join(ops_desc)}")

        self._worker = _Worker(params)
        self._worker.progresso.connect(self._log)
        self._worker.concluido.connect(self._concluido)
        self._worker.erro.connect(self._erro)
        self._worker.start()

    def _carregar_no_qgis(self, arquivos):
        """Carrega os TIFs gerados no projeto, aplicando o QML quando existir."""
        try:
            from qgis.core import QgsRasterLayer, QgsProject
        except Exception as e:
            self._log(f"  ⚠ Não foi possível carregar no QGIS: {e}")
            return
        tifs = [a for a in arquivos if a.lower().endswith('.tif')]
        if not tifs:
            return
        proj  = QgsProject.instance()
        root  = proj.layerTreeRoot()
        grupo = root.insertGroup(0, "AnP — Preparação")
        n = 0
        for t in tifs:
            nome = os.path.splitext(os.path.basename(t))[0]
            rl = QgsRasterLayer(t, nome)
            if not rl.isValid():
                self._log(f"  ⚠ Camada inválida: {nome}")
                continue
            qml = os.path.splitext(t)[0] + '.qml'
            if os.path.exists(qml):
                rl.loadNamedStyle(qml); rl.triggerRepaint()
            proj.addMapLayer(rl, False)
            grupo.addLayer(rl)
            n += 1
        self._log(f"  ✓ {n} raster(s) carregado(s) no projeto "
                  f"(grupo 'AnP — Preparação').")

    def _concluido(self, arquivos):
        self.prog_bar.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log(f"\n✓ Concluído — {len(arquivos)} arquivo(s) gerado(s):")
        for a in arquivos:
            self._log(f"  → {a}")
        adicionar, abrir = self._perguntar_ao_concluir(len(arquivos))
        if adicionar:
            self._carregar_no_qgis(arquivos)
        if abrir and arquivos:
            from qgis.PyQt.QtGui import QDesktopServices
            from qgis.PyQt.QtCore import QUrl
            pasta = os.path.dirname(arquivos[0])
            QDesktopServices.openUrl(QUrl.fromLocalFile(pasta))

    def _perguntar_ao_concluir(self, n_arquivos):
        """Pergunta se adiciona os rasters ao projeto e se abre a pasta."""
        dlg = QDialog(self)
        dlg.setWindowTitle('AnP — Concluído')
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f'{n_arquivos} arquivo(s) gerado(s).'))
        chk_add = QCheckBox(
            'Adicionar os rasters ao projeto QGIS '
            '(com estilo QML quando disponível)')
        chk_add.setChecked(True)
        chk_abrir = QCheckBox('Abrir pasta de saída')
        chk_abrir.setChecked(True)
        lay.addWidget(chk_add)
        lay.addWidget(chk_abrir)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok)
        botoes.accepted.connect(dlg.accept)
        lay.addWidget(botoes)
        if dlg.exec_() != QDialog.Accepted:
            return False, False
        return chk_add.isChecked(), chk_abrir.isChecked()

    def _erro(self, msg):
        self.prog_bar.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log(f"\n⚠ ERRO:\n{msg}")
        QMessageBox.critical(self, 'AnP — Erro', msg[:400])
