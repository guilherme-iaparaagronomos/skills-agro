# Método, conferência e limites

## 1. O que a skill calcula

O balanço hídrico climatológico de Thornthwaite e Mather (1955): a
contabilidade da água num solo de capacidade CAD, que recebe a chuva (P) e
perde a evapotranspiração. Duas contas:

- **ano normal**: 12 meses com a chuva e a temperatura normais do lugar. É
  cíclico: dezembro emenda em janeiro;
- **sequencial**: os períodos de uma safra ou de uma série de anos, na ordem
  em que aconteceram, a partir de um armazenamento inicial.

## 2. A evapotranspiração potencial (ETP)

Três métodos, todos só com temperatura e latitude. A astronomia segue as
equações do boletim FAO 56 (Allen et al., 1998), dia a dia, com a média dos
dias do período:

- declinação: δ = 0,409 · sen(2πJ/365 − 1,39), com J = dia do ano;
- ângulo do pôr do sol: ωs = arccos(−tan φ · tan δ);
- fotoperíodo: N = 24/π · ωs, em horas;
- radiação no topo da atmosfera: Ra = (24·60/π) · 0,0820 · dr · (ωs · sen φ ·
  sen δ + cos φ · cos δ · sen ωs), em MJ/m²/dia, com dr = 1 + 0,033 ·
  cos(2πJ/365); em mm/dia, Qo = 0,408 · Ra.

**Thornthwaite (1948).** Índice de calor do lugar, das 12 temperaturas médias
mensais normais: I = Σ (Tn/5)^1,514; expoente a = 6,75·10⁻⁷·I³ − 7,71·10⁻⁵·I²
+ 1,7912·10⁻²·I + 0,49239. ETP de um mês padrão (30 dias, 12 horas de luz):
ETp = 16 · (10·T/I)^a, para 0 ≤ T < 26,5 °C; para T ≥ 26,5 °C, ETp = −415,85
+ 32,24·T − 0,43·T² (Willmott et al., 1985), mantida constante acima de 37,5
°C, o vértice do polinômio; para T ≤ 0, ETp = 0. Correção para o período: ETP
= ETp · (N/12) · (dias/30). No sequencial, I e a continuam sendo os das
normais do lugar, e T é a temperatura média de cada período.

Algumas publicações usam a forma abreviada I = 12 · (0,2 · Ta)^1,514, com a
temperatura média anual. A skill usa a soma dos 12 meses, a forma original.

**Thornthwaite com temperatura efetiva (Camargo et al., 1999).** A mesma
conta, com Tef = 0,36 · (3 · Tmáx − Tmín) no lugar da temperatura média. I e
a continuam vindo das temperaturas médias normais.

**Hargreaves e Samani (1985).** ETP = 0,0023 · Qo · (Tmáx − Tmín)^0,5 · (Tméd
+ 17,8) · dias, com Qo em mm/dia. Tmáx e Tmín são as médias do período.

**ETP informada.** Quando a tabela do usuário traz a coluna de ETP (estação
com Penman-Monteith, tanque), o balanço usa esse valor e não estima nada.

O que as notas de aula de Sentelhas e Angelocci (ESALQ/USP) dizem dos três:
Thornthwaite foi feito para clima úmido e costuma subestimar a ETP em clima
seco, e não tem sensibilidade para a escala diária; a temperatura efetiva foi
proposta para o método valer em qualquer clima; Hargreaves e Samani foi feito
para clima seco e costuma superestimar em clima úmido. Por isso o diagnóstico
mostra os três lado a lado e a escolha é do usuário.

## 3. O balanço

Em cada período, com D = P − ETP:

| | D < 0 (o solo seca) | D ≥ 0 (o solo repõe) |
|---|---|---|
| armazenamento (ARM) | ARM anterior · exp(D/CAD) | o menor entre CAD e ARM anterior + D |
| alteração (ALT) | ARM − ARM anterior | ARM − ARM anterior |
| ETR | P + \|ALT\| | ETP |
| deficiência (DEF) | ETP − ETR | 0 |
| excedente (EXC) | 0 | o que passou da CAD |

O negativo acumulado é NEG.AC = CAD · ln(ARM/CAD). A retirada exponencial é a
equação de Mendonça (1958), que substituiu as tabelas de água retida do
método original; multiplicar o armazenamento anterior por exp(D/CAD) é o
mesmo que acumular o negativo (Pereira, 2005).

Identidades que o script confere em toda rodada (aferição): ΣP = ΣETR + ΣEXC
+ variação do armazenamento; ΣETP = ΣETR + ΣDEF; no ano normal a variação do
armazenamento é zero.

## 4. A partida do ano normal

No ano normal o armazenamento de dezembro tem de ser o mesmo um ano depois.
Só existe um valor que fecha esse ciclo, e a skill o acha de forma exata:

- se o solo enche em algum mês, o que vem depois não depende mais da partida,
  e uma volta a mais pelo ano dá o valor;
- se a reposição do ano nunca enche o solo, a volta inteira é uma função afim
  do armazenamento de partida, e o ponto que fecha o ciclo sai direto. Com
  uma estação seca só, é o critério de Mendonça: ARM no fim da estação úmida
  = M / (1 − exp(N/CAD)), com M a soma dos D positivos e N a dos negativos.

