"""Dependência espacial numa grade: quanto as células vizinhas se parecem e
quantas observações independentes um mapa realmente tem.

Num mapa, a célula ao lado quase repete a vizinha. Dez mil células de um mapa
suave não são dez mil observações: valem algumas dezenas. Tratar as células
como independentes faz qualquer correlação parecer "significativa".

O que este módulo calcula, para a grade com falhas e contorno irregular:

- o correlograma de uma camada: a correlação entre células separadas por cada
  distância (somas feitas por transformada de Fourier, pares contados só onde
  as duas células têm valor);
- a distância de correlação: a primeira distância em que o correlograma cai
  abaixo de 1/e (cerca de 0,37);
- o tamanho efetivo de amostra de um par de camadas, pela correção de
  Clifford, Richardson e Hémon (1989): n_ef = 1 + 1/var(r), com
  var(r) = Σ N(h)·ρx(h)·ρy(h) / n², somando nas defasagens h até a distância em
  que o produto dos dois correlogramas deixa de ser positivo;
- o intervalo de 95% da correlação com esse tamanho efetivo (transformação z
  de Fisher).

Teste embutido: python scripts/espacial.py
"""

import math

import numpy as np
from scipy import fft as sfft

UM_SOBRE_E = 1 / math.e
PARES_MINIMOS = 30
N_EF_MINIMO = 4.0


