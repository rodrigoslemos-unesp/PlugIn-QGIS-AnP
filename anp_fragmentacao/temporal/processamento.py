"""
AnP Fragmentação — Processamento de rasters e cálculo de métricas.
"""

import math
import numpy as np
from qgis.core import QgsMessageLog, Qgis
from ..comum.legenda import (MAPA_N1, NODATA_VALS, GRUPOS_FRAG,
                      METRICAS_CLASSE_PLS, METRICAS_PAISAGEM_PLS,
                      UNIDADES, agregar_n1)

LOG = 'AnP-Frag'

def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(str(msg), LOG, level)


# ── Abertura de raster ────────────────────────────────────────────────────────

def detectar_crs_raster(path):
    """Verifica se o CRS do raster é projetado (metros) ou geográfico (graus)."""
    from osgeo import gdal, osr
    ds = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    proj = ds.GetProjection()
    gt   = ds.GetGeoTransform()
    ds = None
    srs = osr.SpatialReference()
    srs.ImportFromWkt(proj)
    is_proj = bool(srs.IsProjected())
    nome_crs = srs.GetName() or "Desconhecido"
    return is_proj, nome_crs, gt


def abrir_raster(path, pixel_m_manual=None):
    """
    Abre o raster e calcula a área do pixel em hectares.

    CORREÇÃO IMPORTANTE: antes desta correção, px_m era calculado como
    abs(gt[1]) SEM verificar se o CRS é projetado (metros) ou geográfico
    (graus) — se o raster estivesse em WGS84 geográfico, um pixel de
    ~0,00025° era tratado como se fosse 0,00025 METROS, resultando em
    área de pixel ~6×10⁻¹² ha (praticamente zero). Isso fazia TODOS os
    fragmentos, de qualquer tamanho real, caírem na classe "Menor que
    1 ha" com contagens de centenas de milhares de "fragmentos" — um
    artefato de cálculo, não a paisagem real. Mesmo bug já corrigido
    nos módulos de Preparação, Relatório e Monitoria, mas que nunca
    tinha sido aplicado aqui.

    Se o CRS for geográfico e pixel_m_manual não for informado, usa 30m
    (Landsat) como padrão razoável, mas emite aviso pedindo confirmação
    do usuário — o ideal é reprojetar o raster antes (Módulo I).
    """
    from osgeo import gdal, osr
    ds = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    gt   = ds.GetGeoTransform()
    proj = ds.GetProjection()

    srs = osr.SpatialReference()
    srs.ImportFromWkt(proj)
    is_proj = bool(srs.IsProjected())

    aviso_crs = None
    if is_proj:
        px_m = abs(gt[1])
    else:
        px_m = pixel_m_manual or 30.0
        nome_crs = srs.GetName() or "Desconhecido"
        aviso_crs = (
            f"Raster em CRS geográfico ({nome_crs}, coordenadas em graus). "
            f"Área do pixel estimada com {px_m}m — reprojetar para SIRGAS "
            f"UTM (Módulo I) garante o cálculo exato.")

    px_ha = (px_m ** 2) / 10000.0
    band = ds.GetRasterBand(1)
    nd   = band.GetNoDataValue()
    arr  = band.ReadAsArray().astype(np.int32)
    ds   = None
    return arr, px_m, px_ha, nd, gt, proj, aviso_crs



def detectar_resolucao(path):
    """Retorna resolução espacial em metros."""
    from osgeo import gdal
    ds = gdal.Open(path)
    if ds is None:
        return None
    res = abs(ds.GetGeoTransform()[1])
    ds = None
    return res


