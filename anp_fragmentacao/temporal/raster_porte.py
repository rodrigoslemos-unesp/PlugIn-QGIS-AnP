"""
AnP Fragmentação — Raster de classes de porte (tamanho) dos fragmentos.

Gera, para o fragmento TOTAL (antes da erosão) e para a ÁREA NÚCLEO
(após a erosão morfológica), um raster onde cada fragmento (mancha
conectada) recebe um código correspondente à sua classe de tamanho:

    < 1 ha                  → 1
    >= 1 ha  e  < 10 ha      → 10
    >= 10 ha e  < 20 ha      → 20
    >= 20 ha e  < 30 ha      → 30
    >= 30 ha e  < 50 ha      → 50
    >= 50 ha e  < 100 ha     → 100
    >= 100 ha e < 200 ha     → 200
    >= 200 ha                → 201  (classe "acima de 200 ha")

O objetivo é permitir avaliar espacialmente a distribuição dos
fragmentos por classe de tamanho — por exemplo, visualizar se os
fragmentos pequenos (<10ha) predominam nas bordas da área de estudo
ou se concentram próximos a áreas antrópicas.
"""
import os
import numpy as np


def _esc_xml(txt):
    """
    Escapa caracteres especiais de XML em texto dinâmico antes de
    inserir em atributos do QML — evita quebra de parsing quando o
    rótulo contém '<', '>', '&' ou aspas (ex: "< 1 ha").
    """
    return (str(txt)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))

# Classes de porte: (limite_inferior_ha, limite_superior_ha, codigo, rotulo)
# Rótulos em texto puro (ASCII), sem hífen especial ou símbolos —
# usados tanto no QML (legenda no QGIS) quanto nas planilhas tidy
# Dist_Fragmentos/Dist_Nucleos e no script R de gráficos, garantindo
# correspondência exata de string entre Python e R (factor levels).
#
# IMPORTANTE: esta escala de 1–200 ha foi calibrada para paisagens
# fragmentadas do Sudeste (Mata Atlântica, SP) — nesse contexto,
# "grande" já significa acima de 200 ha. Para biomas com blocos
# florestais muito maiores (ex: Amazônia), essa escala classificaria
# quase toda a paisagem como "Maior que 200 ha", perdendo capacidade
# de diferenciação. Por isso os limiares agora são configuráveis —
# ver PRESETS_PORTE e construir_classes_porte() abaixo. Esta lista
# continua sendo o padrão ("Sudeste / Mata Atlântica").
CLASSES_PORTE_PADRAO = [
    (0,     1,       1, "Menor que 1 ha"),
    (1,     10,      2, "1 a 10 ha"),
    (10,    20,      3, "10 a 20 ha"),
    (20,    30,      4, "20 a 30 ha"),
    (30,    50,      5, "30 a 50 ha"),
    (50,    100,     6, "50 a 100 ha"),
    (100,   200,     7, "100 a 200 ha"),
    (200,   float('inf'), 8, "Maior que 200 ha"),
]

# Compatibilidade: código antigo que importa CLASSES_PORTE direto
# continua funcionando, apontando para o padrão.
CLASSES_PORTE = CLASSES_PORTE_PADRAO

# ── Presets de limiares por contexto de paisagem ──────────────────────────────
# Cada preset é uma lista de PONTOS DE CORTE em hectares (não a tupla
# completa) — construir_classes_porte() monta os intervalos, códigos
# e rótulos automaticamente a partir desses pontos.
PRESETS_PORTE = {
    "Sudeste / Mata Atlântica (padrão)": [1, 10, 20, 30, 50, 100, 200],
    "Cerrado / Paisagens intermediárias": [5, 25, 50, 100, 250, 500, 1000],
    "Amazônia / Grandes blocos florestais": [10, 100, 500, 1000, 5000, 10000, 50000],
    "Bacias hidrográficas / Escala regional": [50, 250, 500, 1000, 2500, 5000, 10000],
}


