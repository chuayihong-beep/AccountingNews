---
title: CAPA PAO News Monitor - PRD
status: draft
created: 2026-10-20
updated: 2026-10-20
---

# PRD: CAPA PAO News Monitor

## 0. Document Purpose

This PRD records what the PAO News Monitor is for, what it must do, and what it deliberately does not do. It is written for CAPA management, for the staff who will run it, and above all for whoever maintains it after the current developer leaves (about mid-2027). The system already exists and is in testing; this document describes it as built plus agreed direction, so a newcomer can understand the intent without reading the chat history.

Related documents: the staff **User Guide** (how to use it day to day), the project `README.md` (setup and operations), and *CAPA AI Intelligence Project Brief* (18 Oct 2026), which set the original direction. Technical choices live in `addendum.md`, not here. Inferred points are tagged `[ASSUMPTION]` and listed in §10.

## 1. Vision

CAPA needs to know what is happening across its network of professional accountancy organisations (PAOs) and standard-setters - who has a new president, which body launched an AI guide, what IESBA is consulting on - without staff checking 51 websites by hand.

The monitor collects that news automatically every day, lets staff sort it in a few clicks, and turns the sorted news into a weekly intelligence brief for CAPA staff. A person stays responsible for what goes out: staff decide what is relevant, and nothing is emailed until an admin approves it. The aim is a brief that is reliably current and relevant, produced with minimal effort and at no recurring cost.

## 2. Target Users

### 2.1 Jobs To Be Done
- **Know what changed this week** across members and stakeholders, in one place, without visiting every site.
- **Keep the brief trustworthy** - no outdated, duplicate or irrelevant items reach readers.
- **Spot changes at member bodies** (new leaders, new contact details) early enough to act, e.g. congratulation letters or updating records.
- **Understand the profession's direction** - recurring themes (AI and digitalisation, talent, sustainability, ethics and standards) and what they mean for Asia-Pacific.

### 2.2 Users and roles
| Role | Who | Does |
| --- | --- | --- |
| Team | CAPA staff | Review collected items and categorise them |
| Admin | Responsible staff member(s) | Everything Team does, plus approve and send the brief, and manage people, roles, members and the mailing list |
| Viewer | Other staff | Read only |
| Brief reader | Internal CAPA staff on the mailing list | Receive the weekly brief by email |

Roles are configurable: admins can create roles and choose their permissions.

### 2.3 Non-users
- Member bodies and the public do not use the monitor or receive the brief.
- The newsletter team does not build newsletters here; they use a separate CRM.

### 2.4 Key User Journeys
- **UJ-1. Team member clears the week's items.** Signs in, filters to *Unreviewed*, tags each item Regional, Country-specific, PAO-specific or Not relevant, fixes a wrongly filed item with *Move to another PAO*, removes junk.
- **UJ-2. Admin approves and sends the Monday brief.** Opens the AI draft, checks it against the listed sources, edits a line, approves, presses *Send now*; staff receive it in their inbox within about an hour.
- **UJ-3. Admin follows up a leadership change.** Sees a red *Leadership change* item, opens *before / now*, checks the PAO's page, then updates CAPA's member records outside the monitor.
- **UJ-4. Team member adds what the scrapers missed.** A Facebook-only post: takes a screenshot, the monitor reads its text, the team member picks the PAO and date and saves it.

## 3. Glossary
- **PAO** - a professional accountancy organisation in CAPA's network. Used loosely for every monitored organisation.
- **Member** - one monitored organisation record (33 CAPA organisations + 18 stakeholders = 51 at the start). Group: Member, Associate, Affiliate or Stakeholder.
- **Source** - where items come from: Website, Google News, Email, Page watch, or Added by team.
- **Item** - one collected link or post, filed under exactly one Member.
- **Type** - what an Item is: News, Event, Publication, Newsletter / article, Leadership change, Contact change.
- **Relevance tag** - staff judgement on an Item: Regional, Country-specific, PAO-specific, or Not relevant. Untagged = unreviewed.
- **Category** - free-text label for what an Item is for (e.g. Insights & trends, Research & surveys).
- **First scan** - Items found the first time a page is checked; possibly old, hidden by default, never in the Brief.
- **Brief** - the weekly AI-drafted intelligence report. States: Draft, Approved, Sent.
- **Health** - per-Source, per-Member result of the last check: OK, Warning, Error, or Not run.
- **Removed** - an Item hidden everywhere by staff; restorable.

