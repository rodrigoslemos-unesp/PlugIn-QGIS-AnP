# PlugIn-QGIS-AnP
Conjunto de plugins QGIS para análise de cobertura e uso da terra e fragmentação de paisagens naturais com dados MapBiomas Coleção 10. Prof. Dr. Rodrigo Silva Lemos, Departamento de Geografia e Planejamento Ambiental/IGCE — Unesp Rio Claro    · rodrigo.s.lemos@unesp.br.  Grupo de Pesquisa: Planejamento Ambiental e Dinâmicas da Paisagem

## Plugins (versão 1.1)

| Arquivo | Plugin | Módulos |
|---|---|---|
| `AnP_Analise_Monitoria_v1.0.3.zip` | AnP - Análise e Monitoria da Paisagem (v1.0.3) | Preparação (alinhar/recortar/reprojetar), Monitoria (comparação entre dois anos e matriz de transição) e Relatório (composição multi-ano) |
| `AnP_Fragmentacao_v1.0.zip` | AnP - Fragmentação da Paisagem (v1.0) | Análise temporal (métricas de classe e paisagem via PyLandStats) e análise de fragmentos (vetorização com métricas por polígono) |

Os plugins Preparação, Monitoria e Relatório, distribuídos separadamente até a versão 1.0, agora fazem parte de um único plugin com menu de seleção de módulo.

## Instalação

No QGIS (3.16 ou superior): **Complementos → Gerenciar e instalar complementos → Instalar a partir do ZIP** e selecione o arquivo `.zip` do plugin.

A análise temporal de fragmentação exige o pacote Python `pylandstats`. Os plugins não instalam pacotes automaticamente.

## Como citar

LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de plugins QGIS para análise de cobertura e uso da terra e fragmentação de paisagens naturais. Rio Claro: Departamento de Geografia e Planejamento Ambiental, IGCE — Unesp, 2025. Disponível em: https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. DOI: 10.5281/zenodo.21364767

## Licença

GNU GPL-3.0 — ver [LICENSE](LICENSE).