def construir_classes_porte(pontos_corte):
    """
    Constrói a lista de classes (lim_inf, lim_sup, cod, rotulo) a
    partir de uma lista de pontos de corte em hectares, ordenada
    crescentemente. Ex: [1, 10, 20, 30, 50, 100, 200] gera 8 classes
    (a primeira "< 1 ha" e a última "≥ maior ponto de corte").

    Os códigos são sempre sequenciais (1, 2, 3...) — o raster de
    porte é gravado como uint8, então os códigos precisam caber em
    0-255; derivar códigos dos valores de corte (que podem chegar a
    dezenas de milhares de hectares na Amazônia) estouraria esse
    limite. O valor de hectares fica só no rótulo, não no código.
    """
    pontos = sorted(set(float(p) for p in pontos_corte if p > 0))
    if not pontos:
        return list(CLASSES_PORTE_PADRAO)
    if len(pontos) > 200:
        pontos = pontos[:200]  # limite de seguranca para uint8

    classes = [(0.0, pontos[0], 1, f"Menor que {_fmt_ha(pontos[0])}")]
    for i in range(len(pontos) - 1):
        classes.append((
            pontos[i], pontos[i+1], i + 2,
            f"{_fmt_num(pontos[i])} a {_fmt_ha(pontos[i+1])}"
        ))
    classes.append((
        pontos[-1], float('inf'), len(pontos) + 1,
        f"Maior que {_fmt_ha(pontos[-1])}"
    ))
    return classes


def _fmt_num(v):
    """Formata um número sem casas decimais desnecessárias (sem 'ha')."""
    return f"{int(v)}" if v == int(v) else f"{v:g}"


def _fmt_ha(v):
    """Formata um valor em hectares sem casas decimais desnecessárias."""
    if v == int(v):
        return f"{int(v)} ha"
    return f"{v:g} ha"


def gerar_cores_porte(classes_porte):
    """
    Gera uma rampa de cores clara→escura com uma cor por classe,
    proporcional ao número de classes (funciona para 4, 8 ou 12
    classes, não só as 8 do padrão).
    """
    import colorsys
    n = len(classes_porte)
    cores = {}
    # Rampa amarelo -> laranja -> vermelho -> roxo -> azul escuro
    paleta_base = ["FFF9C4","FFE082","FFB74D","FF8A65",
                   "E57373","AB47BC","5C6BC0","1A237E"]
    for i, (_, _, cod, _) in enumerate(classes_porte):
        idx = round(i * (len(paleta_base)-1) / max(1, n-1))
        cores[cod] = paleta_base[idx]
    return cores


def classificar_porte(area_ha, classes_porte=None):
    """Retorna o código de classe de porte para uma área em hectares."""
    classes = classes_porte if classes_porte is not None else CLASSES_PORTE_PADRAO
    for lim_inf, lim_sup, cod, _ in classes:
        if lim_inf <= area_ha < lim_sup:
            return cod
    return classes[-1][2]


def gerar_raster_porte(mask_bool, px_ha, gt, proj, caminho_tif,
                       classes_porte=None, progresso_fn=None):
    """
    Rotula cada fragmento (componente conectado) da máscara binária
    com o código de classe de porte correspondente à sua área total.

    mask_bool  : array booleano — True onde há cobertura do grupo/núcleo
    px_ha      : área de um pixel em hectares
    gt, proj   : geotransform e projeção do raster de origem
    caminho_tif: caminho de saída do GeoTIFF classificado

    Retorna o caminho do arquivo gerado.
    """
    from osgeo import gdal
    from scipy.ndimage import label

    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    rotulos, n_frags = label(mask_bool)
    if n_frags == 0:
        prog("  ⚠ Nenhum fragmento encontrado — raster de porte não gerado.")
        return None

    # Área de cada fragmento (vetorizado via bincount)
    areas_px = np.bincount(rotulos.ravel())
    areas_ha = areas_px * px_ha  # índice 0 = fundo, ignorado

    # Construir array de saída: cada pixel recebe o código de porte
    # do fragmento ao qual pertence
    arr_porte = np.zeros(mask_bool.shape, dtype=np.uint8)

    classes = classes_porte if classes_porte is not None else CLASSES_PORTE_PADRAO

    # Mapear cada fragmento para seu código de porte
    codigo_por_frag = np.zeros(n_frags + 1, dtype=np.uint8)
    for frag_id in range(1, n_frags + 1):
        codigo_por_frag[frag_id] = classificar_porte(areas_ha[frag_id], classes)

    # Aplicar o mapeamento vetorizado (fancy indexing)
    arr_porte = codigo_por_frag[rotulos]

    rows, cols = mask_bool.shape
    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(caminho_tif, cols, rows, 1, gdal.GDT_Byte,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt); ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(0)
    b.WriteArray(arr_porte)
    b.FlushCache(); ds = None

    prog(f"  ✓ Raster de porte: {os.path.basename(caminho_tif)} "
         f"({n_frags} fragmento(s))")
    return caminho_tif


