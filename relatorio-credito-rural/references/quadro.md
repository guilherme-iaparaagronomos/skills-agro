# O quadro de fatos: formato fixo

Escreva o quadro sempre com estes blocos, nesta ordem e com estes títulos.
Bloco sem dado não some: fica com uma linha dizendo por que não tem ("o
número do CAR não foi informado", "conector de clima não disponível", "a
ferramenta não devolveu esta seção").

Os números entre colchetes no modelo são os campos a preencher. O exemplo
preenchido no fim é **inventado**, só para mostrar o tom.

## Modelo

```
QUADRO DE FATOS PARA ANÁLISE DE CRÉDITO RURAL
[nome da propriedade] · [município/UF] · emitido em [data]

Este quadro reúne registros de bases públicas e de satélite, cada um com a
fonte. Não é parecer, laudo nem recomendação e não conclui sobre o crédito.

1. IDENTIFICAÇÃO
- Imóvel: [nome], [área] ha, [município/UF]. Perímetro: [de onde veio].
- Área do financiamento: [imóvel inteiro | lavoura de X ha, perímetro enviado
  pelo solicitante].
- Cultura e janela informadas pelo solicitante: [cultura], de [mês] a [mês].
- Solicitante e responsável técnico: [se informados].

2. O QUE O CAR DECLARA  (consulta pública do SICAR, em [data])
- Situação do cadastro: [...]; condição da análise: [...].
- Áreas declaradas: [reserva legal, vegetação nativa, área consolidada, APP].

3. USO DO SOLO  ([fonte e ano do mapa, como a ferramenta escreveu])
- Classes do último mapa: [classe, ha, %].
- Vegetação nativa aberta depois de 2008: [ha]; depois de 2019: [ha];
  depois de 2020: [ha].
- Cobertura dos últimos 12 meses ([fonte]): [classe, ha, %].
- Declarado no CAR ao lado do observado: [item: declarado, observado,
  diferença].

4. REGISTROS SOCIOAMBIENTAIS  (bases públicas, na data de cada uma)
- PRODES depois de 31/07/2019: [polígonos, ha]. PRODES de 2019: [...].
  PRODES de 2008 a 2018: [...]. DETER desde [data]: [alertas, ha].
- Unidades de conservação que o perímetro sobrepõe: [n, ha].
- Terras indígenas: [n, ha].
- Termos de embargo que tocam o perímetro: [n, ha], sem nome nem documento
  de pessoa. [número do termo, quando houver]
- Itens perto do perímetro: [n]. O que são e a distância: no dossiê, seção
  Restrições.

5. SAFRAS POR SATÉLITE  (índice: Copernicus Sentinel-2 L2A; chuva:
   pluviômetros e satélites da comunidade agrônomo10X (OagronomIA))
   Área consultada: [lavoura de X ha | imóvel inteiro de X ha]. Índice: [NDVI].

| Safra | Período | Imagens | Maior intervalo sem imagem | Pico do índice | Chuva | Dias de chuva | Veranicos | Maior veranico |
|---|---|---|---|---|---|---|---|---|
| [aaaa/aa] | [dd/mm/aaaa a dd/mm/aaaa] | [n] | [n dias, de dd/mm a dd/mm] | [valor em dd/mm/aaaa] | [mm] | [n] | [n] | [n dias, de dd/mm a dd/mm, x mm] |

   Veranico: [a definição que a ferramenta usou].
   O índice mostra o vigor da vegetação, não a produtividade colhida.
   [observações, quando valem: a janela foi o ano agrícola e os veranicos do
   inverno seco entram na contagem; a área foi o imóvel inteiro; safra sem
   imagem; nas safras com intervalo de 30 dias ou mais sem imagem, o pico de
   verdade pode ter caído no intervalo e não aparecer]

6. CHUVA DOS ÚLTIMOS ANOS  (pluviômetros e satélites da comunidade
   agrônomo10X (OagronomIA))

| Ano | Chuva | Média histórica (1991–2020) | Diferença |
|---|---|---|---|
| [aaaa] | [mm] | [mm] | [%] |

   Média dos [n] anos completos: [mm] por ano; normal da região: [mm] por
   ano ([%]). Confiança do dado: [como a ferramenta disse].
   [O ano em curso: as frases da contexto_chuva, como vieram. É descrição do
   registro, não previsão.]

7. RELEVO  ([fonte])
- Altitude de [..] a [..] m; declive médio de [..]% (máximo [..]%).
- Classes de relevo e faixas de mecanização: no dossiê, seção Relevo.

8. RETRATO ATUAL E SOLO
- Imagem em cor real: cena de [data], [..]% do perímetro sem nuvem.
- Imagem de 2 m: cena de [data] [ou "não incluída nesta emissão"].
- Solo ([fonte] — estimativa de um mapa mundial de 250 m, não medição):
  [argila, textura, carbono, estoque].

ANEXOS (links que expiram em 1 hora)
- Dossiê de uso e ocupação do solo, PDF de [n] páginas.
- Gráfico do índice e da chuva: safra [..], safra [..], ...

AVISOS DAS FERRAMENTAS
- [cada aviso, com as palavras da ferramenta]

O QUE ESTE QUADRO NÃO TRAZ
- Parecer sobre o crédito, estimativa de produtividade, ZARC, matrícula,
  certidões e vistoria.
```

## Regras de preenchimento

- Os blocos 1 a 4, 7 e 8 saem do texto que a `dossie_pdf` devolveu. Copie os
  números como vieram: sem somar, sem arredondar de outro jeito e sem trocar
  a ordem de grandeza. O que não veio no texto está no PDF: diga a seção.
- Zero é dado: "0 polígono(s), 0 ha" se escreve assim, com a fonte. Não
  troque por "nada consta", "limpo" nem "sem problema".
- Base que a ferramenta não conseguiu ler não é zero: escreva "a base X não
  foi lida nesta emissão".
- O bloco 5 segue a tabela de leitura do SKILL.md. Uma linha por safra, da
  mais antiga para a mais recente; a safra em andamento vai por último,
  marcada.
- O bloco 6 só tem anos completos na tabela.
- Datas em dd/mm/aaaa. Milhar com ponto e decimal com vírgula.
- Nada de negrito para destacar número "que chama atenção", nada de cor,
  seta, emoji ou marca de alerta.

## Exemplo preenchido (dados inventados)

```
QUADRO DE FATOS PARA ANÁLISE DE CRÉDITO RURAL
Fazenda Exemplo · Município Exemplo/UF · emitido em 10/11/2026

Este quadro reúne registros de bases públicas e de satélite, cada um com a
fonte. Não é parecer, laudo nem recomendação e não conclui sobre o crédito.

1. IDENTIFICAÇÃO
- Imóvel: Fazenda Exemplo, 412,3 ha, Município Exemplo/UF. Perímetro:
  polígono do imóvel no SICAR.
- Área do financiamento: lavoura de 286,0 ha, perímetro enviado pelo
  solicitante.
- Cultura e janela informadas pelo solicitante: soja, de outubro a março.

5. SAFRAS POR SATÉLITE  (índice: Copernicus Sentinel-2 L2A; chuva:
   pluviômetros e satélites da comunidade agrônomo10X (OagronomIA))
   Área consultada: lavoura de 286,0 ha. Índice: NDVI.

| Safra | Período | Imagens | Maior intervalo sem imagem | Pico do índice | Chuva | Dias de chuva | Veranicos | Maior veranico |
|---|---|---|---|---|---|---|---|---|
| 2023/24 | 01/10/2023 a 31/03/2024 | 19 | 25 dias, de 13/11 a 08/12 | 0,84 em 21/01/2024 | 742,0 mm | 61 | 3 | 12 dias, de 12/12 a 23/12, 0,4 mm |
| 2024/25 | 01/10/2024 a 31/03/2025 | 14 | 41 dias, de 17/12 a 27/01 | 0,81 em 15/02/2025 | 918,5 mm | 74 | 2 | 16 dias, de 23/02 a 10/03, 4,2 mm |

   Veranico: 7 ou mais dias seguidos com menos de 2 mm por dia.
   O índice mostra o vigor da vegetação, não a produtividade colhida.
   Na safra 2024/25 há 41 dias sem imagem: o pico de verdade pode ter caído
   no intervalo e não aparecer.
```

O exemplo mostra só dois blocos. O quadro de verdade tem todos.
