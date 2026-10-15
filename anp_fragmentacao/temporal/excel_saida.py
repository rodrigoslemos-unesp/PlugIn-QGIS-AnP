"""
AnP Fragmentação — Geração das planilhas Excel de saída.
Arquivo: ano1_ano2_paisagem.xlsx
Abas tidy: Metricas | Paisagem | Variacoes
"""
import os
from ..comum.xlsx_writer import XlsxBook
from ..comum.metadados import escrever_metadados, VERSAO_SUITE
from ..comum.legenda import GRUPOS_TEMATICOS, UNIDADES

# CRED removido — creditação consta apenas no aplicativo, não nos produtos

COR_A = "F5F5F5"
COR_B = "FFFFFF"


def _aba_como_citar(wb):
    """Aba com orientação de citação — MapBiomas e AnP como software."""
    ws = wb.add_sheet("Como_Citar")
    ws.set_col_width(1, 100)
    linhas = [
        "COMO CITAR OS DADOS DESTE RELATÓRIO",
        "",
        "Este relatório foi gerado a partir de dados de cobertura e uso "
        "da terra do projeto MapBiomas. Ao utilizar estes dados, cite a "
        "fonte primária:",
        "",
        "MAPBIOMAS. Coleção 10 da Série Anual de Mapas de Cobertura e Uso "
        "da Terra do Brasil. São Paulo: MapBiomas, 2025. "
        "Disponível em: https://mapbiomas.org.",
        "",
        "Se este relatório for citado como produto metodológico (citando "
        "o processamento realizado, não apenas os dados brutos), a "
        "referência do software é:",
        "",
        "LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de "
        "plugins QGIS para análise de cobertura e uso da terra e "
        "fragmentação de paisagens naturais. Rio Claro: Departamento de "
        "Geografia e Planejamento Ambiental, IGCE — Unesp, 2025. "
        "Disponível em: https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. "
        "DOI: 10.5281/zenodo.21364767",
    ]
    for i, txt in enumerate(linhas, 2):
        ws.write(i, 1, txt, header=(i == 2))


def _hdr(ws, col, texto, largura):
    ws.write(1, col, texto, header=True)
    ws.set_col_width(col, largura)


def _aba_metricas(wb, resultado, ano1, ano2):
    """
    Tidy: recorte | grupo | tema | metrica | unidade | ano | valor
    """
    ws   = wb.add_sheet("Metricas")
    hdrs = [("recorte",30),("grupo",28),("tema",16),
            ("metrica",12),("unidade",10),("ano",7),("valor",16)]
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    row = 2; i = 0
    for rec, dados in resultado.items():
        if not isinstance(dados, dict) or 'grupos' not in dados.get(str(ano1), dados.get(str(ano2), {})):
            continue
        lbl = 'Shape Completo' if rec == '__shape_completo__' else rec
        for ano_k in [str(ano1), str(ano2)]:
            ano_d = dados.get(ano_k, {})
            grupos = ano_d.get('grupos', {})
            for nome_g, metricas in grupos.items():
                for tema, siglas in GRUPOS_TEMATICOS.items():
                    if tema == "Paisagem":
                        continue
                    for sigla in siglas:
                        v = metricas.get(sigla)
                        if v is None:
                            continue
                        shade = COR_A if i % 2 == 0 else COR_B
                        ws.write(row, 1, lbl,                   color=shade)
                        ws.write(row, 2, nome_g,                color=shade)
                        ws.write(row, 3, tema,                  color=shade)
                        ws.write(row, 4, sigla,                 color=shade)
                        ws.write(row, 5, UNIDADES.get(sigla,''),color=shade)
                        ws.write(row, 6, int(ano_k),            color=shade)
                        ws.write(row, 7, v, color=shade,
                                 num_fmt='num' if isinstance(v,float) else None)
                        row += 1; i += 1


