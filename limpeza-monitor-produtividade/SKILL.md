---
name: limpeza-monitor-produtividade
description: >-
  Limpa dado denso de máquina (monitor de colheita, condutividade elétrica,
  sensor de dossel, altimetria) com filtros em ordem, cada um com o parâmetro
  e a contagem do que removeu, e entrega os pontos limpos e o relatório.
  Primeiro faz o diagnóstico do arquivo bruto (colunas, passadas, velocidade,
  enchimento da máquina, largura parcial), depois aplica os filtros de posição,
  perímetro, valor impossível, bordadura, velocidade, largura, umidade, começo
  e fim de passada, limites do conjunto e vizinhança. Saídas: CSV e shapefile
  dos pontos limpos, CSV do que saiu com o motivo e relatório em PDF com os
  mapas de antes e depois. Acione com "limpar dados de colheita", "filtrar mapa
  de produtividade", "tirar outliers do monitor", "limpar dados de
  condutividade elétrica", "dado bruto da colhedora" ou quando o usuário enviar
  pontos brutos de máquina e pedir mapa.
---

# Limpeza de dados de monitor de produtividade

Dado bruto de máquina não vira mapa direto: tem ponto repetido, salto de GPS,
máquina enchendo no começo da passada, velocidade quase zero, plataforma pela
metade e valor absurdo. Esta skill **remove** esses pontos, um filtro de cada
vez, e mostra o que cada filtro tirou.

## Para que serve
- Limpar pontos de **monitor de colheita** (grãos, cana, algodão, café).
- Limpar dado denso de **sensor embarcado**: condutividade elétrica aparente,
  sensor de dossel, altimetria.
- Entregar os pontos limpos para o mapa e um relatório do que saiu e por quê.

## Para que NÃO serve
- **Não corrige valor.** Não desloca o dado pelo atraso do grão na máquina,
  não recalcula produtividade pela largura e não interpola. Só remove ponto.
  Calibração e correção de atraso são do monitor ou do programa do fabricante.
- Não lê formato fechado de fabricante. O usuário exporta para CSV, TXT ou
  shapefile de pontos.
- Não faz o mapa interpolado nem as zonas: para isso, os pontos limpos seguem
  para as skills de interpolação da casa ou para o QGIS.
- Não diz o que fazer na lavoura. Informa o dado; a decisão é do responsável
  técnico.

## O que pedir ao usuário
1. O arquivo de pontos brutos: CSV/TXT (com colunas de coordenada) ou
   shapefile de pontos (`.zip` com `.shp`, `.dbf`, `.shx`).
2. O perímetro do talhão, se tiver (GeoJSON, KML ou shapefile). Sem ele, os
   filtros de ponto fora do talhão e de bordadura não rodam.
3. O que é o dado (colheita de quê, ou qual sensor) e a unidade do valor.

## Fluxo de trabalho (siga nesta ordem)

1. **Diagnóstico** (não remove nada):
   ```
   python scripts/limpar.py --pontos <arquivo> --perimetro <perímetro> --diagnostico --saida saida
   ```
   Sem perímetro, tire o `--perimetro`. Para sensor, acrescente `--perfil sensor`.
2. **Mostre ao usuário** a figura `saida/diagnostico.png` e os números que o
   script imprimiu, e **confirme com ele**:
   - a **coluna do valor** e a unidade (o script dá um palpite; palpite não é
     resposta);
   - as colunas de velocidade, largura, umidade e hora, se o palpite errou;
   - o **perfil**: `colheita` ou `sensor`;
   - os parâmetros que você vai usar. Diga os padrões do perfil e o que o
     diagnóstico sugere (quantos pontos cortar no começo e no fim das
     passadas; se a largura parcial tem valor diferente da cheia; os limites
     do conjunto). O usuário pode mudar qualquer um.
3. **Limpeza**, com a coluna confirmada:
   ```
   python scripts/limpar.py --pontos <arquivo> --perimetro <perímetro> --valor "<coluna>" \
       --unidade "<unidade>" --nome "<talhão · cultura · safra>" --saida saida
   ```
   Acrescente só os parâmetros que o usuário mudou (tabela abaixo).
4. **Relate o resultado inteiro**: pontos lidos, mantidos e removidos; a
   linha de cada filtro (regra e quantos saíram), inclusive os que não
   rodaram e por quê; média, mediana e CV antes e depois; e **todos os
   avisos**, com as palavras do script. Entregue o PDF e os arquivos.
5. **Pare e converse antes de entregar** se houver aviso de que a limpeza
   tirou mais de 35% dos pontos, de limite apertado, ou de **pontos
   agrupados** removidos pelo limite do conjunto: ponto agrupado pode ser
   mancha real da área. Mostre o mapa "O que saiu" (página 3 do PDF) e
   pergunte se aquilo é erro ou é a lavoura.
