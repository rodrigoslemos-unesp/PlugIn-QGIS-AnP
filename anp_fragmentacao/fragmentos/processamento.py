# -*- coding: utf-8 -*-
"""
AnP — Fragmentos: processamento (GDAL/OGR).

Fluxo:
  1. abre o raster e EXIGE CRS projetado (área/borda/núcleo só valem em metros);
  2. (opcional) recorta por feição do shapefile, etiquetando a unidade —
     reprojetando a geometria para o CRS do raster (padrão da suíte AnP);
  3. monta a máscara-alvo (um valor, ou vários — agregando ou separando);
  4. rotula e mede os fragmentos (motor em `metricas.py`);
  5. vetoriza o raster rotulado (GDAL Polygonize, casando id↔polígono 1:1);
  6. grava um shapefile de fragmentos + um Excel-resumo.
"""
import os
import numpy as np

from .metricas import metricas_de_mascara
from ..comum.legenda import nome_classe


# ── CRS / raster ───────────────────────────────────────────────────────────────
def crs_projetado(proj_wkt):
    from osgeo import osr
    srs = osr.SpatialReference()
    srs.ImportFromWkt(proj_wkt)
    return bool(srs.IsProjected())


def mesmo_crs(proj_wkt_a, wkt_b):
    """True se os dois CRS forem o mesmo (osr.IsSame)."""
    from osgeo import osr
    a = osr.SpatialReference(); a.ImportFromWkt(proj_wkt_a)
    b = osr.SpatialReference(); b.ImportFromWkt(wkt_b)
    return bool(a.IsSame(b))


def _slug(texto):
    return "".join(c if c.isalnum() else "_" for c in str(texto))[:60]


def salvar_tif(labeled, gt, proj, path):
    """Grava o array de fragmentos rotulados (id por pixel, 0 = fundo)."""
    from osgeo import gdal
    rows, cols = labeled.shape
    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(path, cols, rows, 1, gdal.GDT_Int32,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt); ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(0)
    b.WriteArray(labeled)
    b.FlushCache()
    ds = None


def abrir_raster(path):
    from osgeo import gdal
    ds = gdal.Open(path)
    if ds is None:
        raise IOError(f"Não foi possível abrir o raster: {path}")
    band = ds.GetRasterBand(1)
    arr  = band.ReadAsArray()
    gt   = ds.GetGeoTransform()
    proj = ds.GetProjection()
    nd   = band.GetNoDataValue()
    ds = None
    return arr, gt, proj, nd


