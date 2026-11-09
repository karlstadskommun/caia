-- Verktyget hette Zaid till oktober 2026. Den här migreringen står kvar som den
-- kördes. Schemat zaid heter caia sedan 2026-10-rename-schema-caia.sql.
-- Zaid: omgranskningen 7 oktober 2026 (F2), för en tabell som redan finns.
-- Kör en gång i Supabase (SQL Editor), efter 2026-10-reports-security.sql.
-- Ny installation: kör reports.sql i stället, där allt nedan redan ingår.
-- Går att köra flera gånger.
--
--   1. En lista i databasen över vilka konton som får spara, och en regel
--      som frågar den. Förut räckte det att ha ett konto i Supabase-projektet.
--   2. Gränser i byte på de två långa texterna. NOT VALID, som förra gången:
--      de gäller nya rader och prövar inte de befintliga.
--   3. SISTA STEGET, utanför transaktionen, skriver ni själva: era poster.
--      Tills det är gjort kan ingen spara en analys.

begin;

-- Vilka konton som får spara, i databasen själv. Appen släpper bara in konton
-- som står i ZAID_ALLOWED_EMAILS, men tabellen nås också direkt genom
-- Supabases API med projektets publika nyckel, förbi appen. Utan det här kan
-- varje konto i projektet lägga rader i tabellen, och i ett projekt med öppen
-- registrering är det vem som helst (omgranskningen 7 oktober 2026, F2).
--
-- Listan ligger i ett eget schema som API:t inte visar. Den ska ha samma
-- poster som ZAID_ALLOWED_EMAILS: hela adresser, domäner skrivna som
-- @kommun.se, eller * för alla inloggade. Små bokstäver.
create schema if not exists zaid;
grant usage on schema zaid to authenticated;

create table if not exists zaid.allowed (
  entry text primary key
    check (entry = lower(entry) and (entry = '*' or position('@' in entry) > 0))
);
alter table zaid.allowed enable row level security;
revoke all on zaid.allowed from anon, authenticated;

-- Läser kontots adress ur Supabases egen användartabell, inte ur
-- inloggningsbeviset, och kräver att adressen är bekräftad. collate "C" gör
-- att bara A-Z görs till små bokstäver: annars blir Kelvin-tecknet (U+212A)
-- ett vanligt k, och en domän skriven med det läses som @kommun.se.
create or replace function zaid.account_allowed() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from zaid.allowed where entry = '*')
      or exists (
        select 1
        from auth.users u
        join zaid.allowed a
          on a.entry = lower(u.email collate "C")
          or a.entry = substring(lower(u.email collate "C") from '@[^@]*$')
        where u.id = (select auth.uid())
          and u.email_confirmed_at is not null
          and position('@' in u.email) > 1
      );
$$;
revoke all on function zaid.account_allowed() from public, anon;
grant execute on function zaid.account_allowed() to authenticated;

alter table public.reports drop constraint if exists reports_intake_summary_bytes_check;
alter table public.reports drop constraint if exists reports_formatted_report_bytes_check;
alter table public.reports add constraint reports_intake_summary_bytes_check
  check (octet_length(intake_summary) <= 100000) not valid;
alter table public.reports add constraint reports_formatted_report_bytes_check
  check (octet_length(formatted_report) <= 600000) not valid;

drop policy if exists "reports: spara egna" on public.reports;
create policy "reports: spara egna" on public.reports
  for insert to authenticated
  with check ((select auth.uid()) = user_id
              and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
              and (select zaid.account_allowed()));

commit;

-- SISTA STEGET, som ni skriver själva: lägg in era poster, samma som i
-- ZAID_ALLOWED_EMAILS. Tom lista betyder att ingen kan spara en analys.
--
--   insert into zaid.allowed (entry) values ('@kommun.se'), ('anna.andersson@konsult.se');
--
-- Ändrar ni ZAID_ALLOWED_EMAILS senare, ändra här också (RUNBOOK, "Vem som
-- släpps in"). Se vad som står i listan: select entry from zaid.allowed;
