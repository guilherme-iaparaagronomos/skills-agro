# Classes de interpretação usadas nos mapas

Os limites abaixo estão em `scripts/classes.py` e vêm das skills
`5a-aproximacao-mg` e `boletim-100-sp`, conferidos nos boletins. **A fonte
oficial tem a palavra final**: divergência com o boletim é erro da skill.

Em todas as tabelas a classe inclui o limite superior: "≤ 15" e "15 – 40"
significam que 15 é da primeira classe e 15,1 da segunda.

## 5ª Aproximação — Minas Gerais (`--tabela mg`)

> Ribeiro, A.C.; Guimarães, P.T.G.; Alvarez V., V.H. (eds., 1999).
> *Recomendações para o uso de corretivos e fertilizantes em Minas Gerais —
> 5ª Aproximação*. CFSEMG, Viçosa. Quadros 5.1 a 5.5.

| Item | Coluna reconhecida | Unidade | Limites superiores | Classes |
|---|---|---|---|---|
| `ph` | pH H2O / pH em água | — | 4,5 · 5,4 · 6,0 · 7,0 | Muito baixo, Baixo, Bom, Alto, Muito alto |
| `mo` | M.O., matéria orgânica | dag/kg | 0,70 · 2,00 · 4,00 · 7,00 | Muito baixo … Muito bom |
| `co` | C.O., carbono | dag/kg | 0,40 · 1,16 · 2,32 · 4,06 | Muito baixo … Muito bom |
| `ca` | Ca | cmolc/dm³ | 0,40 · 1,20 · 2,40 · 4,00 | Muito baixo … Muito bom |
| `mg` | Mg | cmolc/dm³ | 0,15 · 0,45 · 0,90 · 1,50 | Muito baixo … Muito bom |
| `al` | Al | cmolc/dm³ | 0,20 · 0,50 · 1,00 · 2,00 | Muito baixo … Muito alto (alto é ruim) |
| `sb` | SB | cmolc/dm³ | 0,60 · 1,80 · 3,60 · 6,00 | Muito baixo … Muito bom |
| `hal` | H+Al | cmolc/dm³ | 1,00 · 2,50 · 5,00 · 9,00 | Muito baixo … Muito alto (alto é ruim) |
| `t` | t, CTC efetiva | cmolc/dm³ | 0,80 · 2,30 · 4,60 · 8,00 | Muito baixo … Muito bom |
| `T` | T, CTC, CTC pH 7 | cmolc/dm³ | 1,60 · 4,30 · 8,60 · 15,00 | Muito baixo … Muito bom |
| `m` | m, saturação por Al | % | 15 · 30 · 50 · 75 | Muito baixo … Muito alto (alto é ruim) |
| `v` | V, saturação por bases | % | 20 · 40 · 60 · 80 | Muito baixo … Muito bom |
| `k` | K (Mehlich-1) | mg/dm³ | 15 · 40 · 70 · 120 | Muito baixo … Muito bom |
| `zn` | Zn (Mehlich-1) | mg/dm³ | 0,4 · 0,9 · 1,5 · 2,2 | Muito baixo, Baixo, Médio, Bom, Alto |
| `mn` | Mn (Mehlich-1) | mg/dm³ | 2 · 5 · 8 · 12 | idem |
| `fe` | Fe (Mehlich-1) | mg/dm³ | 8 · 18 · 30 · 45 | idem |
| `cu` | Cu (Mehlich-1) | mg/dm³ | 0,3 · 0,7 · 1,2 · 1,8 | idem |
| `b` | B (água quente) | mg/dm³ | 0,15 · 0,35 · 0,60 · 0,90 | idem |
| `argila` | Argila | % | 15 · 35 · 60 | Arenosa, Média, Argilosa, Muito argilosa |

`T` e `t` são diferenciados pela caixa da letra. A textura usa as faixas de
argila do Quadro 5.3; não é classe de fertilidade.

### P (Mehlich-1) — depende da argila ou do P-rem (Quadro 5.3)