## 4. Features

### 4.1 Daily collection
**Description:** Every morning (about 05:40 Malaysia time) the system checks every active Member's Sources and stores new Items. It must never overwrite an Item staff have already handled, and must not flood staff with old links. Realizes UJ-1, UJ-3.

#### FR-1: Collect from each Source
The system collects Items daily from each Member's websites (news, publications, events, newsletter pages), Google News searches, the monitor's email inbox, and leadership/contact pages.
- Each Item records title, link, date (when known), Source, Type and the Member it belongs to.
- A site that blocks simple requests is retried once with a real browser.

#### FR-2: No duplicates, no overwrites
- Each Item has a stable fingerprint (Member + Source + link, tracking codes removed); an Item already stored, Removed or cleaned up is never added again.
- Collection never changes an existing Item's tags, notes, Type or Member.

#### FR-3: First scan protection
- On a page's first check, all its links are saved as First scan and hidden.
- If most links on a known page are new at once (a redesign), the new links are treated as First scan.

#### FR-4: Leadership and contact change alerts
- The system compares each Member's leadership and contact pages with the previous copy and creates a Leadership change / Contact change Item listing lines added and removed.
- Only the latest copy of each page is kept.
- Out of scope: updating member records automatically (see §5).

#### FR-5: Health reporting
- After each run, every Source of every Member gets a Health status with a plain-language message, last-run time and consecutive-failure count.
- "Checked, nothing new" is distinguishable from "check failed".
- A website with no new links for 60+ days is flagged as a Warning.

### 4.2 Review and categorisation
**Description:** Staff turn raw Items into a sorted record. One click per Item decides whether and where it appears in the Brief. Realizes UJ-1, UJ-4.

#### FR-6: Relevance tagging
Team members can set or clear one Relevance tag per Item.
- Regional Items lead the Brief; Country-specific go in *Country updates*; PAO-specific in *PAO updates*; Not relevant are excluded and hidden by default.

#### FR-7: Item details and corrections
Team members can set Category, Notes and Type, and move an Item to a different Member.
- A moved Item stays moved after later collections.

#### FR-8: Remove and restore
Users with the *Remove items* permission can hide an Item everywhere and restore it later from a Removed view.

#### FR-9: Find and filter
Users can filter by period (24 hours to all time), relevance state, Source, Type and First scan, search text, and export the visible Items as CSV.

#### FR-10: Manual additions
Team members can add Items one at a time, import many from Excel/CSV, or create them from screenshots (text read in the browser, Member and date chosen by the user).

#### FR-11: Readable non-English headlines
Users can translate a non-English headline in place, or open the full article translated.

### 4.3 Weekly brief
**Description:** Every Monday (about 07:45 Malaysia time) the system drafts a Brief from the past week's Items; an Admin approves it and it is emailed to the mailing list. Realizes UJ-2.

#### FR-12: Draft generation
- Uses Items published in the week (or first found in it when undated); excludes Not relevant, Removed, First scan and duplicate headlines.
- AI summarises and themes Items (staff-tagged first), then writes sections: Headlines, By theme (AI & digitalisation, Talent, Sustainability, Ethics & standards, Other), Leadership changes, Country updates, PAO updates, Upcoming events.
- Every statement cites its source Items; the source list and the list of Members with no news are produced by code, not AI.
- AI interpretation is labelled as such and kept apart from source facts.

#### FR-13: Resilient AI
- The AI step tries several free providers in order; if all fail, the Brief is a plain list of the week's Items rather than nothing.
- Each Brief records which models produced it.
- Re-running replaces unedited Drafts for the same week; edited or approved Briefs are kept.

#### FR-14: Edit, approve, send
- Users with permission can edit a Draft, approve it, or return it to Draft.
- Only an Approved Brief can be sent. Sending emails every active mailing-list address in BCC within about an hour, with replies going to the sender; a pending send can be cancelled.
- The Brief shows who approved and sent it, when, and to how many recipients.

### 4.4 Administration
**Description:** Admins control who can do what and what is monitored, without code.

#### FR-15: Access control
- Only email addresses an admin has added can create an account; sign-in is email + password with self-service reset.
- Admins create roles and tick permissions per role (tag, add, remove items; edit, approve, send briefs; manage mailing list; manage members). Admin always has every permission; there is always at least one admin.
- Permissions are enforced by the database, not only hidden on screen.

