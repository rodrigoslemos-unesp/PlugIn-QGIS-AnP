# -*- coding: utf-8 -*-
"""
AnP Integrado — Relatório de Cobertura: geração do Excel.

Reescrito para usar o motor único xlsx_writer (sem openpyxl) e o
Metadados/Como_Citar padronizados do pacote comum. Saída: uma aba única
"Cobertura" (tidy) com os níveis N1–N4 em colunas, permitindo agregação
por tabela dinâmica/SOMASE em qualquer nível.
"""
import os
from ..comum.xlsx_writer import XlsxBook
from ..comum.metadados import escrever_metadados
from ..comum.legenda import cor_original


COLS = [
    "unidade_analise", "ano",
    "cod_original", "classe_original",
    "cod_n1", "classe_n1",
    "cod_n2", "classe_n2",
    "cod_n3", "classe_n3",
    "cod_n4", "classe_n4",
    "area_ha", "area_km2", "percentual",
]
LARGURAS = [26, 7, 11, 26, 8, 22, 8, 22, 8, 22, 8, 22, 13, 13, 12]


def _aba_cobertura(wb, resultado, anos):
    """Uma linha por unidade × ano × classe original, com N1–N4 em colunas."""
    ws = wb.add_sheet("Cobertura")
    for c, (nome, larg) in enumerate(zip(COLS, LARGURAS), 1):
        ws.write(1, c, nome, header=True)
        ws.set_col_width(c, larg)

    row = 2
    for unidade, dados_anos in resultado.items():
        if unidade == '_meta':
            continue
        for ano in sorted(anos):
            if ano not in dados_anos:
                continue
            contagem = dados_anos[ano]
            for cod in sorted(contagem.keys()):
                d = contagem[cod]
                ws.write(row, 1, unidade)
                ws.write(row, 2, ano, num_fmt='num')
                ws.write(row, 3, cod, num_fmt='num')
                # classe original — fundo na cor MapBiomas (fonte automática)
                ws.write(row, 4, d['nome'], color=cor_original(cod))
                ws.write(row, 5, d['cod_n1'], num_fmt='num')
                ws.write(row, 6, d['nome_n1'], color=cor_original(d['cod_n1']))
                ws.write(row, 7, d['cod_n2'], num_fmt='num')
                ws.write(row, 8, d['nome_n2'])
                ws.write(row, 9, d['cod_n3'], num_fmt='num')
                ws.write(row, 10, d['nome_n3'])
                ws.write(row, 11, d['cod_n4'], num_fmt='num')
                ws.write(row, 12, d['nome_n4'])
                ws.write(row, 13, round(d['ha'], 4), num_fmt='num')
                ws.write(row, 14, round(d['ha'] / 100.0, 4), num_fmt='num')
                # percentual mantido em escala 0–100 (compatível com o script R)
                ws.write(row, 15, round(d['pct'] * 100.0, 4), num_fmt='num')
                row += 1
    return row - 1


def _params_relatorio(resultado, anos, nome_base):
    n = len([k for k in resultado.keys() if k != '_meta'])
    return [("Anos analisados", ", ".join(str(a) for a in anos)),
            ("Unidades de análise", n),
            ("Arquivo base", nome_base),
            ("Escala do percentual", "0–100 (%)")]


def exportar(resultado, pasta, nome_base, progresso_fn=None):
    def prog(msg):
        if progresso_fn:
            progresso_fn(msg)

    meta = resultado.get('_meta', {})
    anos = sorted(meta.keys())
    prog(f"  Gerando Excel — {len(anos)} ano(s)...")

    wb = XlsxBook()
    prog("  → Aba: Metadados e Como Citar")
    escrever_metadados(wb, "Relatório de Cobertura da Terra",
                       params=_params_relatorio(resultado, anos, nome_base))
    prog("  → Aba: Cobertura (planilha única, N1–N4 em colunas)")
    n = _aba_cobertura(wb, resultado, anos)

    path = os.path.join(pasta, f"{nome_base}_cobertura.xlsx")
    wb.save(path)
    prog(f"  ✓ Salvo: {os.path.basename(path)}  ({n} linhas)")
    return path
