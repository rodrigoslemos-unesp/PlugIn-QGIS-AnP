"""
AnP — Relatório de Cobertura da Terra v1.1
Processa múltiplos rasters (anos) mantendo o código original de cada pixel
(nível mais detalhado disponível no raster) e anexando os códigos e nomes
de todos os níveis ancestrais (N1–N4) como colunas — formato tidy único,
sem agregação prévia por nível.
"""
import os
import numpy as np
from qgis.core import QgsMessageLog, Qgis

LOG = 'AnP-Relatorio'

def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(str(msg), LOG, level)


def abrir_info_raster(path):
    from osgeo import gdal, osr
    ds  = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"Não foi possível abrir: {path}")
    gt   = ds.GetGeoTransform()
    proj = ds.GetProjection()
    nd   = ds.GetRasterBand(1).GetNoDataValue()
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    srs  = osr.SpatialReference(); srs.ImportFromWkt(proj)
    is_proj = bool(srs.IsProjected())
    px_m    = abs(gt[1]) if is_proj else None
    px_ha   = (px_m**2)/10000 if is_proj else None
    nome_crs = srs.GetName() or "Desconhecido"
    srs.AutoIdentifyEPSG()
    epsg = srs.GetAuthorityCode(None)
    try: epsg = int(epsg)
    except Exception: epsg = None
    return dict(gt=gt, proj=proj, nd=nd, cols=cols, rows=rows,
                is_proj=is_proj, px_m=px_m, px_ha=px_ha,
                nome_crs=nome_crs, epsg=epsg)


def calcular_area_pixel(info, pixel_m_manual=None):
    """
    Retorna (px_ha, aviso).
    Se projetado: calcula do geotransform (área exata).
    Se geográfico: usa pixel_m_manual (default 30m Landsat) — estimativa.
    """
    if info['is_proj']:
        return info['px_ha'], None
    pm = pixel_m_manual or 30
    px_ha = (pm**2)/10000
    aviso = (f"CRS geográfico ({info['nome_crs']}). "
             f"Área estimada com pixel de {pm}m × {pm}m "
             f"({pm**2} m² = {px_ha:.4f} ha/pixel).")
    return px_ha, aviso


def contar_por_classe(arr_orig, nd, px_ha):
    """
    Conta pixels por código ORIGINAL (sem agregação prévia) e anexa
    os códigos/nomes de todos os níveis ancestrais (N1-N4).

    Retorna dict: { cod_original: {n, ha, pct, nome,
                                    cod_n1, nome_n1, ..., cod_n4, nome_n4} }
    """
    from ..comum.legenda import CLASSES_EXCLUIR, nome_classe, ancestrais

    excluir = set(CLASSES_EXCLUIR)
    if nd is not None:
        excluir.add(int(nd))

    valid = arr_orig[(arr_orig > 0) & (~np.isin(arr_orig, list(excluir)))]
    tot   = len(valid) or 1

    contagem = {}
    for cod in np.unique(valid):
        c   = int(cod)
        n   = int(np.sum(valid == c))
        ha  = round(n * px_ha, 4)
        pct = round(n / tot, 6)
        anc = ancestrais(c)
        contagem[c] = {
            'n': n, 'ha': ha, 'pct': pct,
            'nome': nome_classe(c),
            **anc,
        }
    return contagem


def recortar_janela(ds, gt, proj, geom, crs_wkt):
    """Leitura em janela + reprojeção automática de geometria."""
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

    sub = sub.copy(); nd_v = -1
    sub[mask == 0] = nd_v
    return sub, nd_v, gt_s


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


