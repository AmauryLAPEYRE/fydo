"""
Configuration nommée du moteur QV (QARP) — SOURCE UNIQUE des seuils.

Axiome SPEC §7 : zéro magic value. Aucun nombre métier ne doit apparaître ailleurs
que dans ce fichier. Chaque run enregistre le hash de ce fichier (runs.config_hash)
pour que ses signaux soient rejouables à l'identique (déterminisme SPEC §7).

Chaque constante cite sa section de SPEC_QV_ENGINE_FINAL.md.
Les valeurs marquées « prior » sont des choix a priori NON fittés sur backtest
survivant (règle dure SPEC §7.1). Ne pas les optimiser sur données contaminées.
"""
from __future__ import annotations

# Hash de version de la config, calculé au runtime à partir de ce fichier.
# (Le calcul vit dans le code d'orchestration, pas ici, pour rester pur.)

# ─────────────────────────────────────────────────────────────────────────────
# §4.1 — UNIVERS
# L'univers se définit par une RÈGLE transparente (large-caps US+Europe au-dessus
# d'un plancher de market cap / appartenance indicielle), JAMAIS par cherry-pick
# des « forteresses » d'aujourd'hui (= biais de sélection chiffré à +26%/an).
# Distinction critique : live_watchlist (curé, aucune claim backtest) ≠ univers de
# backtest (point-in-time, morts inclus → Bloc E). Ne jamais mélanger les deux.
# ─────────────────────────────────────────────────────────────────────────────
UNIVERSE_TARGET_SIZE_MIN = 80          # cible basse (≥6-8 noms/secteur)
UNIVERSE_TARGET_SIZE_MAX = 120         # cible haute
UNIVERSE_MIN_MARKET_CAP_EUR = 5_000_000_000  # prior : plancher large-cap (5 Md€)

# FIN_STRUCTURE : banques + assureurs, exclus du scoring qualité ROIC/marge
# (capital/marges non comparables). Classés par INDUSTRIE FMP (règle, pas liste
# de tickers en dur — remplace le set codé en dur du prototype v4).
FIN_STRUCTURE_INDUSTRY_KEYWORDS = ("Bank", "Insurance")

# ─────────────────────────────────────────────────────────────────────────────
# §4.2 — SCORE QUALITÉ (sector-neutral, 5 ans, winsorisé, shrinké)
# ─────────────────────────────────────────────────────────────────────────────
QUALITY_YEARS = 5                      # fenêtre de moyenne des fondamentaux
QUALITY_WINSOR_LOW = 0.05              # winsorisation basse
QUALITY_WINSOR_HIGH = 0.95             # winsorisation haute
QUALITY_SHRINKAGE_LAMBDA = 0.5         # prior : z_final = λ·z_secteur + (1-λ)·z_univers

# Poids (somme des |poids| sert de normalisateur). Signe inclus.
QUALITY_WEIGHTS = {
    "roic_5y_avg":          1.5,
    "gross_margin_5y_avg":  1.0,
    "net_margin_5y_avg":    1.0,
    "rev_cagr_5y":          0.7,
    "debt_to_equity":      -1.0,
    "interest_coverage":    0.5,
}

# Taux d'impôt de repli quand non disponible / aberrant, pour le NOPAT du ROIC.
TAX_RATE_DEFAULT = 0.25
TAX_RATE_MIN = 0.0
TAX_RATE_MAX = 0.6

# ─────────────────────────────────────────────────────────────────────────────
# §4.3 — SCORE VALUE (yields EV-based, 5 ans, cross-sectional)
# value_xs_z = mean(z(fcf_ev), z(ebit_ev), z(e_p)) intra-secteur, winsor 5/95.
# own_pctile = GARDE-FOU / tie-break uniquement — JAMAIS pondéré en alpha
# (pari de mean-reversion de multiple, contaminé survivance comme le tilt mort).
# ─────────────────────────────────────────────────────────────────────────────
VALUE_YEARS = 5                        # numérateur 5 ans (Graham-Dodd, anti-cyclique)
VALUE_WINSOR_LOW = 0.05
VALUE_WINSOR_HIGH = 0.95
VALUE_METRICS = ("fcf_ev", "ebit_ev", "e_p")  # equal-weight (corrélés)
VALUE_OWN_HISTORY_YEARS = 5            # fenêtre du percentile vs propre histoire (garde-fou)

