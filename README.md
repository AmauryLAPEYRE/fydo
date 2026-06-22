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
- **Données** : FMP — prix quotidiens (1 batch quote/jour) + cache fondamental trimestriel.

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

## État du build

- [x] Step 0 — squelette, `config.py`, repo, oracle gelé
- [ ] Step 1 — couche données FMP + table `positions` + fixture-oracle
- [ ] Step 2 — port qualité/prix/construction (parité vs oracle) + value §4.3 + bouclier §4.4
- [ ] Step 3 — cron quotidien → `signals`
- [ ] Step 4 — alertes
- [ ] Step 5 — UI (démarcation §0 visible)