#### FR-16: Member list
Users with permission can add, edit, deactivate or delete Members and set their Sources (website pages, search terms, leadership/contact pages). Deactivating stops monitoring and keeps history.

#### FR-17: Mailing list
Users with permission can add, pause and remove Brief recipients.

#### FR-18: Data upkeep
- Removed Items are deleted 90 days after removal; untagged and Not relevant Items 12 months after collection.
- Tagged Items and Items cited in any Brief are kept indefinitely.

## 5. Non-Goals
- **Not a newsletter tool.** Newsletters are built in a separate CRM. The monitor may export lists but does not compose or send newsletters.
- **Not a member database or CRM.** Member records live in Excel now and Glue Up later. The monitor does not store member profiles, contacts or engagement history.
- **No automatic member-record updates.** Leadership/contact changes are alerts for a person to check. Suggesting record updates is on hold until criteria exist (§9).
- **Not public.** No access for member bodies or the public; the Brief is for internal staff.
- **No Facebook or social-media scraping.** Platforms block it; staff use screenshots instead.
- **No automatic reading of CAPA's own correspondence** beyond the dedicated monitor inbox.
- **No paid services** without management approval.

## 6. Scope

### 6.1 In scope now (built, in testing)
Everything in §4.

### 6.2 Out of scope for now
- Engagement tracker (meetings, action owners, follow-ups) from the original brief - `[ASSUMPTION]` belongs in the CRM/Glue Up; confirm with management (§9).
- Glue Up integration - revisit once CAPA's Glue Up plan and API access are known.
- Member-update suggestions - on hold until criteria are agreed.
- Visual redesign with CAPA branding - planned after testing.

## 7. Cross-Cutting Requirements

### 7.1 Cost
- Runs entirely on free tiers (GitHub, Cloudflare, Supabase, free AI providers). Recurring cost target: RM0/month.
- Database growth stays within the free 500 MB through FR-18.

### 7.2 Security and privacy
- Secrets only in GitHub Actions secrets; never in the repository, which is public during testing.
- No real member personal data in repository files.
- All data behind sign-in and role permissions (FR-15).

### 7.3 Reliability and operations
- Scheduled jobs: daily collection, Monday brief, send queue every 10 minutes.
- One failing Source or Member never stops the rest of the run.
- Every run writes a readable summary (per Member, per Source) to GitHub Actions.
- Database changes ship as numbered, re-runnable SQL update files.

### 7.4 Handover
- Before go-live, everything moves from test accounts to CAPA-owned accounts (GitHub, Cloudflare, Supabase, email, AI keys) with at least two admins, and all test keys are replaced.
- The User Guide, README and this PRD are enough for a successor to run, update and recover the system.

## 8. Success Metrics

**Primary**
- **SM-1: Brief goes out every week** - an approved Brief is sent every Monday it is due. Validates FR-12, FR-14.
- **SM-2: Brief stays clean** - Admin approves with no more than minor edits; readers find no outdated or irrelevant items. Validates FR-3, FR-6, FR-12.

**Secondary**
- **SM-3: Items reviewed on time** - each week's items are tagged before the Monday brief is reviewed. Validates FR-6.
- **SM-4: Changes caught** - leadership and contact changes at Members are noticed through the monitor rather than by chance. Validates FR-4.
- **SM-5: Coverage is visible** - every Member's Health is known; failing Sources are fixed or replaced. Validates FR-5.

**Counter-metric**
- **SM-C1: Item count** - more items collected is not better. Optimising volume adds noise and tagging work; relevance and accuracy matter more. Counterbalances SM-3.

`[ASSUMPTION]` No numeric targets yet; set them after a month of testing data.

## 9. Open Questions
1. Engagement tracker: is it dropped, or moved to Glue Up? (Management)
2. What criteria would make a member-record update suggestion worth building? (Membership team)
3. Who is the long-term owner and second admin after the developer leaves?
4. Will CAPA's Glue Up plan include API access?
5. Does CAPA want alerts for urgent deadlines (e.g. consultation closing dates) between Briefs?

## 10. Assumptions Index
- §6.2 / §9 - Engagement tracker is out of scope here and belongs in the CRM.
- §8 - Success targets are qualitative until testing produces baseline numbers.
