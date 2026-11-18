---
name: balanco-hidrico
description: >-
  Calcula o balanço hídrico climatológico de Thornthwaite e Mather (1955): o
  do ano normal, por mês, e o sequencial de uma safra, por decêndio ou por
  mês, para a CAD que o usuário informar. Entra a chuva e a temperatura da
  ferramenta `clima_historico` (ClaudIA Clima) ou da estação do usuário; sai a
  tabela com ETP, armazenamento, ETR, deficiência e excedente, o gráfico, o
  CSV e o PDF. ETP por Thornthwaite, Thornthwaite com temperatura efetiva ou
  Hargreaves e Samani. Confere a transcrição dos dados contra o total que a
  ferramenta informa. Não escolhe a CAD, o método de ETP nem o armazenamento
  inicial: pergunta. Não recomenda irrigação, época de plantio nem cultura.
  Acione com "balanço hídrico", "deficiência hídrica", "excedente hídrico",
  "Thornthwaite", "armazenamento de água no solo", "BH climatológico", "BH
  sequencial da safra" ou quando o usuário pedir o déficit e o excedente de
  água de um lugar ou de uma safra.
---

# Balanço hídrico

Calcula o balanço hídrico climatológico pelo método de Thornthwaite e Mather
(1955) e entrega a tabela, os gráficos e o relatório em PDF:

- **Ano normal**, por mês: quanto chove, quanto a atmosfera pede (ETP),
  quanto o solo guarda, e em que meses há deficiência ou excedente.
- **Sequencial**, por decêndio ou por mês: o mesmo, para uma safra ou para uma
  sequência de anos de verdade.

## Para que serve
- Descrever a disponibilidade de água de um lugar no ano normal.
- Acompanhar o que aconteceu em uma safra: quando faltou e quando sobrou água,
  para a CAD informada.

## Para que NÃO serve
- **Não escolhe** a CAD, o método de ETP, a chuva normal nem o armazenamento
  inicial. Mostra as opções e pergunta.
- **Não recomenda** irrigação, lâmina, época de plantio, cultura nem cultivar.
  Deficiência é um número do balanço; o que fazer com ele é do responsável
  técnico.
- **Não é balanço de cultura**: não usa Kc, fase da lavoura nem profundidade
  de raiz que muda no ciclo. Não é o ZARC e não o substitui.
- **Não prevê**: usa o que já choveu. Não diga como será a próxima safra.
- Balanço do ano normal por decêndio não sai dos dados mensais: repartir a
  chuva do mês em três partes iguais esconderia a distribuição dentro do mês.
  Por decêndio, só o sequencial, que usa a chuva de cada dia.

## O que precisa estar disponível
- **Um ambiente que rode Python** com `matplotlib`. Sem ele, não faça a conta
  de cabeça: explique o método e diga que a skill precisa de um ambiente com
  código.
- **Os dados**, de um destes jeitos:
  - **conector ClaudIA Clima**, com a ferramenta `clima_historico`; ou
  - **tabela do usuário** (estação própria): CSV, TXT ou XLSX com data, chuva
    e temperatura (mínima e máxima, ou a média), ou as 12 normais do lugar.
- **A latitude** do lugar, em graus decimais (sul é negativo). Com ponto, é a
  do ponto consultado. Com fazenda salva ou perímetro, pergunte o município ou
  use a do centro da área: 1 grau de erro muda a ETP do ano em até 1% (e a
  de um mês em até 3,5%, com Hargreaves no sul do país).

## Antes de buscar os dados: as perguntas (em uma mensagem só)
1. **O lugar**: fazenda salva (`listar_fazendas` mostra os nomes), perímetro,
   ponto por latitude e longitude, ou a tabela da estação dele.
2. **Qual balanço**: o do ano normal, o de uma safra, ou os dois.
3. Para a safra: **as datas de início e fim** (até 400 dias por consulta).
   Vale começar dois ou três meses antes do período que interessa: o começo
   da série depende do armazenamento inicial (veja o passo 5).
4. Para o ano normal: **quantos anos entram na temperatura média**. A série
   da ferramenta começa em 02/01/1998: o primeiro ano inteiro é 1999. Cada
   ano são 12 linhas para transcrever: 10 anos, 120 linhas; a série toda,
   mais de 300. Se ele disser que tanto faz, use todos os anos completos e
   escreva isso no relato.

A CAD, o método de ETP e o resto ficam para depois do diagnóstico, quando há
números para mostrar. O que ele já disse, não pergunte de novo.

