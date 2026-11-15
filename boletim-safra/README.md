# Boletim da safra

Skill da comunidade agrônomo10X para montar, com a sua IA, o boletim periódico
de uma fazenda: talhão por talhão, o índice de vegetação da última imagem ao
lado da imagem anterior e da mesma época das safras passadas; a chuva do
período e da safra ao lado da média histórica; a previsão dos próximos dias;
e o laudo em PDF da última imagem.

O formato é fixo, para o boletim desta semana ficar comparável com o da
semana passada. Serve para quem acompanha várias áreas e quer o mesmo retrato
toda semana, quinzena ou mês.

Só fatos. O boletim não recomenda manejo e não aponta talhão bom ou ruim.

## O que precisa

- Os conectores **ClaudIA Sat** e **ClaudIA Clima** ligados na sua IA.
- A fazenda salva na conta, com os talhões, ou o arquivo de perímetro.

Não tem script e não precisa de ambiente de código. Cada boletim faz de 2 a
5 consultas de satélite (a curva recente, uma por safra passada e o laudo;
cada uma consome a área consultada) e 3 de clima.

## Estrutura

```
boletim-safra/
  SKILL.md                o roteiro que a IA segue
  README.md
  references/boletim.md   o formato fixo do boletim e um exemplo inventado
```

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- O roteiro foi seguido uma vez com as ferramentas de verdade, numa fazenda de
  cerca de 90 ha com 5 talhões: a curva recente por talhão, a mesma época do
  ano anterior, a chuva dos últimos 15 dias e da safra, a previsão de 7 dias
  e o laudo pedido pela data da última imagem.
- **O que não foi feito**: repetir o boletim por várias semanas na mesma
  fazenda; usar numa fazenda com dezenas de talhões; rodar a skill inteira
  dentro de uma conversa em duas IAs diferentes. O exemplo do `boletim.md` é
  inventado.

## Avisos

- O boletim descreve a lavoura na data da última imagem limpa, que pode ter
  vários dias, mais ainda em época de chuva.
- Comparar com o ano passado compara calendários: o que estava plantado e
  quando.
- A chuva dos dias mais recentes é provisória e pode ser revisada.
- Boletim semanal de fazenda grande consome a franquia de satélite depressa;
  a skill faz a conta antes de chamar.
- A leitura da lavoura e a decisão de manejo são do responsável técnico.

Autoria: Equipe agrônomo10X (OagronomIA).
