# SPEC — Moteur Qualité-Value-Contrarien (QV Engine)

> Feuille de route pour Claude Code.
> **La logique est validée et figée. La plomberie (données, persistance, UI) est à construire.**
> Implémentation de référence du cerveau : `qv_engine_v4.py`.

---

## 0. Ce qui est validé / ce qui ne l'est pas — à respecter, sans overclaim

| | Statut |
|---|---|
| **Construction** (pondération capé+gated > equal-weight) | ✅ **VALIDÉ** — bat l'EW en Sharpe sur les US (+0.14), stable par sous-période, par bootstrap (IC90% [+0.08, +0.21]) et par grille de paramètres ; **regagne sur l'Europe (+0.13)** → vraie prime, pas du curve-fit US |
| **Diversification géographique** (US + Europe) | ✅ Validée : réduit le risque *et* confirme l'edge hors-US |
| **Sélection** (quels noms acheter) | ❌ **NON validée** sans données point-in-time (le panier de backtest est survivant) |
| **Rendement de ~20%** | ❌ Survivorship + décennie exceptionnelle. **Attente forward honnête : marché + quelques points (~12-13% en bon régime), années négatives incluses** |

**Le moteur est une AIDE-DÉCISION / outil de discipline.** Il trouve la qualité en solde et retire l'émotion du accumuler/alléger. Il **ne garantit pas** de rendement. Toute copie produit doit refléter ça.

---

## 1. Objet

Outil où l'utilisateur **saisit manuellement ses positions + prix d'achat** (pas de connexion courtier). Le moteur tourne **quotidiennement**, score un univers de qualités, croise avec les positions, et émet des signaux : **ACCUMULER / TENIR / ALLÉGER** (génériques) + signaux **personnalisés au prix de revient**. L'utilisateur exécute lui-même chez son courtier.

---

## 2. Architecture & stack

- **Frontend** : Next.js + React. (Widgets de charts TradingView en option, pour la visualisation uniquement.)
- **Backend** : Supabase — Postgres + Edge Functions + cron quotidien.
- **Données** : FMP (Financial Modeling Prep), une seule API. (Voir §3.)
- **Tables** :
  - `positions` (user_id, ticker, quantité, prix_achat, date) — **source de vérité unique**.
  - `universe` (ticker, secteur, is_fin_structure).
  - `signals` (ticker, date, signal, scores, déclencheur).
- **Flux quotidien** : cron → fetch FMP (prix + fondamentaux) → score univers → croise `positions` → écrit `signals` → déclenche alertes (email/push).

---

## 3. Couche données — FMP

Remplace **tous** les appels `yfinance` du prototype par FMP. Le cerveau ne change pas.

