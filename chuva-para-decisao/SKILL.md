---
name: chuva-para-decisao
description: >-
  Descreve o que o registro de chuva de um local mostra para apoiar uma decisão
  de plantio ou de manejo: calendário mensal, veranicos, chuva por decêndio e
  início e fim das águas, sempre em contagem de anos. Usa as ferramentas da
  ClaudIA Clima: a tabela mensal desde 1998, o ano em curso e, numa janela de
  dias que o usuário escolhe, o dia a dia de vários anos. Um script confere a
  transcrição contra os totais da ferramenta antes de calcular e entrega
  tabelas, gráficos e PDF. Os cortes e as regras (dia seco, veranico,
  milímetros do decêndio, início e fim das águas, base dos graus-dia) são do
  usuário: a skill pergunta, não escolhe. É descrição do registro, não
  previsão: não recomenda data de plantio, cultura nem manejo e não substitui
  o ZARC. Acione com "quando costuma firmar a chuva", "em quantos anos teve
  veranico em janeiro", "chance de chuva por decêndio", "início das águas",
  "graus-dia da safra" ou quando o usuário pedir o histórico de chuva para
  decidir uma data.
---

# Chuva para decisão

O usuário tem uma decisão que depende da chuva (a janela de plantio, a
safrinha, uma aplicação, a colheita) e quer saber como a chuva se comportou
naquela época nos outros anos. A skill entrega, sempre como **contagem de
anos** ("em 7 de 10 anos"):

1. o **calendário da chuva**: por mês, a mediana, a faixa onde ficou a maioria
   dos anos, o menor e o maior com o ano; o total de cada ano agrícola; o mês
   em que as águas firmaram e terminaram; os graus-dia;
2. o **ano em curso** ao lado dos outros, com as frases da ferramenta;
3. a **janela dia a dia** que ele escolher, em vários anos: chuva por decêndio,
   veranicos, a data em que as águas firmaram e, noutra janela, a data em que
   terminaram;
4. o relato em texto, as tabelas em CSV, os gráficos e um **PDF**.

Quem produz o dado são as ferramentas do conector ClaudIA Clima. Quem faz as
contas é o script `scripts/chuva.py`, a partir do texto que as ferramentas
devolveram.

## A regra que vale para tudo: descrição, não previsão

- Diga sempre "em k de N anos", com os anos. Não converta em "chance de 70%",
  "probabilidade", "risco alto" ou "risco baixo".
- NUNCA diga quanto vai chover, que o ano será igual a outro, nem que uma data
  é a certa, a ideal, a melhor ou a segura. Não recomende data de plantio,
  cultura, cultivar, ciclo nem manejo. A decisão é do responsável técnico.
- Se o usuário pedir a conclusão ("planto dia 10?"), entregue as contagens e
  devolva a decisão a ele.
- Amostra pequena: 10 a 28 anos mostram o que é comum, não o que é raro. "Em 0
  de 10 anos" não quer dizer que não acontece. Diga isso junto do resultado.
- **Os números das regras são do usuário.** Dia seco, tamanho do veranico,
  cortes de milímetros, regra do início e do fim das águas, base dos
  graus-dia: mostre os valores de uso comum, pergunte e use o que ele
  disser. O script recusa calcular sem eles.
- O relato não é o Zoneamento Agrícola de Risco Climático (ZARC) e não o
  substitui.
- Cada número vai com a fonte, nas palavras da ferramenta.

## O que precisa estar disponível

- **Conector ClaudIA Clima**, com `clima_historico` e `contexto_chuva`. Sem
  ele, avise e pare.
- **Ambiente que roda Python** com `numpy` e `matplotlib`. Sem ele, entregue só
  o que as ferramentas dizem (o resumo de cada chamada e as frases do ano em
  curso) e avise que as contagens entre anos não foram feitas. Não conte de
  cabeça.
- **O local**: fazenda salva na conta (`listar_fazendas` mostra os nomes),
  perímetro (GeoJSON, KML ou WKT) ou latitude e longitude. Use o MESMO local
  em todas as chamadas.

