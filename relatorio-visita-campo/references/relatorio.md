# O arquivo da visita e a estrutura do relatório

## O visita.json

É o arquivo que a IA escreve com o que o usuário mandou. Os caminhos de
arquivo são relativos à pasta onde ele está.

```json
{
  "fazenda": "Fazenda Exemplo",
  "cidade": "Cidade Exemplo",
  "estado": "MT",
  "data": "2025-11-17",
  "visitante": "Nome de quem fez a visita",

  "proprietario": "Nome do proprietário",
  "empresa": "Consultoria",
  "safra": "2025/26",
  "cultura": "Soja",
  "talhoes": "Pivô 1, Baixada e Talhão 12",
  "tipo": "Vistoria geral",

  "resumo": "Até 3 frases.",
  "observacoes": ["Quem visitou indicou reavaliar o estande em sete dias."],

  "paradas": [
    {"n": 1, "lat": -22.70752, "lon": -50.99510, "hora": "09:10", "nome": "Pivô 1", "origem": "usuario"}
  ],

  "grupos": [
    {
      "titulo": "Pivô 1: estande e falhas",
      "parada": 1,
      "texto": "De 1 a 3 frases com o que quem visitou relatou.",
      "notas": [{"hora": "09:25", "texto": "Produtor relata chuva de 40 mm no sábado."}],
      "fotos": [
        {"arquivo": "fotos/foto-01.jpg", "descricao": "Só o que dá para ver, em 1 ou 2 frases.", "hora": "09:14"}
      ]
    }
  ],

  "transcricoes": [{"hora": "09:16", "texto": "O áudio, palavra por palavra.", "origem": "transcrição enviada pelo usuário"}],
  "incluir_transcricoes": true,
  "audios": 2,

  "perimetro": "talhoes.geojson",
  "satelite": {"rgb": "sat/rgb.tif", "ndvi": null, "data": "2025-11-12", "sem_nuvem_pct": 98.4}
}
```

| Campo | Obrigatório | O que é |
|---|---|---|
| `fazenda`, `cidade`, `estado`, `data`, `visitante` | sim | o cabeçalho. A data em `AAAA-MM-DD` ou `dd/mm/aaaa` |
| `proprietario`, `empresa`, `safra`, `cultura`, `talhoes`, `tipo` | não | o cartão "Dados da visita"; o que ficar de fora não aparece |
| `resumo` | sim | até 3 frases |
| `observacoes` | não | de 3 a 6 frases curtas |
| `paradas` | não | os pontos da visita: `n`, `lat`, `lon` em graus decimais; `hora`, `nome`; `origem` = `usuario` (informada por quem visitou), `foto` (GPS da foto) ou `area` (centro da área) |
| `grupos` | sim, pelo menos um | os assuntos: `titulo`; `texto`; `parada` (o número, se houver); `notas`; `fotos` |
| `grupos[].fotos[]` | não | `arquivo`; `descricao`; `hora` (se faltar, vale a que a câmera gravou) |
| `transcricoes` | não | um item por áudio: `texto`, `hora`, `origem` |
| `incluir_transcricoes` | não | `true` põe a transcrição no fim do relatório |
| `audios` | não | quantos áudios o usuário mandou (para a contagem do cabeçalho) |
| `inicio`, `fim` | não | `HH:MM`, para a duração; sem eles vale a primeira e a última hora dos registros |
| `perimetro` | não | arquivo do contorno, em graus: GeoJSON, KML, shapefile ou WKT |
| `satelite` | não | `rgb` (e `ndvi`): os `.tif` da ferramenta; `data` da cena; `sem_nuvem_pct` |

Regras que o script confere: cada foto em um assunto só; foto que abre como
JPEG, PNG ou WebP; parada citada em um assunto existe; coordenada dentro do
globo; data que não está no futuro; hora em `HH:MM`.

## A estrutura do relatório

A mesma no PDF, no `relatorio.md` e, sem ambiente de código, no texto da
conversa:

```
# Relatório de visita técnica — [fazenda]
[cidade] / [estado] · [data]

## Dados da visita
- Visita realizada por: ...
- Tipo de visita: ...            (só os campos informados)
- Proprietário(a): ...
- Safra: ... · Cultura: ... · Talhões: ... · Empresa: ...
- Registros: N fotos, N áudios, N notas, N paradas, duração

## Localização da visita
- Parada 1 (nome): latitude; longitude · origem · hora · abrir no mapa
[ou "Nenhuma localização foi informada nesta visita."]
[o crédito da imagem de satélite, quando houver]

## Resumo
[até 3 frases]

## Observações
- [de 3 a 6 frases curtas]

## Registros da visita
### [título do assunto]
_Parada N · hora · coordenada_
[texto de 1 a 3 frases]
> Nota · hora: [texto de quem visitou]
- Foto `arquivo` (hora): [descrição]

## Transcrição dos áudios        (só se o usuário pediu)
**hora** — [o áudio, palavra por palavra]

---
As descrições das fotos foram escritas pela IA a partir das imagens e do que
quem visitou informou; o conteúdo técnico é de responsabilidade de quem fez a
visita.
```

## Como escrever cada parte

- **Título do assunto**: o lugar e o tema ("Pivô 1: estande e falhas"), sem
  "Parada 2" (o relatório já mostra).
- **Texto do assunto**: o que quem visitou relatou, com as palavras e os
  números dele. "Segundo quem visitou" quando for avaliação dele.
- **Nota**: o texto que ele escreveu ou ditou, sem reescrever.
- **Descrição da foto**: o que se vê. "Linhas de soja em fase inicial, com o
  dossel ainda aberto", e não "lavoura com bom desenvolvimento".
- **Resumo**: o que foi visto e onde, sem conclusão sua.
- **Observações**: os pontos principais e o que ele indicou fazer, cada um em
  uma frase, atribuído a ele.
