# ============================================================
#  AnP — Análise da Paisagem
#  Visualizações integradas: Cobertura · Matriz · Fragmentação
#  Rodrigo Lemos — DGPA / UNESP Rio Claro
#  Versão 1.1 (2025)
#
#  Versão inicial publicada, compatível com os plugins AnP v1.1.
#  Recursos:
#   - Menu interativo: escolha quais famílias de gráficos gerar
#     (Cobertura/Alterações, Matriz, Fragmentação/Paisagem,
#     Composição de Cobertura) — só pede o(s) arquivo(s)
#     necessário(s) para o que for selecionado. É a única pergunta
#     interativa do script; nomes e recortes são detectados
#     automaticamente.
#   - Pergunta o formato de saída (PNG / SVG / ambos) e onde salvar
#     os gráficos; cada janela de seleção abre na última pasta usada.
#   - Paleta de cores MapBiomas Coleção 10 (a mesma dos QML gerados
#     pelo plugin AnP), com contraste automático de rótulos
#     (.cor_texto_contraste) sobre fundos claros/escuros.
#   - Normalização de texto via stringi::stri_trans_general(),
#     independente do locale do sistema operacional.
#   - Sankey, Matriz (M1) e Heatmap agrupados no Nível 2 da legenda
#     MapBiomas; Sankey com origem em Nível 1 e destino em Nível 2.
#   - Pizza (P1), Matriz (M1) e Heatmap somam as classes < 1% em
#     "Soma de outros valores inferiores a 1%"; fatias pequenas da
#     pizza recebem rótulo externo com seta (LIMIAR_CALLOUT).
#   - M1: heatmap da matriz de transição (ha e %), lido das duas
#     matrizes empilhadas exportadas pelo Módulo II (Monitoria).
#   - Composição de Cobertura: gráficos de rosca por ano, níveis N1
#     e N2, a partir do Módulo III (Relatório de Cobertura).
#   - Fragmentação (F1, F2, F2b): gráficos para todos os grupos de
#     cobertura presentes (Cobertura Natural, Floresta, Veg.
#     Herbácea) e todas as unidades espaciais; deltas recalculados a
#     partir dos valores de cada ano; F1 com índice numérico no eixo
#     X e legenda de recortes; F2/F2b leem as abas Dist_Fragmentos e
#     Dist_Nucleos do Módulo IV.
# ============================================================

# ---- 0. Pacotes ----
pkgs <- c("readxl","ggplot2","dplyr","tidyr","scales","forcats",
          "patchwork","svglite","stringr","stringi",
          "ggrepel","ggalluvial","circlize","ggfx","RColorBrewer")
novos <- pkgs[!pkgs %in% installed.packages()[,"Package"]]
if (length(novos)) install.packages(novos)
invisible(lapply(pkgs, library, character.only = TRUE))

# ============================================================
#  1. UTILITÁRIOS DE INTERAÇÃO
# ============================================================

# Guarda a pasta do último arquivo selecionado — cada nova chamada de
# sel_arquivo() abre a janela já na última pasta usada, em vez de
# sempre voltar para "Documentos".
.ULTIMA_PASTA <- NULL

sel_arquivo <- function(caption) {
  pasta_inicial <- if (!is.null(.ULTIMA_PASTA)) .ULTIMA_PASTA else path.expand("~")
  
  if (requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
    caminho <- rstudioapi::selectFile(caption = caption, filter = "Excel (*.xlsx)",
                                      path = pasta_inicial, existing = TRUE)
  } else {
    if (!require(tcltk, quietly = TRUE)) install.packages("tcltk")
    caminho <- tcltk::tk_choose.files(
      default = file.path(pasta_inicial, "*.xlsx"),
      caption = caption, multi = FALSE,
      filters = matrix(c("Excel", "*.xlsx"), ncol = 2, byrow = TRUE))
  }
  
  if (!is.null(caminho) && length(caminho) > 0 && caminho != "") {
    .ULTIMA_PASTA <<- dirname(caminho)
  }
  caminho
}

# Mesma lógica de "lembrar a última pasta", mas para escolher uma
# PASTA de destino (usada na pergunta de onde salvar os g1111,2,5 3ráficos).
sel_pasta <- function(caption, pasta_sugerida = NULL) {
  pasta_inicial <- if (!is.null(pasta_sugerida)) pasta_sugerida
  else if (!is.null(.ULTIMA_PASTA)) .ULTIMA_PASTA
  else path.expand("~")
  
  if (requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
    caminho <- rstudioapi::selectDirectory(caption = caption, path = pasta_inicial)
  } else {
    if (!require(tcltk, quietly = TRUE)) install.packages("tcltk")
    caminho <- tcltk::tk_choose.dir(default = pasta_inicial, caption = caption)
  }
  if (!is.null(caminho) && length(caminho) > 0 && !is.na(caminho) && caminho != "") {
    .ULTIMA_PASTA <<- caminho
    return(caminho)
  }
  NULL
}

.ler_opcao <- function(prompt_txt, default = "") {
  if (interactive()) readline(prompt = prompt_txt) else default
}

# ============================================================
#  2. MENU — QUAIS FAMÍLIAS DE GRÁFICOS GERAR
# ============================================================

message("\n", strrep("=", 62))
message("  AnP v1.1 — Selecao das familias de graficos")
message(strrep("=", 62))
message("\n  [1] Cobertura e Alteracoes  (C2, C2A, C4, C4A)")
message("      -> requer o arquivo de MONITORIA (Modulo II)")
message("\n  [2] Matriz de Transicao  (M1 - heatmap)")
message("      -> requer o arquivo de MATRIZ (Modulo II)")
message("\n  [3] Fragmentacao / Paisagem  (F1, F2, F2b)")
message("      -> requer o arquivo de PAISAGEM (Modulo IV)")
message("\n  [4] Composicao de Cobertura  (P1 - graficos de rosca/pizza)")
message("      -> requer o arquivo de RELATORIO DE COBERTURA (Modulo III)")
message("\n  [5] Analises Multivariadas e Fluxos  (PCA, Heatmap, Dispersao, Sankey, Chord)")
message("      -> requer familia [1] Cobertura (usa os mesmos dados)")
message(strrep("-", 62))
message("\n  Digite os numeros desejados separados por virgula.")
message("  Exemplos: '1,3'  ou  '1,5'  ou Enter para todos\n")

.entrada_familias <- .ler_opcao("  Familias a gerar: ", "1,2,3,4,5")
if (trimws(.entrada_familias) == "") .entrada_familias <- "1,2,3,4,5"
FAMILIAS <- suppressWarnings(as.integer(trimws(strsplit(.entrada_familias, ",")[[1]])))
FAMILIAS <- FAMILIAS[!is.na(FAMILIAS) & FAMILIAS %in% 1:5]
if (length(FAMILIAS) == 0) FAMILIAS <- 1:5

GERAR_COBERTURA <- 1 %in% FAMILIAS
GERAR_MATRIZ    <- 2 %in% FAMILIAS
GERAR_FRAG      <- 3 %in% FAMILIAS
GERAR_RELATORIO <- 4 %in% FAMILIAS
GERAR_MULTIVAR  <- 5 %in% FAMILIAS

# Família 5 requer dados da família 1
if (GERAR_MULTIVAR && !GERAR_COBERTURA) {
  message("  [AVISO] Familia 5 requer os dados da familia 1.")
  message("  Ativando familia 1 automaticamente.")
  GERAR_COBERTURA <- TRUE
}

message("\n  Familias selecionadas:")
if (GERAR_COBERTURA) message("    - Cobertura e Alteracoes")
if (GERAR_MATRIZ)    message("    - Matriz de Transicao")
if (GERAR_FRAG)      message("    - Fragmentacao / Paisagem")
if (GERAR_RELATORIO) message("    - Composicao de Cobertura (pizza/rosca)")
if (GERAR_MULTIVAR)  message("    - Analises Multivariadas e Fluxos")
message("")

# ── Formato de saída dos gráficos ────────────────────────────────────────
message(strrep("-", 62))
message("  Formato de saida dos graficos:")
message("    [1] PNG apenas")
message("    [2] SVG apenas")
message("    [3] PNG e SVG  (padrao)")
message("")
.entrada_formato <- .ler_opcao("  Formato [1/2/3]: ", "3")
FORMATO_SAIDA <- switch(trimws(.entrada_formato),
                        "1" = "png",
                        "2" = "svg",
                        c("png", "svg")   # "3", vazio ou qualquer outra entrada -> ambos
)
message("  Formato selecionado: ", paste(toupper(FORMATO_SAIDA), collapse = " + "))
message("")

# ============================================================
#  3. SELEÇÃO DE ARQUIVOS — SÓ O QUE FOR NECESSÁRIO
# ============================================================

arq_cob  <- NULL
arq_mat  <- NULL
arq_frag <- NULL
arq_rel  <- NULL
pasta_ref <- NULL

if (GERAR_COBERTURA) {
  message("[Arquivo] COBERTURA E ALTERACOES (saida do Modulo II - Monitoria)")
  arq_cob <- sel_arquivo("Selecione: Cobertura e Alteracoes (monitoria.xlsx)")
  if (is.null(arq_cob) || arq_cob == "")
    stop("Arquivo de cobertura nao selecionado — obrigatorio para a familia 'Cobertura'.")
  pasta_ref <- dirname(arq_cob)
}

if (GERAR_MATRIZ) {
  message("[Arquivo] MATRIZ DE TRANSICAO (saida do Modulo II - Monitoria)")
  arq_mat <- sel_arquivo("Selecione: Matriz de Transicao (Matriz.xlsx)")
  if (is.null(arq_mat) || arq_mat == "")
    stop("Arquivo de matriz nao selecionado — obrigatorio para a familia 'Matriz'.")
  if (is.null(pasta_ref)) pasta_ref <- dirname(arq_mat)
}

if (GERAR_FRAG) {
  message("[Arquivo] METRICAS DE FRAGMENTACAO (saida do Modulo IV)")
  arq_frag <- sel_arquivo("Selecione: Metricas de Fragmentacao (paisagem.xlsx)")
  if (is.null(arq_frag) || arq_frag == "")
    stop("Arquivo de fragmentacao nao selecionado — obrigatorio para a familia 'Fragmentacao'.")
  if (is.null(pasta_ref)) pasta_ref <- dirname(arq_frag)
}

if (GERAR_RELATORIO) {
  message("[Arquivo] RELATORIO DE COBERTURA DA TERRA (saida do Modulo III)")
  arq_rel <- sel_arquivo("Selecione: Relatorio de Cobertura (relatorio_cobertura.xlsx)")
  if (is.null(arq_rel) || arq_rel == "")
    stop("Arquivo de relatorio nao selecionado — obrigatorio para a familia 'Composicao de Cobertura'.")
  if (is.null(pasta_ref)) pasta_ref <- dirname(arq_rel)
}

# ── Onde salvar os gráficos ────────────────────────────────────────────
# Nome fixo: "Graficos AnP" + data de geração (AAAA-MM-DD)
.data_geracao   <- format(Sys.Date(), "%Y-%m-%d")
.nome_pasta     <- paste0("Graficos AnP ", .data_geracao)
.pasta_sugerida <- file.path(pasta_ref, .nome_pasta)

message("\n", strrep("-", 62))
message("  Onde salvar os graficos?")
message("    [1] Pasta sugerida: ", .pasta_sugerida)
message("    [2] Escolher outra pasta (abre janela de selecao)")
message("")
.entrada_pasta <- .ler_opcao("  Opcao [1/2]: ", "1")

if (trimws(.entrada_pasta) == "2") {
  .pasta_base <- sel_pasta("Escolha a pasta raiz onde criar a subpasta de graficos",
                           pasta_sugerida = pasta_ref)
  pasta_saida <- if (!is.null(.pasta_base))
    file.path(.pasta_base, .nome_pasta) else .pasta_sugerida
} else {
  pasta_saida <- .pasta_sugerida
}

dir.create(pasta_saida, showWarnings = FALSE, recursive = TRUE)
message("\nPasta de saida: ", pasta_saida)

# ============================================================
#  4. NOMENCLATURA — DETECCAO DINAMICA
# ============================================================

# Abas de metadados/citação (formato antigo "Metadados" + "Como_Citar" e
# formato v1.1+ "Metadados e Como Citar") — nunca contêm dados.
.RE_ABA_META <- "^Metadados|^Como_?Citar"

.detectar_nomes_reais <- function(arq_cob, arq_frag, arq_rel = NULL) {
  nomes <- c()
  if (!is.null(arq_cob)) {
    tryCatch({
      abas <- excel_sheets(arq_cob)
      aba  <- abas[grepl("obertura", abas, ignore.case = TRUE)][1]
      df   <- read_excel(arq_cob, sheet = aba)   # sem n_max: lê todas as linhas
      col  <- names(df)[grepl("unidade|recorte", names(df), ignore.case = TRUE)][1]
      if (!is.na(col)) nomes <- c(nomes, unique(df[[col]]))
    }, error = function(e) NULL)
  }
  if (!is.null(arq_frag)) {
    tryCatch({
      abas2 <- excel_sheets(arq_frag)
      aba2  <- abas2[grepl("Variacoes|Metricas", abas2)][1]
      if (is.na(aba2)) aba2 <- abas2[!grepl(.RE_ABA_META, abas2)][1]
      df2  <- read_excel(arq_frag, sheet = aba2)   # sem n_max
      col2 <- names(df2)[grepl("recorte|unidade", names(df2), ignore.case = TRUE)][1]
      if (!is.na(col2)) nomes <- c(nomes, unique(df2[[col2]]))
    }, error = function(e) NULL)
  }
  if (!is.null(arq_rel)) {
    tryCatch({
      abas3 <- excel_sheets(arq_rel)
      aba3  <- abas3[grepl("obertura", abas3, ignore.case = TRUE)][1]
      df3   <- read_excel(arq_rel, sheet = aba3)   # sem n_max
      col3  <- names(df3)[grepl("unidade|recorte", names(df3), ignore.case = TRUE)][1]
      if (!is.na(col3)) nomes <- c(nomes, unique(df3[[col3]]))
    }, error = function(e) NULL)
  }
  nomes <- nomes[!is.na(nomes) & nchar(as.character(nomes)) < 80]
  unique(as.character(nomes))
}

# NOTA: a única pergunta interativa de todo o script é a seleção de
# famílias de gráficos (Secao 2). Após essa escolha, tudo é gerado automaticamente com
# os nomes originais das planilhas e incluindo todos os recortes
# detectados nos gráficos integrados (C2A, C4A, F1).

.nomes_reais   <- .detectar_nomes_reais(arq_cob, arq_frag, arq_rel)
NOMES_PADRAO   <- setNames(.nomes_reais, .nomes_reais)
if (length(.nomes_reais) > 0) {
  message("\nRecortes/unidades detectados nas planilhas:")
  for (nm in .nomes_reais) message("    - ", nm)
}
ORDEM_RECORTES <- unique(unname(NOMES_PADRAO))

padronizar <- function(x) {
  if (length(NOMES_PADRAO) == 0) return(as.character(x))
  resultado <- NOMES_PADRAO[as.character(x)]
  resultado[is.na(resultado)] <- as.character(x)[is.na(resultado)]
  unname(resultado)
}

# ============================================================
#  5. PALETAS — REVISADA CONTRA A FONTE OFICIAL MAPBIOMAS C10
#     (mesmos valores usados nos QML gerados pelo plugin AnP —
#      arquivo Legenda-Colecao-10-Legend-Code.pdf, MapBiomas 2025)
# ============================================================

CORES_MB <- c(
  # Floresta
  "1"="#1F4E31","3"="#1F4E31","4"="#7DC36B","5"="#04381D",
  "6"="#026975","49"="#02D659",
  # Veg. Herbacea e Arbustiva
  "10"="#AAD374","11"="#519799","12"="#D6BC74","29"="#AD5100",
  "32"="#FF99FF","50"="#D68FE5",
  # Agropecuaria
  "9"="#935132","14"="#FFEFC3","15"="#EDDE8E","18"="#E974ED",
  "19"="#C27BA0","21"="#FFEFC3","20"="#DB7093","36"="#C3814B",
  "39"="#C3814B","40"="#9DC5A4","41"="#C27BA0","46"="#C8A06B",
  "47"="#FFC0CB","48"="#D4A96A","62"="#E1C4A4","35"="#A87C52",
  # Area nao Vegetada
  "22"="#D4271E","23"="#DD5F9B","24"="#D4271E","25"="#DB4D4F",
  "30"="#9C0027","75"="#C12100",
  # Corpo D'agua
  "26"="#2532E4","31"="#091077","33"="#2532E4",
  # Nao observado
  "27"="#CCCCCC","255"="#CCCCCC"
)

.PALETA_RECORTES <- c(
  "#1D9E75","#E24B4A","#378ADD","#BA7517","#0F6E56",
  "#9B59B6","#E67E22","#2C5282","#5D4037","#00838F",
  "#558B2F","#AD1457"
)

CORES_RECORTE <- if (length(ORDEM_RECORTES) > 0) {
  setNames(rep_len(.PALETA_RECORTES, length(ORDEM_RECORTES)), ORDEM_RECORTES)
} else { c() }

if (length(CORES_RECORTE) > 0) {
  message("\nCores por recorte:")
  for (nm in names(CORES_RECORTE))
    message(sprintf("  %-42s  %s", nm, CORES_RECORTE[nm]))
}

.CORES_CAT_BASE <- c(
  "Manteve-se em cobertura natural"    = "#1F4E31",
  "Mudou entre coberturas naturais"    = "#7DC36B",
  "Mudou de antrópico para natural"    = "#519799",
  "Manteve-se em cobertura antrópica"  = "#C0392B",
  "Mudou entre coberturas antrópicas"  = "#7B241C",
  "Mudou de natural para antrópico"    = "#E85C28"
)

