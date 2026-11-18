# Relatório de visita de campo

Skill da comunidade agrônomo10X para transformar, com a sua IA, o material
solto de uma visita técnica em um relatório padronizado em PDF. Você manda as
fotos, os textos, as anotações e os áudios (ou as transcrições); a IA
pergunta o que faltar, organiza por assunto, descreve as fotos e monta o
documento.

O formato é o mesmo do relatório de visita da ClaudIA Geo no WhatsApp:
cabeçalho com as contagens, dados da visita, localização com o mapa e as
paradas, resumo, observações, registros com as fotos e a transcrição dos
áudios.

No alto da primeira página vai a **logo da empresa de quem fez a visita**. Se
você não mandar, a IA pede. Se você não tem ou não quer, diga, e o relatório
sai sem logo.

Se o conector **ClaudIA Sat** estiver ligado e você passar o ponto, o
perímetro ou a fazenda salva, o relatório leva a imagem de satélite da área.

A skill só organiza o que você mandou. Não diagnostica, não recomenda e não
inventa número, produto nem dose: o conteúdo técnico é de quem fez a visita.

## O que precisa

- Um ambiente que rode Python 3 com numpy, Pillow e matplotlib, para o PDF.
  Sem ele, a IA entrega o relatório em texto, na mesma estrutura.
- As fotos em JPEG, PNG ou WebP. Foto em HEIC precisa ser exportada em JPEG.
- A logo da sua empresa em PNG, JPEG ou WebP (SVG e PDF não são lidos).
- Para os áudios: uma IA que ouça o arquivo, ou a transcrição.
- Opcional: o conector ClaudIA Sat. A imagem consome, da franquia de
  satélite, a área consultada.

## Estrutura

```
relatorio-visita-campo/
  SKILL.md                 o roteiro que a IA segue
  README.md
  references/relatorio.md  o formato do visita.json e a estrutura do relatório
  scripts/
    montar.py              entrada: --fotos, --conferir, a montagem, --baixar e --demo
    visita.py              lê e confere o visita.json; escreve o relatório em texto
    fotos.py               abre as fotos e a logo; lê a data, a hora e o GPS da câmera
    mapa.py                o mapa da localização, com a imagem de satélite
    relatorio.py           o desenho das páginas
    pdfmini.py             escritor de PDF (fotos em JPEG, logo sem perda, texto e links)
    sintetico.py           visita inventada para a demonstração
    geotiff.py, geometria.py, areas.py, shapefile_min.py
                           leitura de GeoTIFF e de perímetro (iguais aos da skill zonas-de-manejo)
```

Para ver funcionando sem dado nenhum:

```
python scripts/montar.py --demo --saida saida-demo
```

Cada módulo roda sozinho como teste: `python scripts/visita.py`.

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- **Visita inventada** (a da demonstração): cinco fotos desenhadas, três
  paradas, dois talhões, notas e transcrições. O PDF de três páginas foi
  relido por outro leitor de PDF (texto, links, número de imagens) e olhado
  página a página.
- **Imagem de satélite de verdade**: a ferramenta `imagem_satelite` foi
  chamada para um ponto com raio de 500 m, o GeoTIFF baixado e o mapa
  montado com ele.
- **Logo**: quatro logos desenhadas pelo teste (uma em PNG com fundo
  transparente, uma muito larga, uma quadrada e uma em JPEG com fundo escuro)
  entraram no cabeçalho e foram olhadas no PDF; arquivo em SVG, imagem
  minúscula, arquivo que não existe e arquivo que não abre foram recusados
  com o motivo. Sem o campo `logo`, a conferência manda pedir a logo ao
  usuário.
- **Conferência do visita.json**: dezesseis problemas plantados de uma vez
  (campo que falta, logo que falta, data impossível, coordenada trocada, foto
  repetida, foto que não abre, arquivo de satélite que não existe), todos
  apontados.
- **O que não foi feito**: usar com a logo de uma empresa de verdade (logo
  com fundo escuro sai como está, dentro do cartão branco); usar com fotos
  de celular de verdade (a leitura da
  data e do GPS foi testada com fotos gravadas pelo próprio teste); ouvir e
  transcrever áudio (depende da IA de cada um); rodar a skill inteira dentro
  de uma conversa em duas IAs diferentes; abrir o PDF em todos os leitores
  (foi conferido em dois).

## Avisos

- As descrições das fotos são escritas pela IA: leia antes de mandar o
  relatório ao cliente.
- Foto que passou por aplicativo de mensagem costuma chegar sem data e sem
  GPS. Para a localização, informe o ponto, o perímetro ou a fazenda salva.
- O relatório não é laudo, receituário nem ART.
- As fotos e os áudios ficam no ambiente da sua IA: o script não envia nada
  para fora. O único acesso à internet é o download da imagem de satélite,
  quando você pede, pelo link que a ferramenta devolveu.

Autoria: Equipe agrônomo10X (OagronomIA).
