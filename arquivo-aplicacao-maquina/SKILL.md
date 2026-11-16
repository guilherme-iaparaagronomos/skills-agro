---
name: arquivo-aplicacao-maquina
description: >-
  Adequa o mapa de aplicação em taxa variável ao monitor da máquina e entrega o
  zip pronto para extrair na raiz do pen drive. Entra o mapa de polígonos com a
  dose (shapefile, GeoJSON, KML ou KMZ; ou as zonas de manejo com a dose de
  cada zona); saem só o .shp, o .shx e o .dbf, em graus, sem projeção e sem Z,
  com a dose em campo numérico, nome curto e a pasta que o controlador espera
  (Trimble CFX 750 e GFX 750, Stara, Raven, John Deere, New Holland, Hexagon,
  Arvus, Agres, Jacto), mais o passo a passo e o relatório do que mudou. Confere
  o arquivo relendo o que gravou. Não calcula, não recomenda e não altera dose:
  conversão de unidade, degrau e limites só com o valor que o usuário informar.
  Pergunta o controlador, o produto, a unidade e o campo da dose. Acione com
  "arquivo para a máquina", "mapa de taxa variável no pen drive", "o monitor
  não lê o shape", "preparar a prescrição para o controlador" ou quando o
  usuário quiser levar um mapa de aplicação para o monitor.
---

# Arquivo de aplicação para a máquina

O usuário tem o mapa de aplicação pronto (zonas ou grade, cada polígono com a
dose) e precisa que o monitor da máquina leia. Esta skill cuida do formato:
confere o arquivo, corrige o que os monitores costumam rejeitar e entrega:

1. um **zip para extrair na raiz do pen drive**, com a pasta que o controlador
   espera e, dentro dela, só o `.shp`, o `.shx` e o `.dbf`;
2. o **passo a passo** para o operador (`passo-a-passo.md`);
3. o **relatório** do que foi conferido e do que mudou (`relatorio.md`), com
   `conferencia.csv` (a dose de cada polígono do arquivo de máquina) e
   `mudancas.csv` (cada polígono recebido, antes e depois).

## A regra que vale para tudo: a dose é do usuário

- A skill **não calcula, não recomenda e não corrige dose**. Ela não diz se a
  dose está certa para a área, a cultura ou o produto.
- **Nenhuma dose muda sem o valor vir do usuário.** Conversão de unidade,
  arredondamento ao degrau da máquina e limite mínimo e máximo só rodam com o
  número que ele informar, e o relatório lista polígono a polígono o que mudou
  e quanto mudaram a dose média e o total de produto. Mostre essa diferença a
  ele antes de entregar.
- **Pergunte, não escolha**: o controlador, o tipo de produto, a unidade em
  que a dose está, o campo da dose e o nome do arquivo. O arquivo não diz a
  unidade; não deduza pela grandeza dos números.
- Polígono sem dose, dose em texto que não é número, dose negativa, polígonos
  sobrepostos com doses diferentes: o script **para e diz por quê**. Repasse o
  motivo e a pergunta ao usuário. Não contorne.
- Não diga que o arquivo "vai funcionar" no monitor. O formato foi conferido;
  nenhum arquivo desta skill foi carregado num monitor de verdade. Quem
  confirma é o operador, olhando a dose de dois ou três polígonos na tela
  antes de aplicar.

## O que precisa estar disponível

- **Ambiente que roda Python 3 com numpy.** Sem ele, explique as regras de
  `references/regras.md` para o usuário ajustar no QGIS e não gere arquivo.
- **O mapa**: shapefile (o `.zip` com `.shp`, `.shx`, `.dbf` e, se houver,
  `.prj`), GeoJSON, KML ou KMZ, com polígonos e a dose num campo. Ou as zonas
  (por exemplo o `zonas.geojson` da skill `zonas-de-manejo`) e a dose de cada
  zona, que o usuário informa.

## Antes de gerar: as perguntas (numa mensagem só)

1. **O controlador** da máquina: Trimble CFX 750, Trimble GFX 750, Stara,
   Raven, John Deere, New Holland (IntelliView IV e Pro 700), Hexagon, Arvus,
   Agres ou Jacto. Verion usa formato próprio: veja "Verion" abaixo.
2. **O produto**: sólido (adubo, calcário, gesso), líquido ou semente.
3. **A unidade em que a dose está no arquivo**: kg/ha ou t/ha para sólido;
   l/ha ou m³/ha para líquido; sem/ha ou sem/m para semente.
4. **O nome do arquivo** no pen drive: até 8 letras e números.

Depois do diagnóstico, com os campos na tela:

5. **Qual campo traz a dose** (ou a dose de cada zona).
6. Só se ele trouxer o assunto: a unidade que a máquina pede (para converter),
   o degrau de dose que ela aceita e a menor e a maior dose que ela aplica.
   Não ofereça números; se ele não souber, o arquivo sai com a dose como veio.

O que ele já disse, não pergunte de novo.

## Fluxo de trabalho (siga nesta ordem)

1. **Diagnóstico** (não grava nada):
   `python scripts/aplicacao.py <arquivo> --diagnostico`
   Mostra os polígonos, o sistema de coordenadas, a área, cada campo com
   exemplos, a faixa, a média ponderada pela área e a dose × área, os defeitos
   de geometria, sobreposição e frestas. Com `--campo-dose` diz também quantos
   polígonos ficariam juntando os vizinhos de mesma dose.
2. **Mostre o diagnóstico e faça as perguntas que faltam.** Se o diagnóstico
   parar pedindo o fuso (coordenadas em metros sem o arquivo de projeção),
   pergunte o fuso e o hemisfério e repita com `--src-entrada utm22s`.
