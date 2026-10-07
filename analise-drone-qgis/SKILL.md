---
name: "analise-drone-qgis"
description: "Roteiro para analisar ortomosaico de drone no QGIS pela ClaudIA QGIS — linhas de plantio, falhas, contagem de plantas e segmentação — rápido, validado e evitando os erros já vistos."
---

# Análise de ortomosaico de drone no QGIS

Use quando o usuário tiver um ortomosaico de drone aberto no QGIS, com a ClaudIA QGIS conectada, e pedir:
- restituição de linhas;
- falhas de plantio;
- contagem de plantas;
- segmentação (copas, daninhas, outras plantas).

Não use para imagem de satélite, mapa de solo, interpolação ou vetor.

Esta skill diz **o que fazer e em que ordem**. Você escreve e roda o código com `execute_code`. Nunca entregue script para o usuário rodar; explique o caminho em linguagem simples enquanto executa.

## Regras de ouro

1. **Nenhum número sem validação.** Todo resultado vai com o status: "não validado", "validado nas janelas de ajuste" ou "validado às cegas". Junto, sempre: número de janelas, tolerância e métricas.
2. **O critério agronômico é do usuário.** Comprimento mínimo de falha, o que medir (solo exposto ou distância entre plantas), classes e meta de acurácia. Sem critério, ofereça Stolf (1986) para cana **como sugestão antiga** e registre a origem. Não recuse rodar por falta de critério.
3. **Grave tudo em disco.**
    - Resultados vão para um GeoPackage na pasta de trabalho, nunca para camada temporária: ela some ao fechar o QGIS.
    - As funções vão para um arquivo `.py` na mesma pasta: se a conversa for resumida, o código continua lá.
4. **Cada chamada do `execute_code` deve terminar em até ~40 s.** Teste num bloco, meça o tempo, e só então rode o talhão em lotes, gravando o parcial de cada lote.
5. **No Python do QGIS, só numpy, scipy e GDAL** (o scikit-learn às vezes existe; confira). Não há scikit-image nem OpenCV. Nunca rode `pip install` no Python do QGIS.
6. **`create_checkpoint` antes de alterar o projeto.** Avise que dá para voltar com `restore_checkpoint`.
7. **Super-resolução por IA nunca entra na medição.** Só para visualizar, sempre marcada como tal.
8. **Informação, não recomendação.** Entregue a medição. Replantio, dose, produto e manejo são decisão do responsável técnico.

## 0. Preparação (sempre)

1. **Confira a conexão e o projeto:** `ping`, depois `get_project_info` e `get_layers`. Ache o ortomosaico e o polígono da área.
2. **Leia o ortomosaico com `get_raster_info`:** pixel, SRC, bandas e extensão.
    - **SRC.** Precisa ser projetado em metros (UTM, SIRGAS 2000). Em EPSG:3857, distâncias e áreas saem infladas por 1/cos(latitude): ~8% nas distâncias a 23° S. Trabalhe em UTM ou corrija.
    - **Alfa.** Se houver banda 4, ela é a máscara de pixels válidos. Pixel com alfa 0 ou com r + g + b = 0 é inválido.
    - **Pixel de exatamente 5,0 cm.** Pode ser o padrão do OpenDroneMap e estar acima do GSD real das fotos. Pergunte se existe o `odm_report/stats.json` (campo `average_gsd`). Se as fotos forem bem mais finas, reprocessar o ortomosaico perto do GSD é o único ganho real de resolução.
3. **Pergunte de uma vez, numa mensagem só:**
    - a tarefa;
    - o polígono da área útil (sem carreadores e bordaduras);
    - o espaçamento nominal entre linhas e entre plantas, se souber;
    - a cultura (opcional);
    - para falhas, o critério.
4. **Crie a pasta de trabalho** `analise_drone/`, ao lado do ortomosaico, com:
    - `resultados.gpkg`;
    - `funcoes_drone.py`, importado com `sys.path.insert` + `importlib.reload`;
    - `estado.json`, com os parâmetros, as janelas e as versões.
5. **Meça o perfil da imagem** em 3–5 blocos de 20 m, antes de escolher o caminho:
    - cobertura vegetal (ExG acima do Otsu);
    - orientação e espaçamento das linhas (FFT);
    - **periodicidade ao longo da linha**, que dá o espaçamento entre plantas;
    - contraste planta–solo;
    - dossel aberto ou fechado.

    Proponha o arquétipo e peça confirmação:
    - linhas contínuas (cana);
    - plantas individuais em linha (grãos);
    - perene com copa em linha (citros, café, eucalipto);
    - sem linha definida.
