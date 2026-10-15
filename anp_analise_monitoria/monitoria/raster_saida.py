"""
AnP — Monitoria de Cobertura da Terra
Exportação de rasters de apoio à análise:

  1. Raster de MUDANÇA (transição) — cada pixel recebe o código
     cod_trans = classe_origem*100 + classe_destino, preservando os
     códigos ORIGINAIS de cada classe MapBiomas (não as 6 categorias
     agregadas do Excel). Isso permite identificar espacialmente
     transições específicas — por exemplo, filtrar no QGIS apenas os
     pixels onde Soja (39) virou Cana (20): cod_trans = 3920.
     Gerado sempre para o Shape Completo, e também para cada feição
     quando a análise é desagregada.

  2. Rasters de COBERTURA recortados — os arrays já recortados por
     feição (arr1/arr2), salvos como GeoTIFF + QML para conferência
     visual direta do recorte usado em cada unidade de análise.
     Gerado apenas quando a desagregação por feições está ativa (o
     raster do Shape Completo já é o próprio arquivo de entrada).
"""
import os
import numpy as np


def salvar_raster(arr, gt, proj, path, nd=0, dtype_gdal=None):
    """Salva um array numpy como GeoTIFF com compressão LZW."""
    from osgeo import gdal
    dtype_gdal = dtype_gdal or gdal.GDT_Int32
    rows, cols = arr.shape
    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(path, cols, rows, 1, dtype_gdal,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt); ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(nd)
    b.WriteArray(arr)
    b.FlushCache()
    ds = None


def calcular_raster_mudanca(arr1, arr2, nd):
    """
    Retorna um array onde cada pixel = cod_orig*100 + cod_dest,
    usando os códigos ORIGINAIS de classe (já agregados ao nível de
    legenda escolhido pelo usuário, mas preservando a granularidade
    daquele nível — não as 6 categorias do Excel). Pixels inválidos
    em qualquer um dos dois anos recebem nodata.
    """
    valido = (arr1 > 0) & (arr2 > 0)
    if nd is not None:
        valido &= (arr1 != nd) & (arr2 != nd)

    saida = np.zeros(arr1.shape, dtype=np.int32)
    saida[valido] = arr1[valido].astype(np.int32) * 100 + arr2[valido].astype(np.int32)
    return saida


def exportar_rasters(resultado, pasta, ano1, ano2,
                     gerar_mudanca_codigos=True,
                     gerar_mudanca_categorias=True,
                     progresso_fn=None):
    """
    Percorre todas as unidades em `resultado` (Shape Completo + cada
    feição, se desagregado) e exporta os rasters solicitados:

      1. gerar_mudanca_codigos: raster com cod_trans = orig*100+dest
         (códigos ORIGINAIS de classe MapBiomas) — permite localizar
         transições específicas (ex: Soja → Cana). Gerado para TODAS
         as unidades, inclusive Shape Completo.

      2. gerar_mudanca_categorias: raster com as 6 categorias
         ecológicas de mudança (reaproveita gerar_raster_mudancas() já
         existente em qml_gerador.py, antes gerado só para o Shape
         Completo — agora também por feição quando desagregado).

    Obs.: o recorte da cobertura de cada ano por feição NÃO é exportado
    aqui — essa etapa pertence ao módulo AnP - Preparação de Dados
    (recorte/regionalização por campo do shapefile). A Monitoria gera
    apenas o comparativo entre os dois anos.

    Retorna a lista de arquivos gerados (TIF + QML).
    """
    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    arquivos = []
    meta = resultado.get('_raster_meta', {})
    nd   = meta.get('nd')
    proj = meta.get('proj')

    unidades = {k: v for k, v in resultado.items()
               if isinstance(v, dict) and '_arr1' in v}

    for nome, dados in unidades.items():
        lbl  = 'ShapeCompleto' if nome == '__shape_completo__' else nome
        slug = "".join(c if c.isalnum() else "_" for c in lbl)[:60]
        a1   = dados['_arr1']; a2 = dados['_arr2']
        gt_u = dados.get('_gt') or meta.get('gt')
        eh_recorte = (nome != '__shape_completo__')

        if gerar_mudanca_codigos:
            try:
                arr_mud = calcular_raster_mudanca(a1, a2, nd)
                tif = os.path.join(pasta, f"{ano1}_{ano2}_{slug}_mudanca_codigos.tif")
                salvar_raster(arr_mud, gt_u, proj, tif, nd=0)
                arquivos.append(tif)
                prog(f"  ✓ Raster de mudança (códigos originais): {os.path.basename(tif)}")
            except Exception as e:
                prog(f"  ⚠ Falha no raster de mudança (códigos) de {lbl}: {e}")

        if gerar_mudanca_categorias:
            try:
                from .qml_gerador import gerar_raster_mudancas, gerar_qml
                tif = os.path.join(pasta, f"{ano1}_{ano2}_{slug}_mudanca_categorias.tif")
                qml = os.path.splitext(tif)[0] + ".qml"
                gerar_raster_mudancas(
                    arr1=a1, arr2=a2, nodata=nd, gt=gt_u, proj=proj,
                    caminho_tif=tif, progresso_fn=prog)
                gerar_qml(qml, ano1, ano2)
                arquivos += [tif, qml]
                prog(f"  ✓ Raster de mudança (categorias): {os.path.basename(tif)}")
            except Exception as e:
                prog(f"  ⚠ Falha no raster de categorias de {lbl}: {e}")

    return arquivos