| Argila (%) | Muito baixo | Baixo | Médio | Bom | Muito bom |
|---|---|---|---|---|---|
| 60–100 | ≤ 2,7 | ≤ 5,4 | ≤ 8,0 | ≤ 12,0 | > 12,0 |
| 35–60 | ≤ 4,0 | ≤ 8,0 | ≤ 12,0 | ≤ 18,0 | > 18,0 |
| 15–35 | ≤ 6,6 | ≤ 12,0 | ≤ 20,0 | ≤ 30,0 | > 30,0 |
| 0–15 | ≤ 10,0 | ≤ 20,0 | ≤ 30,0 | ≤ 45,0 | > 45,0 |

| P-rem (mg/L) | Muito baixo | Baixo | Médio | Bom | Muito bom |
|---|---|---|---|---|---|
| 0–4 | ≤ 3,0 | ≤ 4,3 | ≤ 6,0 | ≤ 9,0 | > 9,0 |
| 4–10 | ≤ 4,0 | ≤ 6,0 | ≤ 8,3 | ≤ 12,5 | > 12,5 |
| 10–19 | ≤ 6,0 | ≤ 8,3 | ≤ 11,4 | ≤ 17,5 | > 17,5 |
| 19–30 | ≤ 8,0 | ≤ 11,4 | ≤ 15,8 | ≤ 24,0 | > 24,0 |
| 30–44 | ≤ 11,0 | ≤ 15,8 | ≤ 21,8 | ≤ 33,0 | > 33,0 |
| 44–60 | ≤ 15,0 | ≤ 21,8 | ≤ 30,0 | ≤ 45,0 | > 45,0 |

### S — depende do P-rem (Quadro 5.4)

| P-rem (mg/L) | Muito baixo | Baixo | Médio | Bom | Muito bom |
|---|---|---|---|---|---|
| 0–4 | ≤ 1,7 | ≤ 2,5 | ≤ 3,6 | ≤ 5,4 | > 5,4 |
| 4–10 | ≤ 2,4 | ≤ 3,6 | ≤ 5,0 | ≤ 7,5 | > 7,5 |
| 10–19 | ≤ 3,3 | ≤ 5,0 | ≤ 6,9 | ≤ 10,3 | > 10,3 |
| 19–30 | ≤ 4,6 | ≤ 6,9 | ≤ 9,4 | ≤ 14,2 | > 14,2 |
| 30–44 | ≤ 6,4 | ≤ 9,4 | ≤ 13,0 | ≤ 19,6 | > 19,6 |
| 44–60 | ≤ 8,9 | ≤ 13,0 | ≤ 18,0 | ≤ 27,0 | > 27,0 |

**Como o mapa aplica**: a argila (ou o P-rem) é interpolada com o mesmo IDW e
cada pixel de P é classificado com os limites da faixa em que a argila daquele
pixel cai. Com as duas colunas no laudo, vale a argila. Por isso a legenda de P
e S em MG mostra a área de cada classe, mas não uma faixa única de valores.
Sem a coluna, `--argila-fixa` (em %) ou `--prem-fixo` (em mg/L) aplicam uma
faixa só à área toda. Argila acima de 100% ou P-rem acima de 60 mg/L usam a
última faixa.

## Boletim 100 — São Paulo (`--tabela sp`)

> van Raij, B.; Cantarella, H.; Quaggio, J.A.; Furlani, Â.M.C. (1997).
> *Recomendações de Adubação e Calagem para o Estado de São Paulo*, 2ª ed.,
> Boletim Técnico 100, IAC, Campinas. Quadros 4.1 a 4.4.