- **Prix** : EOD historiques (drawdown 3 ans, RSI 14, MA 200j) + cours courant.
- **Fondamentaux** : income statement + balance sheet (EBIT, Invested Capital, Net Income, Gross Profit, Total Revenue, Total Debt, Common Stock Equity, taux d'impôt) → ROIC, marges, dette, croissance, EPS. Ratios pré-calculés disponibles.
- **Secteur** : classification par symbole.
- **Tier** : démarrer sur le **gratuit (250 appels/jour)** — suffisant pour ~50 noms vérifiés 1×/jour en batch. Passer en **Starter (~19$/mois)** en prod (lève le plafond, fondamentaux + ratios).
- **Auth** : clé API en variable d'environnement (jamais en dur).

---

## 4. Le moteur — logique (source de vérité : `qv_engine_v4.py`)

### 4.1 Univers
Qualités large-cap, **US + Europe**, multi-secteurs/pays (listes de départ dans le prototype). Élargissable. Réévalué périodiquement.

### 4.2 Score qualité — sector-neutral, 5 ans, winsorisé
Pour chaque métrique : z-score **intra-secteur (GICS)**, après **winsorisation 5/95**, sur **moyennes 5 ans**. Pondérations :

| Métrique | Poids |
|---|---|
| ROIC (NOPAT / Invested Capital) | **+1.5** |
| Marge brute | +1.0 |
| Marge nette | +1.0 |
| Croissance CA 5 ans (CAGR) | +0.7 |
| Dette / Equity | **−1.0** |
| Couverture des intérêts | +0.5 |

`quality_z` = somme pondérée / somme des |poids|. `quality_pct` = rang percentile.

**FIN_STRUCTURE** (banques + assureurs) → **exclus** du scoring ROIC/marge (capital/marges non comparables) → flag « non-scorable », bucket séparé.

### 4.3 Score peur / décote — prix
- `drawdown` = cours / plus-haut sur 756 jours − 1
- `rsi` = RSI(14)
- `vs200` = cours / MA(200) − 1

### 4.4 Garde value-trap — obligatoire
Une décote n'est « qualité en solde » que si :
`quality_pct ≥ 0.5` **ET** `eps_cagr_5y > −0.02`.
Sinon → **couteau qui tombe** (le marché re-rate un business en déclin) → ne pas accumuler.

### 4.5 Signaux (par nom)
- **ACCUMULER** : `quality_pct ≥ 0.5` ET `drawdown ≤ −15%` ET `rsi < 48` ET garde value-trap OK
- **ALLÉGER** : `quality_pct ≥ 0.4` ET `drawdown ≥ −5%` ET `rsi > 65`
- **TENIR** : qualité OK mais pleinement valorisée
- **FILTRER** (pas de signal) : `quality_pct < 0.4`

### 4.6 Construction de portefeuille — VALIDÉE
Cœur **equal-weight** sur les noms gated (`quality_pct ≥ 0.4`) **+ tilt contrarien capé** : `poids = base × (1 + 0.5 × cheapness)`, où `cheapness ∈ [0,1]` ∝ profondeur du drawdown, **gated** sur qualité + value-trap. Tilt borné à **1.5×** le poids de base. Renormaliser.
> NE PAS pondérer par drawdown sans borne (concave / short-gamma : monte le rendement brut mais casse le Sharpe).

### 4.7 Plafonds — garde-fou
Cap position **~8%**, cap secteur **~30%**. Actuellement **non-contraignants** (le livre est déjà diversifié : ligne max ~6%, secteur max ~29%). Les garder comme filet de sécurité.

### 4.8 Cash
Garder une **réserve de cash** (réduit le drawdown). **NE PAS** implémenter de timing « déploiement sur peur / température » : testé, **aucun edge risk-adjusted** vs un coussin constant. Réserve fixe, pas de market-timing.

---

## 5. Signaux personnalisés — prix d'achat

Croiser les signaux génériques avec les positions de l'utilisateur :
- **ALLÉGER perso** : ligne à **+40 à +50%** de son prix d'achat → zone de trim.
- **RENFORCER perso** : ligne à **−15%** de son prix d'achat **ET** toujours qualité + cheap → renforcer.
- Affichage : « ton {ticker} est à **+47%** → zone de trim » / « ton {ticker} à **−18%** et toujours qualité → renforce » / « peur large : {n} noms sous leur 200j ».

---

## 6. Ce qu'il NE faut PAS construire (pièges testés et écartés)

- ❌ **Timing de déploiement de cash** sur « température » (% sous 200j) — aucun edge risk-adjusted → coussin constant à la place.
- ❌ **Sentiment politique / news / social per-nom** — bruit. Le moteur **exploite** l'excès (achète la peur), il ne le **suit** pas.
- ❌ **Market-timing de régime** (bull/bear gating).
- ❌ **Connexion / exécution courtier** — inutile, exécution manuelle.
- ❌ **Toute promesse de 20% garanti** ou « formule magique » — aide-décision, pas garantie d'alpha.

---

## 7. Attentes honnêtes — à refléter dans l'UI

- Forward : **marché + quelques points (~12-13% en bon régime)**, **pas** 20%.
- **Années négatives assumées** (−9% à −18% en bear).
- L'edge = **sélection + discipline + prime de construction validée**, pas un signal magique.
- La **sélection** n'est pas validée sans point-in-time. Ce qui est validé : la **construction**, qui généralise US + Europe.

---

## 8. Axiomes d'implémentation

- **Déterminisme** : mêmes entrées → mêmes signaux.
- **Fail-neutral** : erreur/absence de données → **pas de signal**, jamais un faux signal.
- **Auditabilité** : chaque signal traçable à ses scores et entrées.
- **Zero magic values** : tous les seuils en config nommée (§4), pas de nombres en dur.
- **Single source of truth** : `positions` (prix d'achat) = source unique pour les signaux perso.

---

## 9. Critères d'acceptation

- [ ] Reproduit l'edge de construction validé sur l'univers (capé+gated > EW).
- [ ] Signaux déterministes + fail-neutral.
- [ ] Démarcation honnête visible dans l'UI (zéro overclaim).
- [ ] Cron quotidien fonctionnel ; alertes fiables.
- [ ] Migration yfinance → FMP **sans** changer le cerveau.

---

## 10. Roadmap de build

1. **Données** : couche FMP (remplace yfinance) + table `positions`.
2. **Cerveau** : porter `qv_engine_v4.py` → Supabase Edge Function (déterministe, fail-neutral).
3. **Cron quotidien** : score univers → croise positions → écrit `signals`.
4. **Alertes** : email/push sur ACCUMULER / ALLÉGER / signaux perso.
5. **UI** : dashboard positions + signaux (+ charts TradingView en option).
6. **(Optionnel — si déploiement de capital réel)** Bloc E : backtest **point-in-time cross-univers** (Sharadar SF1) pour *tester la sélection* — screen pré-enregistré, DSR déflaté, holdout de régime, même screen Europe/EM sans re-fit. Falsifie un mauvais screen ; ne prouve pas 20%.
