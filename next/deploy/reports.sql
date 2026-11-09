-- CAIA: tabellen för sparade analyser. Kör en gång i Supabase (SQL Editor).
-- Koden skriver user_id, action_name, key_metric, intake_summary och
-- formatted_report, och läser id, action_name, key_metric, created_at och
-- formatted_report. Varje användare ser, sparar och raderar bara sina egna
-- rader. Anonyma konton (Supabase "anonymous sign-in") får ingenting, och
-- bara konton i listan caia.allowed får spara (se längre ner, och sista
-- steget i filen som ni skriver själva).
-- Längdgränserna är desamma som appens (REPORT_MAX_CHARS i app.py), så en
-- rad som går förbi appen direkt mot API:t kan inte bli större. Tecken och
-- byte räknas var för sig: 300 000 tecken kan annars vara 1,2 MB.

create table public.reports (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at       timestamptz not null default now(),
  action_name      text check (char_length(action_name) <= 300),
  key_metric       jsonb check (octet_length(key_metric::text) <= 1000),
  intake_summary   text check (char_length(intake_summary) <= 50000),
  formatted_report text check (char_length(formatted_report) <= 300000),
  constraint reports_intake_summary_bytes_check check (octet_length(intake_summary) <= 100000),
  constraint reports_formatted_report_bytes_check check (octet_length(formatted_report) <= 600000)
);

create index reports_user_created_idx on public.reports (user_id, created_at desc);

-- Vilka konton som får spara, i databasen själv. Appen släpper bara in konton
-- som står i CAIA_ALLOWED_EMAILS, men tabellen nås också direkt genom
-- Supabases API med projektets publika nyckel, förbi appen. Utan det här kan
-- varje konto i projektet lägga rader i tabellen, och i ett projekt med öppen
-- registrering är det vem som helst (omgranskningen 7 oktober 2026, F2).
--
-- Listan ligger i ett eget schema som API:t inte visar. Den ska ha samma
-- poster som CAIA_ALLOWED_EMAILS: hela adresser, domäner skrivna som
-- @kommun.se, eller * för alla inloggade. Små bokstäver.
create schema if not exists caia;
grant usage on schema caia to authenticated;

create table if not exists caia.allowed (
  entry text primary key
    check (entry = lower(entry) and (entry = '*' or position('@' in entry) > 0))
);
alter table caia.allowed enable row level security;
revoke all on caia.allowed from anon, authenticated;

-- Läser kontots adress ur Supabases egen användartabell, inte ur
-- inloggningsbeviset, och kräver att adressen är bekräftad. collate "C" gör
-- att bara A-Z görs till små bokstäver: annars blir Kelvin-tecknet (U+212A)
-- ett vanligt k, och en domän skriven med det läses som @kommun.se.
create or replace function caia.account_allowed() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from caia.allowed where entry = '*')
      or exists (
        select 1
        from auth.users u
        join caia.allowed a
          on a.entry = lower(u.email collate "C")
          or a.entry = substring(lower(u.email collate "C") from '@[^@]*$')
        where u.id = (select auth.uid())
          and u.email_confirmed_at is not null
          and position('@' in u.email) > 1
      );
$$;
revoke all on function caia.account_allowed() from public, anon;
grant execute on function caia.account_allowed() to authenticated;

alter table public.reports enable row level security;

create policy "reports: läsa egna" on public.reports
  for select to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

create policy "reports: spara egna" on public.reports
  for insert to authenticated
  with check ((select auth.uid()) = user_id
              and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
              and (select caia.account_allowed()));

create policy "reports: radera egna" on public.reports
  for delete to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

-- Nya Supabase-projekt (från 30 maj 2026) exponerar inte tabeller mot API:t
-- av sig själva. Utan raden nedan svarar sparandet med ett behörighetsfel.
-- Ingen update: en sparad rapport ändras aldrig.
grant select, insert, delete on public.reports to authenticated;

-- SISTA STEGET, som ni skriver själva: lägg in era poster, samma som i
-- CAIA_ALLOWED_EMAILS. Tom lista betyder att ingen kan spara en analys.
--
--   insert into caia.allowed (entry) values ('@kommun.se'), ('anna.andersson@konsult.se');
--
-- Ändrar ni CAIA_ALLOWED_EMAILS senare, ändra här också (RUNBOOK, "Vem som
-- släpps in"). Se vad som står i listan: select entry from caia.allowed;
