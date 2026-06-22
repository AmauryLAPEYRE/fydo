# Fydo — Moteur Qualité-Value-Contrarien (QARP)

> Projet **distinct d'Eydo** (app d'avis alimentaires). Repo standalone.
> Outil d'**aide-décision / discipline** d'investissement : l'utilisateur saisit ses
> positions + prix d'achat (pas de connexion courtier), le moteur score un univers
> de qualités et émet ACCUMULER / TENIR / ALLÉGER + signaux au prix de revient.
> L'utilisateur exécute lui-même.

## ⚠️ Statut épistémique (SPEC §0 — à respecter, zéro overclaim)

**Aucun alpha local n'est prouvé.** Le moteur retire l'émotion, il ne garantit pas de rendement.

| Étage | Validé sans point-in-time |
|---|---|
| Qualité | Prime externe documentée (QMJ/RMW), **modeste** |
| Value | Construit principié — **alpha local NON validé** |
| Bouclier détresse (niveau) | ✅ prise de rang incrémentale sur le prix, signe robuste |
| Construction (gated-EW Q+V) | ✅ gate ordinal robuste à la survivance |
| Tilt drawdown | ❌ **falsifié et retiré** (la survivance gonflait l'edge au-delà de l'edge mesuré) |

**Plafond honnête : marché + 1 à 4 % en bon régime, cyclique, possiblement nul net de coûts.**
Pas « mieux qu'un ETF ». Le seul juge final de l'alpha = backtest point-in-time (Bloc E).

Source de vérité figée : `SPEC_QV_ENGINE_FINAL.md` (à déposer à la racine).

## Architecture

- **Cerveau** : Python déterministe (`engine/qv/`), testé **au point près** contre l'oracle gelé `engine/qv_engine_v4.py`.
  *(On surcharge la lettre de SPEC §2 « Edge Function » : réécrire la cervelle en TS rouvrirait la divergence silencieuse et casserait l'oracle. Les axiomes — déterminisme, single source of truth, auditabilité — exigent un cerveau unique en Python.)*
- **Scheduler** : GitHub Actions cron (V1) → durcissement container managé ensuite.
- **Backend** : Supabase (Postgres + RLS + Edge Functions = API auth + dispatch alertes uniquement).
- **Frontend** : Next.js (`web/`).
- **Données** : FMP (API « stable »). **Périmètre V1 = US-only** : les fondamentaux EU sont *premium* sur le tier gratuit (income/balance/cash-flow EU → HTTP 402 ; profils/prix EU OK). Europe à rajouter sur un plan international. Pas de batch quote en gratuit → 1 appel `quote`/nom/jour (≤120 noms < 250) + cache fondamental trimestriel.

## Structure

```
engine/
  qv_engine_v4.py       # ORACLE GELÉ (interdit d'édition) — fixe les conventions de calcul
  qv/
    config.py           # tous les seuils nommés (zéro magic value)
    data/               # client FMP + persistance Supabase
    brain/              # quality · value · distress · price · construct · signals
  tests/                # parity (vs oracle) · determinism · invariants · MC bouclier
web/                    # Next.js
supabase/               # migrations SQL + RLS + Edge Functions
.github/workflows/      # cron quotidien + refresh trimestriel
docs/archive/           # specs superseded
```

## Invariants (SPEC §7 — Claude Code ne doit JAMAIS les défaire)

1. Hyperparamètres = **priors, jamais fittés** sur backtest survivant.
2. `own-history value` = garde-fou, **jamais alpha**.
3. **Pas de factor-timing**, pas de **tilt de magnitude**, pas de **timing de cash**.
4. Déterminisme · fail-neutral (donnée manquante → pas de signal) · **log de chaque nom droppé** · zéro magic value · `positions` = single source of truth.

## Gouvernance — conflit oracle vs SPEC

L'oracle `qv_engine_v4.py` et `SPEC_QV_ENGINE_FINAL.md` peuvent diverger. Règle de tie-break :

> **La SPEC a-t-elle *décidé* ce point, ou *comble-t-elle un trou* qu'elle a laissé ?**
> - **Décision SPEC** (différente du prototype) → **la SPEC gagne** : divergence intentionnelle, **hors parité**, documentée et testée en propriété. Le prototype est superseded sur ce point.
> - **Trou** (définition sous-spécifiée : invested capital, EV avec/sans minoritaires…) → **convention de l'oracle**, **parité requise** (faute d'autre autorité).

Divergences intentionnelles actées (la SPEC gagne, hors parité) :
- **Fenêtre de drawdown = 756 j** (SPEC §4.3) vs 252 j dans l'oracle. Un creux 3 ans est un meilleur ancrage de « peur » ; et le tilt étant mort, le drawdown n'est plus que contextuel/audit. Garde : historique < 756 j → drawdown **fail-neutral** (NaN/insuffisant), jamais un drawdown 200 j déguisé en 756.
- **Couverture d'intérêts (+0.5)** et **shrinkage (λ=0.5)** ajoutés au score qualité (SPEC §4.2), absents de l'oracle.

## État du build

- [x] Step 0 — squelette, `config.py`, repo, oracle gelé
- [x] Step 1 — golden master figé + `quality.py` (parité oracle au point près)
- [x] Step 2 — `price.py` (RSI/MA200 parité, drawdown 756 propriété) + `construct.py` (gated-EW de base, caps)
- [x] Step 3 — `value.py` §4.3 + `distress.py` §4.4 + pipeline `build_portfolio` + invariants + MC en régression
- [x] Step 3e — `signals.py` §4.5/§5 (ACCUMULER/TENIR/ALLÉGER/FILTRER + perso) → **cerveau complet**
- [~] Step 4 — feeder FMP : `metrics.py` (dérivation FMP→contrat) ✓ · reste `fmp_client.py` (HTTP) + `store.py`/migrations + table `positions`
- [ ] Step 5 — cron quotidien → `signals` → alertes
- [ ] Step 6 — UI (démarcation §0 visible)

Suite de tests : `pytest` (rapide, 43) · `pytest -m slow` (régression MC, 4) · scripts d'évidence dans `tests/validation/`.