6. **Antes de rodar o caminho, crie as janelas de validação** (seção 5).

**Índice padrão:** ExG = (2g − r − b) / (r + g + b), com r, g e b em float.

## 1. Restituição de linhas

**Caminho (validado em duas áreas de cana, a 4 e 5 cm)**
1. ExG reamostrado a ~8 cm (média, não vizinho mais próximo), em blocos de 20 m com 4 m de sobreposição.
2. **Em cada bloco, FFT 2D** do ExG, menos a média e com janela de Hann.
    - Procure o pico na faixa de período de 0,8–1,2× o espaçamento nominal (1,2–1,8 m para 1,5 m).
    - O vetor do pico dá a perpendicular às linhas; o período dá o espaçamento.
    - Se houver um segundo pico forte com outra orientação, é uma divisa entre blocos de plantio: trate as duas.
3. **Linhas do bloco.**
    - **Versão validada:** demodulação complexa (sinal analítico) na frequência achada. Suavize 1,5 m ao longo e 2,5 m através da fileira. A linha é a crista (fase zero), mantida onde a amplitude é suficiente.
    - **Versão rápida, para aula:** projete os pixels na direção perpendicular, faça o perfil médio e use os picos (distância mínima de 0,6× o espaçamento) como centros das fileiras. Valide nas janelas antes de usar.
4. **Use só o miolo de cada bloco** (descarte os 2 m de cada borda) para não duplicar linhas na sobreposição.
5. **Una os segmentos de blocos vizinhos** quando as pontas estiverem a até 0,35 m e o ângulo for menor que 30°.
6. **Grave no GPKG** com os campos `id`, `comprimento_m` e `bloco_orientacao`.

**Validação.** Janelas com 6 fileiras ou mais. Meça:
- % de fileiras encontradas;
- cobertura (comprimento detectado ÷ área válida ÷ espaçamento);
- espaçamento entre vizinhas (p10, mediana, p90);
- desvio lateral: o pico do perfil perpendicular deve cair a ~0 m da linha.

**Critério inicial:**
- espaçamento mediano a ±3% do nominal;
- cobertura de pelo menos 97%;
- desvio p90 de no máximo ⅕ do espaçamento.

**Resultado de referência:**
- **Cana a 4 cm:** 114 linhas e 32,4 km; mediana de 1,50 m; desvio p90 de 0,20–0,28 m.
- **Promisso a 5 cm:** a mesma receita, sem ajuste, deu 100% das fileiras e desvio p90 de 13,9 cm.

**Onde falha:**
- divisa entre blocos;
- bordas: linha extra em sulco sem cana emergida e trecho inicial sem linha;
- linhas curvas: a FFT serve para retas; para curvas, rastreie a linha.

## 2. Falhas de plantio (motor híbrido v3)

Precisa das linhas. **Limiar fixo não transfere entre áreas.** Na 2ª área, a receita da 1ª achou só 47% das falhas. Use o limiar local.

1. **Limiar local de solo.** Divida a área em trechos de ~25 m e calcule o Otsu do ExG dos pixels válidos de cada trecho. Então:
    - `t2` = Otsu − 0,02;
    - `th` = máx(0,05, `t2`).
2. **Perfil ao longo de cada linha,** a cada 5 cm:
    - em cada ponto, pegue o **maior** ExG numa faixa de ±0,15 m na perpendicular (interpolação bilinear);
    - suavize com gaussiana de 0,1 m (σ de 2 amostras).
3. **Plantas** são os picos do perfil com altura ≥ `th` e a pelo menos 0,1 m um do outro (`scipy.signal.find_peaks`).
4. **Falha.** Para cada par de plantas vizinhas a **mais de 0,5 m**, a falha vai do primeiro ao último ponto com perfil < `t2` entre elas (solo exposto). **Vãos nas pontas das linhas não contam.**
5. **Grave todas as falhas candidatas,** sem filtro, com os campos:
    - `linha_id`, `ini_m`, `fim_m`;
    - `comp_solo_m` e `dist_plantas_m`;
    - `limiar_local`.

    Assim o critério do usuário se aplica depois, sem rodar de novo.
6. **% de falha** = soma das falhas no critério ÷ comprimento de linha analisado. Entregue uma tabela com qualquer, ≥ 0,3, ≥ 0,5 e ≥ 1,0 m, mais o critério do usuário.

