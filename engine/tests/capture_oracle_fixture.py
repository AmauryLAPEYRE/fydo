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

ENGINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

import qv_engine_v4 as oracle  # noqa: E402  — exécute le pipeline complet (réseau)

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"
FIX.mkdir(exist_ok=True)

# Entrées brutes du scoring qualité + sortie de référence (quality_pct).
# nonscore = flag FIN_STRUCTURE (exclu du z-score), input du scoring.
COLS = [
    "sector", "roic_5y_avg", "gross_margin_5y_avg", "net_margin_5y_avg",
    "rev_cagr_5y", "debt_to_equity", "nonscore", "quality_pct",
]
golden = oracle.df[COLS].copy()
out = FIX / "oracle_golden_quality.pkl"
golden.to_pickle(out)

print(f"\n[CAPTURE] {len(golden)} noms, {golden['sector'].nunique()} secteurs, "
      f"{int(golden['nonscore'].sum())} non-scorables -> {out.name}")
print(golden.round(4).to_string())