def _aba_paisagem(wb, resultado, ano1, ano2):
    """
    Tidy: recorte | metrica | unidade | ano | valor
    """
    ws   = wb.add_sheet("Paisagem")
    hdrs = [("recorte",30),("metrica",12),("unidade",10),
            ("ano",7),("valor",16)]
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    row = 2; i = 0
    for rec, dados in resultado.items():
        if not isinstance(dados, dict) or 'grupos' not in dados.get(str(ano1), dados.get(str(ano2), {})):
            continue
        lbl = 'Shape Completo' if rec == '__shape_completo__' else rec
        for ano_k in [str(ano1), str(ano2)]:
            pai = dados.get(ano_k, {}).get('paisagem', {})
            for sigla, v in pai.items():
                shade = COR_A if i % 2 == 0 else COR_B
                ws.write(row, 1, lbl,                    color=shade)
                ws.write(row, 2, sigla,                  color=shade)
                ws.write(row, 3, UNIDADES.get(sigla,''), color=shade)
                ws.write(row, 4, int(ano_k),             color=shade)
                ws.write(row, 5, v, color=shade,
                         num_fmt='num' if isinstance(v,float) else None)
                row += 1; i += 1


def _aba_variacoes(wb, resultado, ano1, ano2):
    """
    Tidy: recorte | grupo | metrica | unidade | valor_ano1 | valor_ano2 | delta_abs | delta_pct
    """
    ws   = wb.add_sheet("Variacoes")
    hdrs = [("recorte",30),("grupo",28),("metrica",12),("unidade",10),
            (f"valor_{ano1}",16),(f"valor_{ano2}",16),
            ("delta_abs",16),("delta_pct",12)]
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    COR_P = "C8E6C9"; COR_N = "FFCCBC"
    row = 2; i = 0
    for rec, dados in resultado.items():
        if not isinstance(dados, dict) or 'grupos' not in dados.get(str(ano1), dados.get(str(ano2), {})):
            continue
        lbl = 'Shape Completo' if rec == '__shape_completo__' else rec
        g1 = dados.get(str(ano1), {}).get('grupos', {})
        g2 = dados.get(str(ano2), {}).get('grupos', {})
        todos_grupos = set(g1) | set(g2)
        for nome_g in sorted(todos_grupos):
            m1 = g1.get(nome_g, {})
            m2 = g2.get(nome_g, {})
            todas_met = set(m1) | set(m2)
            for sigla in sorted(todas_met):
                v1 = m1.get(sigla)
                v2 = m2.get(sigla)
                if v1 is None and v2 is None:
                    continue
                v1 = v1 if v1 is not None else 0.0
                v2 = v2 if v2 is not None else 0.0
                dabs = round(v2 - v1, 4)
                dpct = round((v2-v1)/abs(v1)*100, 2) if v1 != 0 else None
                shade = COR_P if dabs > 0 else (COR_N if dabs < 0 else COR_A)
                ws.write(row, 1, lbl,                    color=shade)
                ws.write(row, 2, nome_g,                 color=shade)
                ws.write(row, 3, sigla,                  color=shade)
                ws.write(row, 4, UNIDADES.get(sigla,''), color=shade)
                ws.write(row, 5, v1,   color=shade, num_fmt='num')
                ws.write(row, 6, v2,   color=shade, num_fmt='num')
                ws.write(row, 7, dabs, color=shade, num_fmt='num')
                # IMPORTANTE: gravar como número (fração), não como texto
                # formatado ("+24.44%"). O formato Excel 'pct' multiplica
                # por 100 automaticamente na exibição — a célula continua
                # sendo um número de verdade, o que outras ferramentas
                # (R, Python, tabelas dinâmicas) conseguem ler diretamente
                # com as.numeric()/float() sem quebrar. Uma string como
                # "+24.44%" não é interpretável como número em nenhuma
                # dessas ferramentas e gera NA/erro silencioso.
                ws.write(row, 8,
                         dpct / 100 if dpct is not None else 'N/D',
                         color=shade,
                         num_fmt='pct' if dpct is not None else None)
                row += 1; i += 1


def _aba_distribuicao(wb, resultado, ano1, ano2, chave, nome_aba):
    """
    Tidy: recorte | grupo | ano | classe_tamanho | n_fragmentos |
          area_ha | pct_n | pct_area

    chave: 'fragmentos' (fragmento total, antes da erosão) ou
           'nucleo' (área núcleo, após a erosão)
    """
    ws   = wb.add_sheet(nome_aba)
    hdrs = [("recorte",30),("grupo",26),("ano",7),("classe_tamanho",18),
            ("n_fragmentos",13),("area_ha",14),("pct_n",10),("pct_area",10)]
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    row = 2; i = 0
    for rec, dados in resultado.items():
        if rec == '_meta' or not isinstance(dados, dict):
            continue
        lbl = 'Shape Completo' if rec == '__shape_completo__' else rec
        for ano_k in [str(ano1), str(ano2)]:
            dist_ano = dados.get(ano_k, {}).get('distribuicao', {})
            for nome_g, d in dist_ano.items():
                for item in d.get(chave, []):
                    shade = COR_A if i % 2 == 0 else COR_B
                    ws.write(row, 1, lbl,                   color=shade)
                    ws.write(row, 2, nome_g,                color=shade)
                    ws.write(row, 3, int(ano_k),            color=shade)
                    ws.write(row, 4, item['classe_tamanho'],color=shade)
                    ws.write(row, 5, item['n_fragmentos'],  color=shade)
                    ws.write(row, 6, item['area_ha'],
                             color=shade, num_fmt='num')
                    ws.write(row, 7, item['pct_n'],
                             color=shade, num_fmt='pct')
                    ws.write(row, 8, item['pct_area'],
                             color=shade, num_fmt='pct')
                    row += 1; i += 1


