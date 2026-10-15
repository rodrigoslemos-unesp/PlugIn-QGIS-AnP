# -*- coding: utf-8 -*-
"""AnP — Fragmentos: interface principal (v1.1)."""
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QLineEdit, QFileDialog, QTextEdit,
    QMessageBox, QProgressBar, QSpinBox)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import QgsMapLayerProxyModel

from ..comum.metadados import VERSAO_SUITE


class _Worker(QThread):
    progresso = pyqtSignal(str)
    concluido = pyqtSignal(object)
    erro      = pyqtSignal(str)

    def __init__(self, params):
        super().__init__(); self._p = params

    def run(self):
        try:
            from .processamento import processar_fragmentos
            res = processar_fragmentos(
                raster       = self._p['raster'],
                valores      = self._p['valores'],
                pasta_saida  = self._p['pasta'],
                nome_base    = self._p['nome'],
                modo_agregar = self._p['agregar'],
                conn         = self._p['conn'],
                depth_px     = self._p['depth'],
                area_min_ha  = self._p['area_min'],
                shapefile    = self._p.get('shapefile'),
                campo        = self._p.get('campo'),
                progresso_fn = self.progresso.emit,
            )
            self.concluido.emit(res)
        except Exception as e:
            import traceback
            self.erro.emit(str(e) + '\n' + traceback.format_exc())


