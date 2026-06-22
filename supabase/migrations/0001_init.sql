-- Schéma initial Fydo (QV engine). SPEC §2.
-- positions = source de vérité unique (prix d'achat). RLS par user_id.
-- universe/fundamentals/prices/scores/signals = partagés, écrits par le job backend
-- (role postgres via pooler, bypass RLS), lus par le front via PostgREST + RLS.

-- ── Univers (règle, pas cherry-pick) ───────────────────────────────────────
create table if not exists public.universe (
  ticker            text primary key,
  name              text,
  sector            text,
  currency          text,
  is_fin_structure  boolean not null default false,
  active            boolean not null default true,
  added_at          timestamptz not null default now()
);

-- ── Cache fondamental (contrat dérivé, refresh trimestriel) ────────────────
create table if not exists public.fundamentals_cache (
  ticker               text primary key references public.universe(ticker) on delete cascade,
  sector               text,
  nonscore             boolean,
  currency             text,
  mktcap               double precision,
  roic_5y_avg          double precision,
  gross_margin_5y_avg  double precision,
  net_margin_5y_avg    double precision,
  rev_cagr_5y          double precision,
  debt_to_equity       double precision,
  interest_coverage    double precision,
  net_debt_ebitda      double precision,
  fcf_ni               double precision,
  margin_trend         double precision,
  roic_trend           double precision,
  fcf_5y               double precision,
  ebit_5y              double precision,
  ni_5y                double precision,
  total_debt           double precision,
  cash                 double precision,
  years_available      integer,
  fetched_at           timestamptz not null default now()
);

-- ── Prix EOD (série stockée, append quotidien) ─────────────────────────────
create table if not exists public.prices_daily (
  ticker  text not null references public.universe(ticker) on delete cascade,
  date    date not null,
  close   double precision not null,
  primary key (ticker, date)
);

-- ── Scores (table d'AUDIT §8 : chaque signal traçable à ses scores) ────────
create table if not exists public.scores (
  ticker             text not null,
  as_of              date not null,
  quality_z          double precision,
  quality_pct        double precision,
  value_xs_z         double precision,
  combined_z         double precision,
  drawdown_756       double precision,
  rsi_14             double precision,
  interest_coverage  double precision,
  net_debt_ebitda    double precision,
  fcf_ni             double precision,
  gate_pass          boolean,
  distress_pass      boolean,
  primary key (ticker, as_of)
);

-- ── Signaux génériques (par nom) ───────────────────────────────────────────
create table if not exists public.signals (
  ticker   text not null,
  as_of    date not null,
  signal   text,
  trigger  text,
  primary key (ticker, as_of)
);

-- ── Positions = SOURCE DE VÉRITÉ (RLS par user_id) ─────────────────────────
create table if not exists public.positions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  ticker      text not null,
  quantity    double precision not null,
  buy_price   double precision not null,
  buy_date    date,
  created_at  timestamptz not null default now()
);
create index if not exists positions_user_idx on public.positions(user_id);

-- ── Signaux perso (croise positions, RLS par user_id) ──────────────────────
create table if not exists public.signals_perso (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  ticker      text not null,
  as_of       date not null,
  signal      text,
  trigger     text,
  pct_vs_buy  double precision
);
create index if not exists signals_perso_user_idx on public.signals_perso(user_id);

-- ── Runs (auditabilité / no-fail-silent : noms droppés loggés) ─────────────
create table if not exists public.runs (
  run_id          uuid primary key default gen_random_uuid(),
  as_of           date not null,
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  status          text,
  config_hash     text,
  universe_count  integer,
  fetched_count   integer,
  dropped_count   integer,
  dropped_detail  jsonb
);

-- ── RLS : positions + signals_perso scoped au propriétaire ─────────────────
alter table public.positions     enable row level security;
alter table public.signals_perso enable row level security;

drop policy if exists positions_owner on public.positions;
create policy positions_owner on public.positions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists signals_perso_owner on public.signals_perso;
create policy signals_perso_owner on public.signals_perso
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