**Resultado de referência (Promisso, 5 cm, 114 km de linha):**
- 31.045 falhas candidatas, 21,2% de falha;
- teste às cegas: 85% das falhas encontradas, precisão de 69%, −2,0 pp no %.

**Cuidados que vão no relatório:**
- erro por janela de até ±12 pp: o número vale para o talhão, não para um trecho de 10 m;
- precisão de 60–69%: parte dos "falsos positivos" são vãos curtos (mediana de 0,35 m) que a referência não marcou;
- voo tardio piora tudo: o ideal é 30–45 dias após o corte.

**Não use** (já testados e piores):
- **presença por pixel com limiar fixo:** subestimou 4–10 pp, porque a folha vizinha cobre o vão;
- **distância entre plantas pura:** 42% de precisão com touceiras encostadas;
- **afinar parâmetros sem mudar o método:** 168 combinações e o erro parou em −4 pp.

## 3. Contagem de plantas

1. **Diagnostique o padrão de plantio antes de contar.** Faça a FFT do perfil ao longo de 3–5 fileiras: o período é o espaçamento entre plantas. Foi isso que mostrou que a primeira referência do pomar dividia copas: eram 56 plantas, e não 91.
2. **Mapa do alvo.**
    - K-means com 6 classes de cor (cromaticidade r e g, brilho), com amostra tirada **fora** das janelas de validação.
    - Dê peso 1 às classes de copa e 0,5 às duvidosas. Confira as classes olhando a imagem.
3. **Suavização gaussiana** com σ de ~0,15× o diâmetro da copa (0,35 m para copa de 2,3 m), a ~10 cm de resolução.
4. **Máximos locais**, sem scikit-image:
    - pixel igual ao `scipy.ndimage.maximum_filter` com raio = distância mínima;
    - valor acima do limiar (0,25 no mapa de 0 a 1);
    - distância mínima de ~0,65× o espaçamento entre plantas (1,6 m para 2,5 m).
5. **Variante igualmente boa:** ache a fileira e conte os picos ao longo dela.
6. **Grave os pontos** e reporte plantas por hectare útil, por talhão.

**Resultado de referência (pomar, 5 cm, fileiras de 3,4 m, plantas a 2,5 m):**
- clássico: F1 de 88,9% e erro de −4,6%;
- com SAM e refinos: F1 de 92,5% e erro de −5,9%;
- ambos em 5 janelas de 20 m, com tolerância de 0,8 m.

**Cuidados**
- **A tolerância de pareamento muda muito o F1:** 80% com 0,6 m e 95% com 1,0 m. Declare sempre. Padrão: o menor entre metade do espaçamento na linha e o raio da copa.
- **Copas encostadas** se fundem por cor. Altura (modelo de superfície da fotogrametria) ou SAM ajudam.
- **Milho e soja jovens** pedem pixel de até 1 cm. A 3–5 cm, avise a expectativa baixa e meça.
- **Reajustar parâmetros em janelas grandes não melhorou:** o resultado é estável numa faixa larga.

## 4. Segmentação (só se for pedida)

**Caminho A: clássico, sem instalar nada (o mais rápido para aula)**
1. Máscara de copa a partir do mapa do alvo.
2. `scipy.ndimage.watershed_ift` com os pontos da contagem como sementes, sobre o mapa de copa invertido e restrito à máscara.
3. Polígonos com `gdal.Polygonize`.
4. Aplique os refinos do caminho B.

**Caminho B: SAM 2.1 a partir de pontos**
- **Ambiente.** Só num Python **separado** do QGIS (venv próprio com o SAM 2 oficial, Apache 2.0, ou o Ultralytics, AGPL). Chame por `subprocess` a partir do `execute_code`: grave recortes e pontos em arquivo, leia as máscaras de volta.
- **Recortes:**
    - 480 × 480 px (24 m, com 2 m de margem) e um ponto por planta;
    - tempo: 21–26 s por recorte em CPU de 2 núcleos;
    - talhão inteiro: avise o tempo e rode em segundo plano.
- **Refinos que funcionaram no pomar (F1 de 92,5%):**
    - centralizar o ponto na copa;
    - juntar duplicados (< 1,0 m ou IoU > 0,5);
    - aceitar máscaras de 1–9 m²;
    - dividir máscaras ≥ 7,5 m² com alongamento ≥ 1,6;
    - completar copas que ficaram sem ponto.