def _aba_metadados(wb, resultado, ano1, ano2):
    """Aba de metadados — sempre a primeira do arquivo, com aviso de
    software em desenvolvimento bem destacado."""
    ws = wb.add_sheet("Metadados")
    ws.set_col_width(1, 22)
    ws.set_col_width(2, 90)

    ws.write(1, 1, "AnP — Fragmentação e Conectividade da Paisagem", bold=True)
    ws.write(1, 2, f"v{VERSAO_SUITE}", bold=True)

    aviso_txt = (
        "⚠ SOFTWARE EM DESENVOLVIMENTO — Este plugin está em fase de "
        "testes e aprimoramento contínuo. Os resultados devem ser "
        "conferidos e validados pelo usuário antes de qualquer uso "
        "científico, técnico ou institucional. O autor e a instituição "
        "não se responsabilizam por eventuais erros, omissões, "
        "imprecisões ou uso indevido dos resultados gerados por esta "
        "ferramenta.")
    ws.write(3, 1, "AVISO", color="FFF3E0", bold=True)
    ws.write(3, 2, aviso_txt, color="FFF3E0")

    meta = resultado.get('_meta', {})
    ws.write(5, 1, "Anos analisados", bold=True)
    ws.write(5, 2, f"{ano1} → {ano2}")
    ws.write(6, 1, "Resolução do pixel", bold=True)
    px_m = meta.get('px_m')
    ws.write(6, 2, f"{px_m:.2f} m" if px_m else "não disponível")
    aviso_crs = meta.get('aviso_crs')
    ws.write(7, 1, "CRS", bold=True)
    ws.write(7, 2, aviso_crs or "CRS projetado — área do pixel calculada exatamente do geotransform")
    ws.write(8, 1, "Distância de borda (área núcleo)", bold=True)
    ws.write(8, 2, f"{meta.get('n_pixels','?')} px = {meta.get('dist_m','?')} m")

    classes_porte = meta.get('classes_porte') or []
    if classes_porte:
        ws.write(9, 1, "Classes de porte usadas", bold=True)
        rotulos = " · ".join(c[3] for c in classes_porte)
        ws.write(9, 2, rotulos)



def _params_temporal(resultado, ano1, ano2):
    grupos = resultado.get(ano1, {}).get('grupos', {}) if isinstance(resultado.get(ano1), dict) else {}
    recortes = [k for k in resultado.keys() if isinstance(resultado.get(k), dict) and 'unidade' in str(k).lower()]
    return [("Anos comparados", f"{ano1} \u2192 {ano2}"),
            ("Grupos de cobertura", ", ".join(sorted(grupos.keys())) or "—")]


def exportar(resultado, pasta, ano1, ano2, progresso_fn=None):
    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    prog("  Gerando paisagem.xlsx...")
    wb = XlsxBook()
    escrever_metadados(wb, "Fragmentação temporal da paisagem",
                       params=_params_temporal(resultado, ano1, ano2))
    _aba_metricas(wb,   resultado, ano1, ano2)
    _aba_paisagem(wb,   resultado, ano1, ano2)
    _aba_variacoes(wb,  resultado, ano1, ano2)
    _aba_distribuicao(wb, resultado, ano1, ano2, 'fragmentos', 'Dist_Fragmentos')
    _aba_distribuicao(wb, resultado, ano1, ano2, 'nucleo',     'Dist_Nucleos')

    p = os.path.join(pasta, f"{ano1}_{ano2}_paisagem.xlsx")
    wb.save(p)
    prog(f"  ✓ {os.path.basename(p)}")
    return [p]