6. Se o usuário pedir outro ajuste, rode de novo com o parâmetro mudado e
   diga o que mudou no resultado.

Para ver a skill funcionando sem arquivo: `python scripts/limpar.py --demo`
(colheita simulada, com erros plantados; o script diz que é simulação).

## Os filtros, na ordem

| # | Filtro | O que tira | Parâmetro | Padrão `colheita` | Padrão `sensor` |
|---|---|---|---|---|---|
| 1 | Posição | sem coordenada, ou posição repetida | — | sempre | sempre |
| 2 | Perímetro | ponto fora dos talhões | `--perimetro` | com perímetro | com perímetro |
| 3 | Valor | sem valor, ou fora do possível | `--minimo`, `--maximo` | tira zero e negativo | só sem valor |
| 4 | Bordadura | perto da divisa | `--borda <metros>` | desligado | desligado |
| 5 | Velocidade | fora da faixa | `--vel-faixa 0.5,1.5` ou `--vel-min`, `--vel-max` | 50% a 150% da mediana | desligado |
| 6 | Variação de velocidade | mudança brusca entre pontos seguidos | `--vel-variacao 0.25` | desligado | desligado |
| 7 | Largura parcial | plataforma abaixo da largura cheia | `--largura-min 0.9` | desligado | desligado |
| 8 | Umidade | fora da faixa | `--umid-min`, `--umid-max` | desligado | desligado |
| 9 | Pontas de passada | máquina enchendo e esvaziando | `--inicio`, `--fim` (em PONTOS, ou `auto`) | `auto` (medido no arquivo) | 0 |
| 10 | Passada curta | passada com poucos pontos | `--passada-min` | 5 | desligado |
| 11 | Limites do conjunto | valor longe do resto do talhão | `--global mad\|dp\|iqr\|pct\|nenhum`, `--global-k` | mediana ± 3 desvios robustos | igual |
| 12 | Vizinhança | valor diferente dos vizinhos | `--local pct\|mad\|nenhum`, `--local-limite`, `--local-raio` | 30% da mediana local | 4 desvios robustos locais |

Cada ponto removido fica com o motivo do **primeiro** filtro que o tirou. O
que cada filtro faz, quando mexer no padrão e de onde vem a ideia:
`references/filtros.md`.

Outros parâmetros: `--x`, `--y` (colunas de coordenada, se o script não
achar); `--zona 22S` (coordenada em metros sem `.prj`); `--velocidade`,
`--largura`, `--umidade`, `--tempo`, `--passada` (nome da coluna, ou
`nenhuma`); `--casas` (casas decimais nos textos).

## Regras de honestidade

- **Diagnóstico antes, sempre.** Não rode a limpeza sem o usuário confirmar a
  coluna do valor.
- **Nenhum parâmetro escolhido em silêncio.** Diga quais vai usar, inclusive
  os padrões.
- **Mostre o que não rodou.** Sem coluna de velocidade, sem perímetro ou sem
  hora, o filtro correspondente não roda: o relatório diz, e você também.
- **A velocidade padrão é relativa à mediana do próprio arquivo**, então vale
  em km/h, m/s ou mph. Limite absoluto (`--vel-min`, `--vel-max`) vai na
  unidade da coluna.
- **Limite do conjunto não distingue erro de mancha.** Uma reboleira real de
  baixa produtividade pode sair por ele. O script avisa quando os pontos
  removidos estão agrupados; nesse caso, afrouxe (`--global-k 4`) ou desligue
  (`--global nenhum`) e deixe a vizinhança trabalhar.
- **Não esconda aviso** e não troque as palavras dele por outras mais leves.
- A skill foi medida em **dado simulado com erros plantados**, não em arquivo
  de máquina de todas as marcas. Se o resultado parecer estranho, diga isso e
  mostre os números; não force uma explicação.

## Saídas (na pasta `--saida`)

- `pontos-limpos.csv` — as colunas do arquivo original, só os pontos que ficaram.
- `pontos-limpos.zip` — shapefile de pontos, nas coordenadas do original.
- `pontos-removidos.csv` — o que saiu, com a coluna `motivo`.
- `relatorio-limpeza.pdf` — resumo e filtros; mapa bruto e limpo nas mesmas
  classes; mapa do que saiu, histograma e entrada das passadas.
- `relatorio-limpeza.png` — a primeira página, para mostrar na conversa.
- `relatorio.json` — todos os números e os parâmetros usados.
- No diagnóstico: `diagnostico.png` e `diagnostico.json`.

## Tamanho do arquivo

Roda bem até perto de 300 mil pontos no ambiente de código da IA. Arquivo
maior: peça ao usuário para enviar um talhão por vez, ou só as colunas que
importam. O mesmo script roda no computador dele (Python com numpy, scipy e
matplotlib).

## Dependências

Python com `numpy`, `scipy` e `matplotlib`. Sem internet.
