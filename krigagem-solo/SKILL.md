---
name: krigagem-solo
description: >-
  Interpolação por krigagem ordinária de laudos de análise de solo
  georreferenciados. Entradas: perímetro do talhão, pontos de amostragem
  (shapefile/GeoJSON/KML/CSV) e o laudo do laboratório. Casa os IDs do shape
  com os do laudo mesmo com divergências (T01-03 ≈ t1-3), testa três modelos
  de semivariograma (exponencial, esférico e gaussiano), escolhe o melhor por
  validação cruzada e gera mapa raster (GeoTIFF) + PNG com legenda em régua,
  pixel de 5 m. Acione com "mapa de fertilidade", "krigagem", "interpolar
  análise de solo", "agricultura de precisão" ou quando o usuário trouxer
  laudo + pontos de amostragem de um talhão.
---

# Krigagem de Solo — do laudo ao mapa de fertilidade (pixel 5 m)

Transforma laudo de análise de solo + malha de amostragem em **mapas
interpolados por krigagem ordinária**, um por elemento, prontos para o QGIS
(GeoTIFF georreferenciado) e para apresentação (PNG com legenda em régua).

## Para que serve
- Casar os IDs do **shape de amostras** com os do **laudo** mesmo quando
  divergem ("T01-03" vs "t1-3", "Ponto 12" vs "12", maiúsculas, zeros,
  separadores) — e apontar o que não casou para o usuário decidir.
- Testar **três modelos de semivariograma** (exponencial, esférico,
  gaussiano) e escolher o melhor por **validação cruzada leave-one-out**
  (menor RMSE) — por elemento, sem chute.
- Interpolar em **pixel de 5 m** dentro do perímetro (furos respeitados) e
  entregar **GeoTIFF (EPSG SIRGAS 2000/UTM)** + **PNG com régua de valores**,
  escala gráfica e norte.

## Para que NÃO serve
- Não substitui malha amostral decente: com menos de 8 pontos o script se
  recusa; entre 8 e 25 ele avisa que o variograma é frágil.
- Não faz zonas de manejo, anisotropia nem co-krigagem (v1 é isotrópica).
- Não interpreta fertilidade — para recomendar corretivos/adubação use as
  skills `5a-aproximacao-mg` (MG) ou `boletim-100-sp` (SP) sobre os mapas.

## Entradas

1. **Perímetro do talhão**: `.kml`, `.geojson`, `.shp` (polígono) ou WKT.
2. **Pontos de amostragem**: `.shp` (leitor embutido — não precisa de GDAL),
   `.geojson`, `.kml` ou `.csv` com lon/lat. `.zip`/`.kmz`: descompacte antes.
3. **Laudo**: qualquer formato (PDF, foto, planilha). VOCÊ extrai a tabela
   para um CSV com **uma linha por amostra**: primeira coluna = ID da amostra
   como está no laudo; demais colunas = elementos com unidade no cabeçalho
   (ex.: `P (mg/dm3)`). Não invente valores; decimais com vírgula e "<0,1"
   podem ficar como estão (o script trata; "<LD" entra como metade do limite).

Coordenadas em metros (UTM) sem `.prj` exigem a zona: `--zona 22S`.

## Fluxo de trabalho (siga nesta ordem)

1. **Extraia o laudo** para `laudo.csv` (regra acima). Liste as colunas
   numéricas encontradas e **PERGUNTE ao usuário quais elementos ele quer
   interpolar** — nunca decida por ele.
2. **Etapa 1 — casamento** (sempre primeiro):
   `python scripts/interpolar.py --perimetro talhao.kml --pontos amostras.shp
   --laudo laudo.csv --so-casamento --saida ./saida`
   O JSON de saída traz os campos de ID detectados, pares por confiança,
   pontos sem par e duplicatas.
3. **Revise o casamento com o usuário**:
   - `duplicados_laudo` preenchido = laudo com mais de uma linha por ponto
     (profundidades 0-20/20-40). Pergunte qual usar e repita com
     `--filtro-laudo "0-20"`.
   - `aproximados_para_confirmar` = mostre a tabela ponto ↔ laudo e confirme;
     pares confirmados entram com `--par "PONTO=ID DO LAUDO"` (repetível).
   - `pontos_sem_par`/`laudo_sem_uso` = mostre e pergunte (amostra perdida?
     ponto extra?). Detecção de campo errada corrige-se com
     `--id-pontos`/`--id-laudo`.
4. **Etapa 2 — interpolação**:
   `python scripts/interpolar.py ... --elementos "P (mg/dm3),V (%)" --saida ./saida`
   (nomes exatamente como no cabeçalho do CSV; `todos` = todas as numéricas).
   Para variáveis em que valor alto é RUIM (Al³⁺, m%), gere separado com
   `--cmap RdYlGn_r`.
5. **Entregue por elemento**: o PNG (mostre no chat) + o GeoTIFF (pixel 5 m,
   EPSG no relatório). Explique a escolha do modelo com a tabela de RMSE
   LOO dos três candidatos (está em `relatorio.json`), a dependência espacial
   (razão pepita/patamar: ≤0,25 forte · ≤0,75 moderada · >0,75 fraca) e TODOS
   os avisos (`n` baixo, estrutura fraca, valores "<LD", células truncadas).
6. **Honestidade**: se `estrutura_fraca` vier true, diga claramente que o
   mapa tende à média do talhão e que a malha não captou padrão espacial —
   não venda um mapa pobre como bom.

## Detalhes fixos da implementação

- Pixel padrão **5 m** (`--pixel` muda se o usuário pedir).
- Projeção alvo: **UTM / SIRGAS 2000** (zona automática; EPSG no relatório).
- Ajuste do variograma: mínimos quadrados ponderados (Cressie, Np/h²), corte
  em metade da distância máxima, alcance por varredura (sem otimizador
  instável). γ(0)=0; alcance prático (95% do patamar) nos três modelos.
- Concentrações negativas pós-krigagem são truncadas em 0 (contado no aviso).
- Pontos em coordenada repetida viram um só (média).
- Teoria e referências: `references/krigagem.md`.
