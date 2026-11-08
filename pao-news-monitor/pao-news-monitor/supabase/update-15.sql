-- PAO News Monitor - update 15: Ask AI "Whole region" conversations
-- Safe to run more than once.
--
-- Ask AI can now answer across all PAOs at once (pick "Whole region (all PAOs)").
-- Those conversations aren't about one PAO, so they're saved with no PAO (pao_id empty).
-- Without this file, whole-region answers still work, but follow-up questions can't
-- continue the conversation (each question starts fresh).

alter table ask_ai_threads alter column pao_id drop not null;

notify pgrst, 'reload schema';
