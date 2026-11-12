# O modelo do layout e as regras de um mapa bem apresentado

## O modelo (A4 deitada; no A3 tudo cresce na mesma proporção)

```
+----------------+----------------------------------+---------------------+
| logo do        | Fazenda:       <nome>            |       TÍTULO        |
| cliente        | Proprietário:  <nome>            |                     |
+----------------+----------------------------------+---------------------+
|                                                   | Safra:        …     |
|                                                   | Atributo:     …     |
|                                                   | Profundidade: …     |
|                                                   | Área Total:   … ha  |
|                                                   +---------------------+
|                     MAPA                          |       Legenda       |
|        (camada em classes + talhões)              | CLASSE (unidade)    |
|                                                   | ■ faixa | ha (%)    |
|                                                   | ■ faixa | ha (%)    |
|                                                   +---------------------+
|                                                   |  0    1    2 km     |
|                                                   +--------+------------+
|                                                   |   N    | Mínimo: …  |
|                                                   |  data  | Máximo: …  |
|                                                   |        | Média:  …  |
+---------------------------------------------------+--------+------------+
```

Medidas no A4 (mm): margem 6; faixa de cima 17; coluna da direita 78; logo 52
de largura; rodapé da coluna 30 (norte 30 de largura); quadro da escala 16.
Sem logo, os campos Fazenda e Proprietário ocupam a faixa inteira.

A legenda é desenhada linha a linha (quadro de cor + texto), não com a legenda
automática do QGIS, porque o formato é fixo: `faixa | área ha (%)`. A altura
da linha e o tamanho da letra diminuem quando há muitas classes; até 16
classes cabem com boa leitura.

## Regras de um mapa bem apresentado

O modelo já cuida da maior parte. O que depende de quem monta:

1. **Um mapa, uma mensagem.** Um atributo por folha. Dois atributos na mesma
   folha confundem a legenda.
2. **Título que diz o que é**: "Mapa de Fertilidade do Solo", com o atributo e
   a profundidade na coluna da direita. Evite sigla que o produtor não usa.
3. **Classes que o leitor reconhece.** Limites redondos ou os da tabela de
   interpretação que ele usa. De 4 a 7 classes costuma ser o que se lê bem;
   16 cabem, mas viram degradê.
4. **Cor com sentido.** Vermelho para o baixo e verde para o alto quando mais
   é melhor; invertido quando mais é pior. Não troque a paleta de um mapa para
   o outro da mesma apostila.
5. **Área em toda classe.** O número que o produtor pergunta é "quantos
   hectares". O modelo sempre escreve ha e %.
6. **Escala em número redondo**, norte e data. O modelo põe os três; no atlas, o passo da
   escala é recalculado em cada página.
7. **Talhões por cima**, com contorno fino e sem preenchimento, para a cor do
   mapa aparecer. O modelo já desenha assim, sem mexer no estilo da camada.
8. **Sem dado é branco.** Área sem amostra ou fora do raster não recebe cor.
9. **Confira três números antes de entregar**: a área total contra a área que
   o cliente conhece; o mínimo e o máximo contra o laudo; e a classe maior
   contra o que o mapa mostra.

## Como a área de cada classe é calculada

- **Raster**: o estilo precisa ser de cor discreta (classes). Cada pixel com
  dado entra na classe cujo teto é o primeiro maior ou igual ao valor. Área da
  classe = pixels × largura × altura do pixel. Em raster em graus, o tamanho
  do pixel é convertido para metros na latitude do centro.
- **Vetor categorizado**: soma da área elipsoidal dos polígonos de cada valor.
- **Vetor graduado**: soma da área dos polígonos cujo valor cai em cada faixa.
- A **área total** do quadro é a soma das classes.

## Limites da v1

- No atlas (uma página por talhão), a página mostra o nome e a área do talhão, que sai com o
  contorno grosso; os vizinhos aparecem em volta, com o contorno fino e cinza. A legenda segue
  com as áreas do mapa inteiro.
- O layout do atlas é separado do layout do mapa inteiro (outro nome): exportado fora do
  atlas, o nome e a área do talhão saem em branco.
- Página em pé não está no modelo.
- O texto usa a fonte Arial; onde ela não existe, o QGIS troca por outra
  parecida e o espaçamento pode mudar um pouco.
- O módulo não confere se a logo é do cliente: isso é pergunta para o usuário.
