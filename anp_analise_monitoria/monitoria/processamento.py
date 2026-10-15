"""
AnP v1.1 — Monitoria de Cobertura da Terra
Processamento de rasters MapBiomas.

Novidade: alinhamento automático de grade via GDAL Warp
antes de qualquer processamento. Garante que os dois rasters
compartilhem exatamente os mesmos pixels, eliminando erros de
comparação por deslocamento de grade.
"""

import numpy as np
from qgis.core import QgsMessageLog, Qgis
from ..comum.legenda import (LEGENDA, LEGENDA_NIVEL, GRUPOS, CLASSES_EXCLUIR,
                      categoria_transicao, COLECOES,
                      agregar_nivel, descricao_nivel)

LOG = 'AnP-Monitoria'


def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(str(msg), LOG, level)


# ── Detecção de CRS ──────────────────────────────────────────────────────────

def detectar_crs(path):
    from osgeo import gdal, osr
    ds  = gdal.Open(path)
    if ds is None:
        return {'is_projected': False, 'pixel_m2': None,
                'pixel_ha': None, 'unidade_crs': 'desconhecido'}
    gt  = ds.GetGeoTransform()
    prj = ds.GetProjection()
    ds  = None
    srs = osr.SpatialReference()
    srs.ImportFromWkt(prj)
    is_proj = bool(srs.IsProjected())
    if is_proj:
        px_m  = abs(gt[1])
        px_m2 = px_m ** 2
        px_ha = px_m2 / 10000.0
    else:
        px_m2 = None
        px_ha = None
    return {'is_projected': is_proj, 'pixel_m2': px_m2,
            'pixel_ha': px_ha, 'unidade_crs': 'metro' if is_proj else 'grau'}


def area_pixel_ha(crs_info, colecao_nome):
    if crs_info['is_projected']:
        return crs_info['pixel_ha'], None
    col   = COLECOES.get(colecao_nome, {})
    px_m2 = col.get('px_m2', 900)
    px_ha = px_m2 / 10000.0
    res   = col.get('resolucao_m', 30)
    aviso = (
        f"Raster sem coordenadas projetadas. "
        f"Área calculada com pixel padrão de {res}m × {res}m "
        f"({px_m2} m² = {px_ha:.4f} ha). "
        f"Valores em ha/km² são estimativas — use o percentual.")
    return px_ha, aviso


# ── Abertura de raster ────────────────────────────────────────────────────────

def abrir_raster(path):
    from osgeo import gdal
    ds   = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    gt   = ds.GetGeoTransform()
    proj = ds.GetProjection()
    band = ds.GetRasterBand(1)
    nd   = band.GetNoDataValue()
    arr  = band.ReadAsArray().astype(np.int32)
    ds   = None
    return arr, gt, proj, nd


# ── Alinhamento automático de grade ─────────── ───────────────────────────────

def grades_identicas(gt1, shape1, gt2, shape2, tol=1e-6):
    """
    Verifica se dois rasters compartilham exatamente a mesma grade:
    mesma origem, mesma resolução e mesmas dimensões.
    """
    if shape1 != shape2:
        return False
    for i in range(6):
        if abs(gt1[i] - gt2[i]) > tol:
            return False
    return True


