# ============================================================
#  AnP — Análise da Paisagem
#  Visualizações integradas: Cobertura · Matriz · Fragmentação
#  Rodrigo Lemos — DGPA / UNESP Rio Claro
#  Versão 1.2 (2025)
#
#  Compatível com os plugins AnP v1.1 (e com planilhas de versões
#  anteriores dos módulos).
#
#  Novidades da 1.2:
#   - Perfil ABNT: figuras desenhadas no tamanho final da página.
#   - Sínteses entre unidades de análise (família 5): S1 matriz de
#     bolhas da variação líquida; S2 variação líquida por classe,
#     comparando unidades; S3 permanência da área de origem; S4
#     combinação de S1 e S3.
#   - H passa a ser só a variação líquida por unidade; o Sankey da
#     unidade fica no E2 (juntos, não ficavam legíveis).
#   - Correções: classes de tamanho configuráveis (F2/F2b), planilhas
#     de fragmentação antigas, nomes de unidades cortados por versões
#     anteriores, rótulos em p.p., Sankey com rótulos externos.
#
#  Recursos:
#   - Menu interativo: escolha quais famílias de gráficos gerar
#     (Cobertura/Alterações, Matriz, Fragmentação/Paisagem,
#     Composição de Cobertura) — só pede o(s) arquivo(s)
#     necessário(s) para o que for selecionado. É a única pergunta
#     interativa do script; nomes e recortes são detectados
#     automaticamente.
#   - Pergunta o formato de saída (PNG / SVG / ambos) e onde salvar
#     os gráficos; cada janela de seleção abre na última pasta usada.
#   - Perfil das figuras: ABNT (padrão) — 16 cm de largura (A4, NBR
#     14724), 300 dpi, fontes de no mínimo 7 pt impressas, título na
#     imagem (TITULO_NA_FIGURA_ABNT) e subtítulo/fonte fora dela; gera
#     legendas_figuras_ABNT.txt com título, nota e fonte sugeridos para
#     cada figura. Ou Tela — figuras amplas, com título, subtítulo e
#     fonte na imagem.
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
message("  AnP v1.2 — Selecao das familias de graficos")
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
message("      -> inclui as sinteses entre unidades (S1 a S4)")
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

# ── Perfil das figuras ──────────────────────────────────────────────────
message(strrep("-", 62))
message("  Perfil das figuras:")
message("    [1] Relatorio / artigo (ABNT)  (padrao)")
message("        16 cm de largura, 300 dpi, fontes legiveis impressas;")
message("        sem titulo e fonte na imagem (vao na legenda do documento)")
message("    [2] Tela / apresentacao")
message("        figuras amplas, com titulo, subtitulo e fonte na imagem")
message("")
.entrada_perfil <- .ler_opcao("  Perfil [1/2]: ", "1")
PERFIL <- if (trimws(.entrada_perfil) == "2") "tela" else "abnt"
message("  Perfil selecionado: ", if (PERFIL == "abnt") "ABNT (relatorio/artigo)" else "Tela")
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
  # descarta linhas de rodapé de versões antigas ("AMP v3.0 — ... | ...")
  nomes <- nomes[!is.na(nomes) & nchar(as.character(nomes)) < 200 &
                   !grepl("|", as.character(nomes), fixed = TRUE)]
  unique(as.character(nomes))
}

# NOTA: a única pergunta interativa de todo o script é a seleção de
# famílias de gráficos (Secao 2). Após essa escolha, tudo é gerado automaticamente com
# os nomes originais das planilhas e incluindo todos os recortes
# detectados nos gráficos integrados (C2A, C4A, F1).

.nomes_reais   <- .detectar_nomes_reais(arq_cob, arq_frag, arq_rel)
# Planilhas de versões anteriores cortavam os nomes das unidades (40 ou 60
# caracteres). Um nome cortado (>= 30 caracteres) que seja o início de
# outro nome conhecido é mapeado para o nome completo — a mesma unidade
# não aparece duplicada, com cores diferentes, entre os gráficos.
.nome_completo <- function(nm) {
  if (nchar(nm) < 30) return(nm)
  .n   <- function(x) tolower(stringi::stri_trans_general(trimws(x), "Latin-ASCII"))
  cand <- .nomes_reais[startsWith(.n(.nomes_reais), .n(nm))]
  cand[which.max(nchar(cand))]
}
NOMES_PADRAO   <- setNames(vapply(.nomes_reais, .nome_completo, ""), .nomes_reais)
.nomes_reais   <- unique(unname(NOMES_PADRAO))
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
  "1"="Floresta","3"="Formação Florestal","4"="Formação Savânica",
  "5"="Mangue","6"="Floresta Alagável","49"="Restinga Arbórea",
  "10"="Veg. Herbácea e Arbustiva","11"="Campo Alagado e Área Pantanosa",
  "12"="Formação Campestre","29"="Afloramento Rochoso","32"="Apicum",
  "50"="Restinga Herbácea","13"="Outra Formação não Florestal",
  "14"="Agropecuária","15"="Pastagem","9"="Silvicultura",
  "21"="Mosaico de Usos","18"="Agricultura",
  "22"="Área não Vegetada","23"="Praia, Duna e Areal","24"="Área Urbanizada",
  "25"="Outras Áreas não Vegetadas","30"="Mineração","75"="Usina Fotovoltaica",
  "26"="Corpo D'água","33"="Rio, Lago e Oceano","31"="Aquicultura",
  "27"="Não Observado"
)