3. **Gere**, com as escolhas dele:
   ```
   python scripts/aplicacao.py <arquivo> --controlador <controlador> --produto <solido|liquido|semente> \
       --unidade <unidade> --campo-dose <campo> --nome <NOME> --saida saida
   ```
   Com zonas e a dose por zona:
   `--campo-zona zona --tabela-doses "1=120;2=180;3=240"` no lugar de `--campo-dose`.
4. **Leia a saída inteira.** Ela diz a dose antes e depois, quantos polígonos
   mudaram, os avisos (unidade com grandeza estranha, dose zero, sobreposição)
   e a releitura do arquivo gravado, que termina em CONFERE.
5. **Entregue** o zip, o `passo-a-passo.md` e o `relatorio.md`, e diga:
   - extrair o zip na **raiz** do pen drive (FAT32, em geral com menos de 4
     GB), mantendo as pastas;
   - qual é o campo da dose e a unidade, para escolher no monitor;
   - o que mudou na dose, se algo mudou, com a diferença no total de produto;
   - que o arquivo não foi testado num monitor e que o operador deve conferir
     dois ou três polígonos na tela antes de aplicar;
   - o que não foi confirmado em manual para aquele controlador (está no
     passo a passo).
6. **Arquivo pesado.** Os monitores travam com polígonos demais, e o limite de
   cada um não foi confirmado em manual. Se o usuário disser o limite do
   monitor dele, ou se o arquivo for uma grade com muitas células, ofereça
   `--juntar`: junta os polígonos vizinhos de mesma dose, sem mudar a área nem
   o total de produto (o script confere os dois e não grava se mudarem).

## As opções

| Opção | O que faz | Padrão |
|---|---|---|
| `--controlador` | o monitor; define a pasta do pen drive | **sem padrão: o usuário informa** |
| `--produto`, `--unidade` | tipo do produto e unidade da dose no arquivo | **sem padrão** |
| `--campo-dose` | o campo do arquivo que traz a dose | **sem padrão** |
| `--campo-zona`, `--tabela-doses` | dose por zona, informada pelo usuário (texto `zona=dose;...` ou arquivo `zona;dose`) | — |
| `--nome` | nome do arquivo; sai em maiúsculas, sem acento nem símbolo, cortado em 8 | **sem padrão** |
| `--campo-saida` | nome do campo da dose no arquivo de máquina | o do arquivo, limpo |
| `--converter-para` | outra unidade do mesmo produto (t/ha ↔ kg/ha, l/ha ↔ m³/ha, sem/ha ↔ sem/m) | não converte |
| `--espacamento-m` | espaçamento entre linhas, para converter semente | exigido nessa conversão |
| `--degrau` | arredonda a dose ao múltiplo do valor | não arredonda |
| `--minimo`, `--maximo` | limites que a máquina aplica | sem limite |
| `--fora-do-limite cortar` | leva ao limite as doses fora dele | para e lista |
| `--casas` | casas decimais da dose | as que os valores pedem |
| `--sem-dose zero` ou `tirar` | polígono sem dose: zero, ou fora do arquivo | para e pergunta |
| `--juntar` | junta vizinhos de mesma dose | não junta |
| `--separar-partes` | grava cada parte de um multipolígono como um polígono | não separa |
| `--aceitar-sobreposicao` | gera mesmo com polígonos sobrepostos de doses diferentes | para e lista |
| `--src-entrada`, `--camada` | o fuso que o arquivo não diz; a camada, se o zip traz várias | — |

Dose zero nunca é levada ao mínimo: zero continua zero, e o relatório avisa,
porque em alguns monitores a dose zero desliga as seções.

## O que o script confere e ajusta

- só `.shp`, `.shx` e `.dbf` no pacote (sem `.prj`, `.cpg` e outros);
- coordenadas em graus decimais (o que vier em UTM é levado a graus), sem
  arquivo de projeção; polígonos sem Z nem M;
- campo da dose numérico; o `.dbf` leva só `ID` e a dose;
- nome do arquivo curto, só com letras e números; nome de campo sem acento;
- unidade coerente com o produto; aviso quando a grandeza das doses não
  combina com a unidade informada;
- pontos, linhas, feições sem geometria e polígonos sem área ficam de fora, e
  o relatório diz quantos;
- defeitos de geometria que têm conserto seguro (anel aberto, vértice
  repetido, ida e volta);
- sobreposição entre polígonos e frestas (até 2.500 polígonos; acima disso o
  relatório diz que não conferiu).

As regras, de onde vêm e o que cada controlador pede: `references/regras.md`
e `references/controladores.md`.

## Verion

O controlador Verion não usa shapefile: usa uma pasta com o nome do talhão ou
do produto e os arquivos `product1.bmp`, `product1.dat` e `product1.map`. Não
há documentação pública desse formato, então a skill **recusa** gerar: não
haveria como conferir se a máquina leria a dose certa. Diga isso ao usuário e
oriente a usar o programa do fabricante. Se ele quiser só o shapefile
conferido para levar a esse programa, gere com um controlador que grava na
raiz do pen drive e diga que aquele arquivo ainda não é o da Verion.

## O que a skill não faz

- Não calcula dose, não interpreta análise de solo e não faz recomendação.
  Para isso existem as skills de boletim da região.
- Não gera ISOXML (TASKDATA), nem formatos próprios de fabricante.
- Não trata mais de um produto por arquivo: rode uma vez por produto.
- Não simplifica contorno nem recorta sobreposição: isso muda área e precisa
  de quem fez o mapa.
- Não garante a leitura no monitor: versões de programa e opcionais variam.