- **Nunca use o modo automático** ("segmentar tudo") com copas encostadas: deu 12 máscaras para 42 plantas, em 351 s.
- **SAM 3** só com GPU, usando exemplos (caixas positivas e negativas), não texto. Devolve no máximo 200 objetos por imagem: divida em tiles.

**Caminho C: plugins que o usuário já tenha** (GeoAI, Deepness, AI Segmentation da TerraLab). O resultado passa pela mesma validação.

**Outras plantas e daninhas**
1. Tire da máscara de vegetação o que tem forma de fileira (abertura morfológica; raio de 0,40 m na cana).
2. Fique com as manchas longe das linhas, mais verdes ou mais escuras.
3. Ordene as candidatas e confira uma a uma na imagem. Na cana, de 14 candidatas, 3 foram confirmadas.

**Filtrar "mato" só pela cor remove plantas verdadeiras:** piorou o resultado no pomar.

**Validação.** IoU (mediana e distribuição) e erro de área contra polígonos de referência. Critério inicial: IoU de pelo menos 0,75 e erro de área de até 10%.

## 5. Validação (vale para todos os desafios)

**Janelas**
- **Separe ajuste e teste.** As janelas de ajuste servem para mexer em parâmetros; as de teste só são avaliadas no fim, uma vez. Validar perto do ajuste engana: deu 99% no miolo da janela e 86% no anel.
- **Modo completo:**
    - pelo menos 20 janelas de teste, aleatórias, estratificadas por vigor e fora de carreadores e bordas;
    - contagem: lado de 4–6 espaçamentos e ~15–30 plantas por janela, com pelo menos 200 plantas no total;
    - falhas: 20 trechos de 20–25 m e 100 falhas de referência.
- **Modo aula:**
    - 4 janelas de ajuste + 4 de teste (falhas: janelas de 10 m com ~7 fileiras);
    - ou 5 janelas de 20 m (contagem);
    - diga que a margem de erro fica larga.
- **Borda da janela:** só conta objeto com centro dentro dela.

**Referência (marcar ANTES de rodar o modelo naquela janela)**
- **Rota 1, o usuário marca no QGIS.** É a melhor para aula. Crie camadas vazias no GPKG para ele editar:
    - `ref_plantas` (pontos);
    - `ref_falhas` (linhas sobre a fileira, do início ao fim do vão);
    - `ref_copas` (polígonos).
- **Rota 2, você olha os recortes.** Só se você realmente consegue ver imagens: um arquivo lido do computador do usuário, uma imagem anexada ou uma ferramenta que devolve a imagem na resposta. `render_map` e as capturas da ClaudIA QGIS devolvem um link de 1 hora que você **não** consegue abrir. Protocolo:
    - recorte com até 10 plantas, ou faixa de fileira desenrolada, ampliado (lado maior de 1.000–1.500 px), com régua de 1 m e margem escurecida;
    - responda com **pontos**, da esquerda para a direita, cada um "certa", "dúvida" ou "copas juntas". O código conta;
    - **sem pistas:** não use o espaçamento nem a contagem esperada para decidir, porque a IA tende a ver o que espera;
    - **duas passadas** com o recorte deslocado em meia unidade. Discordando, uma terceira; persistindo, chame o usuário;
    - para conferir erros do modelo, use **marcas numeradas** (até 25 por imagem), cada uma "acerto", "erro" ou "dúvida".
- **Referência feita vendo o resultado do modelo** é "assistida" e precisa ser declarada.

**Métricas**
- **Contagem:**
    - pareamento um a um com tolerância (`linear_sum_assignment`);
    - precisão, recall, F1 e erro de contagem;
    - confira sempre: TP + FN = referência e TP + FP = detectado.
- **Falhas:**
    - uma falha da referência conta como **encontrada** se uma falha detectada a sobrepõe, com 0,4 m de tolerância nas pontas; a precisão usa a mesma regra no sentido inverso;
    - % de falha detectado × referência, **por janela e no total**, porque erros de sinal oposto se compensam na média.
- **Linhas:** % de fileiras, cobertura, desvio lateral (p50 e p90) e espaçamento.
- **Margem de erro:** bootstrap sorteando **janelas inteiras**, não plantas.
- **Comparar tentativas:** validação cruzada, deixando uma janela de fora por vez, nas janelas de ajuste. No máximo 5 rodadas. Depois, avaliação final nas de teste.

## 6. Erros que já aconteceram e como evitar