# ── Contraste automático de texto sobre cores de fundo variáveis ─────────────
# Usada em qualquer gráfico onde o rótulo é desenhado DENTRO de uma área
# colorida (fatias de pizza, células de heatmap): sobre cores claras
# (ex: amarelo-claro da Agropecuária) o texto precisa ser escuro; sobre
# cores escuras (ex: verde-escuro da Floresta) o texto precisa ser claro.
# Fórmula de luminância perceptual padrão (mesma usada no VBA/openpyxl
# dos módulos Python do AnP, para manter o critério consistente em toda
# a ferramenta): L = 0,299R + 0,587G + 0,114B.
.cor_texto_contraste <- function(cor_hex, escuro = "#333333", claro = "#FFFFFF",
                                 limiar = 150) {
  cor_hex <- gsub("^#", "", cor_hex)
  r <- strtoi(substr(cor_hex, 1, 2), base = 16L)
  g <- strtoi(substr(cor_hex, 3, 4), base = 16L)
  b <- strtoi(substr(cor_hex, 5, 6), base = 16L)
  lum <- 0.299*r + 0.587*g + 0.114*b
  ifelse(is.na(lum), claro, ifelse(lum > limiar, escuro, claro))
}

.norm <- function(x) {
  # Normalizacao de texto para comparacao (usada para casar nomes de
  # categorias e de recortes). NAO usa iconv(..., to="ASCII//TRANSLIT")
  # nem tolower()/gsub manual de acentos: ambos dependem do locale do
  # sistema operacional e podem falhar silenciosamente — em especial
  # no Windows, onde a codificacao nativa do R (CP1252/latin1) pode
  # nao bater com o encoding do arquivo .xlsx (UTF-8). Quando isso
  # acontece, varias strings diferentes caem em NA ao mesmo tempo e o
  # match() do R trata NA==NA como correspondencia — categorias e ate
  # recortes inteiros (ex: municipios com acento como "Sao Pedro",
  # "Aguas de Sao Pedro", "Cordeiropolis") podem ser silenciosamente
  # confundidos entre si ou excluidos dos graficos integrados.
  #
  # stringi::stri_trans_general() usa tabelas ICU compiladas dentro
  # do proprio pacote — funciona de forma identica em Windows, macOS
  # e Linux, independente do locale do sistema. stringi ja e uma
  # dependencia obrigatoria do stringr (carregado no topo do script).
  #
  # Ordem importa: transliterar ANTES de tolower() — assim tolower()
  # so precisa lidar com ASCII puro, o que nunca depende de locale.
  x <- stringi::stri_trans_general(trimws(x), "Latin-ASCII")
  x <- tolower(x)
  x <- gsub("[^a-z ]", "", x)
  trimws(x)
}

.slug <- function(x, max_chars = 60) {
  # Converte o nome de um recorte/unidade em um trecho seguro para nome
  # de arquivo (ex: "Ia - Sistemas Ferriferos..." -> "Ia_Sistemas_Ferriferos...").
  # Mesma transliteracao via stringi usada em .norm() — independente do
  # locale. Mantem maiusculas/numeros para preservar codigos como "Ia", "II".
  x <- stringi::stri_trans_general(trimws(as.character(x)), "Latin-ASCII")
  x <- gsub("[^A-Za-z0-9]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x <- substr(x, 1, max_chars)
  x <- sub("_+$", "", x)
  ifelse(nzchar(x), x, "recorte")
}

.build_cores_cat <- function(categorias_reais) {
  # Normaliza os DOIS lados em tempo de execucao (nao confia em uma
  # grafia pre-normalizada nas chaves de .CORES_CAT_BASE) — evita que
  # pequenas diferencas de acentuacao/hifen quebrem o casamento e
  # todas as categorias caiam no cinza de fallback.
  base_norm  <- .norm(names(.CORES_CAT_BASE))
  keys       <- .norm(categorias_reais)
  idx        <- match(keys, base_norm)
  cores      <- ifelse(is.na(idx), "#888888", unname(.CORES_CAT_BASE)[idx])
  ordem      <- order(match(keys, base_norm), na.last = TRUE)
  list(
    cores  = setNames(cores, categorias_reais),
    ordem  = categorias_reais[ordem]
  )
}

# ============================================================
#  5b. AGREGACAO PARA O NIVEL 2 DA LEGENDA MAPBIOMAS
#      Usado nos graficos Sankey, Matriz (M1) e Heatmap: os dados
#      passam a ser apresentados agrupados no Nivel 2 da legenda.
# ============================================================

# Codigo MapBiomas -> codigo do Nivel 2. Classes que ja sao de N2
# mapeiam para si; culturas detalhadas (Soja, Cana, Cafe...) e as
# lavouras sobem para "Agricultura" (18). Agregados de N1 (1,10,14,
# 22,26) mapeiam para si mesmos.
MB_COD_N2 <- c(
  "1"="1","3"="3","4"="4","5"="5","6"="6","49"="49",
  "10"="10","11"="11","12"="12","29"="29","32"="32","50"="50","13"="13",
  "14"="14","15"="15","9"="9","21"="21","18"="18",
  "19"="18","36"="18","39"="18","20"="18","40"="18","62"="18",
  "41"="18","46"="18","47"="18","35"="18","48"="18",
  "22"="22","23"="23","24"="24","25"="25","30"="30","75"="75",
  "26"="26","33"="33","31"="31",
  "27"="27","255"="27"
)

MB_N2_NOME <- c(
  "1"="Floresta","3"="Formacao Florestal","4"="Formacao Savanica",
  "5"="Mangue","6"="Floresta Alagavel","49"="Restinga Arborea",
  "10"="Veg. Herbacea e Arbustiva","11"="Campo Alagado e Area Pantanosa",
  "12"="Formacao Campestre","29"="Afloramento Rochoso","32"="Apicum",
  "50"="Restinga Herbacea","13"="Outra Formacao nao Florestal",
  "14"="Agropecuaria","15"="Pastagem","9"="Silvicultura",
  "21"="Mosaico de Usos","18"="Agricultura",
  "22"="Area nao Vegetada","23"="Praia, Duna e Areal","24"="Area Urbanizada",
  "25"="Outras Areas nao Vegetadas","30"="Mineracao","75"="Usina Fotovoltaica",
  "26"="Corpo D'agua","33"="Rio, Lago e Oceano","31"="Aquicultura",
  "27"="Nao Observado"
)

# Legenda completa (codigo -> nome, em todos os niveis) — usada para,
# na Matriz (que so traz NOMES de classe), voltar do nome ao codigo e
# entao ao Nivel 2.
.MB_LEGENDA <- c(
  "1"="Floresta","3"="Formacao Florestal","4"="Formacao Savanica","5"="Mangue",
  "6"="Floresta Alagavel","49"="Restinga Arborea",
  "10"="Vegetacao Herbacea e Arbustiva","11"="Campo Alagado e Area Pantanosa",
  "12"="Formacao Campestre","29"="Afloramento Rochoso","32"="Apicum",
  "50"="Restinga Herbacea","13"="Outra Formacao nao Florestal",
  "14"="Agropecuaria","15"="Pastagem","9"="Silvicultura","21"="Mosaico de Usos",
  "18"="Agricultura","19"="Lavoura Temporaria","36"="Lavoura Perene",
  "39"="Soja","20"="Cana-de-acucar","40"="Arroz","62"="Algodao",
  "41"="Outras Lavouras Temporarias","46"="Cafe","47"="Citrus","35"="Dende",
  "48"="Outras Lavouras Perenes",
  "22"="Area nao Vegetada","23"="Praia, Duna e Areal","24"="Area Urbanizada",
  "25"="Outras Areas nao Vegetadas","30"="Mineracao","75"="Usina Fotovoltaica",
  "26"="Corpo D'agua","33"="Rio, Lago e Oceano","31"="Aquicultura",
  "27"="Nao Observado"
)
.NOME_NORM_PARA_COD  <- setNames(names(.MB_LEGENDA), .norm(unname(.MB_LEGENDA)))
.N2NOME_NORM_PARA_COD <- setNames(names(MB_N2_NOME), .norm(unname(MB_N2_NOME)))

# codigo -> nome N2
.cod_para_n2nome <- function(cod) {
  cod  <- as.character(cod)
  nome <- unname(MB_N2_NOME[MB_COD_N2[cod]])
  ifelse(is.na(nome), paste0("Classe ", cod), nome)
}
# codigo -> cor N2 (cor MapBiomas do codigo N2)
.cod_para_n2cor <- function(cod) {
  cod <- as.character(cod)
  cor <- unname(CORES_MB[MB_COD_N2[cod]])
  ifelse(is.na(cor), "#888888", cor)
}
# nome de classe (qualquer nivel) -> nome N2 (via nome normalizado -> codigo)
.nome_para_n2nome <- function(nome) {
  cod <- .NOME_NORM_PARA_COD[.norm(nome)]
  ifelse(is.na(cod), as.character(nome), .cod_para_n2nome(cod))
}
# nome N2 -> cor MapBiomas
.n2nome_para_cor <- function(nome_n2) {
  cod <- .N2NOME_NORM_PARA_COD[.norm(nome_n2)]
  cor <- unname(CORES_MB[cod])
  ifelse(is.na(cor), "#888888", cor)
}

# Agrega uma matriz de transicao (bloco de AREA, ha) ao Nivel 2:
# soma as areas por (origem N2, destino N2). Recebe df tidy com colunas
# classe_origem, classe_destino, valor (ha).
.agrega_matriz_n2 <- function(df_ha) {
  ag <- df_ha %>%
    mutate(o2 = .nome_para_n2nome(as.character(classe_origem)),
           d2 = .nome_para_n2nome(as.character(classe_destino)),
           valor = suppressWarnings(as.numeric(valor))) %>%
    group_by(classe_origem = o2, classe_destino = d2) %>%
    summarise(valor = sum(valor, na.rm = TRUE), .groups = "drop")
  niveis <- sort(unique(c(as.character(ag$classe_origem),
                          as.character(ag$classe_destino))))
  ag %>% mutate(classe_origem  = factor(classe_origem,  levels = niveis),
                classe_destino = factor(classe_destino, levels = niveis))
}

# Codigo -> Nivel 1 (grandes grupos) — lado de ORIGEM do Sankey
MB_COD_N1 <- c(
  "1"="1","3"="1","4"="1","5"="1","6"="1","49"="1",
  "10"="10","11"="10","12"="10","29"="10","32"="10","50"="10","13"="10",
  "14"="14","15"="14","9"="14","21"="14","18"="14","19"="14","36"="14",
  "39"="14","20"="14","40"="14","62"="14","41"="14","46"="14","47"="14",
  "35"="14","48"="14",
  "22"="22","23"="22","24"="22","25"="22","30"="22","75"="22",
  "26"="26","33"="26","31"="26",
  "27"="27","255"="27"
)
MB_N1_NOME <- c(
  "1"="Floresta","10"="Veg. Herbacea e Arbustiva","14"="Agropecuaria",
  "22"="Area nao Vegetada","26"="Corpo D'agua","27"="Nao Observado"
)
.N1NOME_NORM_PARA_COD <- setNames(names(MB_N1_NOME), .norm(unname(MB_N1_NOME)))
.cod_para_n1nome <- function(cod) {
  cod  <- as.character(cod)
  nome <- unname(MB_N1_NOME[MB_COD_N1[cod]])
  ifelse(is.na(nome), paste0("Classe ", cod), nome)
}
.n1nome_para_cor <- function(nome_n1) {
  cod <- .N1NOME_NORM_PARA_COD[.norm(nome_n1)]
  cor <- unname(CORES_MB[cod])
  ifelse(is.na(cor), "#888888", cor)
}

# Agrupa classes < limiar (fracao do total) numa unica classe "outros"
# na matriz de transicao. So vira "outros" se for pequena tanto como
# origem quanto como destino (nao perde classes em expansao).
.agrupa_pequenas_matriz <- function(df, limiar = 0.01,
                                    rotulo = "Soma de outros valores inferiores a 1%") {
  Tot <- sum(df$valor, na.rm = TRUE)
  if (Tot <= 0) return(df)
  to <- df %>% group_by(classe_origem) %>%
    summarise(s = sum(valor, na.rm = TRUE), .groups = "drop")
  td <- df %>% group_by(classe_destino) %>%
    summarise(s = sum(valor, na.rm = TRUE), .groups = "drop")
  peq <- intersect(
    as.character(to$classe_origem[to$s  < limiar * Tot]),
    as.character(td$classe_destino[td$s < limiar * Tot]))
  if (length(peq) == 0) return(df)
  ag <- df %>%
    mutate(classe_origem  = if_else(as.character(classe_origem)  %in% peq,
                                    rotulo, as.character(classe_origem)),
           classe_destino = if_else(as.character(classe_destino) %in% peq,
                                    rotulo, as.character(classe_destino))) %>%
    group_by(classe_origem, classe_destino) %>%
    summarise(valor = sum(valor, na.rm = TRUE), .groups = "drop")
  niveis <- sort(unique(c(as.character(ag$classe_origem),
                          as.character(ag$classe_destino))))
  niveis <- c(setdiff(niveis, rotulo), intersect(niveis, rotulo))
  ag %>% mutate(classe_origem  = factor(classe_origem,  levels = niveis),
                classe_destino = factor(classe_destino, levels = niveis))
}

COR_1985 <- "#1D9E75"
COR_2024 <- "#9FE1CB"

# ============================================================
#  6. TEMA BASE E EXPORTACAO
# ============================================================
FONTE_BASE <- 12

# ── Ajustes de texto: nomes longos de recortes/unidades ──────────────────
# Os nomes das unidades nunca são cortados — textos longos são QUEBRADOS
# em várias linhas. Ajuste as larguras abaixo (em número de caracteres
# por linha) se algum título ainda ficar apertado ou largo demais.
LARGURA_TITULO  <- 70   # título principal de cada gráfico
LARGURA_FACET   <- 45   # título de cada painel nas grades (C2A, C4A...)
LARGURA_LEGENDA <- 40   # itens de legenda com nome de unidade (F1, PCA...)
LARGURA_EIXO    <- 30   # nomes de unidade usados como rótulo de eixo

.quebrar <- function(x, largura = LARGURA_TITULO) {
  stringr::str_wrap(x, width = largura)
}
rotulo_facet <- ggplot2::label_wrap_gen(width = LARGURA_FACET)

tema_amp <- theme_minimal(base_size = FONTE_BASE) +
  theme(
    plot.title         = element_text(face="bold", size=FONTE_BASE+3, hjust=0, margin=margin(b=4),
                                      lineheight=1.05),
    plot.subtitle      = element_text(color="grey45", size=FONTE_BASE-1, hjust=0, margin=margin(b=8)),
    plot.caption       = element_text(color="grey55", size=FONTE_BASE-3, hjust=1, margin=margin(t=6)),
    axis.text          = element_text(size=FONTE_BASE-1),
    axis.title         = element_text(size=FONTE_BASE-1),
    panel.grid.major.x = element_blank(),
    panel.grid.minor   = element_blank(),
    legend.position    = "top",
    legend.title       = element_blank(),
    legend.text        = element_text(size=FONTE_BASE-2),
    plot.margin        = margin(12,16,8,12),
    strip.text         = element_text(face="bold", size=FONTE_BASE, lineheight=1.0)
  )

CAPTION_PADRAO <- paste0(
  "Fonte: MapBiomas Brasil, Colecao 10  |  AnP v1.1 (2025)"
)

salvar_grafico <- function(nome, plot, w=12, h=7, dpi=180) {
  base <- file.path(pasta_saida, nome)
  gerados <- c()
  if ("png" %in% FORMATO_SAIDA) {
    ggsave(paste0(base,".png"), plot=plot, width=w, height=h, dpi=dpi, bg="white")
    gerados <- c(gerados, ".png")
  }
  if ("svg" %in% FORMATO_SAIDA) {
    svglite::svglite(paste0(base,".svg"), width=w, height=h)
    print(plot); dev.off()
    gerados <- c(gerados, ".svg")
  }
  message("  Salvo: ", nome, " (", paste(gerados, collapse=" | "), ")")
  invisible(plot)
}

# ============================================================
#  7. BLOCO — COBERTURA E ALTERACOES  (familia 1)
# ============================================================

if (GERAR_COBERTURA) {
  
  abas_cob <- excel_sheets(arq_cob)
  aba_cob  <- abas_cob[grepl("obertura", abas_cob, ignore.case = TRUE)][1]
  aba_alt  <- abas_cob[grepl("ltera",    abas_cob, ignore.case = TRUE)][1]
  
  cobertura  <- read_excel(arq_cob, sheet = aba_cob) %>%
    mutate(unidade_analise = as.character(unidade_analise))
  alteracoes <- read_excel(arq_cob, sheet = aba_alt) %>%
    mutate(unidade_analise = as.character(unidade_analise))

  # Garante que TODAS as unidades presentes nos dados completos estejam
  # em ORDEM_RECORTES (a detecção inicial usa n_max=500, podendo perder
  # unidades que aparecem apenas após a linha 500 do XLSX).
  .nomes_cob_completo <- unique(c(
    cobertura$unidade_analise,
    alteracoes$unidade_analise
  ))
  .nomes_cob_completo <- .nomes_cob_completo[
    !is.na(.nomes_cob_completo) & nzchar(trimws(.nomes_cob_completo))]
  .novos_nomes <- setdiff(.nomes_cob_completo, ORDEM_RECORTES)
  if (length(.novos_nomes) > 0) {
    message("[INFO] Unidades adicionais detectadas (alem das primeiras 500 linhas): ",
            paste(.novos_nomes, collapse = ", "))
    NOMES_PADRAO   <<- c(NOMES_PADRAO, setNames(.novos_nomes, .novos_nomes))
    ORDEM_RECORTES <<- unique(c(ORDEM_RECORTES, .novos_nomes))
    CORES_RECORTE  <<- setNames(
      rep_len(.PALETA_RECORTES, length(ORDEM_RECORTES)), ORDEM_RECORTES)
  }

  cobertura  <- cobertura  %>% mutate(unidade_analise = padronizar(unidade_analise))
  alteracoes <- alteracoes %>% mutate(unidade_analise = padronizar(unidade_analise))

  message("\nCobertura: ", nrow(cobertura), " linhas")
  message("Alteracoes: ", nrow(alteracoes), " linhas")
  
  .cats_reais <- unique(as.character(alteracoes[[
    names(alteracoes)[grepl("categ", names(alteracoes), ignore.case = TRUE)][1]
  ]]))
  .cats_reais <- .cats_reais[!is.na(.cats_reais)]
  .cat_cfg    <- .build_cores_cat(.cats_reais)
  CORES_CATEGORIA <- .cat_cfg$cores
  ORDEM_CATEGORIA <- .cat_cfg$ordem
  
  LIMIAR_OUTROS <- 0.01
  # percentual no arquivo vem em fracao (0-1); classes < 1% no maximo
  # entre os anos sao agrupadas em "Outros usos"
  classes_outros <- cobertura %>%
    filter(cod_classe != 255) %>%
    group_by(unidade_analise, classe) %>%
    summarise(max_pct = if (all(is.na(percentual))) NA_real_
                        else max(percentual, na.rm = TRUE), .groups = "drop") %>%
    filter(!is.na(max_pct) & max_pct < LIMIAR_OUTROS) %>% select(unidade_analise, classe)
  
  cob <- cobertura %>%
    filter(cod_classe != 255) %>%
    mutate(
      cod_str         = as.character(cod_classe),
      cor             = coalesce(CORES_MB[cod_str], "#888888"),
      pct             = percentual * 100,
      ano             = factor(ano, levels = sort(unique(ano))),
      unidade_analise = factor(unidade_analise, levels = ORDEM_RECORTES)
    ) %>%
    left_join(classes_outros %>% mutate(e_outro = TRUE),
              by = c("unidade_analise","classe")) %>%
    mutate(
      e_outro     = replace_na(e_outro, FALSE),
      classe_plot = if_else(e_outro, "Outros usos", classe),
      cor_plot    = if_else(e_outro, "#aaaaaa", cor)
    ) %>%
    group_by(unidade_analise, ano, classe_plot, cor_plot) %>%
    summarise(area_ha = sum(area_ha, na.rm = TRUE),
              pct     = sum(pct,     na.rm = TRUE), .groups = "drop")
  
  ANOS_COB <- sort(unique(as.integer(as.character(cobertura$ano))))
  ANO_INI  <- min(ANOS_COB); ANO_FIM <- max(ANOS_COB)
  
  alt <- alteracoes %>%
    rename_with(~ case_when(
      grepl("orig",.,ignore.case=T) & grepl("classe|class",.,ignore.case=T) ~ "cl_orig",
      grepl("dest",.,ignore.case=T) & grepl("classe|class",.,ignore.case=T) ~ "cl_dest",
      grepl("categ",.,ignore.case=T)                                         ~ "categoria",
      grepl("^area|^ha",.,ignore.case=T)                                     ~ "area_ha",
      TRUE ~ .
    ), .cols = everything()) %>%
    mutate(
      categoria       = factor(categoria, levels = ORDEM_CATEGORIA),
      unidade_analise = factor(unidade_analise, levels = ORDEM_RECORTES)
    )
  
  message("\nCategorias detectadas e cores:")
  for (i in seq_along(CORES_CATEGORIA))
    message(sprintf("  %-45s  %s", names(CORES_CATEGORIA)[i], CORES_CATEGORIA[i]))
  
  # ---- C2 — Delta % cobertura individual ----
  grafico_C2_delta <- function(unidade_nome) {
    df <- cob %>%
      filter(unidade_analise == unidade_nome) %>%
      select(classe_plot, cor_plot, ano, pct) %>%
      pivot_wider(names_from=ano, values_from=pct, values_fill=0) %>%
      mutate(delta = .data[[as.character(ANO_FIM)]] - .data[[as.character(ANO_INI)]],
             classe_plot = fct_reorder(classe_plot, delta, .na_rm=TRUE),
             classe_plot = fct_relevel(classe_plot, "Outros usos", after=Inf))
    cores_u <- setNames(df$cor_plot, as.character(df$classe_plot))
    
    ggplot(df, aes(x=classe_plot, y=delta, fill=classe_plot)) +
      geom_col(color="grey40", linewidth=0.2, width=0.68) +
      geom_hline(yintercept=0, linewidth=0.6, color="grey30") +
      geom_text(
        data=df %>% filter(abs(delta) >= 0.3),
        aes(label=paste0(if_else(delta>0,"+",""),
                         number(delta,accuracy=0.1,decimal.mark=","),"%"),
            vjust=if_else(delta>=0,-0.45,1.35)),
        size=3.3, color="grey20", fontface="bold") +
      scale_fill_manual(values=cores_u, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.14,0.16))) +
      labs(title=.quebrar(paste("Variacao de cobertura |", unidade_nome)),
           subtitle=paste0("Diferenca percentual ", ANO_FIM, " - ", ANO_INI,
                           "  |  acima = ganho  |  abaixo = perda"),
           x=NULL, y="Delta (%)", caption=CAPTION_PADRAO) +
      tema_amp + theme(legend.position="none",
                       axis.text.x=element_text(angle=35,hjust=1,size=10))
  }
  
  # ---- C2A — Delta % cobertura integrado (grade) ----
  grafico_C2A_integrado <- function(recortes) {
    rec_norm <- .norm(recortes)
    df <- cob %>%
      filter(.norm(as.character(unidade_analise)) %in% rec_norm) %>%
      select(unidade_analise, classe_plot, cor_plot, ano, pct) %>%
      pivot_wider(names_from=ano, values_from=pct, values_fill=0) %>%
      mutate(delta = .data[[as.character(ANO_FIM)]] - .data[[as.character(ANO_INI)]],
             classe_plot = fct_reorder(classe_plot, delta, .fun=mean, .na_rm=TRUE),
             classe_plot = fct_relevel(classe_plot, "Outros usos", after=Inf),
             unidade_analise = factor(unidade_analise,
                                      levels=unique(as.character(unidade_analise))))
    
    cores_classes <- df %>%
      distinct(classe_plot, cor_plot) %>%
      { setNames(.$cor_plot, as.character(.$classe_plot)) }
    
    n_rec  <- length(recortes)
    n_cols <- if (n_rec <= 2) 1L else if (n_rec <= 9) 2L else if (n_rec <= 20) 3L else 4L

    ggplot(df, aes(x=classe_plot, y=delta, fill=classe_plot)) +
      geom_col(color="grey40", linewidth=0.15, width=0.7) +
      geom_hline(yintercept=0, linewidth=0.5, color="grey30") +
      geom_text(
        data=df %>% filter(abs(delta) >= 0.3),
        aes(label=paste0(if_else(delta>0,"+",""),
                         number(delta,accuracy=0.1,decimal.mark=","),"%"),
            vjust=if_else(delta>=0,-0.45,1.35)),
        size=2.6, color="grey20", fontface="bold") +
      facet_wrap(~unidade_analise, ncol=n_cols, scales="free_y", labeller=rotulo_facet) +
      scale_fill_manual(values=cores_classes, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.18,0.22))) +
      labs(title=paste0("Variacao da cobertura e uso da terra (", ANO_INI, "-", ANO_FIM, ")"),
           subtitle="Diferenca percentual por classe  |  acima = ganho  |  abaixo = perda",
           x=NULL, y="Delta (%)", caption=CAPTION_PADRAO) +
      tema_amp +
      theme(legend.position="none",
            axis.text.x=element_text(angle=35,hjust=1,size=8),
            strip.text=element_text(face="bold",size=11,hjust=0),
            panel.grid.major.x=element_blank(),
            panel.grid.major.y=element_line(color="grey90",linewidth=0.4),
            plot.margin=margin(14,16,10,14))
  }
  
  # ---- C4 — Categorias de alteracao individual ----
  grafico_C4_individual <- function(unidade_nome) {
    total_rec <- alt %>%
      filter(unidade_analise == unidade_nome) %>%
      summarise(tot = sum(area_ha, na.rm=TRUE)) %>% pull(tot)
    
    df <- alt %>%
      filter(unidade_analise == unidade_nome, !is.na(categoria)) %>%
      group_by(categoria) %>%
      summarise(area_ha = sum(area_ha, na.rm=TRUE), .groups="drop") %>%
      mutate(pct     = area_ha / total_rec * 100,
             cor_cat = coalesce(CORES_CATEGORIA[as.character(categoria)], "#888888"),
             categoria = factor(categoria, levels=rev(ORDEM_CATEGORIA)))
    
    lim_x <- max(df$area_ha, na.rm=TRUE) * 1.30
    
    ggplot(df, aes(x=area_ha, y=categoria, fill=cor_cat)) +
      geom_col(color="grey35", linewidth=0.25, width=0.62) +
      geom_text(aes(label=paste0(number(pct,accuracy=0.1,decimal.mark=","),"%")),
                hjust=-0.08, size=3.8, fontface="bold", color="grey15") +
      scale_fill_identity() +
      scale_x_continuous(limits=c(0,lim_x),
                         labels=label_number(big.mark=".",decimal.mark=",",suffix=" ha"),
                         expand=expansion(mult=c(0,0))) +
      scale_y_discrete(labels=function(x) str_wrap(x, width=18)) +
      labs(title=.quebrar(unidade_nome, 55),
           subtitle=paste0("Categorias de alteracao da cobertura | ", ANO_INI, "-", ANO_FIM),
           x="Area (ha)", y=NULL, caption=CAPTION_PADRAO) +
      tema_amp +
      theme(plot.title=element_text(face="bold",size=14,hjust=0),
            axis.text.y=element_text(size=11,lineheight=0.9),
            axis.text.x=element_text(size=9),
            panel.grid.major.x=element_line(color="grey90",linewidth=0.4),
            panel.grid.major.y=element_blank(),
            legend.position="none",
            plot.margin=margin(14,20,10,14))
  }
  
  # ---- C4A — Grade de categorias, todos os recortes selecionados ----
  grafico_C4A_grade <- function(recortes) {
    rec_norm <- .norm(recortes)
    df <- alt %>%
      filter(!is.na(unidade_analise), !is.na(categoria),
             .norm(as.character(unidade_analise)) %in% rec_norm) %>%
      group_by(unidade_analise, categoria) %>%
      summarise(area_ha = sum(area_ha, na.rm=TRUE), .groups="drop") %>%
      group_by(unidade_analise) %>%
      mutate(pct = area_ha / sum(area_ha) * 100) %>% ungroup() %>%
      mutate(unidade_analise = factor(unidade_analise,
                                      levels=intersect(recortes,
                                                       unique(as.character(unidade_analise)))),
             categoria = factor(categoria, levels=rev(ORDEM_CATEGORIA)),
             cor_cat   = coalesce(CORES_CATEGORIA[as.character(categoria)], "#888888"))
    
    n_rec  <- length(recortes)
    n_cols <- if (n_rec <= 2) 1L else if (n_rec <= 9) 2L else if (n_rec <= 20) 3L else 4L

    ggplot(df, aes(x=area_ha, y=categoria, fill=cor_cat)) +
      geom_col(color="grey30", linewidth=0.2, width=0.68) +
      geom_text(aes(label=paste0(number(pct,accuracy=0.1,decimal.mark=","),"%")),
                hjust=-0.08, size=3.2, fontface="bold", color="grey15") +
      facet_wrap(~unidade_analise, ncol=n_cols, scales="free_x", labeller=rotulo_facet) +
      scale_fill_identity() +
      scale_x_continuous(labels=label_number(big.mark=".",decimal.mark=",",suffix=" ha"),
                         expand=expansion(mult=c(0,0.30))) +
      scale_y_discrete(labels=function(x) str_wrap(x, width=20)) +
      labs(title=paste0("Categorias de alteracao da cobertura (", ANO_INI, "-", ANO_FIM, ")"),
           subtitle="Area (ha) por recorte  |  Rotulo = % da area total  |  Cores por categoria",
           x="Area (ha)", y=NULL, caption=CAPTION_PADRAO) +
      tema_amp +
      theme(strip.text=element_text(face="bold",size=11,color="grey15",hjust=0),
            axis.text.y=element_text(size=10,lineheight=0.85),
            axis.text.x=element_text(size=8),
            panel.grid.major.x=element_line(color="grey90",linewidth=0.4),
            panel.grid.major.y=element_blank(),
            legend.position="none",
            plot.margin=margin(14,20,10,14))
  }
  
  .rec_cob <- unique(as.character(alt$unidade_analise))
  .rec_cob <- .rec_cob[!is.na(.rec_cob)]
  message("\nRecortes no arquivo de COBERTURA: ", paste(.rec_cob, collapse=" | "))
  RECORTES_INT_COB <- .rec_cob
}