def gerar_qml_porte(caminho_qml, titulo="Classe de Porte", classes_porte=None):
    """QML paletted com a rampa de cores por classe de tamanho."""
    classes = classes_porte if classes_porte is not None else CLASSES_PORTE_PADRAO
    cores_porte = gerar_cores_porte(classes)
    entradas = ['        <paletteEntry value="0" color="#ffffff" '
               'alpha="0" label="Sem fragmento / Nodata"/>']
    for lim_inf, lim_sup, cod, rotulo in classes:
        cor = cores_porte[cod]
        entradas.append(
            f'        <paletteEntry value="{cod}" color="#{cor}" '
            f'alpha="255" label="{_esc_xml(rotulo)}"/>')

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
      </minMaxOrigin>
      <colorPalette>
{chr(10).join(entradas)}
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


def gerar_rasters_porte(resultado, pasta, ano1, ano2, grupos_ids=None,
                        classes_porte=None, progresso_fn=None):
    """
    Gera, para cada grupo natural × ano, dois rasters classificados por
    porte: um para o fragmento TOTAL e outro para a ÁREA NÚCLEO.

    Requer que resultado['_meta'] contenha arr1_n1, arr2_n1, gt, proj,
    px_ha e n_pixels (mesma estrutura usada por raster_nucleo.py).

    Retorna lista de arquivos gerados (TIF + QML).
    """
    from ..comum.legenda import GRUPOS_FRAG
    from scipy.ndimage import binary_erosion

    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    meta = resultado.get('_meta', {})
    if not meta:
        return []

    gt     = meta['gt']
    proj   = meta['proj']
    px_ha  = meta['px_ha']
    n_px   = meta['n_pixels']
    arquivos = []

    # Respeitar apenas os grupos selecionados pelo usuário na interface
    grupos_ativos = [g for g in GRUPOS_FRAG
                     if grupos_ids is None or g['id'] in grupos_ids]
    if not grupos_ativos:
        grupos_ativos = [g for g in GRUPOS_FRAG if g.get('natural')]

    for ano in (ano1, ano2):
        arr_n1 = meta.get(f'arr{"1" if str(ano)==str(ano1) else "2"}_n1')
        if arr_n1 is None:
            continue

        for grp in grupos_ativos:
            if not grp.get('natural'):
                continue
            nome_g = grp['nome']
            cods   = grp['codigos_n1']
            gid    = grp['id']

            mask = np.zeros(arr_n1.shape, dtype=bool)
            for c in cods:
                mask |= (arr_n1 == c)

            if not np.any(mask):
                continue

            prog(f"  Classificando porte: {nome_g} | {ano}...")

            # ── Fragmento TOTAL (antes da erosão) ────────────────────────────
            tif_tot = os.path.join(pasta, f"{ano}_{gid}_fragmentos_porte.tif")
            qml_tot = os.path.join(pasta, f"{ano}_{gid}_fragmentos_porte.qml")
            try:
                r = gerar_raster_porte(mask, px_ha, gt, proj, tif_tot,
                                       classes_porte=classes_porte,
                                       progresso_fn=prog)
                if r:
                    gerar_qml_porte(qml_tot, f"Porte — {nome_g} (fragmento total)",
                                    classes_porte=classes_porte)
                    arquivos += [tif_tot, qml_tot]
            except Exception as e:
                prog(f"  ⚠ Fragmento total {nome_g} {ano}: {e}")

            # ── Área NÚCLEO (após erosão) ────────────────────────────────────
            r_px = int(n_px)
            y, x = np.ogrid[-r_px:r_px+1, -r_px:r_px+1]
            struct  = (x*x + y*y <= r_px*r_px)
            erodido = binary_erosion(mask, structure=struct)

            if not np.any(erodido):
                continue

            tif_nuc = os.path.join(pasta, f"{ano}_{gid}_nucleo_porte.tif")
            qml_nuc = os.path.join(pasta, f"{ano}_{gid}_nucleo_porte.qml")
            try:
                r = gerar_raster_porte(erodido, px_ha, gt, proj, tif_nuc,
                                       classes_porte=classes_porte,
                                       progresso_fn=prog)
                if r:
                    gerar_qml_porte(qml_nuc, f"Porte — {nome_g} (área núcleo)",
                                    classes_porte=classes_porte)
                    arquivos += [tif_nuc, qml_nuc]
            except Exception as e:
                prog(f"  ⚠ Área núcleo {nome_g} {ano}: {e}")

    return arquivos
