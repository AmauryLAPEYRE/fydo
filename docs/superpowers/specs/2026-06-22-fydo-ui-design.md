# Spec — UI Fydo (dashboard signaux + positions)

> Step 6 du build QV. Front mono-user pour saisir ses positions et lire les signaux
> quotidiens produits par le cron. **Zéro divergence** : l'UI ne recalcule aucune
> logique — elle lit ce que le cerveau Python (parity-locked) a écrit en base.

## Contexte

Le backend est complet et tourne : cerveau (quality/value/distress/construct/signals,
78 tests), feeder FMP, Supabase (8 tables + RLS), `run_daily` (cron GH Actions vérifié
écrivant `scores`/`signals`/`runs`). Il manque la surface utilisateur.

## Décisions actées (brainstorming 2026-06-22)

- **Auth** : magic link (Supabase Auth, sans mot de passe). Mono-user.
- **Périmètre V1** : positions CRUD + dashboard signaux + delta du jour. **Charts
  TradingView déférés** (YAGNI).
- **Démarcation §0** : bandeau permanent + page « Comment lire » dédiée. L'honnêteté
  (aide-décision, pas garantie ; marché +1-4 % en bon régime ; années négatives) est
  structurelle, pas un footnote.
- **Hébergement** : dev local d'abord (`npm run dev`). Vercel plus tard.

## Stack

Next.js 15 (App Router) · TypeScript · Tailwind CSS · `@supabase/ssr` (auth + client
RLS-aware). Aucune dépendance lourde au-delà.

## Principe directeur — zéro recalcul côté UI

La logique des signaux (génériques ET perso) vit dans le Python testé. L'UI lit, elle
ne calcule pas. Deux ajouts backend rendent ça vrai :

1. **Migration `0003_read_policies.sql`** : active RLS + policy *lecture authentifiée*
   (`for select using (auth.role() = 'authenticated')`) sur `universe`, `scores`,
   `signals` (données marché partagées, read-only depuis le front). `positions` et
   `signals_perso` gardent leur RLS owner (`auth.uid() = user_id`).
2. **`run_daily` écrit `signals_perso`** : il calcule déjà `perso_signals` ; on le
   câble au `user_id` des positions via un nouveau `store.write_signals_perso`. La
   logique perso reste donc dans le cerveau Python, jamais réécrite en TS.

## Routes

| Route | Rôle |
|---|---|
| `/login` | Saisie email → envoi magic link |
| `/auth/callback` | Échange le code → pose la session (puis redirige vers `/`) |
| `/` (auth-gated) | Dashboard (voir ci-dessous) |
| `/how-to-read` | Page §0 : construit vs validé, plafond honnête, années négatives |

Le middleware Next protège `/` et `/how-to-read` (redirige vers `/login` si pas de session).

## Dashboard `/`

- **`DisclaimerBanner`** (permanent, en tête) : rappel court « aide-décision, pas
  garantie — marché +1-4 % en bon régime, années négatives incluses » + lien vers
  `/how-to-read`.
- **`SignalsTable`** : signaux du dernier `as_of`. Colonnes : ticker, secteur, signal
  (ACCUMULER/TENIR/ALLÉGER/FILTRER/hors-périmètre), trigger, combined_z, drawdown 3 ans,
  RSI. Tri par combined_z desc. Code couleur sobre par signal.
- **`DeltaPanel`** : nouveaux/changés vs le run précédent (calculé en base via les deux
  derniers `as_of` de `signals`). L'unité utile : ce qui a bougé.
- **`PositionsManager`** : liste des positions de l'user (ticker, prix d'achat, quantité,
  +%/− vs marché) jointes à leurs `signals_perso` (RENFORCER/ALLÉGER perso, trigger).
  Form d'ajout/édition/suppression (écrit `positions`, RLS owner).

## Flux de données

- **Lectures** : client Supabase authentifié.
  - `signals` ⋈ `scores` ⋈ `universe` → SignalsTable (RLS lecture authentifiée).
  - `positions` ⋈ `signals_perso` → PositionsManager (RLS owner).
- **Écritures UI** : uniquement `positions` (insert/update/delete, RLS owner).
- **Le cron reste seul à écrire** `scores`/`signals`/`signals_perso`/`runs`.

## Composants (responsabilité unique, testables isolément)

- `lib/supabase/{client,server,middleware}.ts` — création des clients SSR.
- `SupabaseProvider` — contexte session.
- `DisclaimerBanner` — bandeau §0.
- `SignalsTable` — tableau signaux (props : lignes).
- `DeltaPanel` — delta du jour (props : lignes).
- `PositionsManager` — form + liste + mutations.
- `app/how-to-read/page.tsx` — contenu §0 statique.

## Auth (magic link)

1. `/login` : email → `supabase.auth.signInWithOtp({ email })`.
2. L'user clique le lien reçu → `/auth/callback?code=...` → `exchangeCodeForSession`.
3. Session en cookie (SSR). Middleware garde les routes privées.
4. RLS : `auth.uid()` = `user_id` des positions/perso.

## Tests

La logique est déjà couverte en Python. L'UI = présentation → smoke léger :
- rendu de `SignalsTable`/`DeltaPanel` sur données mockées (composants purs),
- garde d'auth (redirection sans session).
Pas de sur-test du framework.

## Hors périmètre V1 (YAGNI)

Charts TradingView · multi-user (orgs/partage/billing) · alertes email (le delta est
déjà calculé → trivial plus tard avec Resend) · déploiement Vercel (local d'abord).

## Honnêteté (rappel — à refléter partout)

L'UI ne doit JAMAIS suggérer une garantie de rendement. Plafond affiché : marché
+ 1-4 % en bon régime, cyclique, possiblement nul net de coûts. Aucun alpha local
prouvé. La sélection n'est pas validée sans point-in-time (Bloc E).