class AnPFragmentosDialog(QDialog):

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface; self._worker = None
        self.setWindowTitle(f'AnP — Fragmentos (Análise Preliminar)  v{VERSAO_SUITE}')
        self.setMinimumWidth(720)
        self._build_ui()

    # ── Interface ──────────────────────────────────────────────────────────────
    def _grp(self):
        return ("QGroupBox{font-weight:bold;border:1px solid #bbb;"
                "border-radius:6px;margin-top:8px;padding:8px;}"
                "QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px;}")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10); root.setContentsMargins(12, 12, 12, 12)
        root.addWidget(self._bloco_raster())
        root.addWidget(self._bloco_alvo())
        root.addWidget(self._bloco_parametros())
        root.addWidget(self._bloco_feicoes())
        root.addWidget(self._bloco_saida())
        root.addWidget(self._bloco_log())

        barra = QHBoxLayout()
        self.btn_exec = QPushButton("Analisar fragmentos")
        self.btn_exec.clicked.connect(self._executar)
        barra.addStretch(); barra.addWidget(self.btn_exec)
        root.addLayout(barra)

        self.prog = QProgressBar(); self.prog.setVisible(False)
        self.prog.setRange(0, 0)
        root.addWidget(self.prog)

    def _bloco_raster(self):
        grp = QGroupBox("Raster base"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp)
        g.addWidget(QLabel("Camada raster:"), 0, 0)
        self.cb_r = QgsMapLayerComboBox()
        self.cb_r.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cb_r.layerChanged.connect(self._atualizar_borda_m)
        g.addWidget(self.cb_r, 0, 1, 1, 2)
        self.lbl_crs = QLabel("")
        self.lbl_crs.setStyleSheet("font-size:10px;font-style:italic;color:#555;")
        g.addWidget(self.lbl_crs, 1, 1, 1, 2)
        self.cb_r.layerChanged.connect(self._info_crs)
        return grp

    def _bloco_alvo(self):
        grp = QGroupBox("Classe / valores-alvo"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp)
        g.addWidget(QLabel("Valor(es):"), 0, 0)
        self.le_val = QLineEdit()
        self.le_val.setPlaceholderText("Ex.: 3  (só floresta)  ou  3, 4, 5")
        self.le_val.setToolTip(
            "Um valor (ex.: 3 = Formação Florestal) ou vários separados por "
            "vírgula. Funciona com qualquer raster categórico.")
        g.addWidget(self.le_val, 0, 1, 1, 2)
        self.chk_agreg = QCheckBox(
            "Tratar os valores como classe única (agregar em um só fragmento)")
        self.chk_agreg.setToolTip(
            "Marcado: blocos vizinhos de valores diferentes se fundem num "
            "único fragmento (ex.: 'vegetação nativa'). Desmarcado: cada "
            "valor é rotulado e medido separadamente.")
        g.addWidget(self.chk_agreg, 1, 0, 1, 3)
        return grp

    def _bloco_parametros(self):
        grp = QGroupBox("Parâmetros"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp)
        g.addWidget(QLabel("Vizinhança:"), 0, 0)
        self.cb_conn = QComboBox()
        self.cb_conn.addItem("8 conexos (rainha) — padrão", 8)
        self.cb_conn.addItem("4 conexos (torre)", 4)
        g.addWidget(self.cb_conn, 0, 1)

        g.addWidget(QLabel("Profundidade de borda (núcleo):"), 1, 0)
        self.sp_depth = QSpinBox()
        self.sp_depth.setRange(0, 100); self.sp_depth.setValue(1)
        self.sp_depth.setSuffix(" px")
        self.sp_depth.valueChanged.connect(self._atualizar_borda_m)
        g.addWidget(self.sp_depth, 1, 1)
        self.lbl_borda_m = QLabel("")
        self.lbl_borda_m.setStyleSheet("font-style:italic;color:#555;")
        g.addWidget(self.lbl_borda_m, 1, 2)

        g.addWidget(QLabel("Área mínima (ha):"), 2, 0)
        self.le_amin = QLineEdit("0")
        self.le_amin.setToolTip("Descarta fragmentos menores que este valor. "
                                "0 = sem filtro.")
        g.addWidget(self.le_amin, 2, 1)
        return grp

    def _bloco_feicoes(self):
        grp = QGroupBox("Desagregação por unidade (opcional)")
        grp.setStyleSheet(self._grp())
        g = QGridLayout(grp)
        self.chk_feic = QCheckBox(
            "Recortar e etiquetar os fragmentos por feição de um shapefile")
        self.chk_feic.toggled.connect(self._toggle_feic)
        g.addWidget(self.chk_feic, 0, 0, 1, 3)
        self.lbl_shp = QLabel("Shapefile de unidades:"); self.lbl_shp.setEnabled(False)
        g.addWidget(self.lbl_shp, 1, 0)
        self.cb_shp = QgsMapLayerComboBox(); self.cb_shp.setEnabled(False)
        self.cb_shp.setFilters(QgsMapLayerProxyModel.VectorLayer)
        g.addWidget(self.cb_shp, 1, 1, 1, 2)
        self.lbl_campo = QLabel("Campo identificador:"); self.lbl_campo.setEnabled(False)
        g.addWidget(self.lbl_campo, 2, 0)
        self.cb_campo = QgsFieldComboBox(); self.cb_campo.setEnabled(False)
        g.addWidget(self.cb_campo, 2, 1, 1, 2)
        self.cb_shp.layerChanged.connect(
            lambda lyr: self.cb_campo.setLayer(lyr))
        return grp

    def _toggle_feic(self, on):
        for w in (self.lbl_shp, self.cb_shp, self.lbl_campo, self.cb_campo):
            w.setEnabled(on)
        if on:
            self.cb_campo.setLayer(self.cb_shp.currentLayer())

    def _bloco_saida(self):
        grp = QGroupBox("Saída"); grp.setStyleSheet(self._grp())
        g = QGridLayout(grp)
        g.addWidget(QLabel("Nome base:"), 0, 0)
        self.le_nome = QLineEdit("fragmentos")
        g.addWidget(self.le_nome, 0, 1, 1, 2)
        g.addWidget(QLabel("Pasta:"), 1, 0)
        self.le_pasta = QLineEdit()
        g.addWidget(self.le_pasta, 1, 1)
        btn = QPushButton("..."); btn.setFixedWidth(36)
        btn.clicked.connect(self._escolher_pasta)
        g.addWidget(btn, 1, 2)
        self.chk_carregar = QCheckBox(
            "Carregar o shapefile no projeto QGIS ao concluir")
        self.chk_carregar.setChecked(True)
        g.addWidget(self.chk_carregar, 2, 0, 1, 3)
        return grp

    def _bloco_log(self):
        grp = QGroupBox("Log"); grp.setStyleSheet(self._grp())
        v = QVBoxLayout(grp)
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(120)
        v.addWidget(self.log_box)
        return grp

    # ── Auxiliares ─────────────────────────────────────────────────────────────
    def _escolher_pasta(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta de saída")
        if p:
            self.le_pasta.setText(p)

    def _pixel_m(self):
        lyr = self.cb_r.currentLayer()
        if lyr is None:
            return None
        try:
            return abs(lyr.rasterUnitsPerPixelX())
        except Exception:
            return None

    def _atualizar_borda_m(self, *args):
        px = self._pixel_m()
        n = self.sp_depth.value()
        if px:
            self.lbl_borda_m.setText(f"≈ {n * px:.0f} m")
        else:
            self.lbl_borda_m.setText("")

    def _info_crs(self, lyr):
        if lyr is None:
            self.lbl_crs.setText(""); return
        crs = lyr.crs()
        proj = "projetado (metros)" if not crs.isGeographic() else \
               "GEOGRÁFICO (graus) — reprojete antes (Preparação → 31983)"
        self.lbl_crs.setText(f"CRS: {crs.description()}  ·  {proj}")

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    # ── Execução ───────────────────────────────────────────────────────────────
    def _executar(self):
        erros = []
        lyr = self.cb_r.currentLayer()
        if lyr is None:
            erros.append("Selecione o raster base.")
        try:
            valores = [int(v.strip()) for v in self.le_val.text().split(',')
                       if v.strip() != '']
        except ValueError:
            valores = []
        if not valores:
            erros.append("Informe ao menos um valor-alvo inteiro (ex.: 3).")
        try:
            area_min = float(self.le_amin.text().replace(',', '.') or 0)
        except ValueError:
            area_min = 0.0
        pasta = self.le_pasta.text().strip()
        if not pasta:
            erros.append("Escolha a pasta de saída.")
        if self.chk_feic.isChecked():
            if self.cb_shp.currentLayer() is None:
                erros.append("Desagregação marcada: selecione o shapefile.")
            elif not self.cb_campo.currentField():
                erros.append("Desagregação marcada: selecione o campo.")
        if erros:
            QMessageBox.warning(self, "AnP — Fragmentos", "\n".join(erros))
            return

        params = {
            'raster'  : lyr.source().split('|')[0],
            'valores' : valores,
            'pasta'   : pasta,
            'nome'    : self.le_nome.text().strip() or "fragmentos",
            'agregar' : self.chk_agreg.isChecked(),
            'conn'    : self.cb_conn.currentData(),
            'depth'   : self.sp_depth.value(),
            'area_min': area_min,
        }
        if self.chk_feic.isChecked():
            params['shapefile'] = self.cb_shp.currentLayer().source().split('|')[0]
            params['campo']     = self.cb_campo.currentField()

        self.btn_exec.setEnabled(False)
        self.prog.setVisible(True)
        self._log("── Iniciando análise de fragmentos ──")
        self._worker = _Worker(params)
        self._worker.progresso.connect(self._log)
        self._worker.concluido.connect(self._concluido)
        self._worker.erro.connect(self._erro)
        self._worker.start()

    def _erro(self, msg):
        self.prog.setVisible(False)
        self.btn_exec.setEnabled(True)
        self._log("✗ ERRO:\n" + msg)
        QMessageBox.critical(self, "AnP — Erro", msg.split('\n')[0])

    def _concluido(self, res):
        self.prog.setVisible(False)
        self.btn_exec.setEnabled(True)
        shps = res.get('shapefiles', [])
        tifs = res.get('tifs', [])
        self._log(f"\n✓ Concluído — {res['meta']['n_frag']} fragmentos em "
                  f"{len(shps)} arquivo(s).")
        for s in shps:
            self._log(f"  Shapefile: {s}")
        for t in tifs:
            self._log(f"  TIFF:      {t}")
        self._log(f"  Excel:     {res['excel']}")
        if self.chk_carregar.isChecked():
            self._carregar(shps)
        QMessageBox.information(
            self, "AnP — Fragmentos",
            f"Análise concluída: {res['meta']['n_frag']} fragmentos.\n"
            f"{len(shps)} shapefile(s) + {len(tifs)} TIFF(s) + Excel-resumo.")

    def _carregar(self, shps):
        try:
            from qgis.core import QgsVectorLayer, QgsProject, QgsRasterLayer
            root = QgsProject.instance().layerTreeRoot()
            grupo = root.insertGroup(0, "AnP — Fragmentos")
            n = 0
            for shp in shps:
                nome = os.path.splitext(os.path.basename(shp))[0]
                vl = QgsVectorLayer(shp, nome, "ogr")
                if vl.isValid():
                    QgsProject.instance().addMapLayer(vl, False)
                    grupo.addLayer(vl); n += 1
            self._log(f"  ✓ {n} shapefile(s) carregado(s) no projeto "
                      f"(grupo 'AnP — Fragmentos'). Sugestão: simbologia "
                      f"graduada por 'area_ha'.")
        except Exception as e:
            self._log(f"  ⚠ Falha ao carregar: {e}")
