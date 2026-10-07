# Análise de drone no QGIS

Skill que guia a **ClaudIA QGIS** (a IA do membro conectada ao QGIS pelo
plugin ClaudIA QGIS) na análise de um **ortomosaico de drone**: restituição
das linhas de plantio, falhas de plantio, contagem de plantas e segmentação
de copas e daninhas — com janelas de validação, tolerância declarada e
margem de erro em todo número entregue.

**O que ela faz:**

- **Diagnostica a imagem antes de qualquer conta**: pixel, SRC (precisa ser
  projetado em metros, UTM), banda alfa, GSD real; e o perfil do talhão —
  cobertura vegetal, orientação e espaçamento das linhas por FFT,
  periodicidade ao longo da linha (espaçamento entre plantas).
- **Linhas de plantio** por FFT 2D em blocos de 20 m + demodulação
  complexa, unindo os segmentos entre blocos. Validada em duas áreas de
  cana (4 e 5 cm de pixel): 100% das fileiras e desvio lateral p90 de
  14–28 cm.
- **Falhas de plantio** com o motor híbrido v3 (plantas por pico do perfil
  + solo exposto + **limiar local** por trecho de ~25 m): grava todas as
  falhas candidatas com comprimento de solo e distância entre plantas, e o
  **critério do usuário se aplica depois**, sem rodar de novo. Teste às
  cegas: 85% das falhas encontradas, −2 pp no percentual.
- **Contagem de plantas** por mapa do alvo (k-means nas cores) suavizado +
  máximos locais, sempre depois de diagnosticar o espaçamento (foi isso que
  mostrou que uma referência de pomar dividia copas: eram 56 plantas, e
  não 91). Pomar: F1 de 89–92%.
- **Segmentação** (só quando pedida) pelo caminho clássico — watershed do
  scipy, sem instalar nada —, por SAM 2.1 num Python separado do QGIS ou
  pelos plugins que o usuário já tenha; outras plantas e daninhas por forma
  e posição fora da linha, conferidas uma a uma.
- **Validação séria**: janelas de ajuste separadas das de teste, referência
  marcada ANTES de rodar o modelo (o usuário marca no QGIS, ou a IA lê
  recortes às cegas, em duas passadas), pareamento um a um com tolerância,
  margem de 95% por bootstrap de janelas inteiras.
- **Erros já vistos e como evitar** — camada temporária que some, `np.float64`
  que não grava, chamada cortada aos 60 s, limiar fixo que não transfere
  entre áreas, SAM automático inútil com copas encostadas, EPSG:3857
  inflando distâncias — numa tabela que a IA consulta antes de repetir.
- **Tudo em disco**: GeoPackage de resultados, `funcoes_drone.py` e
  `estado.json` na pasta `analise_drone/` ao lado do ortomosaico; chamadas
  de até ~40 s, rodando em lotes; só numpy, scipy e GDAL do Python do QGIS.

## Como usar

1. Instale a skill na sua IA (claude.ai → Configurações → Capacidades →
   Skills) — o zip desta pasta está na [release](../../../releases/latest)
   e no catálogo da comunidade agrônomo10X.
2. Abra o QGIS com o ortomosaico e o polígono da área útil carregados e
   conecte a ClaudIA QGIS (plugin). A skill confere a conexão logo no
   começo (`ping`, `get_project_info`, `get_layers`).
3. Peça o que precisa: "levante as linhas de plantio", "meça as falhas
   neste talhão", "conte as plantas", "segmente as copas". A IA pergunta
   de uma vez o que falta (área útil, espaçamento nominal, cultura,
   critério de falha), cria as janelas de validação e segue o roteiro —
   explicando o caminho em linguagem simples enquanto executa, sem entregar
   script para você rodar.
4. A entrega vem por talhão: números por hectare útil, o critério usado e
   de onde veio, o status da validação (janelas, referência, tolerância,
   métricas, margem) e onde cada camada ficou no GeoPackage.

Também serve de roteiro para **aula**: a seção 7 do playbook lista o que
preparar antes e a sequência que funciona ao vivo.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook: regras de ouro, preparação, os quatro
  desafios (linhas, falhas, contagem, segmentação), validação, erros já
  vistos, roteiro para aula, entrega e trechos de código prontos (Otsu sem
  scikit-image, leitura de bloco sem estourar o raster, pareamento com
  tolerância, núcleo do motor v3).
- `README.md` — este arquivo.

## Limites e postura

- Ortomosaico RGB de drone. Não serve para imagem de satélite, mapa de
  solo, interpolação ou vetor (para isso há outras skills da casa).
- Milho e soja jovens pedem pixel de até 1 cm; a 3–5 cm a skill avisa a
  expectativa baixa e mede mesmo assim, declarando a incerteza.
- Super-resolução por IA nunca entra na medição — só para visualizar.
- **Informação, não recomendação**: a skill entrega a medição. Replantio,
  dose, produto e manejo são decisão do responsável técnico pela área.
