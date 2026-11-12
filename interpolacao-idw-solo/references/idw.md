# IDW — decisões técnicas da skill

Notas para quem quiser auditar (ou melhorar) a implementação de `scripts/`.

## A fórmula

Cada célula da grade recebe a média ponderada das amostras vizinhas:

```
ẑ(x₀) = Σ wᵢ·zᵢ / Σ wᵢ        wᵢ = 1 / dᵢᵖ
```

`dᵢ` é a distância da célula à amostra `i` e `p` é a potência. Quanto maior a
potência, mais a amostra mais próxima manda.

- **Vizinhança**: as `k` amostras mais próximas de cada célula (padrão 12),
  achadas por árvore k-d. Com `--raio`, só entram as que estão dentro do raio;
  célula sem nenhuma fica vazia (NoData) e o relatório conta quantas.
- **Amostra em cima da célula** (distância zero): a célula recebe o valor da
  amostra. O IDW é interpolador exato.
- **Pontos em coordenada repetida** (tolerância de 1 cm) viram um só, com a
  média dos valores.

## Propriedades que o usuário precisa conhecer

- **Nunca extrapola**: todo valor do mapa fica entre o mínimo e o máximo das
  amostras da vizinhança. Um pico real entre dois pontos não aparece.
- **Olho de boi**: manchas redondas em volta de amostras que destoam das
  vizinhas. Crescem com a potência e com a malha rala. Não é defeito do
  desenho: é o que o método faz com um ponto isolado.
- **Não mede incerteza**: diferente da krigagem, o IDW não entrega variância.
  A única medida de erro é a validação cruzada.

## A potência: 2 por padrão, com a validação cruzada ao lado

O padrão é a potência 2, a usual em mapas de fertilidade e a que o agrônomo
espera ver. A validação cruzada leave-one-out roda sempre: para cada potência
candidata (1 · 1,5 · 2 · 2,5 · 3 · 4), cada amostra é retirada e predita pelas
`k` vizinhas. A tabela completa fica em `relatorio.json` (`idw.potencias`),
com o erro médio (viés) de cada uma. Se outra potência tiver RMSE mais de 5%
menor que a usada, o relatório avisa. `--potencia auto` adota a de menor RMSE.

- A lista para em 4 de propósito. Acima disso o mapa vira, na prática, o
  "vizinho mais próximo" (polígonos em volta de cada amostra). Quando a
  vencedora é a 4, o script avisa e sugere comparar com a potência 2, que dá um
  mapa mais suave com RMSE em geral pouco maior.
- O RMSE e o ganho sobre a média informados no mapa são sempre os da potência
  usada.

## O teste contra a média

O mesmo leave-one-out mede o preditor ingênuo: prever cada amostra pela média
das outras. O relatório traz `rmse_da_media` e o **ganho sobre a média**:

```
ganho = 1 − RMSE do IDW / RMSE da média
```

- Ganho perto de zero (abaixo de 5%): `estrutura_fraca = true`. A malha não
  captou padrão espacial e o mapa pouco difere de pintar tudo com a média. A
  página do mapa recebe a frase de atenção e o relatório, o aviso.
- Ganho alto não prova que o mapa está certo entre os pontos; prova só que
  vizinhos se parecem.

## Tamanho da amostra

- Menos de 5 pontos com valor válido: o script recusa o elemento.
- Menos de 15: roda e avisa que o mapa é um esboço.
- Não há número mágico acima disso. O que importa é a malha em relação à
  escala da variação; o ganho sobre a média é o termômetro.

## Quando preferir a krigagem

Com 30 pontos ou mais e ganho sobre a média razoável, vale rodar a
`krigagem-solo` nos mesmos arquivos e comparar o RMSE da validação cruzada. A
krigagem modela a dependência espacial, suaviza o olho de boi e informa a
razão pepita/patamar. O IDW ganha em simplicidade e em malhas pequenas, onde o
semivariograma é frágil.

## Geoprocessamento

- **Projeção**: UTM / SIRGAS 2000 (GRS80), fórmulas de Snyder — erro ≪ 1 m.
  Zona automática pelo centroide (ou do `.prj`; `--zona` em último caso).
  EPSG: 31954+zona (N) / 31960+zona (S).
- **Máscara**: célula entra se o CENTRO cai dentro do perímetro; furos e
  multipolígonos por paridade de anéis.
- **Áreas por classe**: número de células × área da célula. Com pixel de 5 m a
  diferença para a área do polígono é desprezível; com pixel de 20 m ou mais,
  a borda pesa e a área total muda um pouco.
- **GeoTIFF**: escrito em Python puro (float32, NoData −9999, EPSG embutido).
  QGIS e GDAL leem direto. O arquivo não é comprimido: em fazenda grande,
  pixel maior reduz muito o tamanho.
- **Desenho**: grades acima de 4 milhões de células são reduzidas só para o
  desenho da página; o GeoTIFF e as áreas usam a grade inteira.
