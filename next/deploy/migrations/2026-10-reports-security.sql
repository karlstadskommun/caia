-- Verktyget hette Zaid till oktober 2026. Den här migreringen står kvar som den
-- kördes. Schemat zaid heter caia sedan 2026-10-rename-schema-caia.sql.
-- Zaid: säkerhetsgranskningen oktober 2026 (S7), för en tabell som redan finns.
-- Kör en gång i Supabase (SQL Editor). Ny installation: kör reports.sql i
-- stället, där allt nedan redan ingår. Går att köra flera gånger.
--
-- Gör tabellen likadan som reports.sql:
--   1. Längdgränser på texterna, samma som appens. NOT VALID: de gäller nya
--      rader men prövar inte de befintliga, så skriptet kan inte stoppa på en
--      gammal rad. (Största raden i Karlstad 2026-10-07: 20 582 tecken.)
--   2. Policyerna byts mot reports.sql:s: bara inloggade, inte anonyma
--      konton, och bara egna rader. Alla befintliga tas bort först, vad de
--      än heter. Karlstads tabell hade own_select, own_insert, own_update
--      och own_delete för alla roller.
--   3. Rättigheterna: inloggade får läsa, spara och radera. Ingen får ändra
--      en sparad rapport, och utloggade (anon) får ingenting.

begin;

alter table public.reports drop constraint if exists reports_action_name_check;
alter table public.reports drop constraint if exists reports_key_metric_check;
alter table public.reports drop constraint if exists reports_intake_summary_check;
alter table public.reports drop constraint if exists reports_formatted_report_check;
alter table public.reports add constraint reports_action_name_check
  check (char_length(action_name) <= 300) not valid;
alter table public.reports add constraint reports_key_metric_check
  check (octet_length(key_metric::text) <= 1000) not valid;
alter table public.reports add constraint reports_intake_summary_check
  check (char_length(intake_summary) <= 50000) not valid;
alter table public.reports add constraint reports_formatted_report_check
  check (char_length(formatted_report) <= 300000) not valid;

alter table public.reports enable row level security;

-- Alla policyer på tabellen, vad de än heter: policyer gäller med "eller",
-- så en enda kvarglömd höll tabellen lika öppen som förut.
do $$
declare p record;
begin
  for p in
    select policyname from pg_policies
    where schemaname = 'public' and tablename = 'reports'
  loop
    execute format('drop policy %I on public.reports', p.policyname);
  end loop;
end $$;

create policy "reports: läsa egna" on public.reports
  for select to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

create policy "reports: spara egna" on public.reports
  for insert to authenticated
  with check ((select auth.uid()) = user_id
              and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

create policy "reports: radera egna" on public.reports
  for delete to authenticated
  using ((select auth.uid()) = user_id
         and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false);

revoke all on public.reports from anon;
revoke all on public.reports from authenticated;
grant select, insert, delete on public.reports to authenticated;

commit;