def alinhar_raster(raster_ref_path, raster_alinhar_path, prog=None):
    """
    Reamostra raster_alinhar para a grade EXATA do raster_ref usando
    GDAL Warp em memória (sem gravar arquivo temporário em disco).

    Método: vizinho mais próximo (NearestNeighbour) — obrigatório para
    dados categóricos como os do MapBiomas. Interpolações bilineares ou
    cúbicas gerariam valores de classe sem sentido ecológico.

    Retorna (array_numpy, nodata, gt_ref, proj_ref).
    """
    from osgeo import gdal

    def p(msg):
        log(msg)
        if prog: prog(msg)

    # Abrir raster de referência para extrair a grade
    ds_ref = gdal.Open(raster_ref_path)
    if ds_ref is None:
        raise RuntimeError(f"Não foi possível abrir referência: {raster_ref_path}")

    gt   = ds_ref.GetGeoTransform()
    proj = ds_ref.GetProjection()
    cols = ds_ref.RasterXSize
    rows = ds_ref.RasterYSize
    ds_ref = None

    # Calcular extensão geográfica exata da referência
    xmin = gt[0]
    ymax = gt[3]
    xres = gt[1]
    yres = abs(gt[5])
    xmax = xmin + xres * cols
    ymin = ymax - yres * rows

    p(f"  Realinhando grade: {cols}×{rows} px | "
      f"xmin={xmin:.4f} xmax={xmax:.4f} | res={xres}m")

    # Warp em memória — sem arquivo temporário
    ds_out = gdal.Warp(
        '',                          # saída em memória
        raster_alinhar_path,
        format='MEM',
        outputBounds=(xmin, ymin, xmax, ymax),
        width=cols,
        height=rows,
        dstSRS=proj,
        resampleAlg=gdal.GRA_NearestNeighbour,
        outputType=gdal.GDT_Int32,
    )

    if ds_out is None:
        raise RuntimeError(
            f"GDAL Warp falhou ao alinhar: {raster_alinhar_path}")

    band = ds_out.GetRasterBand(1)
    arr  = band.ReadAsArray().astype(np.int32)
    nd   = band.GetNoDataValue()
    ds_out = None

    return arr, nd, gt, proj


def preparar_arrays(raster1, raster2, prog=None):
    """
    Abre os dois rasters e garante que compartilhem exatamente a
    mesma grade.

    Estratégia:
      1. Abrir os dois rasters e comparar grades.
      2. Se as grades forem idênticas → usar diretamente.
      3. Se diferirem → reamostrar raster2 para a grade do raster1
         via GDAL Warp (vizinho mais próximo, em memória).

    O raster1 (Ano 1) é sempre a grade de referência.
    """
    def p(msg):
        log(msg)
        if prog: prog(msg)

    arr1, gt1, proj1, nd1 = abrir_raster(raster1)
    arr2, gt2, proj2, nd2 = abrir_raster(raster2)

    if grades_identicas(gt1, arr1.shape, gt2, arr2.shape):
        p("  Grades idênticas — sem necessidade de realinhamento.")
        return arr1, arr2, gt1, proj1, nd1

    # Grades diferentes — informar e realinhar
    dlin = arr1.shape[0] - arr2.shape[0]
    dcol = arr1.shape[1] - arr2.shape[1]
    dgt  = [abs(gt1[i]-gt2[i]) for i in range(6)]

    p(f"  ⚠ Grades divergentes detectadas:")
    p(f"    Raster Ano 1: {arr1.shape[1]}×{arr1.shape[0]} px | "
      f"origem ({gt1[0]:.6f}, {gt1[3]:.6f}) | res {gt1[1]:.4f}m")
    p(f"    Raster Ano 2: {arr2.shape[1]}×{arr2.shape[0]} px | "
      f"origem ({gt2[0]:.6f}, {gt2[3]:.6f}) | res {gt2[1]:.4f}m")
    p(f"    Diferença: {abs(dlin)} linhas, {abs(dcol)} colunas | "
      f"desl. origem: {max(dgt):.6f}°/m")
    p(f"  → Realinhando Ano 2 para a grade do Ano 1 "
      f"(vizinho mais próximo, em memória)...")

    arr2_alin, nd2_alin, _, _ = alinhar_raster(raster1, raster2, prog)

    p(f"  ✓ Realinhamento concluído. "
      f"Grade final: {arr1.shape[1]}×{arr1.shape[0]} px")

    return arr1, arr2_alin, gt1, proj1, nd1


# ── Contagem e tabelas ────────────────────────────────────────────────────────

