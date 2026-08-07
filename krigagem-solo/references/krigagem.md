# Krigagem ordinária — decisões técnicas da skill

Notas para quem quiser auditar (ou melhorar) a implementação de `scripts/`.

## Semivariograma experimental

γ(h) = ½·média[(z(xᵢ) − z(xⱼ))²] para pares na classe de distância h.

- 12 classes de lag até o **corte = 50% da distância máxima** entre pontos —
  além disso os pares rareiam e o variograma vira ruído (prática padrão).
- Classes com menos de 2 pares caem fora.

## Modelos ajustados (alcance prático)

Com pepita `c0`, patamar parcial `c` e alcance prático `a` (γ ≈ 95% do
patamar em h = a), para h > 0:

- **Exponencial**: γ = c0 + c·(1 − e^(−3h/a))
- **Esférico**: γ = c0 + c·(1,5·h/a − 0,5·(h/a)³) para h < a; c0 + c além
- **Gaussiano**: γ = c0 + c·(1 − e^(−3h²/a²))

γ(0) = 0 por convenção (a pepita é descontinuidade na origem — vale para
h → 0⁺, não para a diagonal da matriz de krigagem).

## Ajuste

Mínimos quadrados **ponderados por Np/h²** (pesos de Cressie: classes com
mais pares e mais próximas pesam mais). O alcance é varrido numa grade
geométrica (80 candidatos entre corte/60 e 2×corte); para cada alcance, c0 e
c saem de um sistema linear 2×2 com não-negatividade forçada. Robusto e
determinístico — sem depender de convergência de otimizador não-linear.

## Escolha do modelo: validação cruzada leave-one-out

Para cada modelo ajustado, cada ponto é retirado e predito pelos demais via
krigagem ordinária; **vence o menor RMSE**. É o critério honesto: mede erro
de predição real, não beleza de ajuste à nuvem do variograma. O erro médio
(ME) acompanha para denunciar viés. A tabela completa dos três modelos fica
em `relatorio.json` — mostre ao usuário.

## Diagnósticos

- **Razão pepita/patamar** c0/(c0+c) — classes de Cambardella et al. (1994):
  ≤ 0,25 dependência espacial FORTE · 0,25–0,75 MODERADA · > 0,75 FRACA.
- **Estrutura fraca** (c < 5% da variância): quase pepita pura — o mapa tende
  à média e a malha não captou padrão espacial. Reportar sempre.
- **n mínimo**: < 8 pontos o script recusa; 8–25 avisa (variograma frágil;
  literatura recomenda ≥ 30–50 pares por classe de lag).

## Krigagem ordinária

Sistema em forma de variograma com multiplicador de Lagrange:

```
| Γ  1 | |λ|   |γ₀|      ẑ = λᵀz
| 1ᵀ 0 | |μ| = |1 |      σ²ₖ = λᵀγ₀ + μ
```

A matriz (n+1)×(n+1) é fatorada UMA vez (LU) e reaproveitada para todas as
células (resolvidas em blocos). A variância de krigagem é calculada (função
`krigar` devolve), ainda sem mapa próprio na v1.

## Geoprocessamento

- **Projeção**: UTM / SIRGAS 2000 (GRS80), fórmulas de Snyder — erro ≪ 1 m,
  irrelevante para pixel de 5 m. Zona automática pelo centroide (ou do .prj;
  `--zona` na mão em último caso). EPSG: 31954+zona (N) / 31960+zona (S).
- **Máscara**: célula entra se o CENTRO cai dentro do perímetro; furos e
  multipolígonos por paridade de anéis.
- **GeoTIFF**: escrito em Python puro (float32, NoData −9999, ModelPixelScale
  + ModelTiepoint + GeoKeyDirectory com o EPSG) — QGIS/GDAL leem direto.

## Vizinhança móvel (malhas grandes)

Acima de 120 pontos a predição vira **krigagem local por ladrilho**: a grade
é varrida em blocos de 64×64 células e cada bloco usa só os pontos dentro do
seu bbox + buffer (máx. `--max-pontos`, os mais próximos do centro). O buffer
padrão é max(0,75×alcance, 3×espaçamento da malha) — além dessa distância os
pesos de krigagem são desprezíveis, então o resultado coincide com o global
(teste embutido: diferença RMS ≪ desvio dos dados) com custo ~(n_local/n)².
Bônus estatístico: em fazendas com dezenas de talhões, a vizinhança local
exige estacionariedade só localmente — suposição mais honesta que a global.

## Limitações conhecidas (v1)

- Isotropia assumida (sem variograma direcional/anisotropia).
- Sem transformação de dados (variáveis muito assimétricas, como P, podem
  merecer log-krigagem — inspecione o histograma se o LOO vier ruim).
- Sem co-krigagem nem deriva externa (altimetria, condutividade elétrica).
- Mapa da variância de krigagem ainda não é exportado.

## Referências

- Isaaks, E. H.; Srivastava, R. M. **An Introduction to Applied
  Geostatistics**. Oxford, 1989.
- Cambardella, C. A. et al. Field-scale variability of soil properties in
  central Iowa soils. **Soil Sci. Soc. Am. J.**, 58:1501–1511, 1994.
- Vieira, S. R. Geoestatística em estudos de variabilidade espacial do solo.
  In: **Tópicos em Ciência do Solo**. SBCS, 2000. v. 1, p. 1–54.
