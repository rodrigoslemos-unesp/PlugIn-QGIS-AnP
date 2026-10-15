# PlugIn-QGIS-AnP
Conjunto de plugins QGIS para análise de cobertura e uso da terra e fragmentação de paisagens naturais com dados MapBiomas Coleção 10. Prof. Dr. Rodrigo Silva Lemos, Departamento de Geografia e Planejamento Ambiental/IGCE — Unesp Rio Claro    · rodrigo.s.lemos@unesp.br.  Grupo de Pesquisa: Planejamento Ambiental e Dinâmicas da Paisagem

## Plugins (versão 1.1)

Os arquivos de instalação (`.zip`) estão na página de [Releases](https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP/releases/latest). O código-fonte de cada plugin está na pasta indicada na tabela.

| Arquivo (Releases) | Código-fonte | Plugin | Módulos |
|---|---|---|---|
| `AnP_Analise_Monitoria_v1.1.zip` | [`anp_analise_monitoria/`](anp_analise_monitoria) | AnP - Análise e Monitoria da Paisagem (v1.1) | Preparação (alinhar/recortar/reprojetar), Relatório (composição multi-ano) e Monitoria (comparação entre dois anos e matriz de transição) |
| `AnP_Fragmentacao_v1.1.zip` | [`anp_fragmentacao/`](anp_fragmentacao) | AnP - Fragmentação da Paisagem (v1.1) | Análise temporal (métricas de classe e paisagem via PyLandStats) e análise de fragmentos (vetorização com métricas por polígono) |

Os plugins Preparação, Relatório e Monitoria, distribuídos separadamente até a versão 1.0, agora fazem parte de um único plugin com menu de seleção de módulo.

## Instalação

No QGIS (3.16 ou superior): **Complementos → Gerenciar e instalar complementos → Instalar a partir do ZIP** e selecione o arquivo `.zip` do plugin, baixado da página de [Releases](https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP/releases/latest).

A análise temporal de fragmentação exige o pacote Python `pylandstats`. Os plugins não instalam pacotes automaticamente.

### Atualização a partir de versões anteriores

Na versão 1.1, a pasta do plugin **AnP - Análise e Monitoria da Paisagem** mudou de nome (`AnP_Analise_Monitoria_v1_0_1` → `anp_analise_monitoria`). Por isso, quem tem a versão anterior instalada (1.0.x) **deve desinstalá-la antes** de instalar a nova: em **Complementos → Gerenciar e instalar complementos → Instalados**, selecione o plugin e clique em **Desinstalar complemento**. Sem isso, o QGIS mantém as duas versões lado a lado, com o mesmo nome no menu.

O plugin **AnP - Fragmentação da Paisagem** manteve o nome da pasta e pode ser atualizado diretamente.

## Como citar

LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de plugins QGIS para análise de cobertura e uso da terra e fragmentação de paisagens naturais. Rio Claro: Departamento de Geografia e Planejamento Ambiental, IGCE — Unesp, 2025. Disponível em: https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. DOI: 10.5281/zenodo.21364767

## Licença

GNU GPL-3.0 — ver [LICENSE](LICENSE).
