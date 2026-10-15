# -*- coding: utf-8 -*-
"""AnP — Fragmentos: geração do Excel-resumo (sem dependências externas)."""
import statistics as st
from ..comum.xlsx_writer import XlsxBook
from ..comum.metadados import escrever_metadados, VERSAO_SUITE

AVISO = (
    "\u26a0 SOFTWARE EM DESENVOLVIMENTO — Este plugin está em fase de "
    "testes e aprimoramento contínuo. Os resultados devem ser conferidos "
    "e validados pelo usuário antes de qualquer uso científico, técnico "
    "ou institucional. O autor e a instituição não se responsabilizam por "
    "eventuais erros, omissões, imprecisões ou uso indevido dos resultados."
)

# nome curto (shapefile) → descrição
DICIONARIO = [
    ("id_frag",  "Identificador único do fragmento"),
    ("classe",   "Código da classe (valor do raster)"),
    ("classe_nm", "Nome da classe (quando MapBiomas)"),
    ("unidade",  "Unidade de análise (feição do shapefile)"),
    ("area_ha",  "Área do fragmento (hectares)"),
    ("perim_m",  "Perímetro / comprimento de borda (metros)"),
    ("core_ha",  "Área núcleo (hectares), pela profundidade de borda"),
    ("n_core",   "Número de manchas de núcleo no fragmento"),
    ("cai_pct",  "Índice de área núcleo = core/área × 100 (%)"),
    ("shape_idx", "Índice de forma FRAGSTATS (1 = quadrado compacto)"),
    ("frac",     "Dimensão fractal (1 = simples, 2 = complexa)"),
    ("circ",     "Circularidade Polsby-Popper (1 = círculo)"),
    ("enn_m",    "Distância ao fragmento vizinho mais próximo (m, aprox.)"),
]


def _aba_metadados(wb, meta):
    ws = wb.add_sheet("Metadados")
    ws.set_col_width(1, 22); ws.set_col_width(2, 70)
    ws.write(1, 1, "AnP — Fragmentos (Análise Preliminar por Fragmento)",
             bold=True)
    ws.write(1, 2, f"v{VERSAO_SUITE}", bold=True)
    ws.write(3, 1, "AVISO", color="FFF3E0", bold=True)
    ws.write(3, 2, AVISO, color="FFF3E0")

    linhas = [
        ("Raster de entrada", meta['raster']),
        ("Tamanho do pixel", f"{meta['res_x']:.2f} × {meta['res_y']:.2f} m"),
        ("Valores-alvo", ", ".join(str(v) for v in meta['valores'])),
        ("Modo", meta['modo']),
        ("Vizinhança", f"{meta['conn']} conexos"),
        ("Profundidade de borda",
         f"{meta['depth_px']} px  ≈  {meta['depth_m']:.0f} m"),
        ("Área mínima", f"{meta['area_min_ha']:.4f} ha"
                        if meta['area_min_ha'] else "sem filtro"),
        ("Desagregação por unidade",
         f"sim (campo '{meta['campo']}')" if meta['por_unidade'] else "não"),
        ("Total de fragmentos", meta['n_frag']),
    ]
    r = 5
    for k, v in linhas:
        ws.write(r, 1, k, bold=True)
        ws.write(r, 2, v)
        r += 1

    r += 1
    ws.write(r, 1, "Campos do shapefile", bold=True); r += 1
    for nome, desc in DICIONARIO:
        ws.write(r, 1, nome)
        ws.write(r, 2, desc)
        r += 1


def _aba_como_citar(wb):
    ws = wb.add_sheet("Como_Citar")
    ws.set_col_width(1, 100)
    txt = [
        "COMO CITAR",
        "",
        "Software (produto metodológico):",
        "LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de plugins "
        "QGIS para análise de cobertura e uso da terra e fragmentação de "
        "paisagens naturais. Rio Claro: Departamento de Geografia e "
        "Planejamento Ambiental, IGCE — Unesp, 2025. Disponível em: "
        "https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. "
        "DOI: 10.5281/zenodo.21364767",
        "",
        "Dados (quando MapBiomas):",
        "MAPBIOMAS. Coleção 10 da Série Anual de Mapas de Cobertura e Uso da "
        "Terra do Brasil. São Paulo: MapBiomas, 2025. Disponível em: "
        "https://mapbiomas.org.",
    ]
    for i, t in enumerate(txt, 1):
        ws.write(i, 1, t, bold=(i == 1))