def recortar_por_geom(arr, nd, gt, proj, geom, crs_wkt):
    """
    Recorta o array pela geometria da feição. Reprojeta automaticamente
    a geometria para o CRS do raster quando os dois divergem — sem essa
    reprojeção, feições em CRS diferente do raster (ex: shapefile em
    WGS84 geográfico, raster em SIRGAS UTM) calculam índices de pixel
    completamente fora dos limites, e a exceção "Feição sem sobreposição
    com o raster" é lançada para TODAS as feições silenciosamente
    (capturada por um except que só grava um aviso no log).
    """
    from osgeo import gdal, ogr, osr
    g = geom.Clone()
    if not g.IsValid():
        g = g.MakeValid()

    srs_raster = osr.SpatialReference()
    srs_raster.ImportFromWkt(proj)
    srs_raster.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    srs_vetor = osr.SpatialReference()
    srs_vetor.ImportFromWkt(crs_wkt)
    srs_vetor.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    if not srs_raster.IsSame(srs_vetor):
        transform = osr.CoordinateTransformation(srs_vetor, srs_raster)
        g.Transform(transform)
        crs_wkt_mascara = proj
    else:
        crs_wkt_mascara = crs_wkt

    rows, cols = arr.shape
    env = g.GetEnvelope()
    px0 = max(0, int((env[0]-gt[0])/gt[1]))
    px1 = min(cols, int((env[1]-gt[0])/gt[1])+2)
    py0 = max(0, int((env[3]-gt[3])/gt[5]))
    py1 = min(rows, int((env[2]-gt[3])/gt[5])+2)
    if px0 >= px1 or py0 >= py1:
        raise ValueError("Feição sem sobreposição com o raster.")
    sub  = arr[py0:py1, px0:px1].copy()
    h, w = sub.shape
    gt_s = (gt[0]+px0*gt[1], gt[1], gt[2], gt[3]+py0*gt[5], gt[4], gt[5])
    mem  = gdal.GetDriverByName('MEM')
    mds  = mem.Create('', w, h, 1, gdal.GDT_Byte)
    mds.SetGeoTransform(gt_s); mds.SetProjection(proj)
    mds.GetRasterBand(1).Fill(0)
    vds  = ogr.GetDriverByName('Memory').CreateDataSource('')
    srs  = osr.SpatialReference(); srs.ImportFromWkt(crs_wkt_mascara)
    lyr  = vds.CreateLayer('', srs=srs)
    ft   = ogr.Feature(lyr.GetLayerDefn()); ft.SetGeometry(g)
    lyr.CreateFeature(ft)
    gdal.RasterizeLayer(mds, [1], lyr, burn_values=[1])
    mds.FlushCache()
    mask = mds.GetRasterBand(1).ReadAsArray()
    mds = vds = None
    nd_v = int(nd) if nd is not None else -1
    sub[mask == 0] = nd_v
    return sub


# ── Cálculo de métricas ───────────────────────────────────────────────────────

def _distribuir_por_classe(areas_ha, classes_porte):
    """
    Classifica uma lista de áreas de fragmentos (ha) nas classes de
    porte definidas em raster_porte.CLASSES_PORTE e retorna uma lista
    de dicts tidy — uma linha por classe — pronta para exportação.
    """
    from .raster_porte import classificar_porte

    if areas_ha.size == 0:
        return [
            {'classe_tamanho': rot, 'n_fragmentos': 0, 'area_ha': 0.0,
             'pct_n': 0.0, 'pct_area': 0.0}
            for _, _, _, rot in classes_porte
        ]

    codigos = np.array([classificar_porte(a, classes_porte) for a in areas_ha])
    tot_n   = len(areas_ha)
    tot_ha  = float(areas_ha.sum())

    resultado = []
    for lim_inf, lim_sup, cod, rotulo in classes_porte:
        sel = (codigos == cod)
        n   = int(np.sum(sel))
        ha  = float(areas_ha[sel].sum())
        resultado.append({
            'classe_tamanho': rotulo,
            'n_fragmentos'  : n,
            'area_ha'       : round(ha, 4),
            'pct_n'         : round(n / tot_n, 6) if tot_n else 0.0,
            'pct_area'      : round(ha / tot_ha, 6) if tot_ha else 0.0,
        })
    return resultado