## O que cada consulta custa (diga antes de chamar)
Cada chamada de `clima_historico` conta como **consulta de clima** na conta
do usuário. O ano normal é uma chamada; cada safra, mais uma. Diga quantas
serão antes de chamar, e não repita chamada para "conferir": o resultado é o
mesmo.

## Fluxo de trabalho (siga nesta ordem)

1. **Busque os dados.**
   - Ano normal: `clima_historico` com `escala` = `mes`, `data_inicio` no dia
     1º de janeiro do primeiro ano e `data_fim` em 31 de dezembro do último
     ano fechado, no lugar escolhido (`fazenda`, `geometria`, ou `latitude` e
     `longitude`).
   - Safra: `clima_historico` com `escala` = `dia` e as datas da safra.
   - Estação do usuário: pule para o passo 2 com o arquivo dele.
2. **Grave a resposta em um arquivo de texto**, um para a tabela mensal e
   outro para a diária. O formato está na seção "Como transcrever". Não
   resuma, não arredonde e não pule linha. O bloco "FONTES DOS DADOS" do fim
   da resposta vai junto: é dele que o relatório tira a fonte de cada dado.
3. **Rode o diagnóstico** (não calcula o balanço):
   ```
   python scripts/balanco.py --diagnostico --mensal mensal.txt --diario diario.txt --saida saida
   ```
   Se alguma linha da conferência disser **NÃO FECHA**, a transcrição tem
   erro: corrija o arquivo comparando com a resposta da ferramenta e rode de
   novo. O balanço não roda enquanto a conferência não fechar.
4. **Mostre o diagnóstico ao usuário**: a conferência, as normais de cada mês,
   a ETP do ano por método, o índice de calor, e, quando as duas tabelas têm
   meses em comum, a diferença entre a soma mensal e a soma diária.
5. **Pergunte o que é dele** (seções abaixo): a **CAD**; o **método de ETP**;
   a **chuva do ano normal** (`referencia` ou `periodo`), quando a tabela traz
   as duas; e, no sequencial, o **armazenamento inicial**. Se ele pedir
   "escolhe você", explique em uma frase o que muda e devolva a pergunta.
   Para ver o efeito da CAD no ano normal antes de decidir, repita o
   diagnóstico com `--etp` e `--chuva` já escolhidos. **Sem a resposta dele,
   não rode.**
6. **Rode o balanço**:
   ```
   python scripts/balanco.py --normal --mensal mensal.txt --cad <mm> --etp <método> \
       --chuva <referencia|periodo> --nome "<lugar>" --fonte conector --saida saida

   python scripts/balanco.py --sequencial --diario diario.txt --mensal mensal.txt --cad <mm> \
       --etp <método> --arm-inicial <cad|normal|mm> [--chuva <referencia|periodo>] --nome "<lugar>" \
       --fonte conector --saida saida
   ```
   Com `--fonte conector`, o relatório cita as fontes que a ferramenta
   escreveu no bloco "FONTES DOS DADOS" dos arquivos; se o bloco não foi
   colado, o script avisa e você corrige o arquivo antes de entregar. Com
   dado de estação, `--fonte "<nome da estação>"`. No sequencial, a
   tabela mensal só é necessária para Thornthwaite (índice de calor) e para
   `--arm-inicial normal`, que também pede `--chuva`. Uma sequência de anos
   por mês sai direto da tabela mensal, sem a diária: `--sequencial --mensal
   mensal.txt --passo mes`.
7. **Relate o resultado inteiro**: as escolhas e a origem de cada número; a
   tabela; os totais; a aferição; a frase sobre o armazenamento inicial; e
   **todos os avisos, com as palavras do script**. Mostre
   `balanco_normal_graficos.png` ou `balanco_sequencial_graficos.png`.
8. **Entregue os arquivos** e diga para que serve cada um. Outra CAD ou outro
   método é outra rodada: rode de novo e diga o que mudou. Os dados são os
   mesmos, não chame a ferramenta outra vez.

Para ver a skill funcionando sem dado nenhum: `python scripts/balanco.py --demo`
(dados inventados; o script diz o que foi fixado só no exemplo).

## Como transcrever a resposta da ferramenta

Dois jeitos, que o script lê igual:

- **Colar o texto como veio**, do título `Chuva — ...` até o fim do bloco
  "FONTES DOS DADOS". O script tira sozinho o período, o total, os avisos e
  as fontes.