def processar_relatorio(entradas, shapefile=None, campo_id=None,
                         pixel_m_manual=None, gerar_tif=True,
                         pasta_tif=None, progresso_fn=None):
    """
    Processa múltiplos rasters e retorna:
    {
      '_meta': { ano: {info_raster, px_ha, aviso_crs} },
      'Shape Completo': { ano: { cod_original: {n, ha, pct, nome, cod_n1...} } },
      'Feição X': { ano: { ... } },
    }
    """
    from osgeo import gdal, ogr

    def prog(msg):
        log(msg); progresso_fn and progresso_fn(msg)

    resultado = {'_meta': {}}
    entradas_ord = sorted(entradas, key=lambda x: x['ano'])
    n_tot = len(entradas_ord)

    for i, entrada in enumerate(entradas_ord):
        ano  = entrada['ano']
        path = entrada['path']
        prog(f"\n[{i+1}/{n_tot}] Processando ano {ano}...")

        info = abrir_info_raster(path)
        px_ha, aviso = calcular_area_pixel(info, pixel_m_manual)
        resultado['_meta'][ano] = {
            'path': path, 'info': info,
            'px_ha': px_ha, 'aviso_crs': aviso
        }
        if aviso:
            prog(f"  ⚠ {aviso}")

        ds = gdal.Open(path)
        arr_orig = ds.GetRasterBand(1).ReadAsArray().astype(np.int32)

        prog(f"  Shape completo...")
        dados_classe = contar_por_classe(arr_orig, info['nd'], px_ha)
        if 'Shape Completo' not in resultado:
            resultado['Shape Completo'] = {}
        resultado['Shape Completo'][ano] = dados_classe

        if gerar_tif and pasta_tif:
            try:
                from .qml_mapbiomas import gerar_qml_junto_tif
                nome_tif = f"{ano}_ShapeCompleto.tif"
                path_tif = os.path.join(pasta_tif, nome_tif)
                salvar_raster(arr_orig, info['gt'], info['proj'],
                              path_tif, nd=int(info['nd']) if info['nd'] else 0)
                cods = list(dados_classe.keys())
                gerar_qml_junto_tif(path_tif, codigos_presentes=cods)
                prog(f"  ✓ TIF+QML: {nome_tif}")
            except Exception as e:
                prog(f"  ⚠ Falha ao salvar TIF do Shape Completo: {e}")

        if shapefile and campo_id:
            ds_vec = ogr.Open(shapefile)
            lyr    = ds_vec.GetLayer(0)
            crs_wkt = (lyr.GetSpatialRef().ExportToWkt()
                       if lyr.GetSpatialRef() else info['proj'])
            n_feats = lyr.GetFeatureCount()

            for feat in lyr:
                nome_feat = str(feat.GetField(campo_id))[:60]
                geom      = feat.GetGeometryRef()
                if geom is None:
                    continue
                try:
                    sub, nd_sub, gt_sub = recortar_janela(
                        ds, info['gt'], info['proj'],
                        geom.Clone(), crs_wkt)
                    dados_f = contar_por_classe(sub, nd_sub, px_ha)
                    if nome_feat not in resultado:
                        resultado[nome_feat] = {}
                    resultado[nome_feat][ano] = dados_f

                    if gerar_tif and pasta_tif:
                        try:
                            from .qml_mapbiomas import gerar_qml_junto_tif
                            slug = "".join(
                                c if c.isalnum() else "_" for c in nome_feat)
                            nome_tif = f"{ano}_{slug}.tif"
                            path_tif = os.path.join(pasta_tif, nome_tif)
                            salvar_raster(sub, gt_sub, info['proj'],
                                          path_tif, nd=nd_sub)
                            cods = list(dados_f.keys())
                            gerar_qml_junto_tif(path_tif, codigos_presentes=cods)
                            prog(f"    ✓ TIF+QML: {nome_tif}")
                        except Exception as e2:
                            prog(f"    ⚠ Falha ao salvar TIF de {nome_feat}: {e2}")

                    prog(f"  {nome_feat} ✓")
                except Exception as e:
                    prog(f"  ⚠ {nome_feat}: {e}")

            lyr.ResetReading(); ds_vec = None
        ds = None

    return resultado
