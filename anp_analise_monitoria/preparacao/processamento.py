"""
AnP — Preparação de Dados v1.1
Três operações independentes e combináveis:
  A) Alinhar grades (snap ao raster de referência)
  B) Recortar por shapefile
  C) Reprojetar para outro CRS
"""
import os
import numpy as np
from qgis.core import QgsMessageLog, Qgis

LOG = 'AnP-Prep'

def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(str(msg), LOG, level)


# Projeção Cônica Equivalente de Albers para o Brasil, nos parâmetros do
# IBGE, sobre o SIRGAS 2000. Não tem código EPSG oficial, então é montada
# a partir dos parâmetros e passada ao GDAL como WKT.
ALBERS_BR = 'ALBERS_BR'
ALBERS_BR_NOME = "SIRGAS 2000 / Brazil Albers Equal Area (IBGE)"


def wkt_albers_brasil():
    from osgeo import osr
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4674)                       # SIRGAS 2000 geográfico
    srs.SetProjCS(ALBERS_BR_NOME)
    srs.SetACEA(-2.0, -22.0,                       # paralelos-padrão
                -12.0, -54.0,                      # latitude de origem, meridiano central
                5000000.0, 10000000.0)             # falso E, falso N
    srs.SetLinearUnits(osr.SRS_UL_METER, 1.0)
    return srs.ExportToWkt()


def detectar_crs_raster(path):
    from osgeo import gdal, osr
    ds  = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    gt  = ds.GetGeoTransform()
    prj = ds.GetProjection()
    ds  = None
    srs = osr.SpatialReference()
    srs.ImportFromWkt(prj)
    is_proj = bool(srs.IsProjected())
    srs.AutoIdentifyEPSG()
    epsg = srs.GetAuthorityCode(None)
    try: epsg = int(epsg)
    except (TypeError, ValueError): epsg = None
    return {
        'is_projected': is_proj,
        'epsg': epsg,
        'nome_crs': srs.GetName() or "Desconhecido",
        'gt': gt,
    }


def obter_info_grade(path):
    from osgeo import gdal
    ds   = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    gt   = ds.GetGeoTransform()
    proj = ds.GetProjection()
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    ds   = None
    return gt, proj, cols, rows


def grades_identicas(gt1, shape1, gt2, shape2, tol=1e-6):
    if shape1 != shape2:
        return False
    for i in range(6):
        if abs(gt1[i] - gt2[i]) > tol:
            return False
    return True


def listar_tifs(pasta):
    exts = {'.tif', '.tiff', '.TIF', '.TIFF'}
    return sorted([
        f for f in os.listdir(pasta)
        if os.path.splitext(f)[1] in exts
    ])


def salvar_raster(arr, gt, proj, path, nd=0):
    """Salva um array numpy como GeoTIFF Int32 com compressão LZW."""
    from osgeo import gdal
    rows, cols = arr.shape
    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(path, cols, rows, 1, gdal.GDT_Int32,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt); ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(nd)
    b.WriteArray(arr)
    b.FlushCache()
    ds = None


def recortar_por_feicao(ds, gt, proj, geom, crs_wkt, nd=0):
    """
    Recorta o raster já processado (ds) pela geometria de UMA feição,
    lendo apenas a janela sobreposta e mascarando o restante.

    Reprojeta automaticamente a geometria para o CRS do raster quando
    diferem (mesma técnica das demais funções de recorte por geometria
    do AnP — evita o erro 'Feição sem sobreposição' quando o shapefile
    está em CRS diferente do raster).

    Retorna (sub, gt_s): array recortado e geotransform da janela.
    """
    from osgeo import gdal, ogr, osr

    g = geom.Clone()
    if not g.IsValid():
        g = g.MakeValid()

    srs_r = osr.SpatialReference(); srs_r.ImportFromWkt(proj)
    srs_r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    srs_v = osr.SpatialReference(); srs_v.ImportFromWkt(crs_wkt)
    srs_v.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    if not srs_r.IsSame(srs_v):
        g.Transform(osr.CoordinateTransformation(srs_v, srs_r))
        crs_mask = proj
    else:
        crs_mask = crs_wkt

    cols_tot = ds.RasterXSize; rows_tot = ds.RasterYSize
    env = g.GetEnvelope()
    px0 = max(0, int((env[0]-gt[0])/gt[1]))
    px1 = min(cols_tot, int((env[1]-gt[0])/gt[1])+2)
    py0 = max(0, int((env[3]-gt[3])/gt[5]))
    py1 = min(rows_tot, int((env[2]-gt[3])/gt[5])+2)
    if px0 >= px1 or py0 >= py1:
        raise ValueError("Feição sem sobreposição com o raster.")

    w, h = px1-px0, py1-py0
    sub  = ds.GetRasterBand(1).ReadAsArray(px0, py0, w, h)
    gt_s = (gt[0]+px0*gt[1], gt[1], gt[2], gt[3]+py0*gt[5], gt[4], gt[5])

    mem = gdal.GetDriverByName('MEM')
    mds = mem.Create('', w, h, 1, gdal.GDT_Byte)
    mds.SetGeoTransform(gt_s); mds.SetProjection(proj)
    mds.GetRasterBand(1).Fill(0)
    vds = ogr.GetDriverByName('Memory').CreateDataSource('')
    srs = osr.SpatialReference(); srs.ImportFromWkt(crs_mask)
    lyr = vds.CreateLayer('', srs=srs)
    ft  = ogr.Feature(lyr.GetLayerDefn()); ft.SetGeometry(g)
    lyr.CreateFeature(ft)
    gdal.RasterizeLayer(mds, [1], lyr, burn_values=[1])
    mds.FlushCache()
    mask = mds.GetRasterBand(1).ReadAsArray()
    mds = vds = None

    sub = sub.copy()
    sub[mask == 0] = nd
    return sub, gt_s


