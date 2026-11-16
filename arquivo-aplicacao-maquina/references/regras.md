# As regras do arquivo de aplicação

As dez regras abaixo vêm do material de campo do fundador da comunidade
agrônomo10X (12/11/2026), que reúne o que os monitores costumam exigir do
shapefile de aplicação. Ao lado de cada uma, o que o script faz.

| Regra do material | O que o script faz |
|---|---|
| Unidades: sólido em t/ha ou kg/ha; líquido em l/ha ou m³/ha; semente em sem/m ou sem/ha | exige o produto e a unidade e recusa a combinação que não existe; converte entre as duas do mesmo produto só quando pedido |
| Cada aplicador ou dosador tem as suas particularidades | escreve no passo a passo o que foi confirmado e o que não foi para o controlador escolhido |
| A maioria das marcas aceita o shapefile sem conversão para formato próprio | gera shapefile para dez controladores; recusa a Verion, que usa formato próprio |
| O shapefile não pode ser grande (muitos polígonos) | mostra quantos polígonos e vértices há e, com `--juntar`, junta os vizinhos de mesma dose |
| Sem caracteres especiais | limpa o nome do arquivo e o nome do campo: só letras, números e sublinhado, sem acento |
| Campo de número em formato numérico, nunca texto | grava a dose como número; dose que veio como texto é lida como número e isso é relatado; texto que não é número faz parar |
| Só as extensões `.shp`, `.dbf` e `.shx` | o pacote leva só as três |
| Sem projeção (coordenadas geográficas) e sem atributo Z ou M | leva tudo a graus decimais, não grava `.prj` e grava polígono simples |
| Nome curto; 8 caracteres é o recomendado | corta o nome em 8 |
| Pen drive em FAT32 e, em geral, com menos de 4 GB | vai escrito no passo a passo |

## O que é do usuário e o script não decide

| Decisão | O que acontece sem ela |
|---|---|
| Controlador | o script para e lista os dez |
| Tipo de produto e unidade | para; o arquivo não diz a unidade |
| Campo da dose, ou dose de cada zona | para; o diagnóstico mostra os campos |
| Nome do arquivo | para |
| Polígono sem dose: zero ou fora | para e lista os polígonos |
| Dose fora do limite da máquina: cortar ou não | para e lista os polígonos |
| Polígonos sobrepostos com doses diferentes | para e lista os pares |
| Fuso, quando as coordenadas estão em metros sem o arquivo de projeção | para e pede o fuso |

## As contas

- **Área**: medida no plano do UTM do fuso do centro do arquivo, em hectares.
- **Total de produto**: soma de dose × área de cada polígono, na unidade da
  dose (kg para kg/ha, t para t/ha, l para l/ha, m³ para m³/ha, sementes para
  sem/ha). Para sem/m não há total por área.
- **Dose média**: o total dividido pela área.
- **Conversão**: t/ha × 1.000 = kg/ha; m³/ha × 1.000 = l/ha; sem/m = sem/ha ×
  espaçamento entre linhas (m) ÷ 10.000.
- **Degrau**: múltiplo mais próximo do valor informado; no meio do caminho,
  para cima. Dose zero continua zero.
- **Limites**: com `--fora-do-limite cortar`, a dose abaixo do mínimo vai ao
  mínimo e a acima do máximo vai ao máximo. Dose zero não é mexida.
- **Ordem**: conversão de unidade, degrau, limites, casas decimais. O degrau e
  os limites valem na unidade final.
- **Aviso de grandeza**: o script avisa quando há dose fora de uma faixa larga
  para a unidade (por exemplo acima de 20 t/ha ou abaixo de 1 kg/ha). É só um
  sinal de unidade trocada, com corte da skill; não é limite agronômico.

## A junção de polígonos

`--juntar` agrupa os polígonos pela dose final e, em cada grupo, tira as
divisas que dois polígonos dividem (dentro de 5 cm). Cada região contígua vira
um polígono; região que não encosta em outra de mesma dose fica separada. A
área e o total de produto são comparados antes e depois, e o arquivo não é
gravado se mudarem. Grupo com polígonos sobrepostos não é juntado.

## A conferência do arquivo gravado

Depois de gravar, o script reabre o zip e confere: os três arquivos no
caminho do controlador e nada mais; geometria de polígono simples; os campos
`ID` e a dose, os dois numéricos; o número de polígonos; coordenadas em graus;
a dose de cada polígono; a área; a soma de dose × área. Se algo difere, não
entrega.

## O que nenhuma conferência daqui substitui

O arquivo não é carregado em monitor nenhum. Versão de programa, opcional de
taxa variável destravado, unidade configurada no monitor e nome de coluna que
um modelo específico exija ficam por conta do operador e do manual da máquina.
