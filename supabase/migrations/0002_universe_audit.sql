-- Auditabilité de l'univers (§8) : quels noms, quel jour, par quelle règle.
alter table public.universe add column if not exists screen_rule text;
alter table public.universe add column if not exists screened_at date;