## Antes de chamar: as perguntas (numa mensagem só)

1. **O local** e o nome dele para o título.
2. **A decisão**: o que ele quer decidir e em que época do ano. Daí sai quais
   blocos fazer; não faça os quatro se ele só quer um.
3. **A janela dia a dia**, se a pergunta for de decêndio, veranico ou data das
   águas: o dia e o mês de início e de fim (a mesma em todos os anos), com até
   92 dias de preferência, e **quantos anos**. O padrão são as 10 últimas
   janelas já encerradas; aceite de 5 a 20. Para a data do início das águas, a
   janela precisa começar ainda na seca e terminar pelo menos 30 dias depois
   da data mais tardia que ele espera.
4. **As regras**, só as dos blocos pedidos:
   - dia seco: abaixo de quantos milímetros (uso comum: 1 ou 2 mm);
   - veranico: quantos dias seguidos (uso comum: 7, 10 e 15);
   - corte do decêndio, em mm (depende da cultura e do solo: 10, 20, 30);
   - início das águas: quantos mm, em quantos dias, e quantos dias secos
     seguidos nos dias seguintes anulam o início (uso comum: 20 mm em 1 a 3
     dias, sem 7 a 10 dias secos nos 30 dias seguintes);
   - fim das águas: quantos dias secos seguidos (uso comum: 15 a 20);
   - mês de águas, para a regra mensal: quantos mm (uso comum: 100);
   - graus-dia: a temperatura-base da cultura, o mês do plantio, o mês final
     e, se quiser, o alvo.
5. **Onde o ano agrícola começa**: julho serve para onde a seca é no inverno.
   Onde a chuva é de inverno, ou no extremo norte, pergunte.

O que ele já disse, não pergunte de novo. Se ele não souber um número, mostre
os de uso comum e peça que escolha; não escolha por ele.

## A conta das consultas (diga antes de chamar)

Cada chamada conta uma consulta de clima da conta do usuário, e o texto de cada
resposta ocupa a conversa.

| Bloco | Chamadas | Tamanho do texto |
|---|---|---|
| Tabela mensal desde 1998 | 1 | cerca de 12 mil tokens |
| Ano em curso | 1 | pequeno |
| Janela dia a dia | 1 por ano | cerca de 3 mil tokens por ano numa janela de 77 dias |
| Janela do fim das águas | 1 por ano | idem |

Some, diga o total ("são 12 consultas") e só chame com o de acordo dele. Dez
anos de uma janela de até 92 dias cabem bem; para mais anos, encurte a janela.
Se a ferramenta recusar por limite, repita o motivo como ela disse e ofereça
menos anos.

## Fluxo de trabalho (siga nesta ordem)

1. **Tabela mensal.** `clima_historico` com `escala` = `mes`, `data_inicio` no
   dia 1º do mês em que o ano agrícola começa (`1998-07-01` quando começa em
   julho) e `data_fim` no último dia do último ano agrícola já encerrado. Se
   houver graus-dia, passe `base_gdd_c` com a base que o usuário informou.
   Grave em `mensal.txt` as linhas `Chuva — ...`, `RESUMO` e `TEMPERATURA` como
   vieram e uma linha por mês (formatos em `references/arquivos.md`).
2. **Ano em curso**, só se a decisão é para a safra que está começando ou em
   andamento: `contexto_chuva` no mesmo local. Grave as frases em
   `contexto.txt` e repasse como vieram.
3. **Janela dia a dia.** Uma chamada de `clima_historico` por ano, com
   `escala` = `dia` e as MESMAS datas de dia e mês em todos os anos. As
   chamadas podem ir juntas. O ano em andamento fica de fora: a ferramenta
   corta o período e a janela dele sai diferente das outras. De cada
   resposta, grave em `janela.txt` as linhas `Chuva — ...`, `RESUMO` e `AGRO`
   **como vieram** e os milímetros de cada dia, na ordem, em linhas `mm:`.
   Copie os números como a ferramenta escreveu. Dia "SEM DADO" vira `SD`.