def calcular_nucleo_e_distribuicao(arr_n1, codigos_n1, px_ha, n_pixels,
                                    classes_porte=None, prog=None):
    """
    Calcula em uma única passagem (evita rotular a mesma máscara mais
    de uma vez com scipy.ndimage.label):

      1. TCA, CORE_MN, NDCA — métricas escalares de área núcleo
         (erosão morfológica binária)
      2. Distribuição por classe de porte do FRAGMENTO TOTAL
         (antes da erosão)
      3. Distribuição por classe de porte da ÁREA NÚCLEO
         (após a erosão)

    Retorna (metricas_dict, dist_fragmentos_lista, dist_nucleo_lista).
    """
    from scipy.ndimage import binary_erosion, label as nd_label
    from .raster_porte import CLASSES_PORTE_PADRAO
    classes_porte = classes_porte if classes_porte is not None else CLASSES_PORTE_PADRAO

    mask = np.zeros(arr_n1.shape, dtype=bool)
    for c in codigos_n1:
        mask |= (arr_n1 == c)

    dist_vazia = _distribuir_por_classe(np.array([]), classes_porte)
    metricas_vazias = {"TCA": 0.0, "CORE_MN": 0.0, "NDCA": 0}

    if not np.any(mask):
        return metricas_vazias, dist_vazia, dist_vazia

    # ── Fragmento total: rotular uma única vez ────────────────────────────
    rot_frag, n_frags  = nd_label(mask)
    areas_px_frag = np.bincount(rot_frag.ravel())[1:]  # ignora fundo (índice 0)
    areas_ha_frag = areas_px_frag * px_ha
    dist_frag = _distribuir_por_classe(areas_ha_frag, classes_porte)

    # ── Área núcleo: erosão + rotular uma única vez ───────────────────────
    r = int(n_pixels)
    y, x = np.ogrid[-r:r+1, -r:r+1]
    struct  = (x*x + y*y <= r*r)
    erodido = binary_erosion(mask, structure=struct)

    if not np.any(erodido):
        return metricas_vazias, dist_frag, dist_vazia

    rot_nuc, n_comp = nd_label(erodido)
    areas_px_nuc = np.bincount(rot_nuc.ravel())[1:]
    areas_ha_nuc = areas_px_nuc * px_ha
    dist_nuc = _distribuir_por_classe(areas_ha_nuc, classes_porte)

    TCA     = round(float(areas_ha_nuc.sum()), 4)
    CORE_MN = round(TCA / max(n_frags, 1), 4)
    metricas = {"TCA": TCA, "CORE_MN": CORE_MN, "NDCA": int(n_comp)}

    return metricas, dist_frag, dist_nuc


def calcular_pls_classe(arr_n1, px_m, codigos_n1, prog=None):
    """
    Calcula métricas de classe via PyLandStats.
    Para grupos com múltiplos códigos (ex: Cobertura Natural = [1,10]),
    cria um array sintético onde todos os códigos viram código 1 antes
    de passar ao PyLandStats — assim as classes são tratadas como uma.
    """
    try:
        import pylandstats as pls
    except ImportError:
        return {}

    # Array de trabalho: remapear todos os codigos do grupo para código 1
    arr_pls = np.zeros_like(arr_n1)
    for c in codigos_n1:
        arr_pls[arr_n1 == c] = 1
    # Demais classes: manter com seus valores originais (contexto da paisagem)
    # para que TE/ED sejam calculados corretamente contra os vizinhos reais
    for val in np.unique(arr_n1):
        if val not in codigos_n1 and val > 0 and val != 255:
            arr_pls[arr_n1 == val] = int(val) + 100  # offset para não colidir

    try:
        ls = pls.Landscape(arr_pls, res=(px_m, px_m), nodata=0)
        nomes_pls = [METRICAS_CLASSE_PLS[s] for s in METRICAS_CLASSE_PLS
                     if hasattr(ls, METRICAS_CLASSE_PLS[s])]
        if not nomes_pls:
            return {}

        df = ls.compute_class_metrics_df(metrics=nomes_pls)
        if 1 not in df.index:
            return {}

        row = df.loc[1]
        resultado = {}
        for sigla, nome_pls in METRICAS_CLASSE_PLS.items():
            if nome_pls not in df.columns:
                continue
            v = float(row[nome_pls])
            if math.isnan(v) or math.isinf(v):
                continue
            if sigla in ("CA", "AREA_MN"):
                v = round(v / 10000, 4)   # m² → ha
            elif sigla == "MESH":
                v = round(v / 10000, 4)
            else:
                v = round(v, 4)
            resultado[sigla] = v
        return resultado

    except Exception as e:
        if prog: prog(f"  ⚠ PyLandStats: {e}")
        return {}