# Legenda completa (codigo -> nome, em todos os niveis) — usada para,
# na Matriz (que so traz NOMES de classe), voltar do nome ao codigo e
# entao ao Nivel 2.
.MB_LEGENDA <- c(
  "1"="Floresta","3"="Formação Florestal","4"="Formação Savânica","5"="Mangue",
  "6"="Floresta Alagável","49"="Restinga Arbórea",
  "10"="Vegetação Herbácea e Arbustiva","11"="Campo Alagado e Área Pantanosa",
  "12"="Formação Campestre","29"="Afloramento Rochoso","32"="Apicum",
  "50"="Restinga Herbácea","13"="Outra Formação não Florestal",
  "14"="Agropecuária","15"="Pastagem","9"="Silvicultura","21"="Mosaico de Usos",
  "18"="Agricultura","19"="Lavoura Temporária","36"="Lavoura Perene",
  "39"="Soja","20"="Cana-de-açúcar","40"="Arroz","62"="Algodão",
  "41"="Outras Lavouras Temporárias","46"="Café","47"="Citrus","35"="Dendê",
  "48"="Outras Lavouras Perenes",
  "22"="Área não Vegetada","23"="Praia, Duna e Areal","24"="Área Urbanizada",
  "25"="Outras Áreas não Vegetadas","30"="Mineração","75"="Usina Fotovoltaica",
  "26"="Corpo D'água","33"="Rio, Lago e Oceano","31"="Aquicultura",
  "27"="Não Observado"
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
  "1"="Floresta","10"="Veg. Herbácea e Arbustiva","14"="Agropecuária",
  "22"="Área não Vegetada","26"="Corpo D'água","27"="Não Observado"
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

# Classes pequenas para agrupar em "Outros usos" num par origem × destino:
# só as que ficam abaixo de limiar_pct (% da área total) NOS DOIS ANOS —
# como origem (ANO_INI) e como destino (ANO_FIM). Uma classe que cresceu
# (ex.: silvicultura de 0,7% para 2,3%) não é escondida.
.classes_pequenas <- function(df, limiar_pct, o = "orig_n2", d = "dest_n2", v = "area_ha") {
  tot <- sum(df[[v]], na.rm = TRUE)
  if (tot <= 0) return(character(0))
  so <- tapply(df[[v]], df[[o]], sum, na.rm = TRUE)
  sd <- tapply(df[[v]], df[[d]], sum, na.rm = TRUE)
  cl <- union(names(so), names(sd))
  mx <- pmax(coalesce(as.numeric(so[cl]), 0), coalesce(as.numeric(sd[cl]), 0)) / tot * 100
  setdiff(cl[mx < limiar_pct], "Outros usos")
}

# Agrupa classes < limiar (fracao do total) numa unica classe "outros"
# na matriz de transicao. So vira "outros" se for pequena tanto como
# origem quanto como destino (nao perde classes em expansao).
.agrupa_pequenas_matriz <- function(df, limiar = 0.01,
                                    rotulo = ROTULO_OUTROS_1PC) {
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
# ── Perfil ABNT: figuras no tamanho final da página ──────────────────────
# O ggplot mede fontes em pontos ABSOLUTOS. Uma figura salva com 35 cm de
# largura e reduzida a 16 cm no documento encolhe todas as fontes na mesma
# proporção (12 pt viram ~5 pt). No perfil ABNT cada figura já é DESENHADA
# com a largura útil de uma página A4 (NBR 14724: margens de 3 cm e 2 cm
# -> 16 cm), e as fontes são calibradas para esse tamanho, com um mínimo
# legível. Insira a imagem no documento a 100% (16 cm), sem redimensionar.
ABNT <- PERFIL == "abnt"
LARGURA_ABNT_CM    <- 16    # largura útil da página A4 (ABNT)
ALTURA_MAX_ABNT_CM <- 22    # deixa espaço para o título e a fonte da figura
DPI_ABNT           <- 300
FONTE_MIN_PT       <- 7     # menor corpo de texto aceito no tamanho impresso
ESCALA_TEXTO       <- 0.78  # fator sobre os tamanhos do perfil de tela

FONTE_BASE <- if (ABNT) 9 else 12

# Tamanhos de texto e símbolos que acompanham o perfil:
#   .pt() — texto de tema (element_text), em pontos
#   .mm() — texto dentro do gráfico (geom_text/geom_label), em mm
#   .sz() — símbolos (pontos, bolhas), sem mínimo
.pt <- function(x) if (ABNT) max(x * ESCALA_TEXTO, FONTE_MIN_PT) else x
.mm <- function(x) if (ABNT) max(x * ESCALA_TEXTO, FONTE_MIN_PT / ggplot2::.pt) else x
.sz <- function(x) if (ABNT) x * 0.7 else x
.tit <- function(x) if (ABNT) 10.5 else x   # títulos: 10,5 pt no perfil ABNT

# ── Ajustes de texto: nomes longos de recortes/unidades ──────────────────
# Os nomes das unidades nunca são cortados — textos longos são QUEBRADOS
# em várias linhas. Ajuste as larguras abaixo (em número de caracteres
# por linha) se algum título ainda ficar apertado ou largo demais.
LARGURA_TITULO  <- 70                    # título principal de cada gráfico
LARGURA_FACET   <- if (ABNT) 38 else 45  # título de cada painel nas grades (C2A, C4A...)
LARGURA_LEGENDA <- if (ABNT) 34 else 40  # itens de legenda com nome de unidade (F1, PCA...)
LARGURA_EIXO    <- if (ABNT) 24 else 30  # nomes de unidade usados como rótulo de eixo

# Rótulo das classes somadas por serem menores que 1% (matriz e roscas).
# No perfil ABNT, versão curta — a longa colide com os vizinhos em 16 cm.
ROTULO_OUTROS_1PC <- if (ABNT) "Outras classes (< 1%)" else "Soma de outros valores inferiores a 1%"

# Identificador curto de unidade sem numeral romano: iniciais das
# palavras significativas (ex.: "Shape Completo" -> "SC").
.iniciais <- function(x) {
  p <- strsplit(gsub("[_-]", " ", x), "\\s+")[[1]]
  p <- p[nchar(p) > 2 | grepl("^[A-Z0-9]", p)]
  toupper(paste0(substr(head(p, 3), 1, 1), collapse = ""))
}

.quebrar <- function(x, largura = LARGURA_TITULO) {
  stringr::str_wrap(x, width = largura)
}
rotulo_facet <- ggplot2::label_wrap_gen(width = LARGURA_FACET)

tema_amp <- theme_minimal(base_size = FONTE_BASE) +
  theme(
    plot.title         = element_text(face="bold", size=if (ABNT) 10.5 else FONTE_BASE+3,
                                      hjust=0, margin=margin(b=6), lineheight=1.05),
    plot.title.position = "plot",
    plot.subtitle      = element_text(color="grey45", size=FONTE_BASE-1, hjust=0, margin=margin(b=8)),
    plot.caption       = element_text(color="grey55", size=FONTE_BASE-3, hjust=1, margin=margin(t=6)),
    axis.text          = element_text(size=FONTE_BASE-1),
    axis.title         = element_text(size=FONTE_BASE-1),
    panel.grid.major.x = element_blank(),
    panel.grid.minor   = element_blank(),
    legend.position    = "top",
    legend.title       = element_blank(),
    legend.text        = element_text(size=.pt(FONTE_BASE-2)),
    plot.margin        = if (ABNT) margin(4,6,4,4) else margin(12,16,8,12),
    strip.text         = element_text(face="bold", size=FONTE_BASE, lineheight=1.0)
  )

CAPTION_PADRAO <- paste0(
  "Fonte: MapBiomas Brasil, Coleção 10  |  AnP v1.2 (2025)"
)

# Linha "Fonte:" sugerida para as legendas ABNT (arquivo de legendas).
# Ajuste a forma de autoria ("autores", "autor", nome) conforme o trabalho.
FONTE_FIGURA_ABNT <- paste0(
  "Fonte: elaborado pelos autores com o AnP v1.2 (LEMOS, 2025), a partir de ",
  "dados do MapBiomas Coleção 10 (MAPBIOMAS, 2025)."
)

# No perfil ABNT, subtítulo e fonte saem da imagem e vão para o arquivo
# legendas_figuras_ABNT.txt (a fonte fica abaixo da figura, no próprio
# documento). O TÍTULO permanece na imagem por padrão — identifica a
# figura com segurança e pode ser cortado depois no editor de texto.
TITULO_NA_FIGURA_ABNT <- TRUE
LEGENDAS_ABNT <- list()

# manter_caption = TRUE: a nota (caption) permanece na imagem — usada quando
# ela é indispensável à leitura (ex.: chave das siglas das unidades).
.sem_titulos <- function(plot, nome, manter_caption = FALSE) {
  if (inherits(plot, "patchwork")) {
    ann <- plot$patches$annotation
    titulo <- ann$title; sub <- ann$subtitle
    plot <- plot + plot_annotation(title = if (TITULO_NA_FIGURA_ABNT) titulo else NULL,
                                   subtitle = NULL,
                                   caption = if (manter_caption) ann$caption else NULL)
  } else {
    lb <- ggplot2::get_labs(plot)
    titulo <- lb$title; sub <- lb$subtitle
    plot <- plot + labs(subtitle = NULL)
    if (!TITULO_NA_FIGURA_ABNT) plot <- plot + labs(title = NULL)
    if (!manter_caption)        plot <- plot + labs(caption = NULL)
  }
  .limpa <- function(x) if (is.null(x)) "" else gsub("\\s*\n\\s*", " ", as.character(x))
  LEGENDAS_ABNT[[nome]] <<- list(titulo = .limpa(titulo), nota = .limpa(sub))
  plot
}

# w, h: tamanho no perfil de tela (polegadas).
# h_abnt: altura no perfil ABNT (cm); se omitida, segue a proporção de
# tela, limitada a ALTURA_MAX_ABNT_CM. A largura ABNT é sempre 16 cm.
salvar_grafico <- function(nome, plot, w=12, h=7, dpi=180, h_abnt=NULL,
                           manter_caption=FALSE) {
  if (ABNT) {
    plot <- .sem_titulos(plot, nome, manter_caption)
    if (is.null(h_abnt)) h_abnt <- h / w * LARGURA_ABNT_CM * 1.1
    # espaço para o título (até 2 linhas) quando ele fica na imagem
    if (TITULO_NA_FIGURA_ABNT) h_abnt <- h_abnt + 1.3
    h_abnt <- min(max(h_abnt, 6), ALTURA_MAX_ABNT_CM)
    w <- LARGURA_ABNT_CM / 2.54; h <- h_abnt / 2.54; dpi <- DPI_ABNT
  }
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
  message("  Salvo: ", nome, " (", paste(gerados, collapse=" | "), ")",
          if (ABNT) sprintf("  [%.0f x %.1f cm]", w * 2.54, h * 2.54) else "")
  invisible(plot)
}

# Arquivo com as legendas sugeridas (título + nota + fonte), uma por
# figura, para colar no documento no padrão ABNT.
.escrever_legendas_abnt <- function() {
  if (!ABNT || length(LEGENDAS_ABNT) == 0) return(invisible(NULL))
  arq <- file.path(pasta_saida, "legendas_figuras_ABNT.txt")
  linhas <- c(
    "LEGENDAS SUGERIDAS PARA AS FIGURAS (padrão ABNT)",
    "Insira cada imagem a 100% (16 cm de largura), sem redimensionar.",
    "Título acima da figura (\"Figura N – ...\"); fonte abaixo.",
    "")
  for (nm in names(LEGENDAS_ABNT)) {
    lg <- LEGENDAS_ABNT[[nm]]
    linhas <- c(linhas, strrep("-", 70), paste0("Arquivo: ", nm),
                paste0("Figura N – ", lg$titulo, "."))
    if (nzchar(lg$nota)) linhas <- c(linhas, paste0("Nota: ", lg$nota, "."))
    linhas <- c(linhas, FONTE_FIGURA_ABNT, "")
  }
  writeLines(linhas, arq, useBytes = FALSE)
  message("  Legendas ABNT: ", basename(arq))
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
  .novos_nomes <- setdiff(.nomes_cob_completo, c(ORDEM_RECORTES, names(NOMES_PADRAO)))
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

  # Área total (sem recorte): a unidade de maior área. O plugin permite dar
  # a ela outro nome além de "Shape Completo" (ex.: "Quadrilátero Ferrífero").
  NOME_AREA_TOTAL <- cobertura %>%
    filter(as.integer(as.character(ano)) == ANO_INI) %>%
    group_by(unidade_analise) %>% summarise(a = sum(area_ha, na.rm = TRUE), .groups = "drop") %>%
    slice_max(a, n = 1, with_ties = FALSE) %>% pull(unidade_analise) %>% as.character()
  
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
                         number(delta,accuracy=0.1,decimal.mark=",")),
            vjust=if_else(delta>=0,-0.45,1.35)),
        size = .mm(3.3), color="grey20", fontface="bold") +
      scale_fill_manual(values=cores_u, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix=" p.p."),
                         expand=expansion(mult=c(0.14,0.16))) +
      labs(title=.quebrar(paste0("Variação da cobertura e uso da terra por classe (",
                                 ANO_INI, "–", ANO_FIM, ") – ", unidade_nome)),
           subtitle=paste0("Diferença de participação na área total (", ANO_FIM, " − ", ANO_INI,
                           "), em pontos percentuais (p.p.); valores positivos indicam ganho ",
                           "e negativos, perda"),
           x=NULL, y="Variação (p.p.)", caption=CAPTION_PADRAO) +
      tema_amp + theme(legend.position="none",
                       axis.text.x=element_text(angle=35,hjust=1,size = .pt(10)))
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
    n_cols <- if (n_rec <= 2) 1L else if (n_rec <= 9 || ABNT) 2L else if (n_rec <= 20) 3L else 4L

    ggplot(df, aes(x=classe_plot, y=delta, fill=classe_plot)) +
      geom_col(color="grey40", linewidth=0.15, width=0.7) +
      geom_hline(yintercept=0, linewidth=0.5, color="grey30") +
      geom_text(
        data=df %>% filter(abs(delta) >= 0.3),
        aes(label=paste0(if_else(delta>0,"+",""),
                         number(delta,accuracy=0.1,decimal.mark=",")),
            vjust=if_else(delta>=0,-0.45,1.35)),
        size = .mm(2.6), color="grey20", fontface="bold") +
      facet_wrap(~unidade_analise, ncol=n_cols, scales="free_y", labeller=rotulo_facet) +
      scale_fill_manual(values=cores_classes, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix=" p.p."),
                         expand=expansion(mult=c(0.18,0.22))) +
      labs(title=paste0("Variação da cobertura e uso da terra por classe e unidade de análise (",
                        ANO_INI, "–", ANO_FIM, ")"),
           subtitle=paste0("Diferença de participação na área total, em pontos percentuais (p.p.); ",
                           "valores positivos indicam ganho e negativos, perda"),
           x=NULL, y="Variação (p.p.)", caption=CAPTION_PADRAO) +
      tema_amp +
      theme(legend.position="none",
            axis.text.x=element_text(angle=35,hjust=1,size = .pt(8)),
            strip.text=element_text(face="bold",size = .pt(11),hjust=0),
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
                hjust=-0.08, size = .mm(3.8), fontface="bold", color="grey15") +
      scale_fill_identity() +
      scale_x_continuous(limits=c(0,lim_x),
                         labels=label_number(big.mark=".",decimal.mark=",",suffix=" ha"),
                         expand=expansion(mult=c(0,0))) +
      scale_y_discrete(labels=function(x) str_wrap(x, width=18)) +
      labs(title=.quebrar(paste0("Categorias de alteração da cobertura (", ANO_INI, "–",
                                 ANO_FIM, ") – ", unidade_nome), 55),
           subtitle="Área (ha) por categoria; rótulos indicam o percentual da área total da unidade",
           x="Área (ha)", y=NULL, caption=CAPTION_PADRAO) +
      tema_amp +
      theme(plot.title=element_text(face="bold",size = .tit(14),hjust=0),
            axis.text.y=element_text(size = .pt(11),lineheight=0.9),
            axis.text.x=element_text(size = .pt(9)),
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
    n_cols <- if (n_rec <= 2) 1L else if (n_rec <= 9 || ABNT) 2L else if (n_rec <= 20) 3L else 4L

    ggplot(df, aes(x=area_ha, y=categoria, fill=cor_cat)) +
      geom_col(color="grey30", linewidth=0.2, width=0.68) +
      geom_text(aes(label=paste0(number(pct,accuracy=0.1,decimal.mark=","),"%")),
                hjust=-0.08, size = .mm(3.2), fontface="bold", color="grey15") +
      facet_wrap(~unidade_analise, ncol=n_cols, scales="free_x", labeller=rotulo_facet) +
      scale_fill_identity() +
      scale_x_continuous(labels=label_number(big.mark=".",decimal.mark=",",suffix=" ha"),
                         expand=expansion(mult=c(0,0.30))) +
      scale_y_discrete(labels=function(x) str_wrap(x, width=20)) +
      labs(title=paste0("Categorias de alteração da cobertura por unidade de análise (",
                        ANO_INI, "–", ANO_FIM, ")"),
           subtitle="Área (ha) por categoria; rótulos indicam o percentual da área total de cada unidade",
           x="Área (ha)", y=NULL, caption=CAPTION_PADRAO) +
      tema_amp +
      theme(strip.text=element_text(face="bold",size = .pt(11),color="grey15",hjust=0),
            axis.text.y=element_text(size = .pt(10),lineheight=0.85),
            axis.text.x=element_text(size = .pt(8)),
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
      lbl_fill <- "Área (ha)"
      df$label_txt <- ifelse(df$valor_show > 0,
                             number(df$valor_show, big.mark=".", decimal.mark=",", accuracy=1), "")
      subt <- "Células: área (ha) que passou da classe de origem (linha) à classe de destino (coluna); classes agregadas no Nível 2"
    } else {
      # % da area de origem RECALCULADO a partir do ha agregado ao Nivel 2
      # (somar as fracoes ja prontas seria incorreto apos o reagrupamento)
      df <- df %>% group_by(classe_origem) %>%
        mutate(tot_orig   = sum(valor, na.rm = TRUE),
               valor_show = ifelse(tot_orig > 0, valor / tot_orig * 100, 0)) %>%
        ungroup()
      lbl_fill <- "% da área
de origem"
      df$label_txt <- ifelse(df$valor_show > 0,
                             paste0(number(df$valor_show, accuracy=0.1, decimal.mark=","), "%"), "")
      subt <- "Células: percentual da área da classe de origem (linha) que passou à classe de destino (coluna); classes agregadas no Nível 2"
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
      geom_text(aes(label = label_txt, color = cor_texto), size = .mm(2.3)) +
      scale_color_identity() +
      scale_fill_gradientn(colors = c("#FFFFFF","#FFE0B2","#FB8C00","#B71C1C"),
                           na.value = "white", name = lbl_fill,
                           labels = label_number(big.mark = ".", decimal.mark = ",")) +
      scale_x_discrete(position = "top",
                       labels = function(x) str_wrap(x, width = 14)) +
      labs(title = .quebrar(paste0("Matriz de transição da cobertura e uso da terra (",
                                   ANO_INI_MAT, "–", ANO_FIM_MAT, ") – ", recorte_nome)),
           subtitle = paste0(subt, "; contorno vermelho = permanência na mesma classe"),
           x = "Classe de destino", y = "Classe de origem",
           caption = CAPTION_PADRAO) +
      tema_amp +
      theme(axis.text.x = element_text(angle = 45, hjust = 0, vjust = 0,
                                       size = .pt(7), lineheight = 0.85),
            axis.text.y = element_text(size = .pt(8)),
            legend.position = "right",
            legend.title = element_text(size = .pt(8)),
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

  # Anos da matriz, lidos do título do bloco ("Matriz de Transição | 1985 → 2024 | ha")
  ANO_INI_MAT <- ANO_FIM_MAT <- NA
  if (length(ABAS_MAT) > 0) {
    .tit_mat <- tryCatch({
      .r <- suppressMessages(read_excel(arq_mat, sheet = ABAS_MAT[1], col_names = FALSE,
                                        col_types = "text", n_max = 5))
      .t <- unlist(.r[[1]]); .t[grepl("Matriz de Transi", .t)][1]
    }, error = function(e) NA_character_)
    .anos_mat <- as.integer(regmatches(.tit_mat, gregexpr("\\b(19|20)\\d{2}\\b", .tit_mat))[[1]])
    if (length(.anos_mat) >= 2) { ANO_INI_MAT <- min(.anos_mat); ANO_FIM_MAT <- max(.anos_mat) }
  }
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
  
  # Ordem das classes de tamanho lida dos próprios rótulos — as classes são
  # configuráveis no plugin (limiares por bioma) e os rótulos variam entre
  # versões ("Menor que 1 ha" / "menor 1 ha"). Ordena pelo primeiro número:
  # "menor/abaixo de X" antes de tudo, "maior/acima de X" depois de tudo.
  .ordem_classes_tam <- function(rotulos) {
    r <- unique(as.character(rotulos)); r <- r[!is.na(r) & nzchar(trimws(r))]
    num <- vapply(seq_along(r), function(i) {
      n <- suppressWarnings(as.numeric(sub(",", ".", regmatches(r[i], regexpr("[0-9]+([.,][0-9]+)?", r[i])))))
      if (length(n) == 0 || is.na(n)) return(Inf)
      if (grepl("menor|abaixo|<", r[i], ignore.case = TRUE)) return(n - 1e-6)
      if (grepl("maior|acima|>", r[i], ignore.case = TRUE)) return(n + 1e9)
      n
    }, numeric(1))
    r[order(num)]
  }
  
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
      col_v1 <- paste0("valor_", ANO1_FRAG)
      col_v2 <- paste0("valor_", ANO2_FRAG)
    } else if (all(c("valor_ano1", "valor_ano2") %in% names(frag_var_raw))) {
      # Formato de versões anteriores do módulo (colunas valor_ano1 /
      # valor_ano2): os anos vêm da aba Metricas (coluna "ano").
      anos_met <- tryCatch(
        sort(unique(as.integer(read_excel(arq_frag, sheet = "Metricas")$ano))),
        error = function(e) integer(0))
      anos_met <- anos_met[!is.na(anos_met)]
      if (length(anos_met) < 2)
        stop("Aba Variacoes no formato antigo (valor_ano1/valor_ano2) e ",
             "a aba Metricas nao informa os anos. Gere a planilha novamente ",
             "com o modulo de Fragmentacao v1.1.")
      ANO1_FRAG <- anos_met[1]; ANO2_FRAG <- anos_met[length(anos_met)]
      col_v1 <- "valor_ano1"; col_v2 <- "valor_ano2"
      message("  [INFO] Planilha de fragmentacao no formato antigo — anos ",
              ANO1_FRAG, " e ", ANO2_FRAG, " lidos da aba Metricas.")
    } else {
      stop("Nao foi possivel detectar as colunas de valor na aba Variacoes ",
           "(esperado valor_<ano> ou valor_ano1/valor_ano2).")
    }
    
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
    .ler_dist <- function(aba) {
      read_excel(arq_frag, sheet = aba) %>%
        filter(!is.na(classe_tamanho), !is.na(suppressWarnings(as.integer(ano)))) %>%
        mutate(recorte = factor(padronizar(recorte), levels = ORDEM_RECORTES),
               across(c(n_fragmentos,area_ha,pct_n,pct_area), as.numeric),
               classe_tamanho = factor(classe_tamanho,
                                       levels = .ordem_classes_tam(classe_tamanho)),
               ano = factor(as.character(as.integer(ano))))
    }
    frag_dist_frag <- .ler_dist("Dist_Fragmentos")
    frag_dist_nuc  <- .ler_dist("Dist_Nucleos")
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
                               "NP"      = "NP – número de fragmentos",
                               "TCA"     = "TCA – área núcleo total",
                               "CORE_MN" = "CORE_MN – área núcleo média",
                               "ED"      = "ED – densidade de borda",
                               "LPI"     = "LPI – índice do maior fragmento",
                               "MESH"    = "MESH – tamanho efetivo de malha"
        ),
        metrica_label = factor(metrica_label, levels=c(
          "NP – número de fragmentos",
          "TCA – área núcleo total",
          "CORE_MN – área núcleo média",
          "ED – densidade de borda",
          "LPI – índice do maior fragmento",
          "MESH – tamanho efetivo de malha"
        ))
      )
    
    # Legenda: "01 · Nome do Recorte" — cor mapeada por recorte, não
    # mais scale_fill_identity() (que não gera legenda nenhuma)
    rotulos_legenda <- setNames(
      .quebrar(paste0(sprintf("%02d", seq_along(recortes)), " \u00b7 ", recortes),
               LARGURA_LEGENDA),
      recortes)
    n_rec        <- length(recortes)
    ncol_legenda <- if (ABNT) min(2, n_rec) else min(6, max(2, ceiling(sqrt(n_rec))))
    
    ggplot(df, aes(x=factor(indice, levels=seq_along(recortes)),
                   y=delta_pct_pct, fill=recorte)) +
      geom_col(width=0.62, color="grey35", linewidth=0.2) +
      geom_hline(yintercept=0, linewidth=0.5, color="grey30") +
      geom_text(
        aes(label=paste0(if_else(delta_pct_pct>=0,"+",""),
                         number(delta_pct_pct,accuracy=0.1,decimal.mark=","),"%"),
            vjust=if_else(delta_pct_pct>=0,-0.4,1.3)),
        size = .mm(2.8), fontface="bold", color="grey15") +
      facet_wrap(~metrica_label, ncol=2, scales="free_y") +
      scale_fill_manual(values = CORES_RECORTE, breaks = recortes,
                        labels = rotulos_legenda, name = NULL) +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.18,0.22))) +
      guides(fill = guide_legend(ncol = ncol_legenda, byrow = FALSE)) +
      labs(title=paste0("Variação relativa das métricas de fragmentação da paisagem (",
                        ANO1_FRAG, "–", ANO2_FRAG, ") – ", grupo_sel),
           subtitle=paste0("Variação relativa = (valor final − valor inicial) / valor inicial × 100; ",
                           "números no eixo identificam a unidade de análise (ver legenda)"),
           x="Unidade de análise", y="Variação relativa (%)", caption=CAPTION_PADRAO) +
      tema_amp +
      theme(strip.text=element_text(face="bold",size = .pt(10),hjust=0),
            axis.text.x=element_text(size = .pt(8)),
            axis.text.y=element_text(size = .pt(8)),
            panel.grid.major.x=element_blank(),
            panel.grid.major.y=element_line(color="grey90",linewidth=0.4),
            legend.position="bottom",
            legend.text=element_text(size = .pt(7.5), lineheight=0.9),
            legend.key.size=unit(0.35,"cm"),
            plot.margin=margin(14,16,10,14))
  }
  
  # ---- F2 — Espelho: distribuicao por classe de tamanho ----
  grafico_F2_espelho <- function(recorte_nome, tipo="fragmentos", grupo_sel=NULL) {
    aba        <- if (tipo=="fragmentos") frag_dist_frag else frag_dist_nuc
    tipo_label <- if (tipo=="fragmentos") "fragmentos" else "áreas núcleo"
    tipo_art   <- if (tipo=="fragmentos") "dos" else "das"
    
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
                 vjust=-0.15, size = .mm(2.6), fontface="bold", lineheight=1.1,
                 linewidth=0.3, label.padding=unit(0.18,"lines"),
                 label.r=unit(0.12,"lines"), fill="white", color="#0A5540") +
      scale_fill_manual(values=cores_ano) +
      scale_color_manual(values=borda_ano, guide="none") +
      scale_y_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0,0.45))) +
      labs(x=NULL, y=paste0("Participação no número
total de ", tipo_label, " (%)"), fill=NULL) +
      tema_amp +
      theme(axis.text.x=element_blank(), axis.ticks.x=element_blank(),
            axis.text.y=element_text(size = .pt(10)), axis.title.y=element_text(size = .pt(10)),
            panel.grid.major.x=element_blank(), legend.position="none",
            plot.margin=margin(10,14,4,14))
    
    p_bot <- ggplot(df, aes(x=classe_tamanho, y=pct_area, fill=ano, color=ano)) +
      geom_col(position=position_dodge(width=0.75), width=0.65, linewidth=0.3) +
      geom_text(aes(label=label_pct_area, group=ano),
                position=position_dodge(width=0.75),
                vjust=1.4, size = .mm(2.8), fontface="bold", color="grey20") +
      scale_fill_manual(values=cores_ano, labels=anos_niveis,
                        guide=guide_legend(title=NULL,
                                           override.aes=list(color=unname(borda_ano)),
                                           label.position="right")) +
      scale_color_manual(values=borda_ano, guide="none") +
      scale_y_continuous(trans="reverse",
                         labels=label_number(accuracy=0.1,decimal.mark=",",suffix="%"),
                         expand=expansion(mult=c(0.28,0))) +
      labs(x="Classe de tamanho", y="Participação na
área total (%)", fill=NULL) +
      tema_amp +
      theme(axis.text.x=element_text(angle=35,hjust=1,size = .pt(10)),
            axis.text.y=element_text(size = .pt(10)), axis.title.y=element_text(size = .pt(10)),
            panel.grid.major.x=element_blank(), legend.position="bottom",
            legend.key.size=unit(0.55,"cm"), legend.text=element_text(size = .pt(11),face="bold"),
            plot.margin=margin(4,14,10,14))
    
    sep <- ggplot() + theme_void() +
      theme(plot.background=element_rect(fill="grey75",color=NA),
            plot.margin=margin(0,0,0,0))
    
    (p_top / sep / p_bot) +
      plot_layout(heights=c(10,0.05,10)) +
      plot_annotation(
        title  = .quebrar(paste0("Distribuição ", tipo_art, " ", tipo_label, " por classe de tamanho",
                                 if (!is.null(grupo_sel)) paste0(" – ", grupo_sel) else "",
                                 " – ", recorte_nome)),
        subtitle = paste0("Acima: participação no número total de ", tipo_label,
                          " (rótulo: quantidade e %); abaixo: participação na área total"),
        caption= paste0(CAPTION_PADRAO),
        theme  = theme(plot.title=element_text(face="bold",size = .tit(14),margin=margin(b=8),
                                               lineheight=1.05),
                       plot.caption=element_text(color="grey55",size = .pt(8),hjust=1,
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
    ROTULO_OUTROS <- ROTULO_OUTROS_1PC
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
    
    # Perfil ABNT: sem setas externas (no tamanho impresso os rótulos das
    # fatias pequenas se sobrepõem). Os percentuais de cada ano vão para a
    # legenda — "Classe (1985% → 2024%)" — e só as fatias grandes recebem
    # rótulo dentro do anel.
    if (ABNT) df_pequena <- df_pequena[0, ]
    tem_pequenas <- nrow(df_pequena) > 0
    .pct_leg <- df %>%
      select(classe, ano, pct) %>%
      tidyr::complete(classe, ano, fill = list(pct = 0)) %>%
      group_by(classe) %>%
      # 0 aqui = classe ausente ou somada em "outros valores inferiores a 1%"
      # naquele ano -> "< 1%" (e não "0,0%", que seria enganoso)
      summarise(txt = paste(ifelse(pct[order(ano)] > 0,
                                   paste0(number(pct[order(ano)], accuracy = 0.1,
                                                 decimal.mark = ","), "%"),
                                   "< 1%"),
                            collapse = " → "), .groups = "drop")
    rotulos_leg <- if (ABNT)
      setNames(paste0(.pct_leg$classe, " (", .pct_leg$txt, ")"), .pct_leg$classe)
    else setNames(as.character(.pct_leg$classe), .pct_leg$classe)
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
        size = .mm(3.1), fontface = "bold") +
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
          size = .mm(2.7), fontface = "bold", color = "grey20")
    }
    
    p +
      geom_text(data = df_central, aes(x = 0.4, y = 0, label = label_central),
                inherit.aes = FALSE, size = .mm(3.6), fontface = "bold", color = "grey20",
                lineheight = 0.95) +
      facet_wrap(~ano, ncol = length(unique(df$ano))) +
      scale_fill_manual(values = cores_map, name = NULL,
                        labels = function(x) str_wrap(rotulos_leg[x], width = if (ABNT) 40 else 24)) +
      guides(fill = guide_legend(ncol = if (ABNT) 2 else 1)) +
      labs(title = .quebrar(paste0("Composição da cobertura e uso da terra – ", unidade_nome,
                                   " (", nivel_label, ")")),
           subtitle = paste0("Percentual da área total por classe; centro: área total (ha) e ano",
                             if (tem_pequenas) paste0("; setas indicam classes com menos de ",
                                                      LIMIAR_CALLOUT, "%") else "",
                             if (ABNT) paste0("; legenda: participação de cada classe em ",
                                              paste(sort(unique(df$ano)), collapse = " → "))
                             else ""),
           caption = CAPTION_PADRAO) +
      theme_void(base_size = FONTE_BASE) +
      theme(legend.position   = if (ABNT) "bottom" else "right",
            legend.text       = element_text(size = .pt(9)),
            legend.key.size   = unit(if (ABNT) 0.35 else 0.5, "cm"),
            strip.text        = element_text(face = "bold", size = FONTE_BASE),
            plot.title.position = "plot",
            plot.title        = element_text(face="bold", size=.tit(FONTE_BASE+3), hjust=0,
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
message("\n=== Gerando graficos [AnP v1.2] ===\n")

if (GERAR_COBERTURA) {
  unidades      <- unique(as.character(cob$unidade_analise))
  unidades      <- unidades[!is.na(unidades) & nzchar(trimws(unidades))]
  unidades_alt  <- unique(as.character(alt$unidade_analise))
  unidades_alt  <- unidades_alt[!is.na(unidades_alt) & nzchar(trimws(unidades_alt))]
  
  message("[C2] Variacao de cobertura por recorte (individual)...")
  for (u in unidades) {
    slug <- .slug(u)
    salvar_grafico(paste0("C2_delta_cobertura_", slug),
                   grafico_C2_delta(u), w=9, h=7, h_abnt=10)
  }
  
  message("[C2A] Variacao de cobertura - integrado...")
  n_c2a    <- length(RECORTES_INT_COB)
  nc_c2a   <- if (n_c2a <= 2) 1L else if (n_c2a <= 9) 2L else if (n_c2a <= 20) 3L else 4L
  nr_c2a   <- ceiling(n_c2a / nc_c2a)
  h_c2a    <- min(49, max(7, nr_c2a * 4.5))
  w_c2a    <- c(10, 14, 19, 24)[nc_c2a]
  salvar_grafico("C2A_delta_cobertura_integrado",
                 grafico_C2A_integrado(RECORTES_INT_COB), w=w_c2a, h=h_c2a,
                 h_abnt=3 + ceiling(n_c2a / min(2, n_c2a)) * 5)
  
  message("[C4] Categorias de alteracao por recorte (individual)...")
  for (u in unidades_alt) {
    slug <- .slug(u)
    salvar_grafico(paste0("C4_categorias_", slug),
                   grafico_C4_individual(u), w=8, h=7, h_abnt=9)
  }
  
  message("[C4A] Grade de categorias - integrado...")
  nc_c4a   <- if (n_c2a <= 2) 1L else if (n_c2a <= 9) 2L else if (n_c2a <= 20) 3L else 4L
  nr_c4a   <- ceiling(n_c2a / nc_c4a)
  h_c4a    <- min(49, max(8, nr_c4a * 4.5))
  w_c4a    <- c(10, 14, 19, 24)[nc_c4a]
  salvar_grafico("C4A_categorias_grade",
                 grafico_C4A_grade(RECORTES_INT_COB), w=w_c4a, h=h_c4a,
                 h_abnt=2 + ceiling(n_c2a / min(2, n_c2a)) * 4.5)
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
                   w=tam+2, h=tam, h_abnt=15)
    salvar_grafico(paste0("M1_matriz_percentual_", slug),
                   grafico_M1_heatmap(df_n2, "percentual", nome_mat),
                   w=tam+2, h=tam, h_abnt=15)
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
                   grafico_F1_deltas(RECORTES_INT_FRAG, gp), w=13, h=10,
                   h_abnt=15 + ceiling(length(RECORTES_INT_FRAG) / 2) * 0.6)

    if (TEM_DIST_PORTE) {
      recortes_frag <- unique(as.character(frag_dist_frag$recorte))
      recortes_frag <- recortes_frag[!is.na(recortes_frag)]
      recortes_nuc  <- unique(as.character(frag_dist_nuc$recorte))
      recortes_nuc  <- recortes_nuc[!is.na(recortes_nuc)]

      message("[F2] Espelho fragmentos — grupo: ", gp)
      for (r in recortes_frag) {
        slug <- .slug(r)
        salvar_grafico(paste0("F2_espelho_fragmentos_", gslug, "_", slug),
                       grafico_F2_espelho(r, tipo="fragmentos", grupo_sel=gp), w=10, h=9, h_abnt=15)
      }
      message("[F2b] Espelho nucleos — grupo: ", gp)
      for (r in recortes_nuc) {
        slug <- .slug(r)
        salvar_grafico(paste0("F2b_espelho_nucleos_", gslug, "_", slug),
                       grafico_F2_espelho(r, tipo="nucleos", grupo_sel=gp), w=10, h=9, h_abnt=15)
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
                   grafico_P1_pizza(pizza_n1, u, "Nível 1"),
                   w = largura_p1, h = 7, h_abnt = 10)
  }
  
  message("[P1b] Composicao de cobertura (rosca) - Nivel 2...")
  for (u in unidades_rel) {
    slug <- .slug(u)
    salvar_grafico(paste0("P1b_pizza_N2_", slug),
                   grafico_P1_pizza(pizza_n2, u, "Nível 2"),
                   w = largura_p1 + 2, h = 7.5, h_abnt = 11.5)
  }
  
  if (!is.null(pizza_n3)) {
    message("[P1c] Composicao de cobertura (rosca) - Nivel 3...")
    for (u in unidades_rel) {
      slug <- .slug(u)
      salvar_grafico(paste0("P1c_pizza_N3_", slug),
                     grafico_P1_pizza(pizza_n3, u, "Nível 3"),
                     w = largura_p1 + 3, h = 8, h_abnt = 12.5)
    }
  }
  
  if (!is.null(pizza_n4)) {
    message("[P1d] Composicao de cobertura (rosca) - Nivel 4...")
    for (u in unidades_rel) {
      slug <- .slug(u)
      salvar_grafico(paste0("P1d_pizza_N4_", slug),
                     grafico_P1_pizza(pizza_n4, u, "Nível 4"),
                     w = largura_p1 + 4, h = 9, h_abnt = 13.5)
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
        if (length(m) == 0 || !nzchar(m)) .iniciais(x) else m
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
                                 size = .mm(2.7), color="grey40", fontface="italic", max.overlaps=20) +
        # Setas de trajetória por unidade
        geom_segment(data=df_seta_pca,
                     aes(x=PC1_ini, y=PC2_ini, xend=PC1_fim, yend=PC2_fim,
                         color=as.character(unidade_analise)),
                     arrow=arrow(length=unit(0.20,"cm"), type="closed"),
                     linewidth=0.95, alpha=0.65, show.legend=FALSE) +
        # Ponto 1985 — círculo aberto/pastel
        geom_point(data=df_pca_ini,
                   aes(x=PC1, y=PC2, color=as.character(unidade_analise)),
                   shape=21, size=.sz(4.2), stroke=.sz(1.3),
                   fill=adjustcolor(cor_pca[as.character(df_pca_ini$unidade_analise)],
                                    alpha.f=0.22),
                   show.legend=FALSE) +
        # Ponto 2024 — círculo cheio
        geom_point(data=df_pca_fim,
                   aes(x=PC1, y=PC2, color=as.character(unidade_analise)),
                   shape=19, size=.sz(4.2), show.legend=TRUE) +
        # Rótulos: id_curto
        geom_text(data=df_pca_ini,
                  aes(x=PC1, y=PC2, label=id_curto,
                      color=as.character(unidade_analise)),
                  size = .mm(2.8), fontface="bold", vjust=2.5, show.legend=FALSE) +
        geom_text(data=df_pca_fim,
                  aes(x=PC1, y=PC2, label=id_curto,
                      color=as.character(unidade_analise)),
                  size = .mm(2.8), fontface="bold", vjust=-1.8, show.legend=FALSE) +
        scale_color_manual(values=cor_pca, name=NULL,
                           labels=setNames(.quebrar(leg_pca$unidade_analise, LARGURA_LEGENDA),
                                           leg_pca$unidade_analise)) +
        guides(color=guide_legend(ncol=if (ABNT) 2 else NULL,
                                  nrow=if (ABNT) NULL else ceiling(n_unid/3),
                                  override.aes=list(shape=19, size=.sz(4)))) +
        labs(
          title    = .quebrar(paste0("Análise de componentes principais (PCA) da composição da ",
                                     "cobertura e uso da terra por unidade de análise (",
                                     a_ini_pca, "–", a_fim_pca, ")")),
          subtitle = paste0("Setas cinza: classes de maior contribuição; círculo vazado: ",
                            a_ini_pca, "; círculo cheio: ", a_fim_pca,
                            "; setas coloridas: trajetória de cada unidade"),
          x=paste0("PC1 (", number(var_exp[1], accuracy=0.1, decimal.mark=","), "%)"),
          y=paste0("PC2 (", number(var_exp[2], accuracy=0.1, decimal.mark=","), "%)"),
          caption=paste0(str_wrap(leg_txt, width=110), "
", CAPTION_PADRAO)
        ) +
        tema_amp +
        theme(panel.grid      = element_line(color="grey93"),
              legend.position = "bottom",
              legend.text     = element_text(size = .pt(8.5), lineheight=0.9),
              legend.key.size = unit(if (ABNT) 0.45 else 0.8,"cm"),
              plot.caption    = element_text(size = .pt(7.5), color="grey35",
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
      
      # Cor = VARIAÇÃO RELATIVA (%) da participação de cada classe, em faixas.
      # (A variação em p.p. favorece as classes e unidades grandes: o mesmo
      # tom representaria dimensões muito diferentes.)
      # Perdas e ganhos com 5 faixas cada, espelhadas em proporção: a perda
      # relativa não passa de 100%, e dobrar (+100%) equivale a cair pela
      # metade (-50%), triplicar (+200%) a cair para um terço (-67%).
      FAIXAS_PERDA <- c(0, 10, 20, 50, 70, Inf)     # |variação| das perdas
      FAIXAS_GANHO <- c(0, 10, 20, 100, 200, Inf)
      # Intervalos fechados à direita: "0 a 10" inclui o 10; "> 10 a 20" começa
      # logo acima de 10 (10,001...) e inclui o 20 — sem sobreposição.
      ROT_PERDA <- c("0 a 10", "> 10 a 20", "> 20 a 50", "> 50 a 70", "> 70")
      ROT_GANHO <- c("0 a 10", "> 10 a 20", "> 20 a 100", "> 100 a 200", "> 200")
      # Laranja/terracota (perda) × azul (ganho): par de contraste neutro, sem a
      # leitura "ambiental" de vermelho/verde; mesmas cores dos painéis G e H.
      CORES_PERDA <- c("#fde3cc", "#f8b98a", "#ec8a4f", "#c95f22", "#7f3410")
      CORES_GANHO <- c("#dce9f5", "#a8c9e6", "#6aa3d3", "#2f74b5", "#163f6e")
      COR_SEM_DADO <- "#e4e4e4"
      NIVEIS_FX <- c(paste0("P", 5:1), "SD", paste0("G", 1:5))
      CORES_FX  <- setNames(c(rev(CORES_PERDA), COR_SEM_DADO, CORES_GANHO), NIVEIS_FX)

      # Grade completa unidade × classe: toda célula aparece, inclusive as
      # sem dado (classe < 1% nos dois anos ou ausente na unidade).
      df_delta <- df_delta %>%
        tidyr::complete(unidade_analise, classe_n2) %>%
        mutate(
          pct_ini_z = coalesce(pct_ini_z, 0), pct_fim_z = coalesce(pct_fim_z, 0),
          nova  = is.na(var_rel) & pct_ini_z == 0 & pct_fim_z >= 1 &
                  as.character(classe_n2) != "Outros usos",
          faixa = case_when(
            nova           ~ "G5",                        # classe surgida: ganho > 200%
            is.na(var_rel) ~ "SD",
            var_rel < 0    ~ paste0("P", pmax(1, findInterval(-var_rel, FAIXAS_PERDA, left.open = TRUE))),
            TRUE           ~ paste0("G", pmax(1, findInterval(var_rel, FAIXAS_GANHO, left.open = TRUE)))),
          faixa  = factor(faixa, levels = NIVEIS_FX),
          rotulo = case_when(nova ~ "nova", faixa == "SD" ~ "s.d.", TRUE ~ coalesce(rotulo, "")),
          cor_texto = if_else(faixa == "SD", "grey45", .cor_texto_contraste(CORES_FX[as.character(faixa)])))
      # Mesma ordem de unidades das sínteses S1–S4
      if (exists(".ordem_unidades"))
        df_delta <- df_delta %>%
          mutate(unidade_analise = factor(as.character(unidade_analise),
                                          levels = rev(.ordem_unidades(unidade_analise))))

      p_hm <- ggplot(df_delta, aes(x = classe_n2, y = unidade_analise, fill = faixa)) +
        geom_tile(color = "white", linewidth = 0.35) +
        geom_text(aes(label = rotulo, color = cor_texto,
                      fontface = if_else(faixa == "SD", "plain", "bold")),
                  size = .mm(2.8)) +
        scale_color_identity() +
        scale_fill_manual(values = CORES_FX, guide = "none", drop = FALSE) +
        scale_x_discrete(labels = function(x) str_wrap(x, width = 12)) +
        scale_y_discrete(labels = function(x) .quebrar(x, LARGURA_EIXO)) +
        labs(x = NULL, y = NULL) +
        theme_minimal(base_size = .pt(11)) +
        # hjust = vjust = 1: o fim do rótulo inclinado cai exatamente sob a coluna
        theme(axis.text.x = element_text(angle = 40, hjust = 1, vjust = 1, size = .pt(9),
                                         lineheight = 0.9),
              axis.text.y = element_text(size = .pt(9.5), lineheight = 0.9),
              panel.grid  = element_blank(),
              plot.margin = margin(4, 12, 2, 10))

      # Faixa de legenda (embaixo): 5 tons de perda | sem dado | 5 tons de ganho
      leg <- data.frame(faixa = factor(NIVEIS_FX, levels = NIVEIS_FX), x = c(1:5, 6.25, 7.5:11.5),
                        rot = sub(" a ", "\na ", c(rev(ROT_PERDA), "Sem dado", ROT_GANHO)))
      leg$rot[leg$faixa == "SD"] <- "Sem\ndado"
      leg$cor_txt <- if_else(leg$faixa == "SD", "grey25", .cor_texto_contraste(CORES_FX[as.character(leg$faixa)]))
      p_leg <- ggplot(leg, aes(x = x, y = 1, fill = faixa)) +
        geom_tile(width = c(rep(1, 5), 1.3, rep(1, 5)), height = 0.95, color = "white", linewidth = 0.6) +
        geom_text(aes(label = rot, color = cor_txt), size = .mm(2.4), lineheight = 0.85) +
        annotate("text", x = 3, y = 1.75, label = "Perda relativa (%)", size = .mm(2.8),
                 fontface = "bold", color = CORES_PERDA[4]) +
        annotate("text", x = 9.5, y = 1.75, label = "Ganho relativo (%)", size = .mm(2.8),
                 fontface = "bold", color = CORES_GANHO[4]) +
        scale_fill_manual(values = CORES_FX, guide = "none") +
        scale_color_identity() +
        # Sem margem lateral (o patchwork a repetiria no heatmap e o
        # estreitaria): a faixa é centralizada pela própria escala x.
        coord_cartesian(xlim = c(0.45, 12.05), ylim = c(0.5, 2.05), clip = "off") +
        theme_void() +
        theme(plot.margin = margin(2, 0, 4, 0))

      (p_hm / p_leg) +
        plot_layout(heights = c(1, 0.13)) +
        plot_annotation(
          title    = .quebrar(paste0("Variação relativa da participação das classes de cobertura e ",
                                     "uso da terra por unidade de análise (", ano_ini_hm, "–",
                                     ano_fim_hm, ")")),
          subtitle = paste0("Cor e rótulo: variação relativa da participação de cada classe na área ",
                            "da unidade (%); \"nova\": classe ausente em ", ano_ini_hm, "; \"s.d.\": ",
                            "sem dado (classe com menos de 1% nos dois anos ou ausente na unidade); ",
                            "classes com menos de 1% agrupadas em \"Outros usos\""),
          caption  = CAPTION_PADRAO,
          theme = theme(plot.title = element_text(face = "bold", size = .tit(12), hjust = 0,
                                                  lineheight = 1.05),
                        plot.title.position = "plot",
                        plot.subtitle = element_text(color = "grey50", size = .pt(8.5), hjust = 0),
                        plot.caption  = element_text(color = "grey55", size = .pt(7), hjust = 1)))
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
        if (length(m) == 0 || !nzchar(m)) .iniciais(x) else m
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
                   shape=21, size=.sz(4.5), stroke=.sz(1.4),
                   fill=adjustcolor(cor_unid[df_1985$unidade_analise], alpha.f=0.25),
                   show.legend=FALSE) +
        # Pontos 2024 — círculo cheio, cor plena
        geom_point(data=df_2024,
                   aes(x=Natural, y=Antropico, color=unidade_analise),
                   shape=19, size=.sz(4.5), show.legend=TRUE) +
        # Rótulo: id_curto em 1985 (abaixo) e 2024 (acima)
        geom_text(data=df_1985,
                  aes(x=Natural, y=Antropico, label=paste0(id_curto, "'", substr(a_ini_d, 3, 4)), color=unidade_analise),
                  size = .mm(2.8), fontface="bold", vjust=2.4, show.legend=FALSE) +
        geom_text(data=df_2024,
                  aes(x=Natural, y=Antropico, label=paste0(id_curto, "'", substr(a_fim_d, 3, 4)), color=unidade_analise),
                  size = .mm(2.8), fontface="bold", vjust=-1.6, show.legend=FALSE) +
        scale_color_manual(
          values = cor_unid,
          name   = NULL,
          labels = setNames(.quebrar(leg_disp$unidade_analise, LARGURA_LEGENDA),
                            leg_disp$unidade_analise)
        ) +
        guides(color = guide_legend(
          ncol = if (ABNT) 2 else NULL,
          nrow = if (ABNT) NULL else ceiling(n_unid/3),
          override.aes = list(shape=19, size=.sz(4))
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
          title    = .quebrar(paste0("Trajetória da cobertura natural e antrópica por unidade de ",
                                     "análise (", a_ini_d, "–", a_fim_d, ")")),
          subtitle = paste0("Círculo vazado: ", a_ini_d, "; círculo cheio: ", a_fim_d,
                            "; seta: trajetória da unidade. Natural: Floresta e Vegetação ",
                            "Herbácea e Arbustiva; antrópica: Agropecuária e Área não Vegetada"),
          x="Cobertura Natural (%)", y="Cobertura Antrópica (%)",
          caption=CAPTION_PADRAO
        ) +
        coord_equal() +
        tema_amp +
        theme(
          panel.grid      = element_line(color="grey93", linewidth=0.3),
          legend.position = "bottom",
          legend.text     = element_text(size = .pt(8.5), lineheight=0.9),
          legend.key.size = unit(if (ABNT) 0.45 else 0.8,"cm")
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
      
      area_total_mb <- sum(df_mb$area_ha)

      # 1) Classes < 1% da paisagem NOS DOIS ANOS -> "Outros usos".
      #    (Olhar só a origem escondia classes que cresceram — ex.: uma
      #    silvicultura de 0,7% em 1985 e 2,3% em 2024.)
      .pequenas_mb <- .classes_pequenas(df_mb, 1)
      df_mb <- df_mb %>%
        mutate(
          orig_n2 = if_else(orig_n2 %in% .pequenas_mb, "Outros usos", orig_n2),
          dest_n2 = if_else(dest_n2 %in% .pequenas_mb, "Outros usos", dest_n2)
        ) %>%
        group_by(orig_n2, dest_n2) %>%
        summarise(area_ha = sum(area_ha, na.rm = TRUE), .groups = "drop")

      # 2) Transições exibidas: >= 0,1% da paisagem OU >= 1% da área da
      #    classe de origem (mesma leitura da matriz em % da origem). Só o
      #    corte pela paisagem ocultava transições relevantes de classes
      #    menores (ex.: Formação Savânica -> Mineração, 4% da origem).
      df_mb <- df_mb %>%
        group_by(orig_n2) %>% mutate(pct_origem = area_ha / sum(area_ha) * 100) %>% ungroup() %>%
        filter(area_ha >= area_total_mb * 0.001 | pct_origem >= 1)
      
      # Classificar origem e destino como Natural ou Antrópico
      .nomes_naturais_mb <- c(
        "Formação Florestal","Formacao Florestal","Floresta",
        "Formação Savânica","Formacao Savanica","Savana",
        "Formação Campestre","Formacao Campestre","Campo",
        "Mangue","Apicum","Campo Alagado e Área Pantanosa","Floresta Alagável",
        "Restinga Arbórea","Restinga Herbácea",
        "Restinga Arborea","Restinga Herbacea",
        "Afloramento Rochoso","Rio, Lago e Oceano","Corpo Dagua"
      )
      df_mb <- df_mb %>%
        mutate(
          nat_orig = .norm(orig_n2) %in% .norm(.nomes_naturais_mb),
          nat_dest = .norm(dest_n2) %in% .norm(.nomes_naturais_mb),
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
        # Camada invisível só para a legenda de tamanho: com cor fixa, o
        # ggplot desenha a chave de todas as faixas, inclusive as sem dados.
        geom_point(aes(size = faixa_pct), color = "grey40", alpha = 0, show.legend = TRUE) +
        geom_point(aes(size = faixa_pct, color = tipo_eco), alpha = 0.88,
                   show.legend = c(size = FALSE, colour = TRUE)) +
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
          size = .mm(2.4), fontface = "bold", color = "grey10"
        ) +
        scale_size_manual(
          values = c("< 2,5%" = .sz(5), "2,5–5%" = .sz(10), "5–10%" = .sz(16), "> 10%" = .sz(24)),
          name   = "Área transicionada\n(tamanho: % da paisagem;\nrótulos: hectares)",
          # limits (e não só breaks): faixas sem dados também aparecem na legenda
          limits = c("< 2,5%", "2,5–5%", "5–10%", "> 10%"),
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
        # Um único bloco de legenda: tamanhos (2 × 2) ao lado dos tipos (1 coluna)
        guides(size  = guide_legend(order = 1, nrow = 2, byrow = TRUE, title.position = "top",
                                    override.aes = list(alpha = 1)),
               color = guide_legend(order = 2, ncol = 1, title.position = "top",
                                    override.aes = list(size = .sz(5)))) +
        labs(
          title    = .quebrar(paste0("Matriz de transição da cobertura e uso da terra (",
                                     ANO_INI, "–", ANO_FIM, ") – ", rec_geral), LARGURA_TITULO),
          subtitle = paste0("Tamanho da bolha: faixa de área transicionada (% da paisagem); rótulo: ",
                            "área (ha); diagonal: permanência na mesma classe; exibidas as transições ",
                            "com ao menos 0,1% da paisagem ou 1% da classe de origem; classes com ",
                            "menos de 1% da área nos dois anos agrupadas em \"Outros usos\""),
          x = paste0("Destino (", ANO_FIM, ")"),
          y = paste0("Origem (", ANO_INI, ")"),
          caption = CAPTION_PADRAO
        ) +
        coord_cartesian(clip = "off") +
        tema_amp +
        theme(
          axis.text.x     = element_text(angle = 45, hjust = 1, vjust = 1, size = .pt(7.5),
                                         lineheight = 0.85),
          axis.text.y     = element_text(size = .pt(8.5)),
          panel.grid      = element_line(color = "grey92", linewidth = 0.3),
          legend.position  = "bottom",
          legend.box       = "horizontal",
          legend.box.just  = "top",           # as duas legendas alinhadas pelo topo
          legend.title     = element_text(size = .pt(8.5), face = "bold", lineheight = 1.05),
          legend.spacing.x = unit(0.8, "cm"),
          legend.spacing.y = unit(0.15, "cm"),
          legend.key.size  = unit(0.45, "cm"),
          legend.text      = element_text(size = .pt(8.5)),
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
                   size = .mm(2.6), fontface = "bold", color = "grey15",
                   fill = alpha("white", 0.82),
                   linewidth = 0.3, label.padding = unit(0.06, "lines")) +
        # Mesmas cores de ganho/perda do painel H (azul/laranja): o verde e o
        # vermelho ficam reservados à manutenção/alteração do painel b).
        scale_fill_manual(values = c("Ganho" = "#2980b9", "Perda" = "#e67e22"),
                          guide = "none") +
        scale_x_continuous(
          labels = label_number(accuracy = 0.1, decimal.mark = ",", suffix = " p.p."),
          expand = expansion(mult = 0.12)
        ) +
        labs(title = "a) Variação líquida da participação",
             subtitle = "Rótulo: variação relativa (%)",
             x = "Variação (p.p.)", y = NULL) +
        theme_minimal(base_size = .pt(10)) +
        theme(plot.title    = element_text(face = "bold", size = .pt(10), hjust = 0),
              plot.subtitle = element_text(size = .pt(8), color = "grey50"),
              axis.text.y   = element_text(size = .pt(8.5)),
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
        geom_label(data = df_alt_u %>% filter(pct_tipo >= if (ABNT) 14 else 7),
                   aes(x = x_meio, y = y_num,
                       label = paste0(number(pct_tipo, accuracy = 0.1,
                                             decimal.mark = ","), "%")),
                   size = .mm(2.6), fontface = "bold", color = "grey15",
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
        labs(title    = "b) Manutenção × alteração",
             subtitle = "Percentual da área de origem de cada classe",
             x = "Área de origem (%)", y = NULL) +
        theme_minimal(base_size = .pt(10)) +
        theme(plot.title    = element_text(face = "bold", size = .pt(10), hjust = 0),
              plot.subtitle = element_text(size = .pt(8), color = "grey50"),
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
          title    = .quebrar(paste0("Dinâmica da cobertura e uso da terra por classe (",
                                     ANO_INI, "–", ANO_FIM, ") – ",
                                     gsub("_"," ", unidade_nome)), LARGURA_TITULO),
          subtitle = paste0("a) variação líquida da participação na área total, em pontos ",
                            "percentuais (p.p.); b) proporção da área de cada classe em ",
                            ANO_INI, " mantida ou convertida em ", ANO_FIM),
          caption  = CAPTION_PADRAO,
          theme    = theme(
            plot.title    = element_text(face = "bold", size = .tit(13), hjust = 0,
                                         lineheight = 1.1),
            plot.subtitle = element_text(color = "grey45", size = .pt(9)),
            plot.caption  = element_text(color = "grey55", size = .pt(7), hjust = 1),
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
      
      # Agregar classes < 2% da área total NOS DOIS ANOS → "Outros usos"
      # (só a origem escondia classes que cresceram, como a silvicultura)
      .peq_su <- .classes_pequenas(df_su, 2)
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
      
      # Classes com menos de LIMIAR_ROT_SANKEY da área têm bloco baixo
      # demais para o texto: o rótulo vai para FORA da barra (à esquerda
      # em ANO_INI, à direita em ANO_FIM), com linha de chamada e
      # afastamento automático entre rótulos vizinhos (ggrepel).
      LIMIAR_ROT_SANKEY <- 0.045
      larg_su <- if (ABNT) 0.42 else 1/3   # blocos largos: o nome cabe em 2 linhas
      tot_su  <- sum(df_su$area_ha)
      .rot_su <- function(stratum, prop)
        paste0(str_wrap(stratum, 16), "\n(",
               number(prop * 100, accuracy = 0.1, decimal.mark = ","), "%)")
      .rot_externo <- function(lado, nudge, hjust)
        ggrepel::geom_text_repel(
          stat = "stratum",
          aes(label = ifelse(after_stat(prop) < LIMIAR_ROT_SANKEY & after_stat(x) == lado,
                             .rot_su(after_stat(stratum), after_stat(prop)), "")),
          nudge_x = nudge, hjust = hjust, direction = "y", size = .mm(2.3),
          fontface = "bold", color = "grey20", segment.color = "grey50",
          segment.size = 0.3, min.segment.length = 0, box.padding = 0.15,
          lineheight = 0.85, max.overlaps = Inf, seed = 1,
          ylim = c(0, tot_su))     # rótulos não passam da altura do diagrama

      ggplot(df_su,
             aes(axis1 = orig_n2, axis2 = dest_n2, y = area_ha)) +
        ggalluvial::geom_alluvium(aes(fill = orig_n2), alpha = 0.78, width = larg_su) +
        ggalluvial::geom_stratum(width = larg_su, fill = "grey92",
                                 color = "grey55", linewidth = 0.3) +
        # Rótulo do stratum: nome da classe + % no respectivo ano
        geom_text(stat = "stratum",
                  aes(label = ifelse(after_stat(prop) >= LIMIAR_ROT_SANKEY,
                                     paste0(str_wrap(after_stat(stratum), 16), "\n(",
                                            number(after_stat(prop)*100,
                                                   accuracy=0.1, decimal.mark=","), "%)"),
                                     "")),
                  size = .mm(2.3), fontface = "bold", color = "grey20",
                  lineheight = 0.85) +
        # Moldura fechando o diagrama (blocos + fluxos), inclusive no topo
        annotate("rect", xmin = 1 - larg_su / 2, xmax = 2 + larg_su / 2,
                 ymin = 0, ymax = tot_su, fill = NA, color = "grey40", linewidth = 0.5) +
        # Classes pequenas: rótulo externo (esquerda em ANO_INI, direita em ANO_FIM)
        .rot_externo(1, -(larg_su / 2 + 0.08), 1) +
        .rot_externo(2,  (larg_su / 2 + 0.08), 0) +
        scale_fill_manual(values = cores_su, guide = "none") +
        scale_x_discrete(
          limits = c(as.character(ANO_INI), as.character(ANO_FIM)),
          expand = expansion(add = 0.62)
        ) +
        # Sem eixo vertical: o percentual de cada bloco já comunica a proporção
        scale_y_continuous(expand = expansion(mult = 0.01)) +
        labs(
          title    = .quebrar(paste0("Fluxos de transição entre classes de cobertura e uso da terra (",
                                     ANO_INI, "–", ANO_FIM, ") – ",
                                     gsub("_"," ", unidade_nome)), min(65, LARGURA_TITULO)),
          subtitle = paste0("Espessura dos fluxos proporcional à área (ha); classes com menos de ",
                            "2% da área nos dois anos agrupadas em \"Outros usos\"; classes com ",
                            "menos de 4,5% rotuladas fora da barra"),
          x = NULL, y = NULL, caption = CAPTION_PADRAO
        ) +
        tema_amp +
        theme(axis.text.x = element_text(face = "bold", size = .pt(11)),
              axis.text.y = element_blank(), axis.ticks.y = element_blank(),
              panel.grid  = element_blank())
    }
    
    # ---- H: Variação líquida da participação por unidade ----
    .grafico_variacao_liquida <- function(unidade_nome) {
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
                   hjust=0.5, size = .mm(2.5), fontface="bold", color="grey15",
                   fill=alpha("white",0.82), linewidth=0.3,
                   label.padding=unit(0.06,"lines")) +
        scale_fill_manual(values=c("Ganho"="#2980b9","Perda"="#e67e22"),
                          guide="none") +
        scale_x_continuous(labels=label_number(accuracy=0.1,decimal.mark=",",
                                               suffix=" p.p."),
                           expand=expansion(mult=0.12)) +
        labs(title    = .quebrar(paste0("Variação líquida da participação das classes de cobertura ",
                                         "e uso da terra (", a_ini_h, "–", a_fim_h, ") – ",
                                         gsub("_"," ",unidade_nome)), LARGURA_TITULO),
             subtitle = paste0("Barras: variação da participação na área total, em pontos ",
                               "percentuais (p.p.); rótulo: variação relativa (%); classes com ",
                               "menos de 1% agrupadas em \"Outros usos\""),
             x = "Variação (p.p.)", y = NULL, caption = CAPTION_PADRAO) +
        tema_amp +
        theme(axis.text.y = element_text(size = .pt(10)),
              panel.grid.major.x = element_line(color = "grey90", linewidth = 0.3),
              panel.grid.major.y = element_blank())
      # O Sankey da unidade é gerado à parte (E2): lado a lado ou empilhado
      # com estas barras, nenhum dos dois ficava legível.
      p_h_esq
    }
    
    # ---- S: Sínteses entre unidades (unidade × classe) ----
    # S1: matriz de bolhas da variação líquida (p.p.)
    # S2: um painel por classe, barras = unidades (variação líquida, p.p.)
    # S3: permanência — % da área de cada classe em ANO_INI mantida em ANO_FIM
    # S4: combinação S1 + S3 (mesma grade de unidades e classes)

    # Sigla curta da unidade: numeral romano do início do nome ou iniciais
    .id_unidade <- function(x) {
      m <- regmatches(x, regexpr("^[IVXivx]+[ab]?(?=\\s|-|$)", x, perl = TRUE))
      if (length(m) == 0 || !nzchar(m)) .iniciais(x) else m
    }
    # Ordem das unidades: numeral romano (I, Ia, Ib, II...), depois as demais
    # em ordem alfabética, e o recorte completo ("Shape Completo") por último
    .ordem_unidades <- function(nomes) {
      nomes <- unique(as.character(nomes))
      ids   <- vapply(nomes, .id_unidade, "")
      rom   <- suppressWarnings(as.integer(utils::as.roman(sub("[AB]$", "", toupper(ids)))))
      ok    <- grepl("^[IVX]+[AB]?$", toupper(ids)) & !is.na(rom)
      chave <- ifelse(ok, sprintf("0%03d%s", rom, tolower(sub("^[IVXivx]+", "", ids))),
                      paste0("1", tolower(nomes)))
      # área total por último (nome padrão ou o escolhido no plugin)
      chave[.norm(nomes) == "shape completo" |
            nomes %in% get0("NOME_AREA_TOTAL", ifnotfound = character(0))] <- "9"
      nomes[order(chave)]
    }

    .dados_sintese <- function() {
      base <- cobertura %>%
        filter(cod_classe != 255) %>%
        mutate(classe = .cod_para_n2nome(cod_classe), pct = percentual * 100,
               ano = as.character(round(as.numeric(ano)))) %>%
        group_by(unidade_analise, ano, classe) %>%
        summarise(pct = sum(pct, na.rm = TRUE), .groups = "drop")
      # classes < 1% em todas as unidades e anos -> "Outros usos"
      peq <- base %>% group_by(classe) %>% summarise(mx = max(pct), .groups = "drop") %>%
        filter(mx < 1) %>% pull(classe)
      base <- base %>%
        mutate(classe = if_else(classe %in% peq, "Outros usos", classe)) %>%
        group_by(unidade_analise, ano, classe) %>%
        summarise(pct = sum(pct), .groups = "drop")
      a1 <- as.character(ANO_INI); a2 <- as.character(ANO_FIM)
      dv <- base %>% filter(ano %in% c(a1, a2)) %>%
        pivot_wider(names_from = ano, values_from = pct, values_fill = 0) %>%
        mutate(delta = .data[[a2]] - .data[[a1]],
               sinal = if_else(delta >= 0, "Ganho", "Perda"))
      # classes: dos maiores ganhos médios às maiores perdas; "Outros usos" no fim
      ord_cl <- dv %>% group_by(classe) %>% summarise(m = mean(delta), .groups = "drop") %>%
        arrange(desc(m)) %>% pull(classe)
      ord_cl <- c(setdiff(ord_cl, "Outros usos"), intersect(ord_cl, "Outros usos"))
      ord_un <- .ordem_unidades(dv$unidade_analise)
      ids    <- make.unique(vapply(ord_un, .id_unidade, ""), sep = "")
      ids_map <- setNames(ids, ord_un)
      # permanência: % da área de cada classe de origem mantida na mesma classe
      dp <- alt %>%
        mutate(orig = .cod_para_n2nome(cod_orig), dest = .cod_para_n2nome(cod_dest),
               orig = if_else(orig %in% ord_cl, orig, "Outros usos"),
               dest = if_else(dest %in% ord_cl, dest, "Outros usos")) %>%
        group_by(unidade_analise, orig) %>%
        summarise(tot = sum(area_ha, na.rm = TRUE),
                  mant = sum(area_ha[orig == dest], na.rm = TRUE), .groups = "drop") %>%
        filter(tot > 0) %>%
        mutate(pct_mant = mant / tot * 100) %>%
        rename(classe = orig)
      .fat <- function(df) df %>%
        mutate(unidade_analise = factor(as.character(unidade_analise), levels = rev(ord_un)),
               classe = factor(classe, levels = ord_cl),
               id = factor(ids_map[as.character(unidade_analise)], levels = ids))
      list(dv = .fat(dv), dp = .fat(dp), a1 = a1, a2 = a2, ord_cl = ord_cl,
           chave = paste(paste0(ids, " = ", ord_un), collapse = "; "))
    }

    COR_GANHO_PERDA <- c("Ganho" = "#2980b9", "Perda" = "#e67e22")
    .num_pp <- function(x) number(x, accuracy = 0.1, decimal.mark = ",", style_positive = "plus")
    .eixo_classes_topo <- function()
      scale_x_discrete(position = "top", drop = FALSE,
                       labels = function(x) str_wrap(x, 14))
    .tema_sintese <- function()
      tema_amp +
      theme(axis.text.x.top = element_text(angle = 40, hjust = 0, vjust = 0,
                                           size = .pt(9), lineheight = 0.85),
            axis.text.y = element_text(size = .pt(9), lineheight = 0.9),
            panel.grid.major.x = element_blank(),
            legend.position = "bottom",
            # folga à direita: o nome inclinado da última classe não é cortado
            plot.margin = margin(6, 28, 6, 6))

    .grafico_S1 <- function(ds, titulo = TRUE) {
      # scale_size_area: diâmetro (mm) ∝ raiz do valor. O rótulo sobe o raio
      # da bolha + uma folga, medidos em alturas de texto (unidade do vjust).
      max_mm <- if (ABNT) 9 else 14
      txt_mm <- .mm(2.4)
      dv <- ds$dv %>%
        mutate(raio_mm = max_mm / 2 * sqrt(abs(delta) / max(abs(delta), na.rm = TRUE)),
               vj = -(raio_mm + 0.8) / txt_mm - 0.2)
      ggplot(dv, aes(x = classe, y = unidade_analise)) +
        geom_point(aes(size = abs(delta), color = sinal), alpha = 0.9) +
        geom_text(aes(label = .num_pp(delta), vjust = vj), size = txt_mm,
                  color = "grey15", fontface = "bold") +
        scale_size_area(max_size = max_mm, guide = "none") +
        scale_color_manual(values = COR_GANHO_PERDA, name = NULL) +
        .eixo_classes_topo() +
        scale_y_discrete(labels = function(x) .quebrar(x, LARGURA_EIXO + 8),
                         expand = expansion(add = c(0.5, 0.9))) +
        labs(title = if (titulo) .quebrar(paste0(
               "Variação líquida da participação das classes de cobertura e uso da terra por ",
               "unidade de análise (", ds$a1, "–", ds$a2, ")")) else "a) Variação líquida da participação (p.p.)",
             subtitle = paste0("Tamanho da bolha proporcional à variação, em pontos percentuais ",
                               "(p.p.); azul indica ganho e laranja, perda"),
             x = NULL, y = NULL, caption = CAPTION_PADRAO) +
        .tema_sintese()
    }

    .grafico_S2 <- function(ds) {
      n_un <- nlevels(ds$dv$id)
      ggplot(ds$dv, aes(x = id, y = delta, fill = sinal)) +
        geom_col(width = 0.7, color = "grey35", linewidth = 0.2) +
        geom_hline(yintercept = 0, color = "grey30", linewidth = 0.4) +
        geom_text(aes(label = .num_pp(delta), vjust = if_else(delta >= 0, -0.3, 1.2)),
                  size = .mm(2.3), color = "grey15") +
        facet_wrap(~classe, ncol = 3, scales = "free_y", labeller = rotulo_facet) +
        scale_fill_manual(values = COR_GANHO_PERDA, guide = "none") +
        scale_y_continuous(expand = expansion(mult = 0.28),
                           labels = function(x) number(x, accuracy = if (max(abs(x), na.rm = TRUE) < 3) 0.1 else 1,
                                                       decimal.mark = ",")) +
        labs(title = .quebrar(paste0("Variação líquida da participação por classe de cobertura e uso ",
                                     "da terra: comparação entre unidades de análise (",
                                     ds$a1, "–", ds$a2, ")")),
             subtitle = paste0("Variação da participação na área total, em pontos percentuais (p.p.); ",
                               "azul indica ganho e laranja, perda"),
             x = NULL, y = "Variação (p.p.)",
             caption = .quebrar(paste0("Unidades: ", ds$chave), if (ABNT) 120 else 160)) +
        tema_amp +
        theme(panel.grid.major.y = element_line(color = "grey92", linewidth = 0.3),
              axis.text.x = element_text(face = "bold", size = .pt(if (n_un > 8) 7 else 8.5),
                                         angle = if (n_un > 8) 90 else 0,
                                         vjust = 0.5, hjust = if (n_un > 8) 1 else 0.5),
              strip.text = element_text(size = .pt(9.5)),
              plot.caption = element_text(hjust = 0, size = .pt(7.5), color = "grey25",
                                          lineheight = 1.1))
    }

    .grafico_S3 <- function(ds, titulo = TRUE) {
      ggplot(ds$dp, aes(x = classe, y = unidade_analise, fill = pct_mant)) +
        geom_tile(color = "white", linewidth = 0.6) +
        geom_text(aes(label = paste0(number(pct_mant, accuracy = 1), "%"),
                      color = if_else(pct_mant > 60, "white", "grey15")),
                  size = .mm(2.6), fontface = "bold") +
        scale_color_identity() +
        scale_fill_gradient(low = "#fbe3d3", high = "#1a7a3c", limits = c(0, 100),
                            name = "Área de origem mantida (%)",
                            guide = guide_colorbar(barwidth = unit(7, "cm"),
                                                   barheight = unit(0.3, "cm"),
                                                   title.position = "top")) +
        .eixo_classes_topo() +
        scale_y_discrete(labels = function(x) .quebrar(x, LARGURA_EIXO + 8)) +
        labs(title = if (titulo) .quebrar(paste0(
               "Permanência das classes de cobertura e uso da terra por unidade de análise (",
               ds$a1, "–", ds$a2, ")")) else "b) Permanência da área de origem (%)",
             subtitle = paste0("Percentual da área de cada classe em ", ds$a1,
                               " que permaneceu na mesma classe em ", ds$a2),
             x = NULL, y = NULL, caption = CAPTION_PADRAO) +
        .tema_sintese() +
        theme(panel.grid = element_blank(),
              legend.title = element_text(size = .pt(8.5)))
    }

    .grafico_S4 <- function(ds) {
      p1 <- .grafico_S1(ds, titulo = FALSE) + labs(subtitle = NULL, caption = NULL) +
        theme(plot.title = element_text(size = .pt(10), face = "bold"))
      p3 <- .grafico_S3(ds, titulo = FALSE) + labs(subtitle = NULL, caption = NULL) +
        theme(plot.title = element_text(size = .pt(10), face = "bold"),
              axis.text.x.top = element_blank(), axis.ticks.x.top = element_blank())
      (p1 / p3) + plot_layout(heights = c(1.15, 1)) +
        plot_annotation(
          title = .quebrar(paste0("Variação líquida e permanência das classes de cobertura e uso ",
                                  "da terra por unidade de análise (", ds$a1, "–", ds$a2, ")")),
          subtitle = paste0("a) variação da participação na área total, em pontos percentuais ",
                            "(p.p.); b) percentual da área de cada classe em ", ds$a1,
                            " que permaneceu na mesma classe em ", ds$a2),
          caption = CAPTION_PADRAO,
          theme = theme(plot.title = element_text(face = "bold", size = .tit(13), hjust = 0,
                                                  lineheight = 1.05),
                        plot.subtitle = element_text(color = "grey45", size = .pt(9)),
                        plot.caption = element_text(color = "grey55", size = .pt(7), hjust = 1)))
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
                                adj = c(0, 0.5), cex = if (ABNT) 0.85 else 0.65, font = 2)
        },
        bg.border = NA
      )
      titulo_ch <- paste0("Diagrama de cordas das transições entre classes de cobertura ",
                          "e uso da terra (", ANO_INI, "–", ANO_FIM, ") – ", rec_geral)
      if (ABNT) {
        LEGENDAS_ABNT[["F_chord_transicao"]] <<- list(
          titulo = titulo_ch,
          nota   = "Largura das cordas proporcional à área (ha) transicionada da classe de origem para a de destino")
        if (TITULO_NA_FIGURA_ABNT)
          title(main = .quebrar(titulo_ch, 60), cex.main = 1.05, font.main = 2,
                col.main = "grey10", adj = 0)
      } else {
        title(main = .quebrar(titulo_ch), cex.main = 1, font.main = 2, col.main = "grey20")
        mtext(CAPTION_PADRAO, side = 1, line = 2, cex = 0.65, col = "grey50")
      }
      circlize::circos.clear()
    }
    
    # -- Gerar e exportar família 5 --
    
    message("\n[B] PCA — perfil de cobertura por unidade...")
    p_b <- tryCatch(.grafico_pca_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_b)) {
      salvar_grafico("B_pca_cobertura", p_b, w = 13, h = 7, h_abnt = 17)
    }

    message("[C] Heatmap — unidades x classes...")
    p_c <- tryCatch(.grafico_heatmap_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_c)) {
      salvar_grafico("C_heatmap_cobertura", p_c, w = 14, h = 6.5,
                     h_abnt = 7 + 0.9 * length(unique(as.character(cob$unidade_analise))))
    }

    message("[S] Sinteses entre unidades — variacao liquida e permanencia...")
    ds_s <- tryCatch(.dados_sintese(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(ds_s)) {
      n_un_s <- nlevels(ds_s$dv$unidade_analise)
      n_cl_s <- length(ds_s$ord_cl)
      .salva_s <- function(nome, f, ...) {
        p <- tryCatch(f(ds_s), error = function(e) { message("  ERRO [", nome, "]: ", e$message); NULL })
        if (!is.null(p)) salvar_grafico(nome, p, ...)
      }
      .salva_s("S1_sintese_variacao_bolhas", .grafico_S1, w = 13, h = 3 + 0.7 * n_un_s,
               h_abnt = 5.5 + 1.25 * n_un_s)
      .salva_s("S2_sintese_variacao_por_classe", .grafico_S2, w = 12, h = 2 + 2.4 * ceiling(n_cl_s / 3),
               h_abnt = 4.5 + 4.2 * ceiling(n_cl_s / 3), manter_caption = TRUE)
      .salva_s("S3_sintese_permanencia", .grafico_S3, w = 13, h = 3 + 0.6 * n_un_s,
               h_abnt = 5 + 1.0 * n_un_s)
      .salva_s("S4_sintese_variacao_permanencia", .grafico_S4, w = 13, h = 5 + 1.3 * n_un_s,
               h_abnt = 8.5 + 2.2 * n_un_s)
    }

    message("[D] Dispersao — Cobertura Natural x Antropica...")
    p_d <- tryCatch(.grafico_dispersao_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_d)) {
      salvar_grafico("D_dispersao_natural_antropico", p_d, w = 12, h = 8, h_abnt = 18)
    }

    message("[E] Matriz de bolhas — fluxos de transicao (todos os pares origem x destino)...")
    p_e <- tryCatch(.grafico_sankey_mv(), error = function(e) { message("  ERRO: ", e$message); NULL })
    if (!is.null(p_e)) {
      salvar_grafico("E_matriz_bolhas_transicao", p_e, w = 8.27, h = 13, h_abnt = 20)
    }

    unidades_mv <- unique(as.character(cob$unidade_analise))
    unidades_mv <- unidades_mv[!is.na(unidades_mv) & nzchar(trimws(unidades_mv))]

    message("[G] Painel delta + manutencao/alteracao por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_g <- tryCatch(.grafico_painel_delta_alt(u_mv),
                      error=function(e){message("  ERRO [G] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_g)) { salvar_grafico(paste0("G_painel_delta_alt_",slug_mv),p_g,w=14,h=7,h_abnt=11) }
    }

    message("[E2] Sankey por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_e2 <- tryCatch(.grafico_sankey_unidade(u_mv),
                       error=function(e){message("  ERRO [E2] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_e2)) { salvar_grafico(paste0("E2_sankey_",slug_mv),p_e2,w=8.27,h=13,h_abnt=18) }
    }

    message("[H] Variacao liquida por unidade...")
    for (u_mv in unidades_mv) {
      slug_mv <- .slug(u_mv)
      p_h <- tryCatch(.grafico_variacao_liquida(u_mv),
                      error=function(e){message("  ERRO [H] ",u_mv,": ",e$message);NULL})
      if (!is.null(p_h)) { salvar_grafico(paste0("H_variacao_liquida_",slug_mv),p_h,w=10,h=7,h_abnt=11) }
    }
    
    message("[F] Chord diagram — transicoes circular...")
    if ("png" %in% FORMATO_SAIDA) {
      arq_chord <- file.path(pasta_saida, "F_chord_transicao.png")
      tryCatch({
        if (ABNT) {
          png(arq_chord, width = LARGURA_ABNT_CM, height = LARGURA_ABNT_CM,
              units = "cm", res = DPI_ABNT, pointsize = 9)
        } else {
          png(arq_chord, width = 2400, height = 2400, res = 200)
        }
        .grafico_chord_mv()
        dev.off()
        cat(" Salvo: F_chord_transicao.png\n")
      }, error = function(e) { dev.off(); message("  ERRO chord: ", e$message) })
    }
    
  } # fim exists(cob)
} # fim GERAR_MULTIVAR

.escrever_legendas_abnt()
message("\n=== Concluido! Arquivos em: ", pasta_saida, " ===\n")