# ============================================================
#  8. BLOCO — MATRIZ DE TRANSICAO  (familia 2)
# ============================================================

if (GERAR_MATRIZ) {
  
  # Le um arquivo com duas matrizes empilhadas (ha e % da origem),
  # cada bloco com titulo, linha "Classe <ano>", cabecalho de colunas
  # e linhas de dados ate encontrar uma linha em branco na coluna
  # "Classe (ano1)". Retorna lista com um data.frame tidy por unidade.
  .ler_matriz <- function(caminho, sheet) {
    raw <- suppressMessages(
      read_excel(caminho, sheet = sheet, col_names = FALSE, col_types = "text")
    )
    raw <- as.data.frame(raw, stringsAsFactors = FALSE)
    n_row <- nrow(raw); n_col <- ncol(raw)
    
    titulos <- which(grepl("Matriz de Transi", raw[[1]]))
    if (length(titulos) == 0) return(list())
    
    blocos <- list()
    for (ti in titulos) {
      titulo_txt <- raw[[1]][ti]
      unidade    <- if (grepl("%", titulo_txt)) "percentual" else "ha"
      
      linha_header <- ti + 2
      if (linha_header > n_row) next
      header <- as.character(unlist(raw[linha_header, ]))
      nomes_col <- header[3:n_col]
      nomes_col <- nomes_col[!is.na(nomes_col) & nchar(trimws(nomes_col)) > 0]
      n_classes_col <- length(nomes_col)
      if (n_classes_col == 0) next
      
      linha_ini <- linha_header + 1
      linha_fim <- linha_ini
      while (linha_fim <= n_row &&
             !is.na(raw[linha_fim, 2]) &&
             nchar(trimws(raw[linha_fim, 2])) > 0) {
        linha_fim <- linha_fim + 1
      }
      linha_fim <- linha_fim - 1
      if (linha_fim < linha_ini) next
      
      sub <- raw[linha_ini:linha_fim, c(2, 3:(2 + n_classes_col)), drop = FALSE]
      names(sub) <- c("classe_origem", nomes_col)
      
      long <- sub %>%
        pivot_longer(cols = -classe_origem, names_to = "classe_destino",
                     values_to = "valor") %>%
        mutate(valor   = suppressWarnings(as.numeric(valor)),
               valor   = replace_na(valor, 0),
               unidade = unidade,
               classe_origem  = factor(classe_origem, levels = unique(sub$classe_origem)),
               classe_destino = factor(classe_destino, levels = nomes_col))
      
      blocos[[unidade]] <- long
    }
    blocos
  }
  
  grafico_M1_heatmap <- function(dados_bloco, unidade_valor, recorte_nome) {
    df <- dados_bloco
    if (unidade_valor == "ha") {
      df$valor_show <- df$valor
      lbl_fill <- "Area (ha)"
      df$label_txt <- ifelse(df$valor_show > 0,
                             number(df$valor_show, big.mark=".", decimal.mark=",", accuracy=1), "")
      subt <- "Celulas = area (ha) que migrou da origem (linha) para o destino (coluna) | agrupado no Nivel 2"
    } else {
      # % da area de origem RECALCULADO a partir do ha agregado ao Nivel 2
      # (somar as fracoes ja prontas seria incorreto apos o reagrupamento)
      df <- df %>% group_by(classe_origem) %>%
        mutate(tot_orig   = sum(valor, na.rm = TRUE),
               valor_show = ifelse(tot_orig > 0, valor / tot_orig * 100, 0)) %>%
        ungroup()
      lbl_fill <- "% da area de origem"
      df$label_txt <- ifelse(df$valor_show > 0,
                             paste0(number(df$valor_show, accuracy=0.1, decimal.mark=","), "%"), "")
      subt <- "Celulas = % da area de origem que migrou para o destino | agrupado no Nivel 2"
    }
    
    diagonal <- df %>% filter(as.character(classe_origem) == as.character(classe_destino))
    
    # Cor de texto por célula: replica a interpolação do gradiente de
    # preenchimento (mesmas 4 cores/estágios do scale_fill_gradientn
    # abaixo) para decidir se o rótulo daquela célula deve ser escrito
    # em branco ou em cinza-escuro, evitando texto ilegível nas células
    # mais escuras do vermelho.
    .rampa_m1 <- grDevices::colorRamp(
      c("#FFFFFF","#FFE0B2","#FB8C00","#B71C1C"), space = "Lab")
    .faixa_m1 <- range(df$valor_show, na.rm = TRUE)
    .frac_m1  <- if (diff(.faixa_m1) > 0) {
      (df$valor_show - .faixa_m1[1]) / diff(.faixa_m1)
    } else 0
    .rgb_m1   <- .rampa_m1(pmin(pmax(.frac_m1, 0), 1))
    df$cor_celula <- rgb(.rgb_m1[,1], .rgb_m1[,2], .rgb_m1[,3], maxColorValue = 255)
    df$cor_texto  <- .cor_texto_contraste(df$cor_celula)
    
    ggplot(df, aes(x = classe_destino, y = fct_rev(classe_origem), fill = valor_show)) +
      geom_tile(color = "white", linewidth = 0.4) +
      geom_tile(data = diagonal, fill = NA, color = "#D32F2F", linewidth = 1.1) +
      geom_text(aes(label = label_txt, color = cor_texto), size = 2.3) +
      scale_color_identity() +
      scale_fill_gradientn(colors = c("#FFFFFF","#FFE0B2","#FB8C00","#B71C1C"),
                           na.value = "white", name = lbl_fill) +
      scale_x_discrete(position = "top",
                       labels = function(x) str_wrap(x, width = 14)) +
      labs(title = .quebrar(paste("Matriz de transicao de cobertura (Nivel 2) |", recorte_nome)),
           subtitle = paste0(subt, "  |  Diagonal em vermelho"),
           x = "Classe de destino", y = "Classe de origem",
           caption = CAPTION_PADRAO) +
      tema_amp +
      theme(axis.text.x = element_text(angle = 45, hjust = 0, vjust = 0,
                                       size = 7, lineheight = 0.85),
            axis.text.y = element_text(size = 8),
            legend.position = "right",
            panel.grid = element_blank())
  }
  
  # Nome completo da unidade de uma aba da Matriz. O Excel limita nomes de
  # aba a 31 caracteres, então o nome da aba pode estar cortado. Ordem:
  #   1. linha "Unidade de análise:" gravada pelo plugin (v1.1+);
  #   2. nome conhecido (das outras planilhas) que comece com o nome da aba;
  #   3. o próprio nome da aba.
  .nome_unidade_matriz <- function(caminho, aba) {
    raw <- tryCatch(suppressMessages(
      read_excel(caminho, sheet = aba, col_names = FALSE, col_types = "text")),
      error = function(e) NULL)
    if (!is.null(raw) && ncol(raw) >= 2) {
      i <- which(grepl("^Unidade de an", raw[[1]]))
      if (length(i) && !is.na(raw[[2]][i[1]]) && nzchar(trimws(raw[[2]][i[1]])))
        return(trimws(raw[[2]][i[1]]))
    }
    candidatos <- ORDEM_RECORTES[startsWith(.norm(ORDEM_RECORTES), .norm(aba))]
    if (length(candidatos) >= 1)
      return(candidatos[which.max(nchar(candidatos))])
    padronizar(aba)
  }

  ABAS_MAT <- excel_sheets(arq_mat)
  ABAS_MAT <- ABAS_MAT[!grepl(.RE_ABA_META, ABAS_MAT)]   # ignora metadados
  message("\nAbas (recortes) no arquivo de Matriz: ", paste(ABAS_MAT, collapse=" | "))
}