4. **Janela do fim das águas**, se pedida: do mesmo jeito, noutro arquivo
   (`janela_fim.txt`), com a janela do fim da estação.
5. **Confira antes de calcular**:
   `python scripts/chuva.py --conferir --mensal mensal.txt --janela janela.txt`
   O script confere cada ano contra o que a ferramenta informou (número de
   dias, total, dia da maior chuva e veranico máximo) e mostra o que leu. Se
   recusar, releia a resposta da ferramenta daquele ano e corrija a
   transcrição. NUNCA altere um valor só para a soma fechar.
6. **Mostre a conferência ao usuário e confirme as regras** que faltarem.
7. **Calcule**, com as regras dele:
   ```
   python scripts/chuva.py --mensal mensal.txt --corte-mes 50,100 --firme-mm 100 \
       --gdd-de 10 --gdd-ate 2 --gdd-alvo 1400 \
       --janela janela.txt --seco-mm 2 --veranico-dias 7,10,15 --corte-decendio 20,40 \
       --inicio-mm 20 --inicio-dias 3 --falso-dias 10 --falso-janela 30 \
       --janela-fim janela_fim.txt --fim-dias 15 \
       --contexto contexto.txt --local "Fazenda X" --saida saida_chuva
   ```
   Os números acima são exemplo de sintaxe. Use só os blocos pedidos; cada
   bloco é independente.
8. **Entregue**: o relato que o script imprime (as frases já vêm no formato
   certo; não reescreva em tom de previsão), o `relatorio.pdf` e os CSV.
   Abra o PDF e olhe antes de entregar.
9. **Repita os avisos** que vierem na seção "Avisos" do relato e os da
   ferramenta, com as palavras dela: a confiança da chuva, os dias que "ainda
   podem ser revisados", a linha `AVISOS`.

## Como ler o que sai

- **Calendário mensal**: "P20 a P80" é a faixa onde ficaram cerca de 6 de cada
  10 anos. Nos meses secos, valores pequenos e repetidos de um ano para outro
  são o piso do dado mensal; não leia diferença entre eles.
- **Regra mensal das águas**: só diz o mês. Para a data, use a janela.
- **Decêndio**: contam só os decêndios inteiros dentro da janela.
- **Veranico**: é a sequência seca DENTRO da janela, pela régua do usuário. Se
  encosta na borda, pode ter sido maior; a tabela marca. O "veranico máximo"
  que a ferramenta informa usa a régua dela e vai ao lado, na tabela.
- **Início das águas**: "sem conferência" quer dizer que a regra fechou perto
  do fim da janela e faltaram dias para ver se era falso início; esse ano fica
  fora da contagem. Se acontecer em vários anos, a janela está curta.
- **Tabela mensal e janela não se misturam.** Os milímetros da chamada longa
  (mensal) e os da chamada curta (dia a dia) saem de réguas diferentes da
  ferramenta e não fecham entre si. Compare ano com ano dentro de cada bloco.
- A "média histórica" e o "→ %" que a ferramenta devolve numa janela curta
  não entram no relato: a skill compara os anos entre si.

## O que a skill não faz

- Não prevê chuva e não diz quando plantar, o que plantar nem como manejar.
- Não consulta o ZARC, a previsão do tempo nem a janela de pulverização (a
  previsão é das ferramentas `previsao_dias` e `previsao_horas`).
- Não faz balanço hídrico: chuva sem a evapotranspiração e a água do solo não
  diz se faltou água para a planta.
- Não trabalha com mais de um local por vez nem com janela acima de 180 dias.
- Não chama a ferramenta de novo para "melhorar" um resultado e não completa
  ano que faltou com estimativa.

## Sigilo das fontes

A fonte da chuva é citada como a ferramenta manda: "pluviômetros e satélites
da comunidade agrônomo10X (OagronomIA)". Não nomeie produto, instituto, índice
ou satélite, e não deduza como o dado é processado.

As regras, as fórmulas e os limites: `references/metodo.md`. O formato dos
arquivos: `references/arquivos.md`.
