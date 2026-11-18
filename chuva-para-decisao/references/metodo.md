# Método: as regras e as contas

Tudo o que a skill calcula é contagem e estatística descritiva sobre o
registro de chuva que a ferramenta devolveu. Não há modelo, ajuste de
distribuição nem previsão.

## 1. De onde vem o dado

- **Tabela mensal**: uma chamada de `clima_historico` em escala de mês, do
  começo da série (1998) ao último ano agrícola encerrado. Traz a chuva de cada
  mês, a média 1991–2020 do mês e os graus-dia do mês.
- **Janela dia a dia**: uma chamada por ano, em escala de dia, com a mesma
  janela do calendário. Traz a chuva de cada dia e o resumo da janela (total,
  dias de chuva, veranico máximo, maior chuva).
- **Ano em curso**: as frases da `contexto_chuva`, copiadas sem mexer.

Fontes: as que a ferramenta escreve no bloco "FONTES DOS DADOS", no fim de
cada resposta. O relato as repete como vieram.

**As duas réguas.** A ferramenta monta a chuva de período longo (seis meses ou
mais) de um jeito e a de período curto de outro. No teste da skill, em um ponto
do Centro-Oeste, os meses da tabela longa ficaram cerca de 10% acima da soma
dos dias da janela curta, nos dez anos comparados. Por isso a skill não cruza
os dois blocos: as contagens mensais usam só a tabela mensal, e as contagens
de decêndio, veranico e data usam só a janela. Um corte em milímetros vale
para o bloco em que foi informado.

## 2. A conferência da transcrição

A IA copia os números do texto da ferramenta para um arquivo. Antes de
qualquer conta, o script confere a cópia contra o que a própria ferramenta
informou:

- número de dias (ou meses contínuos);
- soma contra o total do período. A folga é de `1,0 + 0,12 × √n` mm, onde `n`
  é o número de valores, porque cada valor vem arredondado a 0,1 mm;
- o dia da maior chuva tem o valor informado e nenhum dia o ultrapassa;
- os dias do veranico máximo informado têm no máximo 2 mm, e os dois dias
  vizinhos têm pelo menos 0,9 mm. A ferramenta trata como dia sem chuva o que
  fica abaixo de 1 ou de 2 mm, conforme a fonte do dia;
- os graus-dia somados contra o total, quando há.

A soma e a contagem pegam dia pulado ou repetido. A maior chuva e o veranico
pegam trecho deslocado. Dois erros que se anulam em um trecho sem chuva (um zero
a menos aqui, um zero a mais ali, longe do veranico máximo) podem passar: o
efeito é deslocar um dia de chuva em um dia.

## 3. Calendário mensal

Para cada mês do calendário, com todos os anos da tabela:

- **mediana**: metade dos anos ficou abaixo, metade acima;
- **P20 e P80**: percentis 20 e 80, com interpolação linear entre os valores
  ordenados. Entre eles ficaram cerca de 6 de cada 10 anos;
- **menor e maior**, com o ano;
- **média 1991–2020**: a que a ferramenta devolve ao lado de cada mês;
- **anos abaixo do corte**: contagem simples, para cada corte informado.

Nos meses secos o dado mensal tem um piso: valores pequenos se repetem
idênticos em anos diferentes. Não há informação na diferença entre eles.

**Ano agrícola**: 12 meses a partir do mês informado (julho, se nada for
dito). Só entram anos inteiros. A posição de cada ano é a ordem do total, do
maior para o menor.

**Regra mensal das águas**, com o corte `X` informado:

- *firmaram* no primeiro mês do ano agrícola com pelo menos `X` mm, seguido de
  outro mês também com pelo menos `X` mm;
- *terminaram* no último mês com pelo menos `X` mm antes de dois meses
  seguidos abaixo de `X`.

Se em mais da metade dos anos o primeiro mês do ano agrícola já passa do
corte, a regra não separa estação seca naquele local, e o relato diz isso em
vez de dar os meses.

## 4. Graus-dia

A ferramenta entrega os graus-dia de cada mês, com a temperatura-base pedida
na chamada. A skill só soma:

- **soma no período**: do mês do plantio ao mês final, ano a ano;
- **dias até o alvo**: contados do dia 1º do mês do plantio. Dentro de cada
  mês os graus-dia são repartidos por igual entre os dias, porque a tabela é
  mensal. É uma aproximação: serve para comparar anos, não para marcar o dia
  de uma fase da cultura.

Em período longo a temperatura da ferramenta é dado modelado mensal: boa para
média e graus-dia, com os extremos suavizados.

## 5. Janela dia a dia

**Dia seco**: dia com menos de `L` mm, o valor informado. Dia sem dado não é
seco nem chuvoso: quebra qualquer sequência e fica fora das somas.