| Erro | O que aconteceu | Como evitar |
|---|---|---|
| Camada vazia sem erro | A camada temporária rejeitou valores numpy (`np.float64`, `np.int64`) em silêncio | Converter com `float()`/`int()` antes de `setAttributes`; conferir `featureCount()` depois de gravar |
| Camadas sumindo | Camadas temporárias somem ao fechar o QGIS | Gravar sempre no GPKG da pasta de trabalho |
| Código perdido | Uma função de avaliação se perdeu quando a conversa foi resumida; os resultados estavam em variáveis escondidas | Funções em `funcoes_drone.py`; resultados e parâmetros em disco (GPKG, JSON) |
| Chamada cortada | Limite de ~60 s por chamada | Testar num bloco, medir, rodar em lotes de até ~40 s, gravando o parcial |
| Presença zerada | Um índice de bloco estourou o limite do raster e devolveu zeros sem erro | Recortar a janela aos limites do raster; `assert` no formato do array; conferir a fração de zeros e NaN |
| Métrica errada | Erro de contabilidade (o mesmo objeto contado duas vezes) | Pareamento um a um; conferir TP + FN = referência e TP + FP = detectado |
| Referência com linha vazia | Uma fileira da referência veio como `None` e quebrou a conta | Validar a referência antes de avaliar; pular e contar as linhas sem referência |
| Biblioteca ausente | O QGIS não tinha scikit-image nem OpenCV | Usar numpy/scipy (Otsu próprio, `maximum_filter`, `watershed_ift`); nada de `pip install` no Python do QGIS |
| Referência viesada | A primeira contagem do pomar deu 91 plantas; eram 56 (copas grandes divididas em duas) | Diagnosticar o espaçamento antes; contar às cegas, sem pistas, pela fileira desenrolada, em duas passadas |
| Métrica otimista | Janela pequena usada no ajuste: 99% no miolo × 86% no anel | Ajuste separado do teste; métrica só no que nunca foi usado para ajustar |
| F1 que muda sozinho | F1 de 80% a 95% só mudando a tolerância de 0,6 para 1,0 m | Declarar a tolerância; reportar também com 0,5×, 0,75× e 1,0× |
| Falhas subestimadas | O método por pixel deu 4,2% contra 9,1% da leitura visual: folha vizinha cobrindo o vão | Motor v3 (plantas + solo exposto + limiar local) |
| Receita que não transfere | O limiar fixo da 1ª área achou 47% das falhas na 2ª | Limiar local por trecho de ~25 m |
| Teto de parâmetros | 168 combinações e o erro parou em −4 pp | Mudar o método, não só os números |
| SAM automático inútil | 12 máscaras para 42 plantas, em 351 s | Um ponto por planta + refinos |
| Filtro de mato por cor | Removeu plantas verdadeiras | Forma + posição fora da linha + conferência visual |
| Super-resolução mudando o resultado | O % de falha mudou de −3,8 a +2,2 pp conforme o modelo | Medir só na imagem original ou num ortomosaico reprocessado no GSD das fotos |
| Imagem que a IA não vê | `render_map` e capturas devolvem um link de 1 hora | Ler PNG da pasta pela ponte de arquivos, pedir anexo, ou o usuário marcar no QGIS |
| Distâncias erradas | EPSG:3857 infla distâncias por 1/cos(latitude) | Trabalhar em UTM |

## 7. Roteiro para aula

**Antes da aula (prepare para a aula não depender de esperar)**
- [ ] QGIS aberto, ClaudIA QGIS conectada (`ping` responde), ortomosaico e polígono carregados, SRC em UTM.
- [ ] Pasta `analise_drone/` criada, com `funcoes_drone.py` testado e o GPKG.
- [ ] Linhas do talhão já geradas e gravadas: é a etapa mais longa num talhão grande.
- [ ] Janelas criadas e referências já marcadas. Deixe uma ou duas janelas para marcar ao vivo, como exemplo.
- [ ] Um recorte pequeno escolhido para rodar ao vivo cada etapa em segundos.

**Sequência sugerida**
1. **Perfil da imagem:** pixel, SRC, cobertura e espaçamento por FFT. Mostre o espectro e por que diagnosticar antes de contar.
2. **Linhas no recorte:** mostre a sobreposição na imagem e as métricas da janela.
3. **Falhas:** primeiro o limiar fixo, mostrando que erra; depois o v3 com limiar local. Compare com a referência e aplique dois critérios diferentes sem rodar de novo.
4. **Contagem:** a referência às cegas e o efeito da tolerância no F1.
5. **Segmentação:** o caminho clássico (watershed), sem instalar nada. Mencione SAM e plugins como opções.
6. **Fechamento:** o relatório com status de validação e a diferença entre "até 98%" sem método e um número com janela, tolerância e margem.