def _aba_fragmentos(wb, registros):
    ws = wb.add_sheet("Fragmentos")
    cols = ["id_frag", "classe", "classe_nm", "unidade", "area_ha", "perim_m",
            "core_ha", "n_core", "cai_pct", "shape_idx", "frac", "circ", "enn_m"]
    larg = [8, 8, 24, 18, 12, 12, 12, 8, 10, 10, 8, 8, 10]
    for c, (nome, w) in enumerate(zip(cols, larg), 1):
        ws.write(1, c, nome, header=True)
        ws.set_col_width(c, w)
    numericos = {"area_ha", "perim_m", "core_ha", "cai_pct",
                 "shape_idx", "frac", "circ", "enn_m"}
    for r, reg in enumerate(registros, 2):
        for c, nome in enumerate(cols, 1):
            v = reg.get(nome)
            fmt = 'num' if nome in numericos else None
            ws.write(r, c, v if v is not None else "", num_fmt=fmt)


def _aba_panorama(wb, registros, meta):
    ws = wb.add_sheet("Panorama")
    ws.set_col_width(1, 34); ws.set_col_width(2, 18)
    areas = [r['area_ha'] for r in registros]
    perim = [r['perim_m'] for r in registros]
    cores = [r['core_ha'] for r in registros]

    def stat(nome, val, fmt='num'):
        nonlocal r
        ws.write(r, 1, nome, bold=True)
        ws.write(r, 2, val, num_fmt=fmt if isinstance(val, (int, float)) else None)
        r += 1

    r = 1
    ws.write(r, 1, "PANORAMA DOS FRAGMENTOS", bold=True); r += 2
    if areas:
        stat("Nº de fragmentos", len(areas), None)
        stat("Área total (ha)", round(sum(areas), 2))
        stat("Área núcleo total (ha)", round(sum(cores), 2))
        stat("Comprimento de borda total (m)", round(sum(perim), 2))
        stat("Área média (ha)", round(st.mean(areas), 4))
        stat("Área mediana (ha)", round(st.median(areas), 4))
        stat("Maior fragmento (ha)", round(max(areas), 4))
        stat("Menor fragmento (ha)", round(min(areas), 4))
        cai_medio = (100.0 * sum(cores) / sum(areas)) if sum(areas) else 0
        stat("Índice de área núcleo médio (%)", round(cai_medio, 2))

    # por classe
    r += 1
    ws.write(r, 1, "Por classe", bold=True); r += 1
    ws.write(r, 1, "classe", header=True)
    ws.write(r, 2, "n_frag", header=True)
    ws.write(r, 3, "area_ha", header=True); r += 1
    porc = {}
    for reg in registros:
        chave = reg.get('classe_nm') or str(reg.get('classe'))
        d = porc.setdefault(chave, [0, 0.0])
        d[0] += 1; d[1] += reg['area_ha']
    ws.set_col_width(3, 14)
    for chave, (n, a) in sorted(porc.items(), key=lambda x: -x[1][1]):
        ws.write(r, 1, chave)
        ws.write(r, 2, n, num_fmt='num')
        ws.write(r, 3, round(a, 2), num_fmt='num')
        r += 1



def _params_frag(meta):
    return [("Raster", meta.get('raster')),
            ("Pixel (m)", f"{meta.get('res_x')} x {meta.get('res_y')}"),
            ("Valores-alvo", ", ".join(str(v) for v in meta.get('valores', []))),
            ("Modo", meta.get('modo')),
            ("Vizinhança", f"{meta.get('conn')} conexos"),
            ("Profundidade de borda", f"{meta.get('depth_px')} px \u2248 {meta.get('depth_m'):.0f} m" if meta.get('depth_m') is not None else meta.get('depth_px')),
            ("Área mínima (ha)", meta.get('area_min_ha')),
            ("Desagregação", f"campo '{meta.get('campo')}'" if meta.get('por_unidade') else "não"),
            ("Total de fragmentos", meta.get('n_frag'))]


def exportar_excel(path, registros, meta, progresso_fn=None):
    if progresso_fn:
        progresso_fn("Gerando Excel-resumo...")
    wb = XlsxBook()
    escrever_metadados(wb, "Análise de fragmentos", params=_params_frag(meta))
    _aba_fragmentos(wb, registros)
    _aba_panorama(wb, registros, meta)
    wb.save(path)
    if progresso_fn:
        import os
        progresso_fn(f"✓ Excel: {os.path.basename(path)}")
    return path
