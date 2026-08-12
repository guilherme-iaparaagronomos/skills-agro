# API pública do Consulta Pública do CAR — referência

Mapeada em 2026-08-12 observando as chamadas de rede do próprio site
https://consulta.car.gov.br/ ao clicar em "Buscar".

## Endpoint principal

```
GET https://consulta.car.gov.br/api/totalizer/getDeatilsByIdentifier/<NUMERO>
```

- O nome do caminho tem um typo OFICIAL: `getDeatilsByIdentifier` (não
  "Details"). Não "corrija" — corrigido dá 404.
- `<NUMERO>` aceita os dois formatos: `PI-2200053-1BAB.C06A.E224.43BC.A804.FFEC.51C2.5EB9`
  (como o site exibe) ou sem os pontos.
- Sem autenticação, sem captcha. Use um `User-Agent` identificável e um
  intervalo ≥ 0,5 s entre consultas em lote.

## Formato do número

`UF-CCCCCCC-H×32`

- `UF`: sigla do estado (2 letras)
- `CCCCCCC`: código IBGE do município (7 dígitos)
- `H×32`: 32 caracteres hexadecimais (o site pontua de 4 em 4)

## Resposta (JSON)

```json
{
  "codeProperty": "PI-2200053-1BABC06AE22443BCA804FFEC51C25EB9",
  "latitude": "8°22'26.947\"S",
  "longitude": "40°51'12.019\"W",
  "idState": "PI",
  "nameState": "Piauí",
  "nameCity": "Acauã",
  "fiscalModules": 0.27,
  "createdAt": "07/02/2023",
  "lastRectification": null,
  "haRegisteredArea": 18.58,
  "idOrigin": 11280456,
  "bounderBox": "POLYGON((-40.857 -8.377, ...))"
}
```

- `latitude`/`longitude`: centroide declarado, em graus/min/seg (S/W =
  hemisfério sul/oeste → negativos na conversão decimal).
- `haRegisteredArea`: área do imóvel em hectares.
- `fiscalModules`: módulos fiscais (varia por município).
- `bounderBox`: retângulo envolvente em WKT (não é o perímetro real).
- `lastRectification`: data da última retificação (null se nunca).

## Comportamentos de erro

| Situação | Resposta |
|---|---|
| CAR inexistente | **200 com corpo vazio** (não é 404!) |
| Número mal formado | 200 vazio ou 500 — valide ANTES de chamar |
| Instabilidade do gov.br | 5xx/timeout — tente de novo com espera |

## Endpoints vizinhos (não usados pela skill, úteis p/ evoluções)

- `GET /api/state/getAll` — lista de UFs
- `GET /api/state/getCitiesByUf/<UF>` — municípios da UF
- `POST /api/totalizer/getTotalizerByStateOrCity` — totais por UF/município