O roteiro usual de sala de aula tem três casos para o fim da estação úmida:
(A) soma anual de D ≥ 0, ARM = CAD; (B) soma negativa e M ≥ CAD, ARM = CAD;
(C) soma negativa e M < CAD, pela fórmula de Mendonça. Dois pontos em que a
skill vai além dele:

- vale também para ano com mais de uma estação seca, que o roteiro não cobre;
- no caso C, a fórmula pode dar armazenamento **acima da CAD** quando M < CAD
  mas M / (1 − exp(N/CAD)) > CAD. Aí o solo enche, e a skill limita na CAD.
  Em 4.000 anos sorteados na conferência, isso aconteceu em 52.

## 5. O sequencial

- **Períodos**: decêndios (dias 1 a 10, 11 a 20, 21 ao fim do mês) ou meses.
  Só entram períodos inteiros. A chuva do período é a soma dos dias; a
  temperatura, a média das mínimas e a média das máximas dos dias.
- **Armazenamento inicial**: informado pelo usuário. O script roda a série
  duas vezes por conta própria, com o solo cheio e com o solo vazio, e diz a
  partir de que período as duas dão o mesmo armazenamento (diferença menor
  que 1 mm). Antes desse ponto, o resultado depende do que foi informado.
- **Dia sem dado de chuva**: o balanço não pula dia. O script recusa, a não
  ser que o usuário mande contar como zero; aí o relatório diz quantos foram.

## 6. De onde vêm as normais

- **Chuva de referência**: a média histórica de 1991 a 2020 que a ferramenta
  de clima informa ao lado de cada mês. O script pega os 12 valores.
- **Chuva do período**: a média de cada mês nos anos completos da tabela.
- **Temperatura**: sempre a média dos anos completos da tabela. A ferramenta
  avisa que, em período longo, a temperatura mensal é dado modelado, com os
  extremos suavizados: serve para a média, e a amplitude (que entra em
  Hargreaves e na temperatura efetiva) pode sair menor que a de uma estação.

Com a chuva de referência, chuva e temperatura vêm de períodos diferentes; o
relatório avisa.

**Por que não há ano normal por decêndio.** Das normais mensais não sai a
normal de cada decêndio: seria preciso a chuva diária de todos os anos, e
dividir o mês em três partes iguais esconderia a distribuição dentro do mês.
Com as 12 normais, a skill entrega o balanço mensal.

**A série diária e a série mensal podem não fechar.** No teste com o
conector, os mesmos 12 meses somaram 1.669,5 mm na resposta por mês (série
longa) e 1.518,6 mm na resposta por dia: 9% de diferença. A ferramenta monta
as duas por caminhos diferentes. O diagnóstico mostra essa diferença quando
as tabelas têm meses em comum; cada balanço usa a sua tabela e diz qual.

## 7. A conferência da transcrição

O script não chama o conector: quem leva os números da resposta da ferramenta
para o arquivo é a IA. Por isso todo arquivo passa por:

- dias ou meses seguidos, sem falta e sem repetição;
- período informado igual à primeira e à última linha;
- soma da chuva das linhas contra o total da ferramenta, com folga de
  0,1·√n mm (n = número de linhas; mínimo de 0,5 mm), que é cerca de 3,5
  vezes o desvio do erro de arredondamento somado. Para 365 dias, 1,9 mm;
- menor mínima e maior máxima contra as que a ferramenta informa (dias).

O que a conferência **não** pega: erro menor que a folga; dois erros que se
compensam; troca de temperatura que não mexe nos extremos do período.

## 8. Contra o que foi conferida

**Publicações, número a número.**

- Balanço: cinco tabelas publicadas, com a chuva e a ETP da publicação como
  entrada. Posse (GO), Petrolina (PE), Garanhuns (PE) e Passo Fundo (RS), CAD
  de 100 mm (Sentelhas e Angelocci, aula 9); Campina Grande (PB), CAD de 125
  mm (Pereira, 2005). São 228 casas de armazenamento, ETR, deficiência e
  excedente; todas dentro de 1 mm do valor impresso (inteiro). A maior
  diferença, 0,82 mm, está na ETR e na deficiência de meses em que a
  publicação somou valores já arredondados. Cobrem os três casos de partida
  e o ano sem deficiência.
- ETP: os exemplos de Piracicaba da aula 8. Thornthwaite de janeiro (ETp
  111,3 e ETP 128,4 mm; a skill dá 111,5 e 128,6 com o mesmo fotoperíodo: a
  aula arredonda o expoente para 2,33); temperatura efetiva de julho (23,4
  °C; 92,1 mm, a skill dá 92,3); Hargreaves de janeiro e de julho (170,2 e
  92,0 mm; a skill dá 170,2 e 92,1).
- Radiação no topo da atmosfera: a tabela da mesma aula (latitudes 0, 10, 20
  e 30° sul, 12 meses). A equação da FAO 56 fica de 1,4% a 4,7% **acima** em
  todas as 48 casas (2,5% na média). A diferença é sistemática: tabelas e
  equação adotam constantes diferentes. A skill usa a equação.