def preparar_rasters(entradas, pasta_saida,
                     op_alinhar=True,
                     op_recortar=True,
                     op_reprojetar=False,
                     shapefile=None,
                     epsg_saida=31983,
                     gerar_qml=False,
                     desagregar=False,
                     campo_id=None,
                     progresso_fn=None):
    """
    Executa as operações selecionadas sobre cada raster de entrada.

    op_alinhar   : alinhar à grade do raster de menor ano
    op_recortar  : recortar pelo shapefile
    op_reprojetar: reprojetar para epsg_saida (código EPSG ou ALBERS_BR)

    Qualquer combinação é válida, inclusive uma única operação.
    Se nenhuma operação for selecionada, lança ValueError.
    """
    from osgeo import gdal, ogr

    def prog(msg):
        log(msg)
        if progresso_fn: progresso_fn(msg)

    if not (op_alinhar or op_recortar or op_reprojetar):
        raise ValueError(
            "Selecione ao menos uma operação (Alinhar, Recortar ou Reprojetar).")

    if not entradas:
        raise ValueError("Nenhum raster fornecido.")

    os.makedirs(pasta_saida, exist_ok=True)

    # Ordenar por ano
    entradas_ord = sorted(entradas, key=lambda x: x['ano'])

    # ── Grade de referência (só usada se op_alinhar=True) ─────────────────────
    ref = entradas_ord[0]
    gt_ref = proj_ref = None
    cols_ref = rows_ref = None
    xmin_ref = ymin_ref = xmax_ref = ymax_ref = None
    xres_ref = yres_ref = None

    if op_alinhar:
        gt_ref, proj_ref, cols_ref, rows_ref = obter_info_grade(ref['path'])
        xres_ref = gt_ref[1]
        yres_ref = abs(gt_ref[5])
        xmin_ref = gt_ref[0]
        ymax_ref = gt_ref[3]
        xmax_ref = xmin_ref + xres_ref * cols_ref
        ymin_ref = ymax_ref - yres_ref * rows_ref
        prog(f"Grade de referência: {ref['ano']} — "
             f"{cols_ref}×{rows_ref} px | res={xres_ref}m")

    arquivos_gerados = []

    for i, entrada in enumerate(entradas_ord):
        ano       = entrada['ano']
        path_orig = entrada['path']
        nome_base = entrada['nome_base']

        nome_saida = nome_base
        if not nome_saida.lower().endswith('.tif'):
            nome_saida += '.tif'
        path_saida = os.path.join(pasta_saida, nome_saida)

        prog(f"\n[{i+1}/{len(entradas_ord)}] {ano} — {os.path.basename(path_orig)}")
        prog(f"  → {nome_saida}")

        # ── Construir opções do Warp de acordo com as operações ───────────────
        last_pct = [0]
        def gdal_prog(complete, message, cb_data):
            pct = int(complete * 100)
            if pct >= last_pct[0] + 10:
                last_pct[0] = pct
                prog(f"    ... {pct}%")
            return 1

        warp_opts = dict(
            format          = 'GTiff',
            resampleAlg     = gdal.GRA_NearestNeighbour,
            outputType      = gdal.GDT_Int32,
            creationOptions = ['COMPRESS=LZW', 'TILED=YES'],
            dstNodata       = 0,
            callback        = gdal_prog,
        )

        # Operação C — Reprojeção
        if op_reprojetar:
            if epsg_saida == ALBERS_BR:
                warp_opts['dstSRS'] = wkt_albers_brasil()
                prog(f"  → Reprojetando para {ALBERS_BR_NOME}")
            else:
                warp_opts['dstSRS'] = f"EPSG:{epsg_saida}"
                prog(f"  → Reprojetando para EPSG:{epsg_saida}")

        # Operação B — Recorte por shapefile
        if op_recortar and shapefile:
            warp_opts['cutlineDSName'] = shapefile
            warp_opts['cropToCutline'] = True
            prog(f"  → Recortando pelo shapefile")

        # Operação A — Alinhamento de grade
        # (aplica em todos exceto o raster de referência)
        if op_alinhar and i > 0:
            gt_this, _, cols_this, rows_this = obter_info_grade(path_orig)
            if not grades_identicas(gt_ref, (rows_ref, cols_ref),
                                    gt_this, (rows_this, cols_this)):
                prog(f"  → Alinhando grade ao raster de referência ({ref['ano']})")
                warp_opts['outputBounds'] = (xmin_ref, ymin_ref,
                                             xmax_ref, ymax_ref)
                warp_opts['width']  = cols_ref
                warp_opts['height'] = rows_ref
            else:
                prog(f"  → Grade já idêntica à referência")
        elif op_alinhar and i == 0:
            prog(f"  → Raster de referência (grade mantida)")

        # ── Executar ──────────────────────────────────────────────────────────
        ops_ativas = []
        if op_alinhar:   ops_ativas.append("A:alinhar")
        if op_recortar:  ops_ativas.append("B:recortar")
        if op_reprojetar: ops_ativas.append("C:reprojetar")
        prog(f"  Executando Warp [{' + '.join(ops_ativas)}]...")

        resultado = gdal.Warp(path_saida, path_orig, **warp_opts)

        if resultado is None:
            prog(f"  ⚠ Falha ao processar {ano}.")
            continue

        resultado.FlushCache()
        resultado = None

        tamanho = os.path.getsize(path_saida) / (1024*1024)
        prog(f"  ✓ Salvo: {nome_saida} ({tamanho:.1f} MB)")
        arquivos_gerados.append(path_saida)

        # Gerar QML MapBiomas se solicitado
        if gerar_qml:
            try:
                from .qml_mapbiomas import gerar_qml_junto_tif
                path_qml = gerar_qml_junto_tif(path_saida)
                prog(f"  ✓ QML: {os.path.basename(path_qml)}")
                arquivos_gerados.append(path_qml)
            except Exception as e:
                prog(f"  ⚠ Falha ao gerar QML: {e}")

        # ── Desagregação: um TIF recortado por feição (regionalização) ────────
        # Gera, a partir do raster já processado, um recorte para cada feição
        # do shapefile, usando o campo escolhido como identificador da região
        # (mesma lógica de desagregação do módulo Relatório de Cobertura).
        if desagregar and shapefile and campo_id:
            try:
                ds_r   = gdal.Open(path_saida)
                gt_r   = ds_r.GetGeoTransform()
                proj_r = ds_r.GetProjection()
                ds_v   = ogr.Open(shapefile)
                lyr    = ds_v.GetLayer(0)
                crs_wkt = (lyr.GetSpatialRef().ExportToWkt()
                           if lyr.GetSpatialRef() else proj_r)
                stem = os.path.splitext(nome_saida)[0]
                n_ok = 0
                for feat in lyr:
                    valor     = feat.GetField(campo_id)
                    nome_feat = str(valor)[:60] if valor is not None else "sem_valor"
                    geom      = feat.GetGeometryRef()
                    if geom is None:
                        continue
                    slug = "".join(c if c.isalnum() else "_" for c in nome_feat)
                    try:
                        sub, gt_s = recortar_por_feicao(
                            ds_r, gt_r, proj_r, geom.Clone(), crs_wkt, nd=0)
                        nome_sub = f"{stem}_{slug}.tif"
                        path_sub = os.path.join(pasta_saida, nome_sub)
                        salvar_raster(sub, gt_s, proj_r, path_sub, nd=0)
                        arquivos_gerados.append(path_sub)
                        n_ok += 1
                        prog(f"    ✓ Recorte por feição: {nome_sub}")
                        if gerar_qml:
                            try:
                                from .qml_mapbiomas import gerar_qml_junto_tif
                                pq = gerar_qml_junto_tif(path_sub)
                                arquivos_gerados.append(pq)
                            except Exception as eq:
                                prog(f"      ⚠ Falha no QML de {slug}: {eq}")
                    except Exception as ef:
                        prog(f"    ⚠ {nome_feat}: {ef}")
                lyr.ResetReading(); ds_v = None; ds_r = None
                prog(f"  ✓ Desagregação por '{campo_id}': "
                     f"{n_ok} feição(ões) recortada(s).")
            except Exception as e:
                prog(f"  ⚠ Falha na desagregação por feição: {e}")

    return arquivos_gerados