**Decêndio**: do dia 1 ao 10, do 11 ao 20 e do 21 ao fim do mês. Só contam os
decêndios inteiros dentro da janela. Para cada um: o total de cada ano, a
mediana, o menor e o maior com o ano, em quantos anos o total chegou a cada
corte informado e em quantos não houve nenhum dia com `L` mm ou mais.

**Veranico**: sequência de `D` ou mais dias secos seguidos, dentro da janela.
Para cada `D` informado: em quantos anos houve pelo menos uma. De cada ano
sai também a maior sequência seca, com as datas. Sequência que encosta no
primeiro ou no último dia da janela pode ter sido maior do que aparece.

O veranico máximo que a ferramenta informa vai ao lado, na tabela por ano. Ele
usa a régua da ferramenta para o dia sem chuva e pode diferir do contado aqui
quando o `L` informado é outro.

**Início das águas**, com quatro números informados (`A` mm, em `N` dias, `F`
dias secos, `J` dias de conferência): o primeiro dia `t` da janela em que

1. choveu pelo menos `L` mm no dia `t`;
2. os `N` dias a partir de `t` somam pelo menos `A` mm;
3. nos `J` dias depois de `t` não há `F` dias secos seguidos (se houver, `t`
   é um **falso início** e a procura continua).

Situações possíveis em cada ano:

- *determinado*: a regra fechou e os `J` dias de conferência cabem na janela;
- *sem conferência*: a regra fechou a menos de `J` dias do fim da janela. A
  data aparece na tabela, marcada, e fica fora das contagens;
- *não firmou na janela*: nenhum dia fecha os itens 1 e 2 sem cair no 3.

Se a regra fecha no primeiro dia da janela, as águas podem ter firmado antes:
o relato diz "ou antes". Comece a janela ainda na seca.

**Fim das águas**, com o número `E` informado: o último dia com pelo menos `L`
mm antes da primeira sequência de `E` ou mais dias secos seguidos, em uma janela
do fim da estação. Se a sequência começa no primeiro dia da janela, as águas
já tinham terminado antes. Se não há sequência desse tamanho inteira dentro da
janela, não terminaram na janela.

**Do início ao fim**: quando as duas janelas foram consultadas e as duas datas
fecharam, a diferença em dias, contando os dois extremos.

**Resumo das datas entre os anos**:

- a mais cedo e a mais tarde, com o ano;
- "em metade dos anos até": a data em que pelo menos metade de TODOS os anos
  da contagem já tinha fechado a regra (com 10 anos, a 5ª data);
- o acumulado no fim de cada decêndio: "até 10/10, em 6 de 10 anos". O
  denominador é sempre o total de anos consultados, não só os determinados.

## 6. De onde vêm as regras de início e fim

Definir o início da estação chuvosa por um acumulado mínimo em poucos dias,
seguido de um teste de falso início, é prática da agroclimatologia desde os
trabalhos de Stern, Dennett e Garbutt (1981) e de Sivakumar (1988) para a
África Ocidental. Os números variam de um trabalho para outro e de uma região
para outra. Por isso a skill não tem valor padrão: mostra os de uso comum e
usa os que o usuário informar. Trocar os números troca as datas; o relato
sempre traz a regra escrita por extenso.

- Stern, R. D.; Dennett, M. D.; Garbutt, D. J. (1981). The start of the rains
  in West Africa. *Journal of Climatology*, 1, 59–68.
- Sivakumar, M. V. K. (1988). Predicting rainy season potential from the onset
  of rains in Southern Sahelian and Sudanian climatic zones of West Africa.
  *Agricultural and Forest Meteorology*, 42, 295–305.

## 7. Limites

- **Amostra.** A série tem menos de 30 anos, e a janela dia a dia costuma ter
  10. Contagem em 10 anos muda bastante com um ano a mais ou a menos, e evento
  raro pode não aparecer. Por isso o relato dá contagens, com os anos, e não
  porcentagens.
- **O dado.** É chuva estimada para o local a partir de pluviômetros e
  satélites, não a do pluviômetro da fazenda. A ferramenta informa a confiança
  de cada período; o relato repete.
- **O clima muda.** Os anos de 1998 para cá não são uma amostra de um clima
  parado. A skill não testa tendência.
- **Chuva não é água disponível.** Sem evapotranspiração e sem a capacidade
  de água do solo, a contagem de dias secos não diz se a planta sofreu.
- **Um local por vez**, com janela de até 180 dias (a partir de seis meses a
  ferramenta muda a régua dos milímetros diários).
- **Não é o ZARC.** O zoneamento oficial usa balanço hídrico, ciclo da
  cultivar e tipo de solo. Este relato não o reproduz nem o substitui.