- **Formato compacto**, mais curto: uma linha por dia ou por mês, com as
  linhas de controle em cima.

```
local: -17.8, -50.93
periodo: 01/07/2024 a 30/06/2025
total: 1.518,2
temperatura: 10 40
avisos: 15 dia(s): o pluviômetro de referência mais próximo somou bem menos...
fonte: [uma linha do bloco "FONTES DOS DADOS", copiada como veio]
2024-07-01 0,0 17 30
2024-07-02 0,0 17 31
```

| Linha | De onde vem na resposta da ferramenta |
|---|---|
| `local:` | o que vem depois de `Chuva —`: as coordenadas ou "área de N ha" |
| `periodo:` | as duas datas do título |
| `total:` | o total em mm da linha `RESUMO` |
| `temperatura:` | só na escala de dia: `mín` e `máx` da linha `TEMPERATURA` |
| `normal:` | só na escala de mês: os 12 valores de `média` de um ano inteiro, de janeiro a dezembro |
| `avisos:` | a linha `AVISOS`, inteira; uma linha `avisos:` para cada aviso |
| `fonte:` | cada linha do bloco `FONTES DOS DADOS`, inteira e como veio; uma linha `fonte:` para cada uma |
| dia | `AAAA-MM-DD chuva mínima máxima` (a faixa `temp 17–30°C` vira `17 30`) |
| mês | `AAAA-MM chuva mínima máxima` (a faixa `temp média 20.5–28.5°C` vira `20.5 28.5`) |

Copie os números como estão: chuva com vírgula, temperatura com ponto. Dia
com `SEM DADO` vira `sd`. Linha com `confiança baixa` pode levar `cb` no fim.
Umidade, vento e graus-dia não entram.

O script confere: nenhum dia ou mês faltando ou repetido; o período; **a soma
da chuva contra o total da ferramenta**; e a menor mínima e a maior máxima.
Erro pequeno, menor que a folga de arredondamento (perto de 2 mm em um ano de
dias), ou dois erros que se compensam, passam: transcreva com calma.

## As escolhas do usuário

**CAD (capacidade de água disponível), em mm.** É do solo e da profundidade
das raízes: CAD = (capacidade de campo − ponto de murcha, em %) ÷ 100 ×
densidade do solo × profundidade efetiva das raízes (mm). Como referência,
para ele decidir (Sentelhas e Angelocci, ESALQ/USP; valores gerais de
Doorenbos e Kassam, 1994, e de Alfonsi et al., 1990):

- por textura: solo argiloso 2,0 mm por cm de profundidade; textura média
  1,4; arenoso 0,6;
- profundidade efetiva das raízes: hortaliças 10 a 20 cm; arroz, batata e
  feijão 20 a 30; trigo 30 a 40; milho e soja 40 a 50; amendoim 50 a 60;
  cana, citros e café 70 a 100;
- para caracterizar o clima de uma região, é comum usar de 75 a 125 mm.

Mostre a referência; não escolha o valor.

**Método de ETP** (`--etp`). Liste os que rodam com os dados (o diagnóstico
diz) com a linha de cada um. Não indique um.

| `--etp` | O que é |
|---|---|
| `thornthwaite` | Thornthwaite (1948): só a temperatura média. Feito para clima úmido e para o mês; em clima seco costuma subestimar a ETP. É o método original do balanço climatológico. |
| `thornthwaite-tef` | O mesmo, com a temperatura efetiva de Camargo et al. (1999), 0,36 × (3 × máxima − mínima), proposta para valer também em clima seco. |
| `hargreaves` | Hargreaves e Samani (1985): mínima, máxima e radiação no topo da atmosfera. Feito para clima seco; em clima úmido costuma superestimar a ETP. |
| `informada` | A ETP da tabela do usuário (estação com Penman-Monteith, tanque). A skill não recalcula. |

**Chuva do ano normal** (`--chuva`): `referencia` é a média histórica de 1991
a 2020 que a ferramenta informa em cada mês; `periodo` é a média dos anos da
tabela. A temperatura é sempre a dos anos da tabela: com `referencia`, chuva
e temperatura vêm de períodos diferentes, e o relatório avisa.

**Armazenamento inicial do sequencial** (`--arm-inicial`): `cad` (solo cheio,
quando a série começa depois de um período chuvoso); `normal` (o do ano
normal no fim do mês anterior ao começo da série); ou o valor em mm. O
relatório diz até que período o resultado depende dessa escolha.