# ============================================================
#  9. BLOCO — FRAGMENTACAO / PAISAGEM  (familia 3)
# ============================================================

if (GERAR_FRAG) {
  
  .abas_frag <- excel_sheets(arq_frag)
  message("\nAbas fragmentacao: ", paste(.abas_frag, collapse = ", "))
  
  TEM_DIST_PORTE <- all(c("Dist_Fragmentos","Dist_Nucleos") %in% .abas_frag)
  if (!TEM_DIST_PORTE) {
    message("\n  [AVISO] Este arquivo nao contem as abas Dist_Fragmentos/Dist_Nucleos.")
    message("  Os graficos F2/F2b (distribuicao por classe de tamanho) serao pulados.")
    message("  Atualize o plugin AnP - Fragmentacao para v1.1 ou superior e reprocesse.\n")
  }
  
  ORDEM_CLASSES_TAM <- c(
    "Menor que 1 ha","1 a 10 ha","10 a 20 ha","20 a 30 ha",
    "30 a 50 ha","50 a 100 ha","100 a 200 ha","Maior que 200 ha"
  )
  
  # ── Grupo alvo dos gráficos F1/F2/F2b ────────────────────────────────────
  # O módulo de Fragmentação só calcula métricas para os grupos que o
  # usuário MARCOU na interface ao rodar o processamento — se apenas
  # "Cobertura Natural" foi selecionado (sem marcar "Floresta" também),
  # a planilha não terá NENHUMA linha com grupo == "Floresta", e um
  # filtro fixo nesse nome deixaria os painéis F1 completamente em
  # branco sem nenhum erro visível. Por isso detectamos automaticamente
  # qual grupo está de fato disponível nos dados, priorizando
  # "Floresta" quando presente.
  GRUPO_F1_PREFERIDO <- "Floresta"
  
  .detectar_grupo_disponivel <- function(df_com_grupo, preferido) {
    if (!"grupo" %in% names(df_com_grupo)) return(NULL)
    grupos_disp <- unique(as.character(df_com_grupo$grupo))
    grupos_disp <- grupos_disp[!is.na(grupos_disp)]
    if (length(grupos_disp) == 0) return(NULL)
    if (preferido %in% grupos_disp) {
      message("  [F1] Grupo utilizado: '", preferido, "' (conforme configurado)")
      return(preferido)
    }
    escolhido <- grupos_disp[1]
    message("  [AVISO] Grupo '", preferido, "' nao encontrado na planilha de ",
            "fragmentacao (provavelmente nao foi selecionado ao rodar o ",
            "modulo). Grupos disponiveis: ", paste(grupos_disp, collapse=", "),
            ". Usando '", escolhido, "' automaticamente.")
    escolhido
  }
  
  if ("Variacoes" %in% .abas_frag) {
    frag_var_raw <- read_excel(arq_frag, sheet = "Variacoes") %>%
      mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES))
    
    # Deteccao dinamica das colunas valor_<ano1>/valor_<ano2> —
    # o nome real inclui o ano (ex: valor_1985), nao "valor_ano1" fixo
    cols_valor <- names(frag_var_raw)[grepl("^valor_\\d{4}$", names(frag_var_raw))]
    anos_det   <- sort(as.integer(gsub("valor_", "", cols_valor)))
    if (length(anos_det) >= 2) {
      ANO1_FRAG <- anos_det[1]; ANO2_FRAG <- anos_det[length(anos_det)]
    } else {
      stop("Nao foi possivel detectar as colunas valor_<ano> na aba Variacoes.")
    }
    col_v1 <- paste0("valor_", ANO1_FRAG)
    col_v2 <- paste0("valor_", ANO2_FRAG)
    
    GRUPO_F1 <- .detectar_grupo_disponivel(frag_var_raw, GRUPO_F1_PREFERIDO)
    
    metricas <- frag_var_raw %>%
      rename(valor_ano1 = all_of(col_v1), valor_ano2 = all_of(col_v2)) %>%
      select(recorte, grupo, metrica, valor_ano1, valor_ano2) %>%
      mutate(recorte = as.character(recorte),
             across(c(valor_ano1, valor_ano2), ~ suppressWarnings(as.numeric(.))),
             # Recalcula o delta diretamente de valor_ano1/valor_ano2 em vez
             # de usar as colunas delta_abs/delta_pct do Excel: versões
             # anteriores do módulo de Fragmentação gravavam delta_pct como
             # TEXTO formatado ("+24.44%"), que as.numeric() nao consegue
             # interpretar (vira NA silenciosamente, deixando os graficos
             # em branco sem erro nenhum). valor_ano1/valor_ano2 sempre
             # foram numéricos em todas as versões, entao recalcular aqui
             # torna o script compatível tanto com arquivos antigos quanto
             # com os corrigidos, sem depender do formato exportado.
             delta_abs     = valor_ano2 - valor_ano1,
             delta_pct_pct = if_else(valor_ano1 != 0,
                                     (valor_ano2 - valor_ano1) / valor_ano1 * 100,
                                     NA_real_)) %>%
      group_by(recorte, grupo, metrica) %>% slice(1) %>% ungroup()
  } else {
    frag_met_long <- read_excel(arq_frag, sheet = "Metricas") %>%
      mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES))
    anos_det <- sort(unique(as.integer(frag_met_long$ano)))
    ANO1_FRAG <- anos_det[1]; ANO2_FRAG <- anos_det[length(anos_det)]
    
    GRUPO_F1 <- .detectar_grupo_disponivel(frag_met_long, GRUPO_F1_PREFERIDO)
    
    metricas <- frag_met_long %>%
      select(recorte, grupo, metrica, ano, valor) %>%
      mutate(ano = as.character(as.integer(ano)), valor = as.numeric(valor)) %>%
      group_by(recorte, grupo, metrica, ano) %>%
      summarise(valor = first(valor), .groups = "drop") %>%
      pivot_wider(names_from = ano, values_from = valor) %>%
      rename_with(~ "valor_ano1", matches(paste0("^", ANO1_FRAG, "$"))) %>%
      rename_with(~ "valor_ano2", matches(paste0("^", ANO2_FRAG, "$"))) %>%
      mutate(recorte = as.character(recorte),
             delta_abs     = valor_ano2 - valor_ano1,
             delta_pct     = (valor_ano2 - valor_ano1) / valor_ano1,
             delta_pct_pct = delta_pct * 100)
  }
  frag_paisagem <- read_excel(arq_frag, sheet = "Paisagem") %>%
    mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES))
  
  mesh_lsi <- frag_paisagem %>%
    select(any_of(c("recorte","metrica","unidade","ano","valor"))) %>%
    filter(metrica %in% c("MESH","LSI")) %>%
    select(recorte, metrica, ano, valor) %>%
    mutate(recorte = as.character(recorte),
           ano     = as.character(as.integer(ano)),
           valor   = as.numeric(valor)) %>%
    group_by(recorte, metrica, ano) %>%
    summarise(valor = first(valor), .groups = "drop") %>%
    pivot_wider(names_from = ano, values_from = valor) %>%
    rename_with(~ "valor_ano1", matches(paste0("^", ANO1_FRAG, "$"))) %>%
    rename_with(~ "valor_ano2", matches(paste0("^", ANO2_FRAG, "$"))) %>%
    mutate(valor_ano1 = as.numeric(valor_ano1), valor_ano2 = as.numeric(valor_ano2),
           delta_abs = valor_ano2 - valor_ano1,
           delta_pct_pct = (valor_ano2 - valor_ano1) / valor_ano1 * 100)
  
  if (TEM_DIST_PORTE) {
    frag_dist_frag <- read_excel(arq_frag, sheet = "Dist_Fragmentos") %>%
      mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES),
             across(c(n_fragmentos,area_ha,pct_n,pct_area), as.numeric),
             classe_tamanho = factor(classe_tamanho, levels = ORDEM_CLASSES_TAM),
             ano = factor(as.character(as.integer(ano))))
    frag_dist_nuc <- read_excel(arq_frag, sheet = "Dist_Nucleos") %>%
      mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES),
             across(c(n_fragmentos,area_ha,pct_n,pct_area), as.numeric),
             classe_tamanho = factor(classe_tamanho, levels = ORDEM_CLASSES_TAM),
             ano = factor(as.character(as.integer(ano))))
  }
  
  message("\nFragmentacao carregada. Anos detectados: ", ANO1_FRAG, " -> ", ANO2_FRAG)
  message("Recortes: ", paste(unique(as.character(metricas$recorte)), collapse = " | "))
  
  .rec_frag <- unique(as.character(metricas$recorte))
  .rec_frag <- .rec_frag[!is.na(.rec_frag)]
  message("\nRecortes no arquivo de FRAGMENTACAO: ", paste(.rec_frag, collapse=" | "))
  RECORTES_INT_FRAG <- .rec_frag
  
  # ---- F1 — 6 paineis: variacao % das metricas ----
  grafico_F1_deltas <- function(recortes, grupo_sel) {
    met_var <- metricas %>%
      filter(grupo == grupo_sel,
             metrica %in% c("NP","TCA","CORE_MN","ED","LPI"),
             as.character(recorte) %in% recortes) %>%
      mutate(recorte=as.character(recorte),
             delta_pct_pct=as.numeric(delta_pct_pct))
    
    met_mesh <- mesh_lsi %>%
      filter(metrica=="MESH", as.character(recorte) %in% recortes) %>%
      mutate(recorte=as.character(recorte)) %>%
      select(recorte, metrica, delta_pct_pct)
    
    # Índice numérico por recorte — usado no eixo X no lugar do nome
    # completo. Com muitos recortes (ex: 24 municípios da RMP), nomes
    # por extenso no eixo colidem e ficam ilegíveis. A legenda abaixo
    # do gráfico mapeia índice + cor -> nome completo.
    indices_recortes <- setNames(seq_along(recortes), recortes)
    
    df <- bind_rows(
      met_var  %>% select(recorte, metrica, delta_pct_pct),
      met_mesh
    ) %>%
      filter(!is.na(recorte)) %>%
      mutate(
        recorte   = factor(recorte, levels=recortes),
        indice    = indices_recortes[as.character(recorte)],
        cor       = coalesce(CORES_RECORTE[as.character(recorte)], "#888888"),
        metrica_label = recode(metrica,
                               "NP"      = "Delta NP - numero de fragmentos (%)",
                               "TCA"     = "Delta TCA - area nucleo total (%)",
                               "CORE_MN" = "Delta CORE MN - area nucleo media (%)",
                               "ED"      = "Delta ED - densidade de borda (%)",
                               "LPI"     = "Delta LPI - maior fragmento (%)",
                               "MESH"    = "Delta MESH - tamanho efetivo de malha (%)"
        ),
        metrica_label = factor(metrica_label, levels=c(
          "Delta NP - numero de fragmentos (%)",
          "Delta TCA - area nucleo total (%)",
          "Delta CORE MN - area nucleo media (%)",
          "Delta ED - densidade de borda (%)",
          "Delta LPI - maior fragmento (%)",
          "Delta MESH - tamanho efetivo de malha (%)"
        ))
      )
    
    # Legenda: "01 · Nome do Recorte" — cor mapeada por recorte, não
    # mais scale_fill_identity() (que não gera legenda nenhuma)
    rotulos_legenda <- setNames(
      .quebrar(paste0(sprintf("%02d", seq_along(recortes)), " \u00b7 ", recortes),
               LARGURA_LEGENDA),
      recortes)
    n_rec        <- length(recortes)
    ncol_legenda <- min(6, max(2, ceiling(sqrt(n_rec))))
    
    ggplot(df, aes(x=factor(indice, levels=seq_along(recortes)),
                   y=delta_pct_pct, fill=recorte)) +
      geom_col(width=0.62, color="grey35", linewidth=0.2) +
      geom_hline(yintercept=0, linewidth=0.5, color="grey30") +
      geom_text(
        aes(label=paste0(if_else(delta_pct_pct>=0,"+",""),
                         number(delta_pct_pct,accuracy=0.1,decimal.mark=","),"%"),
            vjust=if_else(delta_pct_pct>=0,-0.4,1.3)),
        size=2.8, fontface="bold", color="grey15") +
      facet_wrap(~metrica_label, ncol=2, scales="free_y") +
      scale_fill_manual(values = CORES_RECORTE, breaks = recortes,
                        labels = rotulos_legenda, name = NULL) +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.18,0.22))) +
      guides(fill = guide_legend(ncol = ncol_legenda, byrow = FALSE)) +
      labs(title=paste0("Variacao das metricas de fragmentacao (",
                        ANO1_FRAG, "-", ANO2_FRAG, ") | ", grupo_sel),
           subtitle=paste0("Delta% = (valor final - valor inicial) / valor inicial x 100 | ",
                           grupo_sel, "  |  Numeros do eixo = indice do recorte (ver legenda)"),
           x=NULL, y=NULL, caption=CAPTION_PADRAO) +
      tema_amp +
      theme(strip.text=element_text(face="bold",size=10,hjust=0),
            axis.text.x=element_text(size=8),
            axis.text.y=element_text(size=8),
            panel.grid.major.x=element_blank(),
            panel.grid.major.y=element_line(color="grey90",linewidth=0.4),
            legend.position="bottom",
            legend.text=element_text(size=7.5, lineheight=0.9),
            legend.key.size=unit(0.35,"cm"),
            plot.margin=margin(14,16,10,14))
  }
  
  # ---- F2 — Espelho: distribuicao por classe de tamanho ----
  grafico_F2_espelho <- function(recorte_nome, tipo="fragmentos", grupo_sel=NULL) {
    aba        <- if (tipo=="fragmentos") frag_dist_frag else frag_dist_nuc
    tipo_label <- if (tipo=="fragmentos") "Fragmentos" else "Nucleos"
    
    df <- aba %>%
      filter(if ("grupo" %in% names(.) && !is.null(grupo_sel)) grupo==grupo_sel else TRUE,
             recorte == recorte_nome) %>%
      mutate(
        pct_n    = pct_n    * 100,
        pct_area = pct_area * 100,
        label_combo = paste0(
          formatC(as.integer(n_fragmentos), format="d", big.mark=".", decimal.mark=","),
          "\n",
          number(pct_n, accuracy=0.1, decimal.mark=","), "%"
        ),
        label_pct_area = paste0(number(pct_area, accuracy=0.1, decimal.mark=","), "%")
      )
    
    anos_niveis <- levels(df$ano)
    cores_ano <- setNames(c(COR_1985, COR_2024)[seq_along(anos_niveis)], anos_niveis)
    borda_ano <- setNames(c("#0A5540", "#0F6E56")[seq_along(anos_niveis)], anos_niveis)
    
    p_top <- ggplot(df, aes(x=classe_tamanho, y=pct_n, fill=ano, color=ano)) +
      geom_col(position=position_dodge(width=0.75), width=0.65, linewidth=0.3) +
      geom_label(aes(label=label_combo, group=ano),
                 position=position_dodge(width=0.75),
                 vjust=-0.15, size=2.6, fontface="bold", lineheight=1.1,
                 linewidth=0.3, label.padding=unit(0.18,"lines"),
                 label.r=unit(0.12,"lines"), fill="white", color="#0A5540") +
      scale_fill_manual(values=cores_ano) +
      scale_color_manual(values=borda_ano, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0,0.45))) +
      labs(x=NULL, y="Participacao no num total (%)", fill=NULL) +
      tema_amp +
      theme(axis.text.x=element_blank(), axis.ticks.x=element_blank(),
            axis.text.y=element_text(size=10), axis.title.y=element_text(size=10),
            panel.grid.major.x=element_blank(), legend.position="none",
            plot.margin=margin(10,14,4,14))
    
    p_bot <- ggplot(df, aes(x=classe_tamanho, y=pct_area, fill=ano, color=ano)) +
      geom_col(position=position_dodge(width=0.75), width=0.65, linewidth=0.3) +
      geom_text(aes(label=label_pct_area, group=ano),
                position=position_dodge(width=0.75),
                vjust=1.4, size=2.8, fontface="bold", color="grey20") +
      scale_fill_manual(values=cores_ano, labels=anos_niveis,
                        guide=guide_legend(title=NULL,
                                           override.aes=list(color=unname(borda_ano)),
                                           label.position="right")) +
      scale_color_manual(values=borda_ano, guide="none") +
      scale_y_continuous(trans="reverse",
                         labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.28,0))) +
      labs(x="Classe de tamanho", y="Participacao na area total (%)", fill=NULL) +
      tema_amp +
      theme(axis.text.x=element_text(angle=35,hjust=1,size=10),
            axis.text.y=element_text(size=10), axis.title.y=element_text(size=10),
            panel.grid.major.x=element_blank(), legend.position="bottom",
            legend.key.size=unit(0.55,"cm"), legend.text=element_text(size=11,face="bold"),
            plot.margin=margin(4,14,10,14))
    
    sep <- ggplot() + theme_void() +
      theme(plot.background=element_rect(fill="grey75",color=NA),
            plot.margin=margin(0,0,0,0))
    
    (p_top / sep / p_bot) +
      plot_layout(heights=c(10,0.05,10)) +
      plot_annotation(
        title  = .quebrar(paste("Distribuicao por classe de tamanho -", tipo_label,
                                if (!is.null(grupo_sel)) paste("|", grupo_sel) else "",
                                "|", recorte_nome)),
        caption= paste0("Caixa verde = num de ", tolower(tipo_label),
                        " por classe (resultado global) | ", CAPTION_PADRAO),
        theme  = theme(plot.title=element_text(face="bold",size=14,margin=margin(b=8),
                                               lineheight=1.05),
                       plot.caption=element_text(color="grey55",size=8,hjust=1,
                                                 margin=margin(t=6)))
      )
  }
}