def calcular_pls_paisagem(arr_n1, px_m, prog=None):
    """Calcula MESH e LSI para o recorte como um todo."""
    try:
        import pylandstats as pls
    except ImportError:
        return {}

    arr_pls = arr_n1.copy()
    arr_pls[arr_pls < 0] = 0
    arr_pls[arr_pls == 255] = 0

    try:
        ls  = pls.Landscape(arr_pls, res=(px_m, px_m), nodata=0)
        nomes = [v for v in METRICAS_PAISAGEM_PLS.values()
                 if hasattr(ls, v)]
        if not nomes:
            return {}
        df = ls.compute_landscape_metrics_df(metrics=nomes)
        resultado = {}
        for sigla, nome_pls in METRICAS_PAISAGEM_PLS.items():
            if nome_pls not in df.columns:
                continue
            v = float(df[nome_pls].iloc[0])
            if math.isnan(v) or math.isinf(v):
                continue
            if sigla == "MESH":
                v = round(v / 10000, 4)
            else:
                v = round(v, 4)
            resultado[sigla] = v
        return resultado
    except Exception as e:
        if prog: prog(f"  ⚠ PyLandStats (paisagem): {e}")
        return {}


# ── Processamento completo ────────────────────────────────────────────────────

def processar_completo(raster1, raster2, ano1, ano2,
                        n_pixels_borda,
                        grupos_ids=None,
                        mascara_path=None, campo_feicao=None,
                        pixel_m_manual=None,
                        classes_porte=None,
                        progresso_fn=None):
    """
    Retorna dict:
    {
      '__shape_completo__': {
          ano1: { 'grupos': {nome: {CA, NP, ...}}, 'paisagem': {MESH, LSI} },
          ano2: { ... }
      },
      'Feição X': { ... },
      '_meta': { px_m, px_ha, gt, proj, arr1_n1, arr2_n1, nd }
    }
    """
    def prog(msg):
        log(msg); progresso_fn and progresso_fn(msg)

    prog(f"Abrindo rasters {ano1} e {ano2}...")
    arr1, px_m, px_ha, nd, gt, proj, aviso_crs = abrir_raster(
        raster1, pixel_m_manual)
    arr2, px_m2, _,    _,  _,  _,   _          = abrir_raster(
        raster2, pixel_m_manual)
    if aviso_crs:
        prog(f"  ⚠ {aviso_crs}")

    # Alinhar se dimensões diferentes
    if arr1.shape != arr2.shape:
        r = min(arr1.shape[0], arr2.shape[0])
        c = min(arr1.shape[1], arr2.shape[1])
        prog(f"  ⚠ Dimensões diferentes — alinhando para ({r},{c})")
        arr1 = arr1[:r, :c]
        arr2 = arr2[:r, :c]

    # Usar resolução do raster 1
    dist_m = round(n_pixels_borda * px_m)
    prog(f"Agregando para N1 | Borda: {n_pixels_borda}px = {dist_m}m")

    # Resolver classes de porte (limiares de tamanho de fragmento) —
    # usa o preset padrão (Sudeste/Mata Atlântica) se nada for informado
    from .raster_porte import CLASSES_PORTE_PADRAO
    if classes_porte is None:
        classes_porte = CLASSES_PORTE_PADRAO
    prog(f"Classes de porte: {len(classes_porte)} classe(s), "
         f"maior limiar = {classes_porte[-1][0]:g} ha")

    # Filtrar grupos selecionados pelo usuário
    grupos_ativos = [g for g in GRUPOS_FRAG
                     if grupos_ids is None or g['id'] in grupos_ids]
    if not grupos_ativos:
        grupos_ativos = [g for g in GRUPOS_FRAG if g.get('natural')]
    prog(f"  Grupos: {[g['nome'] for g in grupos_ativos]}")

    arr1_n1 = agregar_n1(arr1)
    arr2_n1 = agregar_n1(arr2)

    resultado = {'_meta': {
        'px_m': px_m, 'px_ha': px_ha, 'gt': gt, 'proj': proj,
        'nd': nd, 'arr1_n1': arr1_n1, 'arr2_n1': arr2_n1,
        'n_pixels': n_pixels_borda, 'dist_m': dist_m,
        'classes_porte': classes_porte, 'aviso_crs': aviso_crs,
    }}

    def processar_rec(a1_n1, a2_n1, nome_rec):
        prog(f"  Processando: {nome_rec}...")
        rec = {}
        for ano, arr_n1 in [(str(ano1), a1_n1), (str(ano2), a2_n1)]:
            grupos_res = {}
            dist_res   = {}
            for grp in grupos_ativos:
                nome_g  = grp['nome']
                cods_n1 = grp['codigos_n1']
                prog(f"    {ano} | {nome_g}...")
                m_pls = calcular_pls_classe(arr_n1, px_m, cods_n1, prog)
                m_nuc, dist_frag, dist_nuc = calcular_nucleo_e_distribuicao(
                    arr_n1, cods_n1, px_ha, n_pixels_borda,
                    classes_porte=classes_porte, prog=prog)
                grupos_res[nome_g] = {**m_pls, **m_nuc}
                dist_res[nome_g]   = {'fragmentos': dist_frag,
                                      'nucleo': dist_nuc}
            m_pai = calcular_pls_paisagem(arr_n1, px_m, prog)
            rec[ano] = {'grupos': grupos_res, 'paisagem': m_pai,
                       'distribuicao': dist_res}
        return rec

    resultado['__shape_completo__'] = processar_rec(
        arr1_n1, arr2_n1, 'Shape Completo')

    if mascara_path and campo_feicao:
        from osgeo import ogr
        ds = ogr.Open(mascara_path)
        if ds:
            lyr     = ds.GetLayer(0)
            crs_wkt = lyr.GetSpatialRef().ExportToWkt() \
                      if lyr.GetSpatialRef() else proj
            n_feats = lyr.GetFeatureCount()
            prog(f"Desagregando por feições: {n_feats} feição(ões) em '{campo_feicao}'...")
            for feat in lyr:
                nome = str(feat.GetField(campo_feicao))
                geom = feat.GetGeometryRef()
                if geom is None:
                    continue
                try:
                    s1 = recortar_por_geom(arr1, nd, gt, proj,
                                           geom.Clone(), crs_wkt)
                    s2 = recortar_por_geom(arr2, nd, gt, proj,
                                           geom.Clone(), crs_wkt)
                    s1_n1 = agregar_n1(s1)
                    s2_n1 = agregar_n1(s2)
                    resultado[nome] = processar_rec(s1_n1, s2_n1, nome)
                except Exception as e:
                    prog(f"  ⚠ {nome}: {e}")
            lyr.ResetReading()
        else:
            prog(f"  ⚠ ATENÇÃO: não foi possível abrir o shape de unidades "
                 f"em '{mascara_path}'. A desagregação por feições foi "
                 f"pulada — apenas o Shape Completo foi processado. "
                 f"Verifique se o caminho do arquivo está correto.")

    return resultado