- Fotoperíodo: o exemplo da aula usa 13,4 h em janeiro e 10,6 h em julho, que
  são os valores dos solstícios naquela latitude; a média do mês pela equação
  é 13,2 h e 10,8 h. A skill usa a média do mês.

**Por outro caminho.**

- O ano normal refeito pelo roteiro clássico (negativo acumulado e critérios
  A, B e C), em programa à parte: 4.000 anos sorteados com uma estação seca,
  os 12 meses de cada um, iguais até a 7ª casa.
- A partida do ano normal contra a força bruta (400 anos seguidos a partir do
  solo cheio): 300 anos sorteados, de 12 e de 36 períodos, com uma ou mais
  estações secas.
- A ETP dos três métodos, o balanço do ano normal e o sequencial por decêndio
  dos dados reais do teste, recalculados em programa à parte a partir do
  arquivo transcrito: 360 casas iguais ao CSV da skill.
- Trocar a declinação da FAO 56 pela de Cooper (1969) muda a ETP anual de
  Hargreaves em 0,01%.

**Com o conector.** Duas consultas a `clima_historico` num ponto do sudoeste
de Goiás: 27 anos por mês (324 linhas) e uma safra por dia (365 linhas),
transcritas à mão para o formato compacto. A soma das linhas ficou a 0,3 mm e
a 0,4 mm do total da ferramenta, e a média anual calculada (1.622,1 mm) bateu
com a que a ferramenta escreve (1.622,0 mm).

**Pela linha de comando.** 269 conferências: os três modos, os três métodos,
as cinco tabelas publicadas passadas como arquivo, texto da ferramenta colado
contra formato compacto, planilha XLSX contra CSV, e 25 pedidos que têm de
parar com o motivo escrito (escolha que falta, transcrição que não fecha,
dado que o método não aceita).

## 9. O que não foi conferido

- Não houve comparação com a planilha BHnorm nem com outro programa rodando
  os mesmos dados; a referência foram as tabelas impressas.
- A temperatura efetiva e Hargreaves e Samani só têm dois valores publicados
  cada na conferência.
- O sequencial por decêndio não foi comparado com tabela publicada; foi
  refeito à parte e conferido pelas identidades.
- A transcrição foi feita uma vez, por uma IA. Não foi usada por um membro
  numa conversa de verdade.
- Dado de estação: só arquivos montados para o teste.
- Latitude norte: as equações valem, e não houve teste com dado de lá.

## 10. Limites

- Balanço **climatológico**: sem cultura, sem Kc, sem fase, sem irrigação,
  sem escorrimento. Do solo, só a CAD.
- A ETP é estimativa por temperatura. Os três métodos diferem bastante entre
  si (no teste, de 1.225 a 1.517 mm por ano no mesmo lugar), e nenhum é
  Penman-Monteith.
- Thornthwaite no decêndio é aproximação de uso corrente; o método é mensal.
- CAD de 5 a 500 mm. Latitude entre 66° sul e 66° norte.
- A chuva do conector é estimativa por pluviômetros e satélites; a ferramenta
  informa a confiança, e o relatório repete os avisos dela.

## Fontes

- Allen, R. G.; Pereira, L. S.; Raes, D.; Smith, M. (1998). Crop
  evapotranspiration. FAO Irrigation and Drainage Paper 56.
- Camargo, A. P.; Marin, F. R.; Sentelhas, P. C.; Picini, A. G. (1999).
  Ajuste da equação de Thornthwaite para estimar a evapotranspiração
  potencial em climas áridos e superúmidos, com base na amplitude térmica
  diária. Revista Brasileira de Agrometeorologia, 7(2), 251–257.
- Hargreaves, G. H.; Samani, Z. A. (1985). Reference crop evapotranspiration
  from temperature. Applied Engineering in Agriculture, 1(2), 96–99.
- Mendonça, P. V. (1958). Sobre o novo método de balanço hidrológico do solo
  de Thornthwaite-Mather. Congresso Luso-Espanhol para o Progresso das
  Ciências, 24, Madri, p. 271–282 (citado por Pereira, 2005).
- Pereira, A. R. (2005). Simplificando o balanço hídrico de
  Thornthwaite-Mather. Bragantia, 64(2), 311–313.
- Sentelhas, P. C.; Angelocci, L. R. (2012). LCE 306 Meteorologia Agrícola,
  ESALQ/USP: aula 8 (evapotranspiração) e aula 9 (balanço hídrico). Dali vêm
  as tabelas de conferência e as referências de CAD (Doorenbos e Kassam,
  1994; Alfonsi et al., 1990).
- Thornthwaite, C. W. (1948). An approach toward a rational classification of
  climate. Geographical Review, 38(1), 55–94.
- Thornthwaite, C. W.; Mather, J. R. (1955). The water balance. Publications
  in Climatology, 8(1). Drexel Institute of Technology.
- Willmott, C. J.; Rowe, C. M.; Mintz, Y. (1985). Climatology of the
  terrestrial seasonal water cycle. Journal of Climatology, 5, 589–606.