# ============================================================
#  9.5. BLOCO — COMPOSIÇÃO DE COBERTURA  (família 4)
#       Gráficos de rosca (donut) — equivalente mais legível à
#       pizza tradicional, mantendo os mesmos padrões de cor
#       (paleta oficial MapBiomas), texto e legenda já usados no
#       restante do script. O centro de cada rosca traz a área
#       total do recorte no ano — a "centralidade" do gráfico.
# ============================================================

if (GERAR_RELATORIO) {
  
  abas_rel <- excel_sheets(arq_rel)
  aba_cob_rel <- abas_rel[grepl("obertura", abas_rel, ignore.case = TRUE)][1]
  
  cob_rel <- read_excel(arq_rel, sheet = aba_cob_rel) %>%
    mutate(unidade_analise = padronizar(unidade_analise),
           ano = as.character(as.integer(ano)))
  
  message("\nRelatório de Cobertura: ", nrow(cob_rel), " linhas")
  message("Anos detectados: ", paste(sort(unique(cob_rel$ano)), collapse = " | "))
  message("Unidades: ", paste(unique(cob_rel$unidade_analise), collapse = " | "))
  
  # Agrega o detalhe por código original para cada nível hierárquico —
  # o arquivo já traz cod_n1..cod_n4/classe_n1..classe_n4 por linha
  # (nível mais fino disponível no pixel); somamos por nível para
  # obter a composição em N1 (poucas classes, mais legível em pizza)
  # e em N2 (mais detalhe).
  .agregar_pizza <- function(df, cod_col, classe_col) {
    df %>%
      filter(!is.na(.data[[cod_col]])) %>%
      group_by(unidade_analise, ano,
               cod = .data[[cod_col]], classe = .data[[classe_col]]) %>%
      summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
      group_by(unidade_analise, ano) %>%
      mutate(pct = area_ha / sum(area_ha) * 100) %>%
      ungroup()
  }
  
  pizza_n1 <- .agregar_pizza(cob_rel, "cod_n1", "classe_n1")
  pizza_n2 <- .agregar_pizza(cob_rel, "cod_n2", "classe_n2")
  pizza_n3 <- if (all(c("cod_n3","classe_n3") %in% names(cob_rel)))
    .agregar_pizza(cob_rel, "cod_n3", "classe_n3") else NULL
  pizza_n4 <- if (all(c("cod_n4","classe_n4") %in% names(cob_rel)))
    .agregar_pizza(cob_rel, "cod_n4", "classe_n4") else NULL
  if (!is.null(pizza_n3)) message("  -> Nivel 3 disponivel (", nrow(pizza_n3), " linhas)")
  if (!is.null(pizza_n4)) message("  -> Nivel 4 disponivel (", nrow(pizza_n4), " linhas)")
  
  # ---- P1 — Rosca de composição, um painel por ano (facetado) ----
  # Fatias pequenas (< LIMIAR_CALLOUT %) recebem uma linha/seta puxando
  # o rótulo para FORA do anel, em vez de tentar escrever o percentual
  # dentro de um espaço minúsculo (ilegível de qualquer cor de texto).
  # Fatias grandes continuam com o rótulo centralizado dentro da fatia,
  # com contraste automático de texto (claro/escuro conforme a cor de
  # fundo daquela fatia).
  LIMIAR_CALLOUT <- 4
  
  grafico_P1_pizza <- function(dados_nivel, unidade_nome, nivel_label) {
    df <- dados_nivel %>%
      filter(unidade_analise == unidade_nome) %>%
      mutate(cod_str   = as.character(cod),
             cor       = coalesce(CORES_MB[cod_str], "#888888"),
             cor_texto = .cor_texto_contraste(cor)) %>%
      arrange(ano, desc(area_ha))
    
    # Soma as fatias < 1% (por ano) numa unica classe
    ROTULO_OUTROS <- "Soma de outros valores inferiores a 1%"
    df <- df %>%
      mutate(classe = if_else(pct < 1, ROTULO_OUTROS, as.character(classe)),
             cor    = if_else(pct < 1, "#B0B0B0", cor)) %>%
      group_by(ano, classe, cor) %>%
      summarise(area_ha = sum(area_ha, na.rm = TRUE),
                pct     = sum(pct,     na.rm = TRUE), .groups = "drop") %>%
      mutate(cor_texto = .cor_texto_contraste(cor))
    
    # Ordem das classes por área total (maior -> menor), consistente
    # entre os anos para a legenda nao "embaralhar" a cada faceta
    ordem_classes <- df %>%
      group_by(classe) %>% summarise(tot = sum(area_ha), .groups="drop") %>%
      arrange(desc(tot)) %>% pull(classe)
    df <- df %>% mutate(classe = factor(classe, levels = ordem_classes))
    if (ROTULO_OUTROS %in% ordem_classes)
      df <- df %>% mutate(classe = fct_relevel(classe, ROTULO_OUTROS, after = Inf))
    
    cores_map <- df %>% distinct(classe, cor) %>%
      { setNames(.$cor, as.character(.$classe)) }
    
    # Posição vertical (ângulo) real de cada fatia dentro do empilhamento
    # do geom_col — replica o algoritmo interno do ggplot2 (confirmado
    # empiricamente): dentro de cada grupo empilhado, o primeiro nível
    # do fator fica no TOPO da pilha, não na base. A fórmula abaixo
    # (soma acumulada de trás para frente) reproduz exatamente o ymin/
    # ymax que o geom_col calcularia, permitindo posicionar os rótulos
    # — inclusive os puxados para fora — no ângulo correto da fatia.
    df <- df %>%
      group_by(ano) %>%
      arrange(classe) %>%
      mutate(ymax = rev(cumsum(rev(pct))),
             ymin = ymax - pct,
             ymid = (ymax + ymin) / 2) %>%
      ungroup()
    
    df_grande <- df %>% filter(pct >= LIMIAR_CALLOUT)
    
    df_pequena <- df %>%
      filter(pct < LIMIAR_CALLOUT) %>%
      group_by(ano) %>%
      arrange(ymid) %>%
      mutate(raio_extra = rep_len(c(0, 0.16, 0.32), n())) %>%
      ungroup() %>%
      mutate(
        x_interna = 2.5,
        x_externa = 2.62 + raio_extra,
        x_rotulo  = 2.7  + raio_extra,
        label_pct = paste0(number(pct, accuracy=0.1, decimal.mark=","), "%")
      )
    
    tem_pequenas <- nrow(df_pequena) > 0
    x_lim_max <- if (tem_pequenas) max(df_pequena$x_rotulo) + 0.35 else 2.5
    
    # Rótulo central de cada rosca — área total do recorte naquele ano
    df_central <- df %>%
      group_by(ano) %>%
      summarise(total_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
      mutate(label_central = paste0(
        number(total_ha, big.mark=".", decimal.mark=",", accuracy=1), "\nha  |  ", ano
      ))
    
    p <- ggplot(df, aes(x = 2, y = pct, fill = classe)) +
      geom_col(color = "white", linewidth = 0.6, width = 1) +
      coord_polar(theta = "y") +
      xlim(0.4, x_lim_max) +
      # Rótulo dentro da fatia — só para fatias >= LIMIAR_CALLOUT%
      geom_text(
        data = df_grande,
        aes(x = 2, y = ymid,
            label = paste0(number(pct, accuracy=0.1, decimal.mark=","), "%"),
            color = cor_texto),
        size = 3.1, fontface = "bold") +
      scale_color_identity()
    
    # Seta + rótulo externo — só para fatias pequenas (se houver)
    if (tem_pequenas) {
      p <- p +
        geom_segment(
          data = df_pequena,
          aes(x = x_interna, xend = x_externa, y = ymid, yend = ymid,
              color = cor),
          linewidth = 0.7,
          arrow = arrow(length = unit(0.08, "cm"), type = "closed")) +
        geom_text(
          data = df_pequena,
          aes(x = x_rotulo, y = ymid, label = label_pct),
          size = 2.7, fontface = "bold", color = "grey20")
    }
    
    p +
      geom_text(data = df_central, aes(x = 0.4, y = 0, label = label_central),
                inherit.aes = FALSE, size = 3.6, fontface = "bold", color = "grey20",
                lineheight = 0.95) +
      facet_wrap(~ano, ncol = length(unique(df$ano))) +
      scale_fill_manual(values = cores_map, name = NULL,
                        labels = function(x) str_wrap(x, width = 24)) +
      labs(title = .quebrar(paste0("Composição de cobertura da terra | ", unidade_nome)),
           subtitle = paste0(nivel_label, "  |  Paleta MapBiomas Coleção 10",
                             if (tem_pequenas) paste0("  |  Setas indicam classes < ", LIMIAR_CALLOUT, "%") else ""),
           caption = CAPTION_PADRAO) +
      theme_void(base_size = FONTE_BASE) +
      theme(legend.position   = "right",
            legend.text       = element_text(size = 9),
            strip.text        = element_text(face = "bold", size = FONTE_BASE),
            plot.title        = element_text(face="bold", size=FONTE_BASE+3, hjust=0,
                                             margin=margin(b=4), lineheight=1.05),
            plot.subtitle     = element_text(color="grey45", size=FONTE_BASE-1, hjust=0,
                                             margin=margin(b=8)),
            plot.caption      = element_text(color="grey55", size=FONTE_BASE-3, hjust=1,
                                             margin=margin(t=6)),
            plot.margin       = margin(12,16,8,12))
  }
}

# ============================================================
#  10. EXECUCAO E EXPORTACAO
# ============================================================
message("\n=== Gerando graficos [AnP v1.1] ===\n")

if (GERAR_COBERTURA) {
  unidades      <- unique(as.character(cob$unidade_analise))
  unidades      <- unidades[!is.na(unidades) & nzchar(trimws(unidades))]
  unidades_alt  <- unique(as.character(alt$unidade_analise))
  unidades_alt  <- unidades_alt[!is.na(unidades_alt) & nzchar(trimws(unidades_alt))]
  
  message("[C2] Variacao de cobertura por recorte (individual)...")
  for (u in unidades) {
    slug <- .slug(u)
    salvar_grafico(paste0("C2_delta_cobertura_", slug),
                   grafico_C2_delta(u), w=9, h=7)
  }
  
  message("[C2A] Variacao de cobertura - integrado...")
  n_c2a    <- length(RECORTES_INT_COB)
  nc_c2a   <- if (n_c2a <= 2) 1L else if (n_c2a <= 9) 2L else if (n_c2a <= 20) 3L else 4L
  nr_c2a   <- ceiling(n_c2a / nc_c2a)
  h_c2a    <- min(49, max(7, nr_c2a * 4.5))
  w_c2a    <- c(10, 14, 19, 24)[nc_c2a]
  salvar_grafico("C2A_delta_cobertura_integrado",
                 grafico_C2A_integrado(RECORTES_INT_COB), w=w_c2a, h=h_c2a)
  
  message("[C4] Categorias de alteracao por recorte (individual)...")
  for (u in unidades_alt) {
    slug <- .slug(u)
    salvar_grafico(paste0("C4_categorias_", slug),
                   grafico_C4_individual(u), w=8, h=7)
  }
  
  message("[C4A] Grade de categorias - integrado...")
  nc_c4a   <- if (n_c2a <= 2) 1L else if (n_c2a <= 9) 2L else if (n_c2a <= 20) 3L else 4L
  nr_c4a   <- ceiling(n_c2a / nc_c4a)
  h_c4a    <- min(49, max(8, nr_c4a * 4.5))
  w_c4a    <- c(10, 14, 19, 24)[nc_c4a]
  salvar_grafico("C4A_categorias_grade",
                 grafico_C4A_grade(RECORTES_INT_COB), w=w_c4a, h=h_c4a)
}

if (GERAR_MATRIZ) {
  message("[M1] Heatmap da matriz de transicao (agrupado no Nivel 2)...")
  for (aba in ABAS_MAT) {
    blocos <- .ler_matriz(arq_mat, aba)
    if (length(blocos) == 0) {
      message("  [AVISO] Nao foi possivel ler a matriz na aba: ", aba)
      next
    }
    nome_mat <- .nome_unidade_matriz(arq_mat, aba)
    slug <- .slug(nome_mat)
    # Usa o bloco de AREA (ha) e agrega origem/destino ao Nivel 2 da
    # legenda MapBiomas. O bloco de % nao e somavel apos reagrupar, entao
    # o % da origem e RECALCULADO dentro de grafico_M1_heatmap a partir
    # do ha agregado.
    bloco_ha <- if ("ha" %in% names(blocos)) blocos[["ha"]] else blocos[[1]]
    df_n2 <- .agrega_matriz_n2(bloco_ha)
    df_n2 <- .agrupa_pequenas_matriz(df_n2, 0.01)
    n_classes <- length(unique(as.character(df_n2$classe_origem)))
    tam <- max(9, n_classes * 0.75)
    salvar_grafico(paste0("M1_matriz_ha_", slug),
                   grafico_M1_heatmap(df_n2, "ha", nome_mat),
                   w=tam+2, h=tam)
    salvar_grafico(paste0("M1_matriz_percentual_", slug),
                   grafico_M1_heatmap(df_n2, "percentual", nome_mat),
                   w=tam+2, h=tam)
  }
}

if (GERAR_FRAG) {
  # Grupos a plotar: todos os presentes nos dados, com Cobertura Natural e
  # Floresta priorizados. Antes o script fixava um unico grupo (Floresta);
  # agora gera F1/F2/F2b para cada grupo (ex.: Cobertura Natural) e para
  # todas as unidades espaciais (recortes) disponiveis.
  grupos_disp <- unique(as.character(metricas$grupo))
  grupos_disp <- grupos_disp[!is.na(grupos_disp)]
  .prio       <- c("Cobertura Natural", "Floresta", "Veg. Herbácea e Arbustiva")
  GRUPOS_PLOT <- c(intersect(.prio, grupos_disp), setdiff(grupos_disp, .prio))
  message("[F] Grupos de cobertura a plotar: ", paste(GRUPOS_PLOT, collapse = " | "))

  for (gp in GRUPOS_PLOT) {
    gslug <- .slug(gp)
    message("[F1] Metricas de fragmentacao — grupo: ", gp)
    salvar_grafico(paste0("F1_deltas_fragmentacao_", gslug),
                   grafico_F1_deltas(RECORTES_INT_FRAG, gp), w=13, h=10)

    if (TEM_DIST_PORTE) {
      recortes_frag <- unique(as.character(frag_dist_frag$recorte))
      recortes_frag <- recortes_frag[!is.na(recortes_frag)]
      recortes_nuc  <- unique(as.character(frag_dist_nuc$recorte))
      recortes_nuc  <- recortes_nuc[!is.na(recortes_nuc)]

      message("[F2] Espelho fragmentos — grupo: ", gp)
      for (r in recortes_frag) {
        slug <- .slug(r)
        salvar_grafico(paste0("F2_espelho_fragmentos_", gslug, "_", slug),
                       grafico_F2_espelho(r, tipo="fragmentos", grupo_sel=gp), w=10, h=9)
      }
      message("[F2b] Espelho nucleos — grupo: ", gp)
      for (r in recortes_nuc) {
        slug <- .slug(r)
        salvar_grafico(paste0("F2b_espelho_nucleos_", gslug, "_", slug),
                       grafico_F2_espelho(r, tipo="nucleos", grupo_sel=gp), w=10, h=9)
      }
    }
  }
}

if (GERAR_RELATORIO) {
  unidades_rel <- unique(as.character(cob_rel$unidade_analise))
  unidades_rel <- unidades_rel[!is.na(unidades_rel) & nzchar(trimws(unidades_rel))]
  n_anos_rel   <- length(unique(cob_rel$ano))
  largura_p1   <- max(9, n_anos_rel * 5.5)
  
  message("[P1] Composicao de cobertura (rosca) - Nivel 1...")
  for (u in unidades_rel) {
    slug <- .slug(u)
    salvar_grafico(paste0("P1_pizza_N1_", slug),
                   grafico_P1_pizza(pizza_n1, u, "Nível 1 — grandes grupos"),
                   w = largura_p1, h = 7)
  }
  
  message("[P1b] Composicao de cobertura (rosca) - Nivel 2...")
  for (u in unidades_rel) {
    slug <- .slug(u)
    salvar_grafico(paste0("P1b_pizza_N2_", slug),
                   grafico_P1_pizza(pizza_n2, u, "Nível 2 — classes detalhadas"),
                   w = largura_p1 + 2, h = 7.5)
  }
  
  if (!is.null(pizza_n3)) {
    message("[P1c] Composicao de cobertura (rosca) - Nivel 3...")
    for (u in unidades_rel) {
      slug <- .slug(u)
      salvar_grafico(paste0("P1c_pizza_N3_", slug),
                     grafico_P1_pizza(pizza_n3, u, "Nível 3 — classes intermediárias"),
                     w = largura_p1 + 3, h = 8)
    }
  }
  
  if (!is.null(pizza_n4)) {
    message("[P1d] Composicao de cobertura (rosca) - Nivel 4...")
    for (u in unidades_rel) {
      slug <- .slug(u)
      salvar_grafico(paste0("P1d_pizza_N4_", slug),
                     grafico_P1_pizza(pizza_n4, u, "Nível 4 — classes detalhadas"),
                     w = largura_p1 + 4, h = 9)
    }
  }
}

# ============================================================
#  10b. FAMILIA 5 — ANALISES MULTIVARIADAS E FLUXOS
#        B: PCA | C: Heatmap | D: Dispersao | E: Sankey | F: Chord
#        Requer dados de cob e alt (familia 1 ja carregada)
# ============================================================

if (GERAR_MULTIVAR) {
  
  if (!exists("cob") || !exists("alt")) {
    message("[AVISO] Dados de cobertura nao encontrados. Familia 5 ignorada.")
  } else {
    
    # Mapa nome da classe -> cor MapBiomas (para Sankey e Chord)
    .nome_cor_mb <- cobertura %>%
      filter(cod_classe != 255) %>%
      distinct(classe, cod_classe) %>%
      mutate(cor = coalesce(CORES_MB[as.character(cod_classe)], "#888888")) %>%
      { setNames(.$cor, .$classe) }
    .nome_cor_mb["Outros usos"] <- "#aaaaaa"
    
    # Matriz wide: linhas = unidade x ano, colunas = classes
    .mat_wide <- cob %>%
      select(unidade_analise, ano, classe_plot, pct) %>%
      pivot_wider(names_from = classe_plot, values_from = pct, values_fill = 0)
    
    # ---- B: PCA ----
    .grafico_pca_mv <- function() {
      mat     <- .mat_wide %>% arrange(unidade_analise, ano)
      X       <- mat %>% select(-unidade_analise, -ano)
      rotulos <- mat %>% select(unidade_analise, ano)
      
      if (ncol(X) < 2 || nrow(X) < 3) {
        message("  [B] PCA: dados insuficientes.")
        return(NULL)
      }
      
      pca     <- prcomp(X, scale. = TRUE, center = TRUE)
      scores  <- bind_cols(rotulos, as.data.frame(pca$x[, 1:2]))
      var_exp <- summary(pca)$importance[2, 1:2] * 100
      
      loadings <- as.data.frame(pca$rotation[, 1:2])
      loadings$classe <- rownames(loadings)
      loadings <- loadings %>%
        mutate(contrib = PC1^2 + PC2^2) %>%
        slice_max(contrib, n = 6)
      
      escala <- max(abs(scores[, c("PC1","PC2")])) /
        max(abs(loadings[, c("PC1","PC2")])) * 0.7
      
      n_unid <- length(unique(scores$unidade_analise))
      pal    <- if (n_unid <= 12) "Paired" else "Set3"
      
      # Extrair identificador curto (ex: "I", "Ia", "II", "V") do nome da unidade
      # Padrão: sequência inicial de letras/algarismos romanos antes do " - " ou espaço
      .id_curto <- function(x) {
        # Numeral romano só conta se vier seguido de espaço, hífen ou fim
        # (evita "I" para "Itirapina", "V" para "Vinhedo").
        m <- regmatches(x, regexpr("^[IVXivx]+[ab]?(?=\\s|-|$)", x, perl=TRUE))
        if (length(m) == 0 || !nzchar(m)) substr(gsub("_"," ",x), 1, 4) else m
      }
      scores <- scores %>%
        mutate(id_curto = sapply(as.character(unidade_analise), .id_curto))
      
      # Legenda: id_curto → nome completo
      leg_pca <- scores %>%
        distinct(unidade_analise, id_curto) %>%
        mutate(unidade_analise = gsub("_"," ", as.character(unidade_analise))) %>%
        arrange(id_curto)
      leg_txt <- paste(
        paste0(leg_pca$id_curto, " = ", leg_pca$unidade_analise),
        collapse = "   |   "
      )
      
      cores_pca <- colorRampPalette(
        RColorBrewer::brewer.pal(min(n_unid, 12), pal)
      )(n_unid)
      nomes_pca <- sort(unique(as.character(scores$unidade_analise)))
      cor_pca   <- setNames(cores_pca, nomes_pca)
      
      # Trajetórias: setas de ano_ini → ano_fim por unidade
      anos_pca <- sort(unique(as.character(scores$ano)))
      a_ini_pca <- anos_pca[1]; a_fim_pca <- anos_pca[length(anos_pca)]
      
      df_seta_pca <- scores %>%
        filter(ano %in% c(a_ini_pca, a_fim_pca)) %>%
        select(unidade_analise, id_curto, ano, PC1, PC2) %>%
        pivot_wider(names_from = ano, values_from = c(PC1, PC2), names_sep = "_") %>%
        rename_with(~gsub(paste0("_", a_ini_pca), "_ini", .x)) %>%
        rename_with(~gsub(paste0("_", a_fim_pca), "_fim", .x))
      
      df_pca_ini <- scores %>% filter(ano == a_ini_pca)
      df_pca_fim <- scores %>% filter(ano == a_fim_pca)
      
      ggplot() +
        geom_hline(yintercept=0, linetype="dashed", color="grey82", linewidth=0.4) +
        geom_vline(xintercept=0, linetype="dashed", color="grey82", linewidth=0.4) +
        # Setas de classe (loadings) — cinza claro
        geom_segment(data = loadings,
                     aes(x=0, y=0, xend=PC1*escala, yend=PC2*escala),
                     inherit.aes = FALSE,
                     arrow=arrow(length=unit(0.18,"cm"), type="closed"),
                     color="grey65", linewidth=0.45) +
        ggrepel::geom_text_repel(data=loadings,
                                 aes(x=PC1*escala*1.14, y=PC2*escala*1.14, label=classe),
                                 inherit.aes=FALSE,
                                 size=2.7, color="grey40", fontface="italic", max.overlaps=20) +
        # Setas de trajetória por unidade
        geom_segment(data=df_seta_pca,
                     aes(x=PC1_ini, y=PC2_ini, xend=PC1_fim, yend=PC2_fim,
                         color=as.character(unidade_analise)),
                     arrow=arrow(length=unit(0.20,"cm"), type="closed"),
                     linewidth=0.95, alpha=0.65, show.legend=FALSE) +
        # Ponto 1985 — círculo aberto/pastel
        geom_point(data=df_pca_ini,
                   aes(x=PC1, y=PC2, color=as.character(unidade_analise)),
                   shape=21, size=4.2, stroke=1.3,
                   fill=adjustcolor(cor_pca[as.character(df_pca_ini$unidade_analise)],
                                    alpha.f=0.22),
                   show.legend=FALSE) +
        # Ponto 2024 — círculo cheio
        geom_point(data=df_pca_fim,
                   aes(x=PC1, y=PC2, color=as.character(unidade_analise)),
                   shape=19, size=4.2, show.legend=TRUE) +
        # Rótulos: id_curto
        geom_text(data=df_pca_ini,
                  aes(x=PC1, y=PC2, label=id_curto,
                      color=as.character(unidade_analise)),
                  size=2.8, fontface="bold", vjust=2.5, show.legend=FALSE) +
        geom_text(data=df_pca_fim,
                  aes(x=PC1, y=PC2, label=id_curto,
                      color=as.character(unidade_analise)),
                  size=2.8, fontface="bold", vjust=-1.8, show.legend=FALSE) +
        scale_color_manual(values=cor_pca, name=NULL,
                           labels=setNames(.quebrar(leg_pca$unidade_analise, LARGURA_LEGENDA),
                                           leg_pca$unidade_analise)) +
        guides(color=guide_legend(nrow=ceiling(n_unid/3),
                                  override.aes=list(shape=19, size=4))) +
        labs(
          title    = str_wrap("PCA — Trajetória do Perfil de Cobertura da Terra (1985 → 2024)",
                              width=75),
          subtitle = paste0("PC1: ", round(var_exp[1],1), "%  |  PC2: ",
                            round(var_exp[2],1), "% da variância  |  ",
                            "Setas cinza = classes determinantes  |  ",
                            "○ = ", a_ini_pca, " (pastel)  |  ● = ", a_fim_pca, " (cheio)"),
          x=paste0("PC1 (", round(var_exp[1],1), "%)"),
          y=paste0("PC2 (", round(var_exp[2],1), "%)"),
          caption=paste0(str_wrap(leg_txt, width=110), "
", CAPTION_PADRAO)
        ) +
        tema_amp +
        theme(panel.grid      = element_line(color="grey93"),
              legend.position = "bottom",
              legend.text     = element_text(size=8.5, lineheight=0.9),
              legend.key.size = unit(0.8,"cm"),
              plot.caption    = element_text(size=7.5, color="grey35",
                                             hjust=0, lineheight=1.3))
    }
    
    # ---- C: Heatmap ----
    .grafico_heatmap_mv <- function() {
      # Agrega cobertura ao Nivel 2, soma classes < 1% em "Outros usos"
      df_base_hm <- cobertura %>%
        filter(cod_classe != 255) %>%
        mutate(classe_n2       = .cod_para_n2nome(cod_classe),
               pct             = percentual * 100,
               unidade_analise = gsub("_"," ", as.character(unidade_analise))) %>%
        group_by(unidade_analise, ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      
      # Eliminar classes < 1% em TODAS as unidades/anos → "Outros usos"
      .pequenas_hm <- df_base_hm %>%
        group_by(classe_n2) %>%
        summarise(mx = max(pct, na.rm = TRUE), .groups = "drop") %>%
        filter(mx < 1) %>% pull(classe_n2)
      df_base_hm <- df_base_hm %>%
        mutate(classe_n2 = if_else(classe_n2 %in% .pequenas_hm,
                                   "Outros usos", classe_n2)) %>%
        group_by(unidade_analise, ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      
      # Anos disponíveis: pegar os dois extremos
      anos_hm <- sort(unique(as.numeric(df_base_hm$ano)))
      if (length(anos_hm) < 2) {
        message("  [C] Heatmap delta: necessario >= 2 anos.")
        return(NULL)
      }
      ano_ini_hm <- as.character(min(anos_hm))
      ano_fim_hm <- as.character(max(anos_hm))
      
      # Calcular delta absoluto (pp) e variação relativa (%)
      # por unidade × classe, ignorando "Outros usos" no rótulo relativo
      # values_fill = NA: sem fill automático → apenas (unidade,classe) que existem
      # em pelo menos um dos anos ficam no dataframe; ausentes = sem tile
      df_delta <- df_base_hm %>%
        filter(ano %in% c(ano_ini_hm, ano_fim_hm)) %>%
        pivot_wider(names_from = ano, values_from = pct,
                    names_prefix = "pct_") %>%          # sem values_fill → NA explícito
        rename(pct_ini = paste0("pct_", ano_ini_hm),
               pct_fim = paste0("pct_", ano_fim_hm)) %>%
        mutate(
          # Tratar NA como 0 para o cálculo (classe ausente = 0%)
          pct_ini_z = coalesce(pct_ini, 0),
          pct_fim_z = coalesce(pct_fim, 0),
          delta_pp  = pct_fim_z - pct_ini_z,
          # Célula branca se AMBOS os anos têm NA (classe nunca existiu na unidade)
          delta_pp_plot = if_else(is.na(pct_ini) & is.na(pct_fim),
                                  NA_real_, delta_pp),
          var_rel   = case_when(
            classe_n2 == "Outros usos"          ~ NA_real_,
            pct_ini_z < 1 & pct_fim_z < 1       ~ NA_real_,
            pct_ini_z == 0                       ~ NA_real_,
            TRUE ~ (pct_fim_z - pct_ini_z) / pct_ini_z * 100
          ),
          rotulo    = case_when(
            is.na(var_rel) ~ "",
            var_rel > 0    ~ paste0("+", number(var_rel, accuracy=0.1,
                                                decimal.mark=","), "%"),
            TRUE           ~ paste0(number(var_rel, accuracy=0.1,
                                           decimal.mark=","), "%")
          ),
          cor_texto = if_else(abs(delta_pp) > max(abs(delta_pp), na.rm=TRUE) * 0.60,
                              "white", "grey20")
        )
      
      # Remover combinações onde delta_pp_plot = NA (sem tile)
      # Ordenar classes por delta médio absoluto (mais alteradas primeiro)
      ordem_classe_hm <- df_delta %>%
        group_by(classe_n2) %>%
        summarise(m = mean(abs(delta_pp), na.rm = TRUE), .groups = "drop") %>%
        arrange(desc(m)) %>% pull(classe_n2)
      # Colocar "Outros usos" sempre no fim
      ordem_classe_hm <- c(setdiff(ordem_classe_hm, "Outros usos"), "Outros usos")
      
      # Ordenar unidades por delta total (que mais variou globalmente)
      ordem_unid_hm <- df_delta %>%
        group_by(unidade_analise) %>%
        summarise(m = sum(abs(delta_pp), na.rm = TRUE), .groups = "drop") %>%
        arrange(m) %>% pull(unidade_analise)
      
      df_delta <- df_delta %>%
        mutate(
          classe_n2       = factor(classe_n2, levels = ordem_classe_hm),
          unidade_analise = factor(unidade_analise, levels = ordem_unid_hm)
        )
      
      lim_delta <- max(abs(df_delta$delta_pp), na.rm = TRUE)
      
      # delta_pp_plot já calculado no pivot (NA onde ambos anos ausentes)
      
      ggplot(df_delta, aes(x = classe_n2, y = unidade_analise, fill = delta_pp_plot)) +
        geom_tile(color = "white", linewidth = 0.35) +
        geom_text(data = df_delta %>% filter(nzchar(rotulo)),
                  aes(label = rotulo, color = cor_texto),
                  size = 3.0, fontface = "bold") +
        scale_color_identity() +
        scale_fill_stepsn(
          colours = c("#7f0000","#c0392b","#e07b74","#f5d5d2",
                      "#d2eeda","#74c493","#2e7d32","#145a32"),
          breaks  = c(-10, -5, -2.5, 0, 2.5, 5, 10),
          limits  = c(-max(lim_delta, 10.01), max(lim_delta, 10.01)),
          na.value = "white",
          name    = paste0("\u0394 pp\n(", ano_ini_hm, "\u2192", ano_fim_hm, ")"),
          labels  = label_number(accuracy = 0.1, decimal.mark = ",", suffix = " pp"),
          guide   = guide_colorsteps(barheight = unit(6,"cm"),
                                     barwidth   = unit(0.5,"cm"),
                                     show.limits = TRUE)
        ) +
        labs(
          title    = str_wrap(paste0("Heatmap de Mudança — Delta de Cobertura da Terra por Unidade e Classe  (",
                                     ano_ini_hm, " → ", ano_fim_hm, ")"), width = 80),
          subtitle = paste0("Cor = delta absoluto (pontos percentuais)  |  ",
                            "Rótulo = variação relativa (%)  |  ",
                            "Vermelho = perda  |  Verde = ganho  |  ",
                            "Classes < 1% agrupadas em 'Outros usos'"),
          x = NULL, y = NULL,
          caption = CAPTION_PADRAO
        ) +
        # Wrap nos labels do eixo X para evitar corte
        scale_x_discrete(labels = function(x) str_wrap(x, width = 12)) +
        scale_y_discrete(labels = function(x) .quebrar(x, LARGURA_EIXO)) +
        theme_minimal(base_size = 11) +
        theme(
          plot.title      = element_text(face = "bold", size = 12, hjust = 0,
                                         lineheight = 1.1),
          plot.subtitle   = element_text(color = "grey50", size = 8.5, hjust = 0),
          plot.caption    = element_text(color = "grey55", size = 7, hjust = 1),
          axis.text.x     = element_text(angle = 35, hjust = 1, size = 9,
                                         lineheight = 0.9),
          axis.text.y     = element_text(size = 9.5, lineheight = 0.9),
          legend.position = "right",
          plot.margin     = margin(8, 12, 6, 10)
        )
    }
    
    # ---- D: Dispersão — Cobertura Natural × Antrópica ----
    # Eixo X: soma das coberturas naturais (N1: Floresta + Form. Natural não Florestal)
    # Eixo Y: soma das coberturas antrópicas (N1: Agropecuária + Área Não Vegetada)
    # Gráfico único com os dois anos diferenciados por cor; seta mostra trajetória
    
    .grafico_dispersao_mv <- function() {
      # Categorias: Natural (N1 Floresta + Form. Natural) vs Antrópico (Agropec. + Não Veg.)
      .n1_code <- function(cod) {
        dplyr::case_when(
          cod %in% c(1,2,3,4,5,6,49,10,11,12,32,29,50,13) ~ "Natural",
          cod %in% c(14,15,18,19,39,20,40,62,41,36,46,47,35,48,9,21,22,23,24,30,25) ~ "Antropico",
          TRUE ~ "Outro"
        )
      }
      
      df_disp <- cobertura %>%
        filter(cod_classe != 255) %>%
        mutate(cat_n1 = .n1_code(as.integer(cod_classe)),
               pct    = percentual * 100,
               unidade_analise = gsub("_"," ", as.character(unidade_analise)),
               ano    = as.character(round(as.numeric(ano)))) %>%
        filter(cat_n1 %in% c("Natural","Antropico")) %>%
        group_by(unidade_analise, ano, cat_n1) %>%
        summarise(pct = sum(pct, na.rm=TRUE), .groups="drop") %>%
        pivot_wider(names_from=cat_n1, values_from=pct, values_fill=0)
      
      if (!"Natural" %in% names(df_disp)) df_disp$Natural <- 0
      if (!"Antropico" %in% names(df_disp)) df_disp$Antropico <- 0
      
      anos_d  <- sort(unique(df_disp$ano))
      n_unid  <- length(unique(df_disp$unidade_analise))
      pal_base <- RColorBrewer::brewer.pal(min(max(3,n_unid), 12),
                                           if(n_unid<=10) "Paired" else "Set3")
      pal_cols  <- colorRampPalette(pal_base)(n_unid)
      nomes_u   <- sort(unique(df_disp$unidade_analise))
      cor_unid  <- setNames(pal_cols, nomes_u)
      # Versão pastel (1985): mesmas cores mas alpha 0.35
      cor_pastel <- setNames(
        adjustcolor(pal_cols, alpha.f = 0.35),
        nomes_u
      )
      
      # Identificador curto para o gráfico
      .id_curto_d <- function(x) {
        m <- regmatches(x, regexpr("^[IVXivx]+[ab]?(?=\\s|-|$)", x, perl=TRUE))
        if (length(m) == 0 || !nzchar(m)) substr(x, 1, 4) else m
      }
      df_disp <- df_disp %>%
        mutate(id_curto = sapply(as.character(unidade_analise), .id_curto_d))
      
      # Setas (ano_ini → ano_fim por unidade)
      a_ini_d <- anos_d[1]; a_fim_d <- anos_d[length(anos_d)]
      df_seta_d <- df_disp %>%
        filter(ano %in% c(a_ini_d, a_fim_d)) %>%
        select(unidade_analise, id_curto, ano, Natural, Antropico) %>%
        pivot_wider(names_from=ano, values_from=c(Natural,Antropico), names_sep="_") %>%
        rename_with(~gsub(paste0("_",a_ini_d),"_ini",.x)) %>%
        rename_with(~gsub(paste0("_",a_fim_d),"_fim",.x))
      
      df_1985 <- df_disp %>% filter(ano == a_ini_d)
      df_2024 <- df_disp %>% filter(ano == a_fim_d)
      
      # Legenda: id_curto → nome completo
      leg_disp <- df_disp %>%
        distinct(unidade_analise, id_curto) %>%
        arrange(id_curto)
      leg_txt_d <- paste(
        paste0(leg_disp$id_curto, " = ", leg_disp$unidade_analise),
        collapse = "   |   "
      )
      
      ggplot() +
        # Sem linha de referência diagonal (removida a pedido)
        # Setas de trajetória (cor por unidade, mesma cor do ponto 2024)
        geom_segment(data=df_seta_d,
                     aes(x=Natural_ini, y=Antropico_ini,
                         xend=Natural_fim, yend=Antropico_fim,
                         color=unidade_analise),
                     arrow=arrow(length=unit(0.20,"cm"), type="closed"),
                     linewidth=0.65, alpha=0.28, show.legend=FALSE) +
        # Pontos 1985 — círculo com preenchimento pastel (fill) e borda cor cheia
        geom_point(data=df_1985,
                   aes(x=Natural, y=Antropico, color=unidade_analise),
                   shape=21, size=4.5, stroke=1.4,
                   fill=adjustcolor(cor_unid[df_1985$unidade_analise], alpha.f=0.25),
                   show.legend=FALSE) +
        # Pontos 2024 — círculo cheio, cor plena
        geom_point(data=df_2024,
                   aes(x=Natural, y=Antropico, color=unidade_analise),
                   shape=19, size=4.5, show.legend=TRUE) +
        # Rótulo: id_curto em 1985 (abaixo) e 2024 (acima)
        geom_text(data=df_1985,
                  aes(x=Natural, y=Antropico, label=paste0(id_curto, "'", substr(a_ini_d, 3, 4)), color=unidade_analise),
                  size=2.8, fontface="bold", vjust=2.4, show.legend=FALSE) +
        geom_text(data=df_2024,
                  aes(x=Natural, y=Antropico, label=paste0(id_curto, "'", substr(a_fim_d, 3, 4)), color=unidade_analise),
                  size=2.8, fontface="bold", vjust=-1.6, show.legend=FALSE) +
        scale_color_manual(
          values = cor_unid,
          name   = NULL,
          labels = setNames(.quebrar(leg_disp$unidade_analise, LARGURA_LEGENDA),
                            leg_disp$unidade_analise)
        ) +
        guides(color = guide_legend(
          nrow = ceiling(n_unid/3),
          override.aes = list(shape=19, size=4)
        )) +
        scale_x_continuous(
          labels=label_number(accuracy=0.1, decimal.mark=",", suffix="%"),
          expand=expansion(mult=c(0.10,0.10))
        ) +
        scale_y_continuous(
          labels=label_number(accuracy=0.1, decimal.mark=",", suffix="%"),
          expand=expansion(mult=c(0.10,0.10))
        ) +
        labs(
          title    = str_wrap(paste0("Trajetória de Cobertura — Cobertura Natural × Antrópica  (",
                                     a_ini_d," → ",a_fim_d,")"), width=75),
          subtitle = paste0("Seta = trajetória por unidade (quanto mais clara, mais tênue a mudança)  |  ",
                            "○ = ", a_ini_d, " (pastel)   |   ● = ", a_fim_d, " (cheio)
",
                            "Natural: Floresta + Form. Natural não Florestal  |  ",
                            "Antrópico: Agropecuária + Área Não Vegetada"),
          x="Cobertura Natural (%)", y="Cobertura Antrópica (%)",
          caption=CAPTION_PADRAO
        ) +
        coord_equal() +
        tema_amp +
        theme(
          panel.grid      = element_line(color="grey93", linewidth=0.3),
          legend.position = "bottom",
          legend.text     = element_text(size=8.5, lineheight=0.9),
          legend.key.size = unit(0.8,"cm")
        )
    }
    
    # ---- E: Matriz de Bolhas de Transição (substituiu Sankey) ----
    # Origem (N2) × Destino (N2), tamanho da bolha = área (ha)
    # Vantagem: mostra TODOS os fluxos simultaneamente sem oclusão
    .grafico_sankey_mv <- function() {
      if (!exists("alt") || nrow(alt) == 0) {
        message("  [E] Matriz de bolhas: dados de transicao nao encontrados.")
        return(NULL)
      }
      
      # Usa o recorte com maior área total (Shape/geral)
      rec_geral <- alt %>%
        group_by(unidade_analise) %>%
        summarise(tot = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        slice_max(tot, n = 1) %>%
        pull(unidade_analise) %>% as.character()
      
      # Agrega por Nivel 2 origem × Nivel 2 destino
      df_mb <- alt %>%
        filter(as.character(unidade_analise) == rec_geral) %>%
        mutate(orig_n2 = .cod_para_n2nome(cod_orig),
               dest_n2 = .cod_para_n2nome(cod_dest)) %>%
        group_by(orig_n2, dest_n2) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        filter(!is.na(orig_n2), !is.na(dest_n2), area_ha > 0)
      
      if (nrow(df_mb) == 0) { message("  [E] Matriz bolhas: sem dados."); return(NULL) }
      
      # Limiar mínimo configurável: ignora transições < 0.1% da área total
      area_total_mb <- sum(df_mb$area_ha)
      LIMIAR_BOLHA  <- area_total_mb * 0.001   # 0.1% da área total
      df_mb <- df_mb %>% filter(area_ha >= LIMIAR_BOLHA)
      
      # Agregar classes < 1% (em relação ao total) em "Outros usos"
      .area_classe <- df_mb %>%
        group_by(orig_n2) %>% summarise(tot = sum(area_ha), .groups = "drop") %>%
        mutate(pct = tot / area_total_mb * 100)
      .pequenas_mb <- .area_classe %>% filter(pct < 1) %>% pull(orig_n2)
      df_mb <- df_mb %>%
        mutate(
          orig_n2 = if_else(orig_n2 %in% .pequenas_mb, "Outros usos", orig_n2),
          dest_n2 = if_else(dest_n2 %in% .pequenas_mb, "Outros usos", dest_n2)
        ) %>%
        group_by(orig_n2, dest_n2) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop")
      
      # Classificar origem e destino como Natural ou Antrópico
      .nomes_naturais_mb <- c(
        "Formação Florestal","Formacao Florestal","Floresta",
        "Formação Savânica","Formacao Savanica","Savana",
        "Formação Campestre","Formacao Campestre","Campo",
        "Mangue","Apicum","Campo Alagado e Área Pantanosa",
        "Restinga Arbórea","Restinga Herbácea",
        "Restinga Arborea","Restinga Herbacea",
        "Afloramento Rochoso","Rio, Lago e Oceano","Corpo Dagua"
      )
      df_mb <- df_mb %>%
        mutate(
          nat_orig = orig_n2 %in% .nomes_naturais_mb,
          nat_dest = dest_n2 %in% .nomes_naturais_mb,
          tipo_eco = case_when(
            orig_n2 == dest_n2 &  nat_orig ~ "Manutenção Natural",
            orig_n2 == dest_n2 & !nat_orig ~ "Manutenção Antrópica",
            nat_orig & !nat_dest           ~ "Perda de Cobertura Natural",
            !nat_orig &  nat_dest           ~ "Recuperação de Cobertura",
            !nat_orig & !nat_dest           ~ "Conversão Antrópica",
            TRUE                            ~ "Outros"
          )
        )
      
      # Ordenar eixos: por área total de origem (decrescente)
      ordem_mb <- df_mb %>%
        group_by(orig_n2) %>%
        summarise(tot = sum(area_ha), .groups = "drop") %>%
        arrange(desc(tot)) %>% pull(orig_n2)
      ordem_mb <- c(setdiff(ordem_mb, "Outros usos"), "Outros usos")
      
      df_mb <- df_mb %>%
        mutate(
          orig_n2 = factor(orig_n2, levels = rev(ordem_mb)),
          dest_n2 = factor(dest_n2, levels = ordem_mb)
        )
      
      # Rótulo em ha formatado (só para bolhas maiores que 5% do máximo)
      lim_rot_mb <- max(df_mb$area_ha) * 0.05
      df_mb <- df_mb %>%
        mutate(rotulo_mb = if_else(
          area_ha >= lim_rot_mb,
          label_number(big.mark = ".", decimal.mark = ",", accuracy = 1)(area_ha),
          ""
        ))
      
      # Converter área em % da paisagem para o tamanho das bolhas
      df_mb <- df_mb %>%
        mutate(pct_paisagem = area_ha / area_total_mb * 100,
               rotulo_pct   = if_else(
                 pct_paisagem >= max(pct_paisagem) * 0.05,
                 paste0(number(pct_paisagem, accuracy = 0.1, decimal.mark = ","), "%"),
                 ""
               ))
      
      # Faixas de tamanho fixas (leitura visual consistente)
      df_mb <- df_mb %>%
        mutate(
          faixa_pct = cut(pct_paisagem,
                          breaks = c(0, 2.5, 5, 10, Inf),
                          labels = c("< 2,5%", "2,5–5%", "5–10%", "> 10%"),
                          right  = FALSE, include.lowest = TRUE),
          # Rótulo em ha acima da bolha — mostrar para todas as conversões + manutenções visíveis
          rot_ha    = label_number(big.mark = ".", decimal.mark = ",",
                                   accuracy = 1)(area_ha)
        )
      
      ggplot(df_mb, aes(x = dest_n2, y = orig_n2)) +
        # Sem fundo de cor na diagonal
        geom_point(aes(size = faixa_pct, color = tipo_eco), alpha = 0.88) +
        # Rótulo em ha acima da bolha — vjust dinâmico por tamanho de faixa
        geom_text(
          aes(label = rot_ha,
              vjust = case_when(
                faixa_pct == "> 10%"   ~ -4.2,
                faixa_pct == "5–10%"   ~ -2.8,
                faixa_pct == "2,5–5%"  ~ -1.9,
                TRUE                   ~ -1.2
              )),
          hjust = 0.5,
          size  = 2.4, fontface = "bold", color = "grey10"
        ) +
        scale_size_manual(
          values = c("< 2,5%" = 5, "2,5–5%" = 10, "5–10%" = 16, "> 10%" = 24),
          name   = "% da paisagem",
          breaks = c("< 2,5%", "2,5–5%", "5–10%", "> 10%"),
          drop   = FALSE
        ) +
        scale_color_manual(
          values = c(
            "Manutenção Natural"         = "#1F4E31",  # = Manteve-se em cobertura natural
            "Recuperação de Cobertura"   = "#519799",  # = Mudou de antrópico para natural
            "Manutenção Antrópica"       = "#C0392B",  # = Manteve-se em cobertura antrópica
            "Conversão Antrópica"        = "#7B241C",  # = Mudou entre coberturas antrópicas
            "Perda de Cobertura Natural" = "#E85C28",  # = Mudou de natural para antrópico
            "Outros"                     = "#888888"
          ),
          name   = "Tipo de transição",
          drop   = FALSE
        ) +
        labs(
          title    = .quebrar(paste0("Matriz de Transição de Cobertura — ", rec_geral,
                                     "  (", ANO_INI, " → ", ANO_FIM, ")"), LARGURA_TITULO),
          subtitle = paste0("Cada bolha = área (ha) transicionada  |  Diagonal (verde) = manutenção  |  ",
                            "Fora da diagonal (vermelho) = conversão
",
                            paste0("Classes < 1% da area total agrupadas em 'Outros usos'  |  "),
                            "Rótulo = ha (bolhas > 5% do máximo)"),
          x = paste0("Destino (", ANO_FIM, ")"),
          y = paste0("Origem (", ANO_INI, ")"),
          caption = CAPTION_PADRAO
        ) +
        coord_cartesian(clip = "off") +
        tema_amp +
        theme(
          axis.text.x     = element_text(angle = 45, hjust = 1, size = 7.5,
                                         lineheight = 0.85),
          axis.text.y     = element_text(size = 8.5),
          panel.grid      = element_line(color = "grey92", linewidth = 0.3),
          legend.position  = "bottom",
          legend.box       = "vertical",
          legend.spacing.y = unit(0.15, "cm"),
          legend.key.size  = unit(0.8, "cm"),
          legend.text      = element_text(size = 8.5),
          plot.title       = element_text(lineheight = 1.1),
          plot.margin      = margin(12, 16, 16, 12)
        )
    }
    
    # ---- G: Painel Delta + Manutenção/Alteração por unidade ----
    .grafico_painel_delta_alt <- function(unidade_nome) {
      if (!exists("alt") || nrow(alt) == 0) return(NULL)
      
      # -- Lado esquerdo: delta % por classe (barras horizontais divergentes)
      df_cob_u <- cobertura %>%
        filter(as.character(unidade_analise) == as.character(unidade_nome),
               cod_classe != 255) %>%
        mutate(classe_n2 = .cod_para_n2nome(cod_classe),
               pct       = percentual * 100,
               ano       = as.character(round(as.numeric(ano)))) %>%
        group_by(ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      
      anos_g <- sort(unique(as.numeric(df_cob_u$ano)))
      if (length(anos_g) < 2) return(NULL)
      a_ini <- as.character(min(anos_g))
      a_fim <- as.character(max(anos_g))
      
      # Eliminar classes < 1% em ambos os anos → "Outros usos"
      .peq_g <- df_cob_u %>%
        group_by(classe_n2) %>%
        summarise(mx = max(pct, na.rm = TRUE), .groups = "drop") %>%
        filter(mx < 1) %>% pull(classe_n2)
      df_cob_u <- df_cob_u %>%
        mutate(classe_n2 = if_else(classe_n2 %in% .peq_g, "Outros usos", classe_n2)) %>%
        group_by(ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      
      df_delta_g <- df_cob_u %>%
        filter(ano %in% c(a_ini, a_fim)) %>%
        pivot_wider(names_from = ano, values_from = pct,
                    names_prefix = "p", values_fill = 0) %>%
        rename(p_ini = paste0("p", a_ini), p_fim = paste0("p", a_fim)) %>%
        mutate(
          delta_pp = p_fim - p_ini,
          var_rel  = case_when(
            classe_n2 == "Outros usos" ~ NA_real_,
            p_ini < 1 & p_fim < 1     ~ NA_real_,
            p_ini == 0                ~ NA_real_,
            TRUE                      ~ (p_fim - p_ini) / p_ini * 100
          ),
          sinal    = if_else(delta_pp >= 0, "Ganho", "Perda"),
          classe_n2 = fct_reorder(classe_n2, delta_pp)
        )
      
      p_esq <- ggplot(df_delta_g,
                      aes(x = delta_pp, y = classe_n2, fill = sinal)) +
        geom_col(width = 0.72, color = "grey40", linewidth = 0.15) +
        geom_vline(xintercept = 0, color = "grey30", linewidth = 0.5) +
        # Rótulo: variação relativa — geom_label com fundo branco
        geom_label(data = df_delta_g %>% filter(!is.na(var_rel)),
                   aes(label = paste0(if_else(var_rel > 0, "+", ""),
                                      number(var_rel, accuracy = 0.1,
                                             decimal.mark = ","), "%"),
                       x = delta_pp),
                   hjust = 0.5, vjust = 0.5,
                   size = 2.6, fontface = "bold", color = "grey15",
                   fill = alpha("white", 0.82),
                   linewidth = 0.3, label.padding = unit(0.06, "lines")) +
        scale_fill_manual(values = c("Ganho" = "#1a7a3c", "Perda" = "#c0392b"),
                          guide = "none") +
        scale_x_continuous(
          labels = label_number(accuracy = 0.1, decimal.mark = ",", suffix = " pp")
        ) +
        labs(title = "Delta de Cobertura",
             subtitle = paste0(a_ini, " → ", a_fim,
                               "  |  Rótulo = variação relativa (%)"),
             x = "Δ pontos percentuais", y = NULL) +
        theme_minimal(base_size = 10) +
        theme(plot.title    = element_text(face = "bold", size = 10, hjust = 0),
              plot.subtitle = element_text(size = 8, color = "grey50"),
              axis.text.y   = element_text(size = 8.5),
              panel.grid.major.y = element_blank())
      
      # -- Lado direito: manutenção × alteração por classe (barras 100%)
      df_alt_u <- alt %>%
        filter(as.character(unidade_analise) == as.character(unidade_nome)) %>%
        mutate(orig_n2 = .cod_para_n2nome(cod_orig),
               dest_n2 = .cod_para_n2nome(cod_dest),
               # Comparar pelo nome N2 (não pelo código bruto)
               # para classificar corretamente manutenção/alteração após agregação
               tipo    = if_else(orig_n2 == dest_n2,
                                 "Manutenção", "Alteração")) %>%
        group_by(orig_n2, tipo) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop")
      
      # Mesmas linhas e mesma ordem do painel esquerdo — cada barra da
      # direita fica alinhada à classe nomeada à esquerda. Classes que não
      # aparecem à esquerda (agrupadas lá em "Outros usos") vão para
      # "Outros usos" também aqui.
      ord_alt <- levels(df_delta_g$classe_n2)
      df_alt_u <- df_alt_u %>%
        mutate(orig_n2 = if_else(orig_n2 %in% ord_alt, orig_n2, "Outros usos")) %>%
        group_by(orig_n2, tipo) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop")
      if ("Outros usos" %in% df_alt_u$orig_n2 && !"Outros usos" %in% ord_alt)
        ord_alt <- c("Outros usos", ord_alt)
      
      # Posições calculadas explicitamente: Manutenção começa em 0 e
      # Alteração vem em seguida; o rótulo fica no centro de cada segmento.
      # (position_stack() num subconjunto filtrado desalinhava os rótulos.)
      df_alt_u <- df_alt_u %>%
        mutate(orig_n2 = factor(orig_n2, levels = ord_alt),
               tipo    = factor(tipo, levels = c("Manutenção", "Alteração"))) %>%
        arrange(orig_n2, tipo) %>%
        group_by(orig_n2) %>%
        mutate(pct_tipo = area_ha / sum(area_ha) * 100,
               x_fim    = cumsum(pct_tipo),
               x_ini    = x_fim - pct_tipo,
               x_meio   = (x_ini + x_fim) / 2) %>%
        ungroup() %>%
        mutate(y_num = as.integer(orig_n2))

      p_dir <- ggplot(df_alt_u) +
        geom_rect(aes(xmin = x_ini, xmax = x_fim,
                      ymin = y_num - 0.36, ymax = y_num + 0.36, fill = tipo),
                  color = "grey40", linewidth = 0.15) +
        geom_label(data = df_alt_u %>% filter(pct_tipo >= 7),
                   aes(x = x_meio, y = y_num,
                       label = paste0(number(pct_tipo, accuracy = 0.1,
                                             decimal.mark = ","), "%")),
                   size = 2.6, fontface = "bold", color = "grey15",
                   fill = alpha("white", 0.80),
                   linewidth = 0.3, label.padding = unit(0.06, "lines")) +
        scale_fill_manual(
          values = c("Manutenção" = "#1a7a3c", "Alteração" = "#c0392b"),
          name   = NULL, drop = FALSE
        ) +
        # Mesmos limites da escala discreta do painel esquerdo
        # (linhas 1..n com 0,6 de margem) — garante o alinhamento.
        scale_y_continuous(breaks = seq_along(levels(df_alt_u$orig_n2)),
                           labels = levels(df_alt_u$orig_n2),
                           limits = c(0.4, nlevels(df_alt_u$orig_n2) + 0.6),
                           expand = c(0, 0)) +
        scale_x_continuous(
          labels = label_number(accuracy = 1, decimal.mark = ",", suffix = "%"),
          breaks = c(0, 25, 50, 75, 100), expand = expansion(mult = c(0, 0.02))
        ) +
        coord_cartesian(xlim = c(0, 100)) +
        labs(title    = "Manutenção × Alteração",
             subtitle = "% da área original de cada classe",
             x = "% da área de origem", y = NULL) +
        theme_minimal(base_size = 10) +
        theme(plot.title    = element_text(face = "bold", size = 10, hjust = 0),
              plot.subtitle = element_text(size = 8, color = "grey50"),
              axis.text.y   = element_blank(),
              panel.grid.major.y = element_blank(),
              legend.position = "bottom",
              plot.margin   = margin(5.5, 5.5, 5.5, 18))
      
      p_esq <- p_esq + scale_y_discrete(limits = ord_alt)

      # guides = "collect": a legenda vai para o rodapé do conjunto, sem
      # encolher só o painel direito (o que desalinhava as linhas).
      (p_esq | p_dir) +
        plot_layout(widths = c(1.2, 1), guides = "collect") +
        plot_annotation(
          title    = .quebrar(paste0("Dinâmica de Cobertura — ",
                                     gsub("_"," ", unidade_nome)), LARGURA_TITULO),
          subtitle = paste0("Esq.: variação líquida por classe (pp)  |  ",
                            "Dir.: proporção mantida × convertida por classe  |  ",
                            ANO_INI, " → ", ANO_FIM),
          caption  = CAPTION_PADRAO,
          theme    = theme(
            plot.title    = element_text(face = "bold", size = 13, hjust = 0,
                                         lineheight = 1.1),
            plot.subtitle = element_text(color = "grey45", size = 9),
            plot.caption  = element_text(color = "grey55", size = 7, hjust = 1),
            plot.margin   = margin(10, 14, 8, 12),
            legend.position = "bottom"
          )
        )
    }
    
    # ---- E2: Sankey por unidade ----
    .grafico_sankey_unidade <- function(unidade_nome) {
      if (!exists("alt") || nrow(alt) == 0) return(NULL)
      df_su <- alt %>%
        filter(as.character(unidade_analise) == as.character(unidade_nome)) %>%
        mutate(orig_n2 = .cod_para_n2nome(cod_orig),
               dest_n2 = .cod_para_n2nome(cod_dest)) %>%
        group_by(orig_n2, dest_n2) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        filter(area_ha > 0, !is.na(orig_n2), !is.na(dest_n2))
      
      if (nrow(df_su) == 0) return(NULL)
      
      # Agregar classes < 1% da área total → "Outros usos"
      tot_su <- sum(df_su$area_ha)
      .peq_su <- df_su %>%
        group_by(orig_n2) %>% summarise(t = sum(area_ha), .groups="drop") %>%
        mutate(p = t/tot_su*100) %>% filter(p < 2) %>% pull(orig_n2)
      df_su <- df_su %>%
        mutate(orig_n2 = if_else(orig_n2 %in% .peq_su, "Outros usos", orig_n2),
               dest_n2 = if_else(dest_n2 %in% .peq_su, "Outros usos", dest_n2)) %>%
        group_by(orig_n2, dest_n2) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        filter(area_ha > 0)
      
      orig_all <- unique(df_su$orig_n2)
      # Usar .n2nome_para_cor: mapeamento N2 → cor MapBiomas oficial
      cores_su <- setNames(.n2nome_para_cor(orig_all), orig_all)
      cores_su["Outros usos"] <- "#aaaaaa"
      
      ggplot(df_su,
             aes(axis1 = orig_n2, axis2 = dest_n2, y = area_ha)) +
        ggalluvial::geom_alluvium(aes(fill = orig_n2), alpha = 0.78, width = 1/4) +
        ggalluvial::geom_stratum(width = 1/4, fill = "grey92",
                                 color = "grey55", linewidth = 0.3) +
        # Rótulo do stratum: nome da classe + % no respectivo ano
        geom_text(stat = "stratum",
                  aes(label = paste0(after_stat(stratum), "\n(",
                                     number(after_stat(prop)*100,
                                            accuracy=0.1, decimal.mark=","), "%)")),
                  size = 2.3, fontface = "bold", color = "grey20",
                  lineheight = 0.85) +
        scale_fill_manual(values = cores_su, guide = "none") +
        scale_x_discrete(
          limits = c(as.character(ANO_INI), as.character(ANO_FIM)),
          expand = expansion(add = 0.15)
        ) +
        scale_y_continuous(
          labels = label_number(big.mark = ".", decimal.mark = ",", suffix = " ha")
        ) +
        labs(
          title    = .quebrar(paste0("Fluxos de Transição — ",
                                     gsub("_"," ", unidade_nome)), min(65, LARGURA_TITULO)),
          subtitle = paste0("Origem (", ANO_INI, ") → Destino (", ANO_FIM,
                            ")  |  Espessura ∝ área (ha)  |  Classes < 1% em 'Outros usos'"),
          x = NULL, y = "Área (ha)", caption = CAPTION_PADRAO
        ) +
        tema_amp +
        theme(axis.text.x = element_text(face = "bold", size = 11),
              panel.grid  = element_blank())
    }
    
    # ---- H: Painel Delta + Sankey por unidade ----
    .grafico_painel_delta_sankey <- function(unidade_nome) {
      # Lado esquerdo: barras de delta (reutiliza lógica do painel G)
      df_cob_h <- cobertura %>%
        filter(as.character(unidade_analise) == as.character(unidade_nome),
               cod_classe != 255) %>%
        mutate(classe_n2 = .cod_para_n2nome(cod_classe),
               pct       = percentual * 100,
               ano       = as.character(round(as.numeric(ano)))) %>%
        group_by(ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      
      anos_h <- sort(unique(as.numeric(df_cob_h$ano)))
      if (length(anos_h) < 2) return(NULL)
      a_ini_h <- as.character(min(anos_h))
      a_fim_h <- as.character(max(anos_h))
      
      .peq_h <- df_cob_h %>%
        group_by(classe_n2) %>%
        summarise(mx = max(pct, na.rm=TRUE), .groups="drop") %>%
        filter(mx < 1) %>% pull(classe_n2)
      df_cob_h <- df_cob_h %>%
        mutate(classe_n2 = if_else(classe_n2 %in% .peq_h, "Outros usos", classe_n2)) %>%
        group_by(ano, classe_n2) %>%
        summarise(pct = sum(pct, na.rm=TRUE), .groups="drop")
      
      df_del_h <- df_cob_h %>%
        filter(ano %in% c(a_ini_h, a_fim_h)) %>%
        pivot_wider(names_from=ano, values_from=pct,
                    names_prefix="p", values_fill=0) %>%
        rename(p_ini=paste0("p",a_ini_h), p_fim=paste0("p",a_fim_h)) %>%
        mutate(
          delta_pp = p_fim - p_ini,
          var_rel  = case_when(
            classe_n2=="Outros usos"    ~ NA_real_,
            p_ini<1 & p_fim<1          ~ NA_real_,
            p_ini==0                   ~ NA_real_,
            TRUE                       ~ (p_fim-p_ini)/p_ini*100),
          sinal = if_else(delta_pp>=0,"Ganho","Perda"),
          classe_n2 = fct_reorder(classe_n2, delta_pp)
        )
      
      p_h_esq <- ggplot(df_del_h,
                        aes(x=delta_pp, y=classe_n2, fill=sinal)) +
        geom_col(width=0.72, color="grey40", linewidth=0.15) +
        geom_vline(xintercept=0, color="grey30", linewidth=0.5) +
        geom_label(data=df_del_h %>% filter(!is.na(var_rel)),
                   aes(label=paste0(if_else(var_rel>0,"+",""),
                                    number(var_rel,accuracy=0.1,decimal.mark=","),"%"),
                       x=delta_pp),
                   hjust=0.5, size=2.5, fontface="bold", color="grey15",
                   fill=alpha("white",0.82), linewidth=0.3,
                   label.padding=unit(0.06,"lines")) +
        scale_fill_manual(values=c("Ganho"="#2980b9","Perda"="#e67e22"),
                          guide="none") +
        scale_x_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",
                                               suffix=" pp")) +
        labs(title="Delta de Cobertura",
             subtitle=paste0(a_ini_h," → ",a_fim_h,
                             "  |  Rótulo = variação relativa (%)"),
             x="Δ pontos percentuais", y=NULL) +
        theme_minimal(base_size=10) +
        theme(plot.title=element_text(face="bold",size=10),
              plot.subtitle=element_text(size=8,color="grey50"),
              axis.text.y=element_text(size=8.5),
              panel.grid.major.y=element_blank())
      
      # Lado direito: Sankey da unidade
      p_h_dir <- tryCatch(.grafico_sankey_unidade(unidade_nome),
                          error=function(e) NULL)
      if (is.null(p_h_dir)) return(NULL)
      
      # Remover caption e título do Sankey (já estão no plot_annotation)
      p_h_dir <- p_h_dir +
        labs(title=NULL, subtitle=NULL, caption=NULL) +
        theme(plot.margin=margin(4,8,4,4))
      
      (p_h_esq | p_h_dir) +
        plot_layout(widths=c(1, 1.4)) +
        plot_annotation(
          title    = .quebrar(paste0("Delta × Fluxos de Transição — ",
                                     gsub("_"," ",unidade_nome)), LARGURA_TITULO),
          subtitle = paste0("Esq.: variação líquida por classe (pp)  |  ",
                            "Dir.: fluxos Sankey de transição  |  ",
                            ANO_INI," → ",ANO_FIM),
          caption  = CAPTION_PADRAO,
          theme    = theme(
            plot.title   =element_text(face="bold",size=13,hjust=0,lineheight=1.1),
            plot.subtitle=element_text(color="grey45",size=9),
            plot.caption =element_text(color="grey55",size=7,hjust=1),
            plot.margin  =margin(10,14,8,12))
        )
    }
    
    # ---- F: Chord Diagram ----
    .grafico_chord_mv <- function() {
      cols_alt <- names(alt)
      col_orig <- cols_alt[grepl("orig.*class|class.*orig|cl_orig", cols_alt, ignore.case=T)][1]
      col_dest <- cols_alt[grepl("dest.*class|class.*dest|cl_dest", cols_alt, ignore.case=T)][1]
      if (is.na(col_orig) || is.na(col_dest)) {
        message("  [F] Chord: colunas origem/destino nao encontradas.")
        return(invisible(NULL))
      }
      
      rec_geral <- alt %>%
        group_by(unidade_analise) %>%
        summarise(tot = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        slice_max(tot, n = 1) %>%
        pull(unidade_analise) %>%
        as.character()
      
      df_ch <- alt %>%
        filter(as.character(unidade_analise) == rec_geral) %>%
        rename(classe_orig = all_of(col_orig),
               classe_dest = all_of(col_dest)) %>%
        group_by(classe_orig = as.character(classe_orig),
                 classe_dest = as.character(classe_dest)) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
        filter(area_ha > 100, !is.na(classe_orig), !is.na(classe_dest))
      
      if (nrow(df_ch) == 0) { message("  [F] Chord: sem dados."); return(invisible(NULL)) }
      
      cls_ch <- union(df_ch$classe_orig, df_ch$classe_dest)
      cors_ch <- .nome_cor_mb[cls_ch]
      cors_ch[is.na(cors_ch)] <- "#888888"
      names(cors_ch) <- cls_ch
      
      circlize::circos.clear()
      circlize::circos.par(gap.after = 3, track.margin = c(0.01, 0.01),
                           points.overflow.warning = FALSE)
      circlize::chordDiagram(
        df_ch,
        grid.col          = cors_ch,
        transparency      = 0.35,
        annotationTrack   = "grid",
        preAllocateTracks = list(track.height = 0.08),
        directional       = 1,
        direction.type    = c("diffHeight","arrows"),
        link.arr.type     = "big.arrow",
        link.arr.length   = 0.1
      )
      circlize::circos.trackPlotRegion(
        track.index = 1,
        panel.fun = function(x, y) {
          xlim   <- circlize::get.cell.meta.data("xlim")
          ylim   <- circlize::get.cell.meta.data("ylim")
          sector <- circlize::get.cell.meta.data("sector.index")
          circlize::circos.text(mean(xlim), ylim[1], sector,
                                facing = "clockwise", niceFacing = TRUE,
                                adj = c(0, 0.5), cex = 0.65, font = 2)
        },
        bg.border = NA
      )
      title(main = .quebrar(paste0("Chord — Transições de Cobertura  |  ", rec_geral,
                                   "  |  ", ANO_INI, " → ", ANO_FIM)),
            cex.main = 1, font.main = 2, col.main = "grey20")
      mtext(CAPTION_PADRAO, side = 1, line = 2, cex = 0.65, col = "grey50")
      circlize::circos.clear()
    }
    
    # -- Gerar e exportar família 5 --
    
    message("\n[B] PCA — perfil de cobertura por unidade...")
    p_b <- tryCatch(.grafico_pca_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_b)) {
      salvar_grafico("B_pca_cobertura", p_b, w = 13, h = 7)
    }

    message("[C] Heatmap — unidades x classes...")
    p_c <- tryCatch(.grafico_heatmap_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_c)) {
      salvar_grafico("C_heatmap_cobertura", p_c, w = 14, h = 6.5)
    }

    message("[D] Dispersao — Cobertura Natural x Antropica...")
    p_d <- tryCatch(.grafico_dispersao_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_d)) {
      salvar_grafico("D_dispersao_natural_antropico", p_d, w = 12, h = 8)
    }

    message("[E] Matriz de bolhas — fluxos de transicao (todos os pares origem x destino)...")
    p_e <- tryCatch(.grafico_sankey_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_e)) {
      salvar_grafico("E_matriz_bolhas_transicao", p_e, w = 8.27, h = 13)
    }

    unidades_mv <- unique(as.character(cob$unidade_analise))
    unidades_mv <- unidades_mv[!is.na(unidades_mv) & nzchar(trimws(unidades_mv))]

    message("[G] Painel delta + manutencao/alteracao por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_g <- tryCatch(.grafico_painel_delta_alt(u_mv),
                      error=function(e){message("  ERRO [G] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_g)) { salvar_grafico(paste0("G_painel_delta_alt_",slug_mv),p_g,w=14,h=7) }
    }

    message("[E2] Sankey por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_e2 <- tryCatch(.grafico_sankey_unidade(u_mv),
                       error=function(e){message("  ERRO [E2] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_e2)) { salvar_grafico(paste0("E2_sankey_",slug_mv),p_e2,w=8.27,h=13) }
    }

    message("[H] Painel Delta + Sankey por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_h <- tryCatch(.grafico_painel_delta_sankey(u_mv),
                      error=function(e){message("  ERRO [H] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_h)) { salvar_grafico(paste0("H_delta_sankey_",slug_mv),p_h,w=16,h=8) }
    }
    
    message("[F] Chord diagram — transicoes circular...")
    if ("png" %in% FORMATO_SAIDA) {
      arq_chord <- file.path(pasta_saida, "F_chord_transicao.png")
      tryCatch({
        png(arq_chord, width = 2400, height = 2400, res = 200)
        .grafico_chord_mv()
        dev.off()
        cat(" Salvo: F_chord_transicao.png\n")
      }, error = function(e) { dev.off(); message("  ERRO chord: ", e$message) })
    }
    
  } # fim exists(cob)
} # fim GERAR_MULTIVAR

message("\n=== Concluido! Arquivos em: ", pasta_saida, " ===\n")