## Parâmetros

| Parâmetro | O que faz | Padrão |
|---|---|---|
| `--mensal`, `--diario` | as tabelas transcritas ou da estação | — |
| `--normais` | tabela de 12 normais do usuário (mês, chuva, temperatura ou ETP), no lugar da mensal | — |
| `--cad` | CAD em mm, de 5 a 500 | **sem padrão: o usuário informa** |
| `--etp` | método de ETP | **sem padrão: o usuário escolhe** |
| `--chuva` | `referencia` ou `periodo` | **sem padrão quando a tabela traz as duas** |
| `--arm-inicial` | `cad`, `normal` ou mm | **sem padrão: o usuário informa** |
| `--anos 2005-2024` | anos que entram nas médias | todos os anos completos da tabela |
| `--passo` | `decendio` ou `mes` no sequencial | `decendio` com tabela diária |
| `--de`, `--ate` | recorta o sequencial | a tabela inteira |
| `--sem-dado zero` | conta como zero os dias sem dado de chuva | recusa |
| `--latitude` | graus decimais, sul negativo | a da linha `local:`, quando é ponto |
| `--nome`, `--fonte` | título do relatório e origem dos dados: `conector` (cita as fontes do bloco "FONTES DOS DADOS" dos arquivos) ou o nome da estação | — |

Decêndios: dias 1 a 10, 11 a 20 e 21 ao fim do mês. Só entram decêndios
inteiros; os dias que sobram nas pontas ficam de fora, e o script diz quantos.
As fórmulas, as fontes e os limites: `references/metodo.md`.

## Regras de honestidade

- **Diagnóstico antes, sempre**, e balanço só com a conferência fechada.
- **CAD, método, chuva normal e armazenamento inicial vêm do usuário.** Não
  use "o mais comum" por conta própria.
- **Descreva, não recomende.** "Em agosto a deficiência do ano normal é de 60
  mm, para a CAD de 100 mm", e não "é preciso irrigar" nem "plante em
  outubro". Não use bom, ruim, crítico, favorável.
- **Diga de onde saiu cada número**: qual tabela, quais anos, qual método,
  qual CAD. O ano normal usa a tabela mensal; o sequencial por decêndio usa a
  diária. As duas séries da ferramenta não precisam fechar entre si no mesmo
  período: quando o diagnóstico mostrar a diferença, repita-a.
- **ETP é estimativa por temperatura.** Os métodos dão valores diferentes
  para os mesmos dados; mostre a tabela do diagnóstico em vez de escolher.
- **Não esconda aviso**: confiança baixa, dia sem dado contado como zero,
  temperatura acima de 26,5 °C, períodos diferentes de chuva e temperatura,
  dependência do armazenamento inicial.
- **Recusa é recusa.** Se o script não rodou, repasse o motivo. Não contorne
  nem faça a conta por fora.
- **Avisos da ferramenta vão com as palavras dela**, e o que ela marcou como
  provisório ou de confiança baixa continua marcado.

## Saídas (na pasta `--saida`)

- `balanco_normal.pdf` ou `balanco_sequencial.pdf` — a tabela com as escolhas,
  a aferição e os avisos; depois os gráficos. O `.png` de mesmo nome é a
  primeira página.
- `..._graficos.png` — extrato (excedente e deficiência), chuva com ETP e
  ETR, e armazenamento.
- `....csv` — a tabela inteira (ponto e vírgula e vírgula decimal). Em série
  com mais de 96 períodos, o PDF resume por ano e o CSV traz todos.
- `....json` — todos os números e as escolhas.
- No diagnóstico: `diagnostico.json`.

## Fontes dos dados

Com dado do conector, a fonte de cada dado é a que a ferramenta escreve no
bloco "FONTES DOS DADOS", no fim da resposta: a da chuva, a da média histórica
e a da temperatura. Cite cada linha inteira e como veio (`--fonte conector`
faz isso no relatório, a partir dos arquivos). Não troque por um nome
genérico, não acrescente fonte que a ferramenta não informou e não descreva
como os dados são combinados nem processados: não cite plataforma, biblioteca,
nuvem nem modelo. Se o usuário perguntar como é feito, o processamento é das
ferramentas da comunidade agrônomo10X (OagronomIA) e não é divulgado. Com dado
de estação, a fonte é a estação do usuário.

## Dependências

Python com `matplotlib` (que traz o `numpy`). As contas usam só a biblioteca
padrão. Sem internet.
