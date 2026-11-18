# Balanço hídrico

Skill que calcula o **balanço hídrico climatológico de Thornthwaite e Mather
(1955)**: o do ano normal, por mês, e o sequencial de uma safra, por decêndio
ou por mês, para a capacidade de água disponível (CAD) que o usuário informar.

**O que ela faz:**

- **Lê a chuva e a temperatura** da ferramenta `clima_historico` do conector
  ClaudIA Clima (a IA transcreve a resposta para um arquivo) ou da planilha
  de uma estação (CSV, TXT, XLSX).
- **Confere a transcrição** antes de qualquer conta: dias seguidos, período e
  a soma da chuva contra o total que a ferramenta informa.
- **Diagnóstico**: as normais de cada mês, a ETP do ano por três métodos
  (Thornthwaite, Thornthwaite com temperatura efetiva e Hargreaves e Samani)
  e o que muda com a CAD.
- **Balanço**: ETP, P − ETP, negativo acumulado, armazenamento, alteração,
  ETR, deficiência e excedente, com a aferição das identidades.
- **Saídas**: tabela em CSV, gráficos e relatório em PDF.

Ela **não escolhe** a CAD, o método de ETP, a chuva normal nem o
armazenamento inicial: mostra os números e pergunta. E **não recomenda**
irrigação, época de plantio nem cultura: descreve o balanço.

## O que precisa

- Um ambiente que rode Python com `matplotlib`.
- Os dados: o conector ClaudIA Clima da comunidade agrônomo10X, ou a tabela
  de chuva e temperatura do usuário.
- A CAD do solo, em mm, e a latitude do lugar.

## Estrutura

- [`SKILL.md`](SKILL.md) — o roteiro que a IA segue.
- `scripts/balanco.py` — a linha de comando (diagnóstico, ano normal,
  sequencial e exemplo).
- `scripts/entrada.py` — lê o texto da ferramenta, o formato compacto e a
  planilha de estação, e confere a transcrição.
- `scripts/etp.py` — fotoperíodo, radiação no topo da atmosfera e os três
  métodos de ETP.
- `scripts/bh.py` — o balanço: ano normal (cíclico) e sequencial.
- `scripts/caso.py` — as normais, a ETP de cada período e os avisos.
- `scripts/saidas.py` — CSV, gráficos e o relatório em PDF.
- `scripts/sintetico.py` — os dados inventados do exemplo e dos testes.
- `references/metodo.md` — as fórmulas, as fontes, contra o que foi conferida
  e os limites.

Cada script tem um teste embutido: `python scripts/<nome>.py`. O exemplo
completo: `python scripts/balanco.py --demo`.

## Instalar

Baixe [`balanco-hidrico.zip`](../../../releases/latest/download/balanco-hidrico.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**. Em outras
IAs, envie a pasta e peça para seguir o `SKILL.md`.

## Como foi testada

**Contra publicações, número a número.** O balanço reproduz cinco tabelas
publicadas (Posse, Petrolina, Garanhuns e Passo Fundo, das notas de aula de
Sentelhas e Angelocci, ESALQ/USP; e Campina Grande, de Pereira, 2005, na
Bragantia): 228 casas de armazenamento, ETR, deficiência e excedente, todas
dentro de 1 mm do valor impresso. As fórmulas de ETP reproduzem os exemplos
de Piracicaba das mesmas notas. A radiação no topo da atmosfera, pela equação
da FAO 56, fica de 1,4% a 4,7% acima da tabela daquelas notas, em todos os
meses: a diferença é sistemática e está descrita no método.

**Por outro caminho.** O ano normal foi refeito pelo roteiro clássico, em
programa à parte, para 4.000 anos sorteados; a ETP e o balanço dos dados do
teste foram recalculados à parte e bateram com o CSV. Pela linha de comando,
269 conferências, com 25 pedidos que têm de parar com o motivo escrito.

**Com o conector de verdade.** Duas consultas à `clima_historico` em um ponto
do sudoeste de Goiás: 27 anos por mês e uma safra por dia. As 689 linhas
foram transcritas à mão por uma IA e a soma fechou com o total da ferramenta
(0,3 mm e 0,4 mm de diferença).

**O que não foi conferido.** Não houve comparação com a planilha BHnorm nem
com outro programa rodando os mesmos dados. O sequencial por decêndio não tem
tabela publicada na conferência. A temperatura efetiva e Hargreaves e Samani
têm só dois valores publicados cada. Dado de estação: só arquivos montados
para o teste. A skill ainda não foi usada por um membro em uma conversa de
verdade. Os detalhes estão em `references/metodo.md`.

**As fontes dos dados.** Desde 18/11/2026 a ferramenta fecha cada resposta com o
bloco "FONTES DOS DADOS", e o relatório cita essas linhas como vieram. Foi
conferido com uma resposta real de 24 meses, colada inteira: as três fontes
(chuva, média histórica e temperatura) saíram no ano normal e no sequencial
por mês, no texto e no PDF; sem o bloco no arquivo, o script avisa. Com a
tabela diária de verdade, esse caminho ainda não foi refeito.

## Avisos

- O balanço é **climatológico**: não considera a cultura, a fase da lavoura,
  irrigação nem escorrimento. Do solo, a única informação é a CAD.
- A ETP é estimativa por temperatura, e os três métodos dão valores
  diferentes para os mesmos dados. A escolha é do usuário.
- A série por dia e a série por mês da ferramenta podem não fechar entre si
  no mesmo período (9% em um teste). O diagnóstico mostra a diferença.
- A conferência da transcrição pega linha faltando e soma que não fecha; não
  pega erro menor que a folga de arredondamento nem dois erros que se
  compensam.
- O relatório descreve o balanço para a CAD e o método escolhidos. A decisão
  de manejo é do responsável técnico.