# ── Recorte por feição (reprojeta a geometria p/ o CRS do raster) ──────────────
def recortar_por_feicao(arr, gt, proj, geom, crs_wkt):
    """
    Retorna (sub, gt_s, dentro): a janela do array que cobre a feição, o
    geotransform dessa janela e uma máscara booleana 'dentro' (True nos
    pixels que caem na geometria). A geometria é reprojetada para o CRS
    do raster quando os dois divergem — sem isso, feição em CRS diferente
    calcula índices de pixel fora dos limites ("Feição sem sobreposição").
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

    rows_tot, cols_tot = arr.shape
    env = g.GetEnvelope()  # (minX, maxX, minY, maxY)
    px0 = max(0, int((env[0] - gt[0]) / gt[1]))
    px1 = min(cols_tot, int((env[1] - gt[0]) / gt[1]) + 2)
    py0 = max(0, int((env[3] - gt[3]) / gt[5]))
    py1 = min(rows_tot, int((env[2] - gt[3]) / gt[5]) + 2)
    if px0 >= px1 or py0 >= py1:
        raise ValueError("Feição sem sobreposição com o raster.")

    w, h = px1 - px0, py1 - py0
    sub  = arr[py0:py1, px0:px1]
    gt_s = (gt[0] + px0 * gt[1], gt[1], gt[2],
            gt[3] + py0 * gt[5], gt[4], gt[5])

    # rasteriza a feição na janela → máscara 'dentro'
    mem = gdal.GetDriverByName('MEM')
    mds = mem.Create('', w, h, 1, gdal.GDT_Byte)
    mds.SetGeoTransform(gt_s); mds.SetProjection(proj)
    mds.GetRasterBand(1).Fill(0)
    vds = ogr.GetDriverByName('Memory').CreateDataSource('')
    lyr = vds.CreateLayer('', srs=srs_r)
    ft  = ogr.Feature(lyr.GetLayerDefn()); ft.SetGeometry(g)
    lyr.CreateFeature(ft)
    gdal.RasterizeLayer(mds, [1], lyr, burn_values=[1])
    dentro = mds.GetRasterBand(1).ReadAsArray().astype(bool)
    mds = vds = None
    return sub, gt_s, dentro


# ── Máscara-alvo ───────────────────────────────────────────────────────────────
def _mascara(sub, valores, dentro):
    m = np.isin(sub, list(valores))
    if dentro is not None:
        m = m & dentro
    return m


# ── Vetorização de um raster rotulado (id global por pixel) ───────────────────
def _vetorizar(labeled, gt_s, proj, dst_layer):
    """Polygoniza o array rotulado e adiciona os polígonos a dst_layer,
    com o campo 'DN' = id do fragmento (0 = fundo, ignorado)."""
    from osgeo import gdal, ogr
    rows, cols = labeled.shape
    mem = gdal.GetDriverByName('MEM')
    rds = mem.Create('', cols, rows, 1, gdal.GDT_Int32)
    rds.SetGeoTransform(gt_s); rds.SetProjection(proj)
    b = rds.GetRasterBand(1)
    b.WriteArray(labeled); b.SetNoDataValue(0)
    mask_b = rds.GetRasterBand(1)  # usa o próprio (nodata=0 exclui o fundo)
    gdal.Polygonize(b, mask_b, dst_layer, 0, ['8CONNECTED=8'])
    rds = None


# ── Definição dos campos do shapefile (nomes ≤ 10 chars) ──────────────────────
CAMPOS = [
    ('id_frag',  'int'),
    ('classe',   'int'),
    ('classe_nm', 'str'),   # nome legível (até 10 chars no shp: 'classe_nm')
    ('unidade',  'str'),
    ('area_ha',  'real'),
    ('perim_m',  'real'),
    ('core_ha',  'real'),
    ('n_core',   'int'),
    ('cai_pct',  'real'),
    ('shape_idx', 'real'),
    ('frac',     'real'),
    ('circ',     'real'),
    ('enn_m',    'real'),
]


def _criar_shapefile(path, proj):
    from osgeo import ogr, osr
    drv = ogr.GetDriverByName('ESRI Shapefile')
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds  = drv.CreateDataSource(path)
    srs = osr.SpatialReference(); srs.ImportFromWkt(proj)
    lyr = ds.CreateLayer('fragmentos', srs=srs, geom_type=ogr.wkbPolygon)
    tipo = {'int': ogr.OFTInteger, 'real': ogr.OFTReal, 'str': ogr.OFTString}
    for nome, t in CAMPOS:
        fd = ogr.FieldDefn(nome, tipo[t])
        if t == 'str':
            fd.SetWidth(60)
        lyr.CreateField(fd)
    return ds, lyr


# ── Função principal ───────────────────────────────────────────────────────────
def processar_fragmentos(raster, valores, pasta_saida, nome_base,
                         modo_agregar=False, conn=8, depth_px=1,
                         area_min_ha=0.0,
                         shapefile=None, campo=None,
                         progresso_fn=None):
    """
    Retorna dict com: 'shapefile', 'excel', 'registros', 'meta'.
    Levanta ValueError se o raster não estiver em CRS projetado.
    """
    from osgeo import ogr

    def prog(m):
        if progresso_fn:
            progresso_fn(m)

    arr, gt, proj, nd = abrir_raster(raster)
    if not crs_projetado(proj):
        raise ValueError(
            "O raster está em CRS geográfico (graus). Área, perímetro, "
            "núcleo e distâncias só têm sentido em metros. Rode primeiro "
            "o módulo Preparação com reprojeção para um CRS projetado "
            "(ex.: EPSG:31983) e use o raster reprojetado aqui.")

    res_x, res_y = abs(gt[1]), abs(gt[5])
    prog(f"Raster: {arr.shape[1]}×{arr.shape[0]} px  ·  pixel {res_x:.1f}×{res_y:.1f} m")
    prog(f"Profundidade de borda (núcleo): {depth_px} px  ≈ {depth_px*res_x:.0f} m")

    # unidades de análise
    unidades = []   # (nome_unidade, sub, gt_s, dentro)
    if shapefile and campo:
        vds = ogr.Open(shapefile)
        lyr = vds.GetLayer(0)
        crs_wkt = (lyr.GetSpatialRef().ExportToWkt()
                   if lyr.GetSpatialRef() else None)
        # ── Exige MESMA projeção entre shapefile e raster ────────────────────
        # (reprojetar a geometria em tempo de execução pode deslocar pixels de
        #  borda e gerar pequenas diferenças de área; melhor recusar e pedir
        #  ao usuário que reprojete o shapefile para o CRS do raster.)
        if crs_wkt is None:
            vds = None
            raise ValueError(
                "O shapefile de unidades não tem CRS definido. Defina o mesmo "
                "CRS do raster e tente de novo.")
        if not mesmo_crs(proj, crs_wkt):
            vds = None
            raise ValueError(
                "O shapefile de unidades e o raster estão em projeções "
                "diferentes. Reprojete o shapefile para o MESMO CRS do raster "
                "(ex.: EPSG:31983) antes de rodar — assim o recorte fica "
                "alinhado ao pixel, sem diferenças de área.")
        prog(f"Desagregando por '{campo}' ({lyr.GetFeatureCount()} feição(ões))...")
        for feat in lyr:
            valor = feat.GetField(campo)
            nome_u = str(valor) if valor is not None else "sem_valor"
            geom = feat.GetGeometryRef()
            if geom is None:
                continue
            try:
                sub, gt_s, dentro = recortar_por_feicao(arr, gt, proj,
                                                        geom.Clone(), crs_wkt)
                unidades.append((nome_u, sub, gt_s, dentro))
            except Exception as e:
                prog(f"  ⚠ Unidade '{nome_u}' ignorada: {e}")
        vds = None
        if not unidades:
            raise ValueError("Nenhuma feição sobrepôs o raster.")
    else:
        unidades.append(("Shape Completo", arr, gt, None))

    os.makedirs(pasta_saida, exist_ok=True)
    por_unidade = bool(shapefile and campo)
    valores = list(valores)

    registros = []          # todos os fragmentos (para o Excel consolidado)
    shapefiles = []         # um por unidade (ou um único, sem desagregação)
    tifs = []               # idem
    id_offset = 0

    for nome_u, sub, gt_s, dentro in unidades:
        # conjuntos-alvo: um só (agregado) ou um por valor
        if modo_agregar:
            grupos = [(valores, "+".join(str(v) for v in valores))]
        else:
            grupos = [([v], v) for v in valores]

        labeled_u = np.zeros(sub.shape, dtype=np.int32)  # canvas da unidade
        regs_u = []
        for vals, classe in grupos:
            mask = _mascara(sub, vals, dentro)
            if not mask.any():
                continue
            labeled, regs, id_offset = metricas_de_mascara(
                mask, res_x, res_y, depth_px, conn=conn,
                classe=(classe if not modo_agregar else None),
                unidade=nome_u, area_min_ha=area_min_ha,
                id_offset=id_offset)
            if not regs:
                continue
            for r in regs:
                if modo_agregar:
                    r['classe']    = None
                    r['classe_nm'] = f"Agregado ({classe})"
                else:
                    r['classe_nm'] = nome_classe(classe)
            # funde no canvas da unidade (grupos são mutuamente exclusivos)
            labeled_u[labeled > 0] = labeled[labeled > 0]
            regs_u.extend(regs)
            prog(f"  {nome_u} · classe {classe}: {len(regs)} fragmento(s)")

        if not regs_u:
            prog(f"  {nome_u}: nenhum fragmento.")
            continue
        registros.extend(regs_u)

        # sufixo de arquivo: por unidade quando desagregado, senão 'fragmentos'
        suf = _slug(nome_u) if por_unidade else "fragmentos"

        # 1) TIFF de fragmentos rotulados desta unidade
        tif_path = os.path.join(pasta_saida, f"{nome_base}_{suf}.tif")
        salvar_tif(labeled_u, gt_s, proj, tif_path)
        tifs.append(tif_path)
        prog(f"  ✓ TIFF: {os.path.basename(tif_path)}")

        # 2) Shapefile desta unidade (vetorizado do MESMO canvas do TIFF)
        shp_path = os.path.join(pasta_saida, f"{nome_base}_{suf}.shp")
        ds_out, lyr_out = _criar_shapefile(shp_path, proj)
        defn = lyr_out.GetLayerDefn()
        metr_por_id = {r['id_frag']: r for r in regs_u}
        mem_ds = ogr.GetDriverByName('Memory').CreateDataSource('')
        from osgeo import osr
        srs = osr.SpatialReference(); srs.ImportFromWkt(proj)
        tmp = mem_ds.CreateLayer('t', srs=srs, geom_type=ogr.wkbPolygon)
        tmp.CreateField(ogr.FieldDefn('DN', ogr.OFTInteger))
        _vetorizar(labeled_u, gt_s, proj, tmp)
        for pf in tmp:
            r = metr_por_id.get(pf.GetField('DN'))
            if r is None:
                continue
            of = ogr.Feature(defn)
            of.SetGeometry(pf.GetGeometryRef().Clone())
            of.SetField('id_frag', int(r['id_frag']))
            if r['classe'] is not None:
                of.SetField('classe', int(r['classe']))
            of.SetField('classe_nm', str(r['classe_nm'])[:60])
            of.SetField('unidade', str(r['unidade'])[:60])
            of.SetField('area_ha', float(r['area_ha']))
            of.SetField('perim_m', float(r['perim_m']))
            of.SetField('core_ha', float(r['core_ha']))
            of.SetField('n_core', int(r['n_core']))
            of.SetField('cai_pct', float(r['cai_pct']))
            of.SetField('shape_idx', float(r['shape_idx']))
            if r['frac'] is not None:
                of.SetField('frac', float(r['frac']))
            if r['circ'] is not None:
                of.SetField('circ', float(r['circ']))
            if r['enn_m'] is not None:
                of.SetField('enn_m', float(r['enn_m']))
            lyr_out.CreateFeature(of); of = None
        mem_ds = None
        ds_out = None
        shapefiles.append(shp_path)
        prog(f"  ✓ Shapefile: {os.path.basename(shp_path)} ({len(regs_u)} frag.)")

    if not registros:
        raise ValueError("Nenhum fragmento encontrado com os valores informados.")

    meta = {
        'raster'      : os.path.basename(raster),
        'res_x'       : res_x, 'res_y': res_y,
        'valores'     : valores,
        'modo'        : "agregado" if modo_agregar else "separado por valor",
        'conn'        : conn,
        'depth_px'    : depth_px,
        'depth_m'     : depth_px * res_x,
        'area_min_ha' : area_min_ha,
        'n_frag'      : len(registros),
        'por_unidade' : por_unidade,
        'campo'       : campo,
        'n_arquivos'  : len(shapefiles),
    }

    from .excel_saida import exportar_excel
    xls_path = os.path.join(pasta_saida, f"{nome_base}_resumo.xlsx")
    exportar_excel(xls_path, registros, meta, progresso_fn=progresso_fn)

    return {'shapefiles': shapefiles, 'tifs': tifs, 'excel': xls_path,
            'registros': registros, 'meta': meta}
