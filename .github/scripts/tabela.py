"""Regenera a tabela de skills do README raiz.

Varre as pastas de primeiro nivel que contem SKILL.md, le a description do
frontmatter e reescreve o bloco entre <!-- SKILLS:START --> e <!-- SKILLS:END -->.
Roda no CI (workflow skills.yml) a cada push que toca uma skill.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INICIO, FIM = "<!-- SKILLS:START -->", "<!-- SKILLS:END -->"


def descricao(skill_md: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", skill_md, re.S)
    if not m:
        return ""
    fm = m.group(1)
    d = re.search(r"description:\s*>-?\n((?:[ \t]+.*\n?)+)", fm)
    texto = (
        re.sub(r"\s+", " ", d.group(1)).strip()
        if d
        else (re.search(r"description:\s*(.+)", fm) or [None, ""])[1].strip()
    )
    # so a primeira frase (a tabela e vitrine; o resto vive no README da skill)
    ponto = texto.find(". ")
    return texto[: ponto + 1] if 0 < ponto < 220 else texto[:220]


linhas = []
for pasta in sorted(RAIZ.iterdir()):
    skill_md = pasta / "SKILL.md"
    if not pasta.is_dir() or pasta.name.startswith(".") or not skill_md.exists():
        continue
    slug = pasta.name
    linhas.append(
        f"| [`{slug}`]({slug}/) | {descricao(skill_md.read_text(encoding='utf-8'))} "
        f"| [zip](../../releases/latest/download/{slug}.zip) |"
    )

tabela = "\n".join(["| Skill | O que faz | Baixar |", "|---|---|---|", *linhas])
readme = RAIZ / "README.md"
conteudo = readme.read_text(encoding="utf-8")
novo = re.sub(
    re.escape(INICIO) + ".*?" + re.escape(FIM),
    f"{INICIO}\n{tabela}\n{FIM}",
    conteudo,
    flags=re.S,
)
if novo != conteudo:
    readme.write_text(novo, encoding="utf-8")
    print(f"README atualizado ({len(linhas)} skills)")
else:
    print(f"README ja em dia ({len(linhas)} skills)")
