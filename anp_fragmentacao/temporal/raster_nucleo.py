"""
AnP Fragmentação — Geração de rasters de área núcleo + QML.
Um TIF por grupo × ano, com QML do mesmo nome.
"""
import os
import numpy as np


def _esc_xml(txt):
    """Escapa caracteres especiais de XML em texto dinâmico do QML."""
    return (str(txt)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))

def gerar_raster_nucleo(arr_n1, codigos_n1, n_pixels, gt, proj,
                         caminho_tif, progresso_fn=None):
    """
    Gera raster binário da área núcleo (1=núcleo, 0=nodata).
    """
    from osgeo import gdal
    from scipy.ndimage import binary_erosion

    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    mask = np.zeros(arr_n1.shape, dtype=bool)
    for c in codigos_n1:
        mask |= (arr_n1 == c)

    r = int(n_pixels)
    y, x = np.ogrid[-r:r+1, -r:r+1]
    struct  = (x*x + y*y <= r*r)
    erodido = binary_erosion(mask, structure=struct).astype(np.uint8)

    rows, cols = arr_n1.shape
    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(caminho_tif, cols, rows, 1, gdal.GDT_Byte,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt)
    ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(0)
    b.WriteArray(erodido)
    b.FlushCache(); ds = None

    fname = os.path.basename(caminho_tif)
    prog(f"  ✓ Raster núcleo: {fname}")
    return caminho_tif


def gerar_qml_nucleo(caminho_qml, nome_grupo, cor_hex="1976D2"):
    """
    QML para raster binário de área núcleo.
    Valor 0 = transparente, Valor 1 = cor do grupo.
    """
    qml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.22" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <pipe>
    <provider>
      <resampling enabled="false" maxOversampling="2"
        zoomedInResamplingMethod="nearestNeighbour"
        zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer type="paletted" band="1" opacity="1" nodataColor="">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <colorPalette>
        <paletteEntry value="0" label="Sem área núcleo / Nodata"
          color="#ffffff" alpha="0"/>
        <paletteEntry value="1" label="Área núcleo — {_esc_xml(nome_grupo)}"
          color="#{cor_hex}" alpha="220"/>
      </colorPalette>
      <colorRamp type="randomcolors" name="Random Colors">
        <Option/>
      </colorRamp>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0"
      colorizeOn="0" colorizeRed="255" colorizeGreen="128"
      colorizeBlue="128" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
  <customproperties><Option/></customproperties>
</qgis>
"""
    with open(caminho_qml, 'w', encoding='utf-8') as f:
        f.write(qml)


# Cores por grupo para os QMLs
CORES_GRUPO = {
    "Floresta"                  : "1B5E20",
    "Veg. Herbácea e Arbustiva" : "558B2F",
    "Cobertura Natural"         : "2E7D32",
    "Corpo D'água"              : "0277BD",
}


def gerar_rasters_nucleo(resultado, pasta, ano1, ano2, grupos_ids=None, progresso_fn=None):
    """
    Gera TIF + QML para cada grupo natural × ano.
    Retorna lista de arquivos gerados.
    """
    from ..comum.legenda import GRUPOS_FRAG

    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    meta = resultado.get('_meta', {})
    if not meta:
        return []

    gt      = meta['gt']
    proj    = meta['proj']
    n_px    = meta['n_pixels']
    dist_m  = meta['dist_m']
    arquivos = []

    # Respeitar apenas os grupos selecionados pelo usuário na interface
    grupos_ativos = [g for g in GRUPOS_FRAG
                     if grupos_ids is None or g['id'] in grupos_ids]
    if not grupos_ativos:
        grupos_ativos = [g for g in GRUPOS_FRAG if g.get('natural')]

    for rec, dados in resultado.items():
        if rec == '_meta' or not isinstance(dados, dict):
            continue
        lbl  = ('SC' if rec == '__shape_completo__' else
                "".join(c if c.isalnum() else "_" for c in str(rec))[:60])

        for ano, ano_k in [(ano1, str(ano1)), (ano2, str(ano2))]:
            arr_n1 = meta.get(f'arr{"1" if str(ano)==str(ano1) else "2"}_n1')
            if arr_n1 is None:
                continue

            for grp in grupos_ativos:
                if not grp.get('natural'):
                    continue
                nome_g   = grp['nome']
                cods     = grp['codigos_n1']
                nome_arq = f"{ano}_{lbl}_nucleo_{grp['id']}"
                tif      = os.path.join(pasta, nome_arq + ".tif")
                qml      = os.path.join(pasta, nome_arq + ".qml")
                cor      = CORES_GRUPO.get(nome_g, "388E3C")

                prog(f"  Área núcleo: {nome_g} | {ano} | borda={n_px}px ({dist_m}m)...")
                try:
                    gerar_raster_nucleo(arr_n1, cods, n_px,
                                        gt, proj, tif, prog)
                    gerar_qml_nucleo(qml, nome_g, cor)
                    prog(f"  ✓ QML: {os.path.basename(qml)}")
                    arquivos += [tif, qml]
                except Exception as e:
                    prog(f"  ⚠ {nome_g} {ano}: {e}")

    return arquivos
