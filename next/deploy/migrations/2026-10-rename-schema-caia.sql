-- CAIA: verktyget hette Zaid till oktober 2026, och schemat med listan över
-- vilka konton som får spara hette zaid. Det här byter namn på schemat till
-- caia. Kör en gång i Supabase (SQL Editor), efter 2026-10-reports-allowlist.sql.
-- Ny installation: kör reports.sql i stället, där schemat redan heter caia.
-- Går att köra flera gånger.
--
-- Allt sker i en transaktion, så sparandet fungerar hela vägen:
--   1. Schemat byter namn. Listan (allowed), dess poster och behörigheterna
--      följer med, och regeln "reports: spara egna" pekar på samma funktion
--      som förut, eftersom den är bunden till funktionen och inte till namnet.
--   2. Funktionen skrivs om. Dess text namnger schemat, och den texten läses
--      varje gång funktionen körs: utan det här steget skulle varje sparande
--      fela med "relation zaid.allowed does not exist".
-- Tabellen public.reports och dess rader rörs inte.

begin;

do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'zaid') then
    -- Båda finns: då pekar tabellens regel på det gamla schemat, och en ny
    -- funktion bredvid skulle inte användas. Stanna hellre än att gissa.
    if exists (select 1 from pg_namespace where nspname = 'caia') then
      raise exception 'Både schemat zaid och schemat caia finns. Slå ihop dem för hand innan migreringen körs.';
    end if;
    alter schema zaid rename to caia;
  end if;
end
$$;

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

commit;

-- Kontroll efteråt. Den första ska visa caia.account_allowed() i regeln, den
-- andra era poster:
--   select pg_get_expr(polwithcheck, polrelid) from pg_policy
--    where polrelid = 'public.reports'::regclass and polname = 'reports: spara egna';
--   select entry from caia.allowed;