Se quiser registrar o que foi feito, use `export_session`.

## 8. Entrega

Para cada desafio, por talhão:
- **Números:** com a unidade e por hectare útil.
- **Critério:** qual foi e de onde veio ("usuário" ou "sugestão Stolf 1986, aceita").
- **Validação:**
    - status;
    - janelas;
    - número de objetos;
    - tipo de referência;
    - tolerância;
    - métricas;
    - margem de 95%.
- **Ressalvas:**
    - imagem;
    - época do voo;
    - erro por janela;
    - referência visual, sem conferência de campo.
- **Camadas:** onde ficaram no GPKG.

Exemplo de frase: "Falhas: 18,1% no critério ≥ 0,5 m (do usuário). Motor validado às cegas em 4 janelas: 85% das falhas encontradas, −2,0 pp. Vale para o talhão; por trecho, o erro chega a ±12 pp."

## Anexo: trechos que evitam os erros mais comuns

**Otsu sem scikit-image**
```python
import numpy as np
def otsu(x, nb=256):
    x = x[np.isfinite(x)]
    h, e = np.histogram(x, bins=nb); c = (e[:-1] + e[1:]) / 2
    w0 = np.cumsum(h); w1 = w0[-1] - w0
    m0 = np.cumsum(h * c) / np.maximum(w0, 1)
    m1 = (np.sum(h * c) - np.cumsum(h * c)) / np.maximum(w1, 1)
    return float(c[np.argmax(w0 * w1 * (m0 - m1) ** 2)])
```

**Ler um bloco reduzido, sem estourar o raster**
```python
from osgeo import gdal
def ler_bloco(ds, x0, y1, lado_m, px_saida):
    gt = ds.GetGeoTransform()
    c0 = max(0, int((x0 - gt[0]) / gt[1])); r0 = max(0, int((gt[3] - y1) / -gt[5]))
    n = int(lado_m / gt[1])
    nc = min(n, ds.RasterXSize - c0); nr = min(n, ds.RasterYSize - r0)
    if nc <= 0 or nr <= 0: return None
    m = max(1, int(lado_m / px_saida))
    a = ds.ReadAsArray(c0, r0, nc, nr, buf_xsize=max(1, int(m * nc / n)), buf_ysize=max(1, int(m * nr / n)),
                       resample_alg=gdal.GRIORA_Average).astype('float64')
    assert a.ndim == 3 and a.shape[1] > 0 and a.shape[2] > 0
    return a  # (bandas, linhas, colunas)
```

**Gravar feições com tipos Python e conferir**
```python
def py(v):
    if isinstance(v, np.integer): return int(v)
    if isinstance(v, np.floating): return float(v)
    return v
# f.setAttributes([py(v) for v in valores])
# depois de gravar no GPKG, reabra a camada e confira: camada.featureCount() == len(feicoes)
```

**Pareamento um a um com tolerância**
```python
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
def parear(det, ref, tol):
    if len(det) == 0 or len(ref) == 0: return 0, len(det), len(ref)
    D = cdist(det, ref); D = np.where(D <= tol, D, 1e6)
    i, j = linear_sum_assignment(D); tp = int((D[i, j] <= tol).sum())
    return tp, len(det) - tp, len(ref) - tp   # TP, FP, FN
```

**Núcleo do v3 numa linha** (M = perfil a cada 0,05 m, já suavizado)
```python
from scipy.signal import find_peaks
du = 0.05; th = max(0.05, t2)
pk, _ = find_peaks(M, height=th, distance=max(1, round(0.1 / du)))
falhas = []
for a, b in zip(pk[:-1], pk[1:]):            # só entre plantas: pontas não contam
    if (b - a) * du <= 0.5: continue
    low = np.where(M[a:b + 1] < t2)[0]
    if len(low) == 0: continue               # sem solo exposto entre elas
    ini = (a + low[0]) * du - du / 2; fim = (a + low[-1]) * du + du / 2
    # float() já aqui: np.float64 não grava na camada (erro da camada vazia)
    falhas.append((float(ini), float(fim), float(fim - ini), float((b - a) * du)))  # ini_m, fim_m, comp_solo_m, dist_plantas_m
```