def contar_pixels(arr, nodata):
    excluir = set(CLASSES_EXCLUIR)
    if nodata is not None:
        excluir.add(int(nodata))
    contagem = {}
    for cls in np.unique(arr):
        cls_i = int(cls)
        if cls_i in excluir or cls_i <= 0:
            continue
        n = int(np.sum(arr == cls_i))
        if n > 0:
            contagem[cls_i] = n
    return contagem


def gerar_tabela_cobertura(c1, c2, px_ha, nivel=4):
    legenda_n = LEGENDA_NIVEL.get(nivel, LEGENDA)
    todas = sorted(
        k for k in set(c1) | set(c2)
        if k not in CLASSES_EXCLUIR and k > 0)
    tot1 = sum(v for k, v in c1.items()
               if k not in CLASSES_EXCLUIR and k > 0) or 1
    tot2 = sum(v for k, v in c2.items()
               if k not in CLASSES_EXCLUIR and k > 0) or 1
    tabela = []
    for cls in todas:
        n1 = c1.get(cls, 0)
        n2 = c2.get(cls, 0)
        tabela.append({
            'cod'  : cls,
            'nome' : legenda_n.get(cls, LEGENDA.get(cls, f'Código {cls}')),
            'grupo': GRUPOS.get(cls, 'Outros'),
            'n1'   : n1, 'n2': n2,
            'ha1'  : round(n1 * px_ha, 4),
            'ha2'  : round(n2 * px_ha, 4),
            'pct1' : round(n1 / tot1, 6),
            'pct2' : round(n2 / tot2, 6),
        })
    return tabela


def gerar_tabela_transicao(arr1, arr2, nodata, px_ha):
    from collections import Counter
    excluir = set(CLASSES_EXCLUIR)
    if nodata is not None:
        excluir.add(int(nodata))
    mask = (
        (arr1 > 0) & (arr2 > 0) &
        (~np.isin(arr1, list(excluir))) &
        (~np.isin(arr2, list(excluir))))
    pares = Counter(zip(arr1[mask].tolist(), arr2[mask].tolist()))
    tabela = []
    for (o, d), n in sorted(pares.items()):
        if n == 0:
            continue
        tabela.append({
            'cod_orig' : o,
            'nome_orig': LEGENDA.get(o, f'Código {o}'),
            'cod_dest' : d,
            'nome_dest': LEGENDA.get(d, f'Código {d}'),
            'cod_trans': o * 100 + d,
            'categoria': categoria_transicao(o, d),
            'n'        : n,
            'area_ha'  : round(n * px_ha, 4),
        })
    return tabela


# ── Recorte por feição ────────────────────────────────────────────────────────