class Defasagens:
    """Guarda, para o conjunto de células válidas, o número de pares em cada defasagem."""

    def __init__(self, valida, celula):
        self.valida = np.asarray(valida, dtype=bool)
        self.celula = float(celula)
        ny, nx = self.valida.shape
        self.forma = (sfft.next_fast_len(2 * ny - 1, real=True), sfft.next_fast_len(2 * nx - 1, real=True))
        self.n = int(self.valida.sum())
        self.pares = np.rint(self._auto(self.valida.astype(float)))
        fy, fx = self.forma
        dy = np.minimum(np.arange(fy), fy - np.arange(fy))[:, None]
        dx = np.minimum(np.arange(fx), fx - np.arange(fx))[None, :]
        self.distancia = np.hypot(dy, dx)                       # em células
        self.faixa = np.rint(self.distancia).astype(int)        # faixa de distância: 0, 1, 2, ...
        self.alcance_maximo = max(2, int(max(ny, nx) // 2))
        self._pares_faixa = np.bincount(self.faixa.ravel(), weights=self.pares.ravel())

    def _auto(self, a):
        f = sfft.rfft2(a, self.forma)
        return sfft.irfft2(f * np.conj(f), self.forma)

    def somas(self, campo):
        """Soma dos produtos x(i)·x(i+h) da camada centrada, em cada defasagem h, e a variância."""
        x = np.where(self.valida, campo, 0.0).astype(float)
        media = x.sum() / self.n
        x = np.where(self.valida, x - media, 0.0)
        s = self._auto(x)
        variancia = float((x * x).sum() / self.n)
        return s, variancia

    def correlograma(self, s, variancia):
        """Correlação por faixa de distância (0, 1, 2, ... células). nan onde há poucos pares."""
        if variancia <= 0:
            return np.full(self.alcance_maximo + 1, np.nan)
        soma = np.bincount(self.faixa.ravel(), weights=s.ravel())
        pares = self._pares_faixa
        k = min(len(soma), self.alcance_maximo + 1)
        r = np.full(k, np.nan)
        bons = pares[:k] >= PARES_MINIMOS
        r[bons] = soma[:k][bons] / pares[:k][bons] / variancia
        return r

    def distancia_de_correlacao(self, correlograma):
        """Em metros: onde o correlograma cruza 1/e. Devolve (distância, limitada?)."""
        r = correlograma
        for d in range(1, len(r)):
            if not np.isfinite(r[d]):
                break
            if r[d] < UM_SOBRE_E:
                anterior = r[d - 1] if np.isfinite(r[d - 1]) else 1.0
                fracao = 0.0 if anterior == r[d] else (anterior - UM_SOBRE_E) / (anterior - r[d])
                return (d - 1 + fracao) * self.celula, False
        return (len(r) - 1) * self.celula, True

    def tamanho_efetivo(self, sx, vx, sy, vy):
        """Tamanho efetivo de amostra do par e a distância (em células) até onde a soma foi feita."""
        if vx <= 0 or vy <= 0 or self.n < 5:
            return float('nan'), 0
        rx, ry = self.correlograma(sx, vx), self.correlograma(sy, vy)
        limite = 0
        for d in range(1, min(len(rx), len(ry))):
            if not (np.isfinite(rx[d]) and np.isfinite(ry[d])) or rx[d] * ry[d] <= 0:
                break
            limite = d
        usar = (self.faixa <= limite) & (self.pares >= 1)
        var_r = float((sx[usar] * sy[usar] / self.pares[usar]).sum() / (self.n ** 2 * vx * vy))
        if var_r <= 0:
            return float(self.n), limite
        return float(min(self.n, max(N_EF_MINIMO, 1 + 1 / var_r))), limite


def intervalo_de_r(r, n_ef, z=1.959964):
    """Intervalo de 95% da correlação pelo z de Fisher, com o tamanho efetivo no lugar do número de células."""
    if not np.isfinite(r) or not np.isfinite(n_ef) or n_ef <= 3.5:
        return float('nan'), float('nan')
    r = max(-0.999999, min(0.999999, float(r)))
    centro, erro = math.atanh(r), 1 / math.sqrt(n_ef - 3)
    return math.tanh(centro - z * erro), math.tanh(centro + z * erro)


def campo_suave(forma, alcance_celulas, gerador):
    """Campo aleatório de variância 1 com semelhança entre vizinhos até cerca de `alcance_celulas`
    (ruído branco filtrado). Serve aos testes e ao exemplo inventado."""
    from scipy import ndimage

    ruido = gerador.standard_normal((forma[0] + 8 * int(alcance_celulas + 1), forma[1] + 8 * int(alcance_celulas + 1)))
    if alcance_celulas > 0:
        ruido = ndimage.gaussian_filter(ruido, sigma=alcance_celulas / 2.0, mode='wrap')
    m = 4 * int(alcance_celulas + 1)
    c = ruido[m:m + forma[0], m:m + forma[1]]
    return (c - c.mean()) / c.std()


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    g = np.random.default_rng(7)
    ny, nx = 60, 70
    yy, xx = np.mgrid[0:ny, 0:nx]
    valida = ((xx - 35) ** 2 / 34 ** 2 + (yy - 30) ** 2 / 28 ** 2) < 1          # contorno irregular (elipse)
    valida &= ~((xx > 50) & (yy < 12))                                          # com um canto a menos
    d = Defasagens(valida, 10.0)
    n = int(valida.sum())
    assert d.n == n and d.pares[0, 0] == n

    # pares contados à mão em duas defasagens
    assert d.pares[0, 1] == int((valida[:, :-1] & valida[:, 1:]).sum())
    assert d.pares[3, 2] == int((valida[:-3, :-2] & valida[3:, 2:]).sum())

    # correlograma contra a conta direta, na defasagem (0, 1)
    campo = campo_suave((ny, nx), 6, g)
    s, v = d.somas(campo)
    x = np.where(valida, campo - campo[valida].mean(), 0.0)
    direto = float((x[:, :-1] * x[:, 1:])[valida[:, :-1] & valida[:, 1:]].sum())
    assert abs(s[0, 1] - direto) < 1e-6 * max(1.0, abs(direto)), (s[0, 1], direto)
    assert abs(v - float((x[valida] ** 2).mean())) < 1e-12

    # ruído branco: tamanho efetivo perto do número de células, distância de correlação menor que uma célula
    branco = g.standard_normal((ny, nx))
    outro = g.standard_normal((ny, nx))
    sb, vb = d.somas(branco)
    so, vo = d.somas(outro)
    n_ef, _ = d.tamanho_efetivo(sb, vb, so, vo)
    assert 0.6 * n < n_ef <= n, (n_ef, n)
    alcance, limitada = d.distancia_de_correlacao(d.correlograma(sb, vb))
    assert alcance < 10.0 and not limitada, alcance

    # campos suaves: o tamanho efetivo despenca e a distância de correlação cresce com a suavidade
    a6, a12 = campo_suave((ny, nx), 6, g), campo_suave((ny, nx), 12, g)
    s6, v6 = d.somas(a6)
    s12, v12 = d.somas(a12)
    ef6, _ = d.tamanho_efetivo(s6, v6, s6, v6)
    ef12, _ = d.tamanho_efetivo(s12, v12, s12, v12)
    assert ef12 < ef6 < n / 5, (ef6, ef12, n)
    d6, _ = d.distancia_de_correlacao(d.correlograma(s6, v6))
    d12, _ = d.distancia_de_correlacao(d.correlograma(s12, v12))
    assert 20 < d6 < d12, (d6, d12)
    # suave contra branco: o produto dos correlogramas morre na primeira defasagem
    ef_misto, limite = d.tamanho_efetivo(s12, v12, sb, vb)
    assert ef_misto > 0.5 * n and limite <= 3, (ef_misto, limite)

    # intervalo de Fisher
    baixo, alto = intervalo_de_r(0.5, 28)
    assert abs(baixo - math.tanh(math.atanh(0.5) - 1.959964 / 5)) < 1e-12 and baixo < 0.5 < alto
    assert all(math.isnan(v) for v in intervalo_de_r(0.5, 3))
    print(f'espacial OK ({n} células; tamanho efetivo: ruído {n_ef:.0f}, suave {ef6:.0f}, muito suave {ef12:.0f})')


if __name__ == '__main__':
    _autoteste()