| Item | Coluna reconhecida | Unidade | Limites superiores | Classes |
|---|---|---|---|---|
| `ph` | pH CaCl2 | — | 4,3 · 5,0 · 5,5 · 6,0 | Acidez muito alta … Acidez muito baixa |
| `v` | V, saturação por bases | % | 25 · 50 · 70 · 90 | Muito baixa … Muito alta |
| `k` | K | mmolc/dm³ | 0,7 · 1,5 · 3,0 · 6,0 | Muito baixo … Muito alto |
| `ca` | Ca | mmolc/dm³ | 3 · 7 | Baixo, Médio, Alto |
| `mg` | Mg | mmolc/dm³ | 4 · 8 | Baixo, Médio, Alto |
| `s` | S (S-SO₄) | mg/dm³ | 4 · 10 | Baixo, Médio, Alto |
| `b` | B (água quente) | mg/dm³ | 0,20 · 0,60 | Baixo, Médio, Alto |
| `cu` | Cu (DTPA) | mg/dm³ | 0,2 · 0,8 | Baixo, Médio, Alto |
| `fe` | Fe (DTPA) | mg/dm³ | 4 · 12 | Baixo, Médio, Alto |
| `mn` | Mn (DTPA) | mg/dm³ | 1,2 · 5,0 | Baixo, Médio, Alto |
| `zn` | Zn (DTPA) | mg/dm³ | 0,5 · 1,2 | Baixo, Médio, Alto |

### P (resina) — depende do grupo de culturas (Quadro 4.1)

| `--grupo-cultura` | Muito baixo | Baixo | Médio | Alto | Muito alto |
|---|---|---|---|---|---|
| `florestais` | ≤ 2 | ≤ 5 | ≤ 8 | ≤ 16 | > 16 |
| `perenes` | ≤ 5 | ≤ 12 | ≤ 30 | ≤ 60 | > 60 |
| `anuais` | ≤ 6 | ≤ 15 | ≤ 40 | ≤ 80 | > 80 |
| `hortalicas` | ≤ 10 | ≤ 25 | ≤ 60 | ≤ 120 | > 120 |

O Boletim 100 não usa a matéria orgânica como classe de fertilidade; a coluna
de MO cai em classes livres com `--tabela sp`.

## Regras de segurança

1. **Unidade no cabeçalho**. O script lê a unidade entre parênteses ou
   colchetes (`K (mg/dm3)`), o `%` colado (`V%`) ou no fim do nome
   (`Argila g/kg`). Sem unidade reconhecida não há classe oficial, exceto pH.
2. **Conversão só entre unidades equivalentes**:
   - cmolc/dm³ = meq/100 cm³; mmolc/dm³ = 10 × cmolc/dm³;
   - mg/dm³ = ppm = mg/kg;
   - % = dag/kg; g/kg = g/dm³ = 10 × %;
   - K: 1 cmolc/dm³ = 391 mg/dm³ (só para o potássio).
   Os limites da tabela são levados para a unidade do laudo; o mapa e o
   GeoTIFF ficam na unidade do laudo. O aviso informa o fator.
3. **Método tem de bater**. pH em água só com a tabela de MG; pH em CaCl₂ só
   com a de SP; P resina só com SP; P Mehlich só com MG. Cabeçalho "pH" ou "P"
   sem o método não é classificado: confirme com o usuário e force com
   `--classe "pH=ph"` ou `--classe "P (mg/dm3)=p"`.
4. **Extrator dos micronutrientes** não dá para ler do cabeçalho. A tabela
   pressupõe Mehlich-1 (MG) ou DTPA (SP), e o rodapé do mapa diz qual.
   Confirme com o usuário.
5. **Coluna não reconhecida** (areia, silte, CE, relações Ca/Mg) cai em classes
   livres. Para classificar, o usuário dá os limites com `--limites`.

## Classes livres e limites do usuário

- **Livres**: 5 intervalos iguais com passo "redondo" (1, 2, 2,5 ou 5 × 10ⁿ)
  entre o mínimo e o máximo do mapa; `--n-classes` muda o número;
  `--classes-livres quantis` usa quantis (cada classe com área parecida).
- **Do usuário**: `--limites "Coluna=a,b,c"` cria uma classe a mais que o
  número de limites; `--nomes "Coluna=n1|n2|n3|n4"` dá os nomes;
  `--sentido "Coluna=alto_bom"`, `alto_ruim` ou `neutra` escolhe as cores.

## Cores

- alto é bom: vermelho → amarelo → verde;
- alto é ruim (Al, m%, H+Al): a mesma escala invertida;
- ótimo no meio (pH em água de MG): vermelho, laranja, verde, azul-claro, azul;
- neutra (textura, classes livres): amarelo → marrom.