def _recortar(arr_full, nd, gt, proj, geom, crs_wkt):
    """
    Recorta o array pela geometria da feição. Reprojeta automaticamente
    a geometria para o CRS do raster quando os dois divergem — sem essa
    reprojeção, feições em CRS diferente do raster (ex: shapefile em
    WGS84 geográfico, raster em SIRGAS UTM) calculam índices de pixel
    completamente fora dos limites, e a exceção "Feição sem sobreposição"
    é lançada para TODAS as feições silenciosamente (mesmo bug já
    corrigido nos módulos de Relatório e Fragmentação).
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

    rows, cols = arr_full.shape
    env = g.GetEnvelope()
    px0 = max(0, int((env[0]-gt[0])/gt[1]))
    px1 = min(cols, int((env[1]-gt[0])/gt[1])+2)
    py0 = max(0, int((env[3]-gt[3])/gt[5]))
    py1 = min(rows, int((env[2]-gt[3])/gt[5])+2)
    if px0 >= px1 or py0 >= py1:
        raise ValueError("Feição sem sobreposição.")
    sub  = arr_full[py0:py1, px0:px1].copy()
    h, w = sub.shape
    gt_s = (gt[0]+px0*gt[1], gt[1], gt[2],
            gt[3]+py0*gt[5], gt[4], gt[5])
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
    return sub, gt_s


# ── Fluxo principal ───────────────────────────────────────────────────────────

def processar_completo(raster1, raster2, ano1, ano2,
                        colecao_nome,
                        nivel_legenda=4,
                        mascara_path=None, campo_feicao=None,
                        progresso_fn=None):
    """
    Fluxo principal:
      1. Abre e alinha automaticamente as grades dos dois rasters
      2. Detecta CRS e calcula área do pixel
      3. Agrega para o nível de legenda solicitado
      4. Processa cobertura e transições (shape completo + feições)
    """
    def prog(msg):
        log(msg); progresso_fn and progresso_fn(msg)

    # ── 1. Alinhamento de grade ───────────────────────────────────────────────
    prog(f"Verificando alinhamento de grade entre {ano1} e {ano2}...")
    arr1, arr2, gt, proj, nd = preparar_arrays(raster1, raster2, prog)

    # ── 2. CRS e área do pixel ────────────────────────────────────────────────
    prog("Detectando sistema de coordenadas...")
    crs_info = detectar_crs(raster1)
    px_ha, aviso_crs = area_pixel_ha(crs_info, colecao_nome)

    avisos = []
    if aviso_crs:
        avisos.append(aviso_crs)
        prog(f"⚠ {aviso_crs}")

    # ── 3. Agregação de nível ─────────────────────────────────────────────────
    prog(f"Agregando ao {descricao_nivel(nivel_legenda)}...")
    arr1 = agregar_nivel(arr1, nivel_legenda)
    arr2 = agregar_nivel(arr2, nivel_legenda)

    resultado = {
        'avisos'        : avisos,
        '_px_ha'        : px_ha,
        '_is_projected' : crs_info['is_projected'],
        '_raster_meta'  : {
            'arr1': arr1, 'arr2': arr2,
            'nd': nd, 'gt': gt, 'proj': proj
        }
    }

    # ── 4. Processamento por recorte ──────────────────────────────────────────
    def processar_rec(a1, a2, nome, gt_unidade=None):
        prog(f"  Processando: {nome}...")
        c1 = contar_pixels(a1, nd)
        c2 = contar_pixels(a2, nd)
        return {
            'tab_cob'  : gerar_tabela_cobertura(c1, c2, px_ha, nivel_legenda),
            'tab_trans': gerar_tabela_transicao(a1, a2, nd, px_ha),
            '_arr1'    : a1,
            '_arr2'    : a2,
            '_gt'      : gt_unidade if gt_unidade is not None else gt,
        }

    resultado['__shape_completo__'] = processar_rec(arr1, arr2,
                                                     'Shape Completo')

    if mascara_path and campo_feicao:
        from osgeo import ogr
        ds = ogr.Open(mascara_path)
        if ds:
            lyr     = ds.GetLayer(0)
            crs_wkt = (lyr.GetSpatialRef().ExportToWkt()
                       if lyr.GetSpatialRef() else proj)
            n_feats = lyr.GetFeatureCount()
            prog(f"Desagregando por feições: {n_feats} feição(ões) em '{campo_feicao}'...")
            for feat in lyr:
                nome = str(feat.GetField(campo_feicao))
                geom = feat.GetGeometryRef()
                if geom is None:
                    continue
                try:
                    s1, gt_s = _recortar(arr1, nd, gt, proj,
                                         geom.Clone(), crs_wkt)
                    s2, _    = _recortar(arr2, nd, gt, proj,
                                         geom.Clone(), crs_wkt)
                    resultado[nome] = processar_rec(s1, s2, nome, gt_s)
                except Exception as e:
                    prog(f"  ⚠ {nome}: {e}")
            lyr.ResetReading()
        else:
            prog(f"  ⚠ ATENÇÃO: não foi possível abrir o shape de unidades "
                 f"em '{mascara_path}'. A desagregação por feições foi "
                 f"pulada — apenas o Shape Completo foi processado. "
                 f"Verifique se o caminho do arquivo está correto.")

    return resultado