# ─────────────────────────────────────────────────────────────────────────────
# §4.4 — BOUCLIER DÉTRESSE (écran fondamental)
# NIVEAU = validé (prise de rang sur le prix, signe robuste) → exclusion dure.
# TENDANCE = plausible mais NON TESTÉE → advisory, PAS d'exclusion dure en V1
# (risque de circularité ; ne pas déclarer validé — SPEC §4.4).
# ─────────────────────────────────────────────────────────────────────────────
SHIELD_INTEREST_COVERAGE_MIN = 2.0     # niveau (exclusion dure)
SHIELD_NET_DEBT_EBITDA_MAX = 3.5       # niveau (exclusion dure)
SHIELD_FCF_TO_NI_MIN = 0.6             # qualité des earnings (Sloan), niveau
SHIELD_FCF_TO_NI_MAX = 2.0             # niveau (exclusion dure)

SHIELD_TREND_ENABLED_AS_HARD_GATE = False  # V1 : tendance non-gating (non testée)
SHIELD_MARGIN_TREND_MIN_PER_YEAR = -0.01   # prior advisory : pente marge brute ≥ -1pt/an
SHIELD_ROIC_TREND_MIN_PER_YEAR = -0.01     # prior advisory : pente ROIC ≥ -1pt/an

# ─────────────────────────────────────────────────────────────────────────────
# §4.3 — SCORE PEUR / PRIX (métriques prix, devise-neutre par nom)
# ─────────────────────────────────────────────────────────────────────────────
PRICE_DRAWDOWN_WINDOW_DAYS = 756       # plus-haut sur 3 ans (≈ 252×3)
PRICE_RSI_PERIOD = 14
PRICE_MA_WINDOW_DAYS = 200

# ─────────────────────────────────────────────────────────────────────────────
# §4.6 — CONSTRUCTION (gated equal-weight Q+V, ZÉRO tilt de magnitude)
# §4.7 — Tilt drawdown INTERDIT (falsifié). Aucune pondération ∝ drawdown ou ∝ z.
# ─────────────────────────────────────────────────────────────────────────────
COMBINED_Z_WEIGHT_QUALITY = 0.5        # prior, jamais tuné (SPEC §7.1)
COMBINED_Z_WEIGHT_VALUE = 0.5          # prior, jamais tuné
GATE_COMBINED_Z = 0.0                  # prior : sélectionne combined_z ≥ 0 (≈ top moitié)
CAP_POSITION = 0.08                    # filet (non-contraignant aujourd'hui)
CAP_SECTOR = 0.30                      # filet
CASH_BUFFER_FRACTION = 0.15            # prior advisory (coussin fixe, ZÉRO timing) — à confirmer

# ─────────────────────────────────────────────────────────────────────────────
# §4.5 — SIGNAUX GÉNÉRIQUES (par nom)
# ─────────────────────────────────────────────────────────────────────────────
# Filtre d'entrée (discipline anti-couteau, PAS alpha) : pas de nouveau plus-bas
# sur N jours ET RSI au-dessus d'un plancher.
ENTRY_NO_NEW_LOW_DAYS = 20
ENTRY_RSI_MIN = 30.0
# ALLÉGER : combined_z bas (cher) OU bouclier cassé. Seuil « cher » = prior.
ALLEGER_COMBINED_Z_MAX = 0.0           # prior : combined_z < 0 = cher → trim générique

# ─────────────────────────────────────────────────────────────────────────────
# §5 — SIGNAUX PERSONNALISÉS (prix d'achat — discipline, pas alpha, heuristiques prior)
# ─────────────────────────────────────────────────────────────────────────────
PERSO_TRIM_LOW = 0.40                  # +40% du prix d'achat → entrée de zone de trim
PERSO_TRIM_HIGH = 0.50                 # +50% → cœur de zone de trim
PERSO_REINFORCE_DROP = -0.15           # -15% du prix d'achat ET toujours sélectionnée

# ─────────────────────────────────────────────────────────────────────────────
# §3 — DONNÉES (FMP)
# ─────────────────────────────────────────────────────────────────────────────
FMP_FREE_TIER_DAILY_CALLS = 250        # plafond du tier gratuit
FUNDAMENTALS_REFRESH_DAYS = 90         # cache trimestriel (les comptes ne bougent pas/jour)
# Lag fondamental : règle de BACKTEST uniquement (anti look-ahead). En LIVE, on
# utilise le dernier filing dispo (= info du moment, zéro look-ahead).
BACKTEST_FUNDAMENTAL_LAG_MONTHS = 3    # 6 = prudent
REBALANCE_FREQUENCY_DAYS = 90          # trimestriel + bandes de no-trade larges (coûts)
