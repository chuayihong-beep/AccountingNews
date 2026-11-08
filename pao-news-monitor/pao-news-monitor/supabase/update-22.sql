-- PAO News Monitor - update 22: AI usage log
-- Safe to run more than once.
--
-- Every AI answer (Ask AI, the daily relevance check, the brief's tagging and highlight explanations)
-- adds one row here: when, which job, which model, and how many tokens went in and out. NO question text,
-- answers or article text is stored. Admin > AI usage reads it to show requests, tokens and an estimated price.
-- Only admins can read it.

create table if not exists public.ai_usage (
  id                bigserial primary key,
  at                timestamptz not null default now(),
  feature           text not null,      -- ask | relevance | tagging | explain
  model             text,
  prompt_tokens     integer not null default 0,
  completion_tokens integer not null default 0
);
create index if not exists ai_usage_at_idx on public.ai_usage (at);

alter table public.ai_usage enable row level security;
drop policy if exists "team reads ai usage" on public.ai_usage;
drop policy if exists "admins read ai usage" on public.ai_usage;
create policy "admins read ai usage" on public.ai_usage for select to authenticated using (public.is_admin());
-- Only the collector and the Ask AI function (service key) can write; nobody can edit or delete from the web page.
