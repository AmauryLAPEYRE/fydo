"""
Capture le GOLDEN MASTER depuis l'oracle gelé qv_engine_v4.py (réseau yfinance, one-shot).

Pourquoi : la parité du cerveau doit être DÉTERMINISTE et hors-réseau. yfinance change
dans le temps (prix, restatements) → on fige une fois la sortie de l'oracle, on la commit,
et tous les tests de parité tournent ensuite offline contre ce fichier.

Lancer avec PYTHONUTF8=1 (sinon les prints Δ/→ de l'oracle crashent sur console cp1252) :
    PYTHONUTF8=1 python tests/capture_oracle_fixture.py
"""
import pathlib
import sys

import pandas as pd

ENGINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

import qv_engine_v4 as oracle  # noqa: E402  — exécute le pipeline complet (réseau)

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"
FIX.mkdir(exist_ok=True)

# ── Golden QUALITÉ ── (fondamentaux annuels = stables) : on NE l'écrase PAS s'il
# existe déjà, pour garder la référence figée et commitée (les prix bougent chaque
# jour, pas les comptes — re-capturer pourrait introduire une micro-dérive Yahoo).
QCOLS = [
    "sector", "roic_5y_avg", "gross_margin_5y_avg", "net_margin_5y_avg",
    "rev_cagr_5y", "debt_to_equity", "nonscore", "quality_pct",
]
qpath = FIX / "oracle_golden_quality.pkl"
if qpath.exists():
    print(f"[SKIP] golden qualité déjà figé : {qpath.name} (préservé)")
else:
    golden = oracle.df[QCOLS].copy()
    golden.to_pickle(qpath)
    print(f"[CAPTURE] qualité : {len(golden)} noms -> {qpath.name}")

# ── Golden PRIX ── série quotidienne brute (pour recomputation) + sorties dérivées
# de référence : RSI(14) Wilder par nom, MA200 (rolling 200 → resample mensuel).
# Le drawdown N'EST PAS capturé : l'oracle est en 252 j, la prod en 756 j
# (divergence intentionnelle SPEC §4.3) → drawdown_756 testé en propriété, pas parité.
ppath = FIX / "oracle_golden_price.pkl"
price_golden = {
    "px": oracle.px[oracle.basket].copy(),   # Close quotidien (index daté)
    "rsi_now": dict(oracle.rsi_now),          # RSI(14) dernier point, par nom
    "ma200": oracle.ma200.copy(),             # MA200 mensuelle (rolling 200 → ME.last)
}
pd.to_pickle(price_golden, ppath)
print(f"[CAPTURE] prix : {len(oracle.basket)} noms, "
      f"{len(price_golden['px'])} jours -> {ppath.name}")
