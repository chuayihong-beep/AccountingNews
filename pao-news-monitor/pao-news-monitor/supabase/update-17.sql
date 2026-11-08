-- PAO News Monitor - update 17: a background profile for each PAO
-- Safe to run more than once.
--
-- Adds two columns to the member list:
--   profile          short plain-text background on the PAO (who they are, leaders, what they are doing,
--                    how they connect to CAPA, gaps, and the public sources behind each line)
--   profile_checked  the date a person last checked the profile against its sources
-- Ask AI shows the profile to the AI as "Background on file", kept separate from the numbered news
-- items, so a question like "profile CA Sri Lanka" can use it. Public facts only - nothing confidential.
-- After this, redeploy Ask AI (same command as before) so it starts using the profiles.

alter table paos add column if not exists profile         text;
alter table paos add column if not exists profile_checked date;

-- ---- Profiles (30 Oct 2026) ----
-- CA Sri Lanka: researched by Claude from public pages. The other 22 (14 member PAOs, IFAC, the
-- standard-setters, AFA and SAFA): drafted by GPT from public pages, then spot-checked by Claude
-- (leadership for FICA, ICAI, CA ANZ and the IASB matched news sources; FICA's 2026 President corrected an
-- earlier draft). CAPA board and committee roles come from CAPA's website and could not be re-opened
-- from here. Re-running this file overwrites these profiles, so edit here rather than in the database.

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: CPA Australia, founded in 1886, is an Australian company limited by guarantee and a voluntary membership and professional-standards body, not the statutory auditor regulator. It provides education, training, technical support and advocacy to 176,327 members (per its integrated report; the page gives no date). It has offices across Australia and in Asia, the Pacific, the UK and the UAE.
LEADERSHIP (as of 1 Oct 2026): President and Chair Warren McRae and Deputy Presidents Louise Cox and Julie Crisp began 12-month terms on 1 October 2026; CEO Chris Freeland took office in March 2024. CPA Congress 2026 also comes to Kuala Lumpur on 5 November 2026.
RECENT: October 2026: CPA Congress 2026 ran in Melbourne and online under “Lead the Outcome”. October 2026: CPA Australia reported that Australian businesses risk falling behind in AI adoption. September 2026: it called for action on audit capacity as assurance demand grows.
CAPA LINK: Member of CAPA and IFAC. Priya Terumalay, Head of SEA, is a CAPA director for 2025-2027 (per CAPA staff and CAPA's board page).
NOT KNOWN: A current student total was not found.
SOURCES: https://www.cpaaustralia.com.au/integrated-report/organisation/about-cpa-australia ; https://www.cpaaustralia.com.au/about-cpa-australia/media/media-releases/cpa-aus-appoints-president-deputy-directors ; https://www.cpaaustralia.com.au/integrated-report/organisation/ceos-report ; https://www.cpaaustralia.com.au/about-cpa-australia/media/media-releases
$card$ where id = 'cpa-australia';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Institute of Chartered Accountants of Sri Lanka (CA Sri Lanka), formed 30 January 1959 by Act of Parliament No. 23 of 1959, based in Colombo. Member of IFAC and CAPA; founder member of SAFA.
LEADERSHIP: Tishan Subasinghe is the 28th President, inducted 20 January 2026 (theme "CONNECT"; said "Accountancy is not a dying profession, but a fast-changing one"). Vice President: Anoji de Silva (Senior Partner, EY Sri Lanka and Maldives). CEO: Lakmali Priyangika (as of November 2025). Previous President: Heshana Kuruppu.
RECENT: Inaugural Sustainability Summit, 26 May 2026, Colombo, on building resilience. Record 617 new Chartered Accountants admitted at the November 2025 convocation.
CAPA LINK: Member of CAPA, IFAC and SAFA; Tishan Subasinghe is a CAPA director for 2025-2027 (CAPA board page).
NOT KNOWN: Current membership size (an undated 7,000 on Wikipedia is not relied on).
SOURCES: https://www.ft.lk/business/Tishan-Subasinghe-takes-the-reins-as-28th-President-of-CA-Sri-Lanka/34-787212 ; https://www.ft.lk/sustainability__environment/CA-Sri-Lanka-unveils-Inaugural-Sustainability-Summit-2026/10519-791834 ; https://www.ft.lk/hr/CA-Sri-Lanka-convocation-sees-record-617-new-Chartered-Accountants/47-784099 ; https://en.wikipedia.org/wiki/Institute_of_Chartered_Accountants_of_Sri_Lanka ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'ca-sri-lanka';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Public Accountants (IPA), founded in 1923, is a company limited by guarantee and a voluntary professional membership and standards body, not a statutory regulator. It supports public practitioners and accountants in business, government and academia; its website reports about 50,000 members and students (undated current claim), with headquarters in Melbourne.
LEADERSHIP (as of 10 Sep 2026): Cheryl Mallett is President and Board Chair, appointed in 2023; Andrew Conway is Group CEO, but the public pages reviewed do not state his start date. Current Deputy President details were not confirmed.
RECENT: September 2026: the CEO addressed AI, digitalisation, sustainability assurance and ethics in global standard-setting. July 2026: a member survey identified technology, AI and workforce pressure as priorities. July 2026: IPA moved to annual CPD periods.
CAPA LINK: Member of CAPA and IFAC; Andrew Conway chairs CAPA’s Member Development Committee for 2024–2027.
NOT KNOWN: The exact date of the 50,000 figure, CEO start date and current Deputy President were not confirmed.
SOURCES: https://www.publicaccountants.org.au/ ; https://www.publicaccountants.org.au/about-ipa/governance/ ; https://www.publicaccountants.org.au/news-advocacy/news/what-members-are-telling-us-about-the-future-of-the-profession/ ; https://www.publicaccountants.org.au/news-advocacy/news/global-standard-setters-must-learn-when-not-to-regulate/ ; https://www.capa-apac.org/about-us/committees/
$card$ where id = 'ipa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Chartered Accountants of Bangladesh (ICAB), established in 1973 under the Bangladesh Chartered Accountants Order 1973 (President’s Order No. 2), is the statutory regulator and membership body for chartered accountants. It is headquartered in Dhaka; a current membership and student total was not confirmed.
LEADERSHIP (as of 30 Jul 2026): President Sabbir Ahmed and Vice-Presidents Neaz Mohammed, Ala Uddin, Asifur Rahman and Mohammad Redwanur Rahman assumed responsibility on 1 July 2026 for the July 2026–June 2027 term. CEO Md. Quamruzzaman was identified in a July 2026 release; his start date was not stated.
RECENT: July 2026: ICAB proposed aligning its syllabus with ICAEW, including AI competencies, while discussing audit-quality and reporting reforms with the Finance Ministry. January 2026: it hosted the SAFA conference on ethical AI and sustainability reporting.
CAPA LINK: Member of CAPA, IFAC and SAFA; President Sabbir Ahmed is a member of CAPA’s Accounting, Reporting and Assurance Coordination Committee.
NOT KNOWN: Current membership/student totals and the CEO’s start date were not confirmed.
SOURCES: https://www.icab.org.bd/publication/news/3/2076/ICAB-Elects-New-President-and-Four-Vice-Presidents-for-2026%E2%80%932027 ; https://www.icab.org.bd/publication/news/3/2101/Reforms-Must-for-Stronger-Financial-Reporting-Ecosystem ; https://www.icab.org.bd/page/safa-int-conf-2026 ; https://www.ifac.org/about-ifac/membership/profile/bangladesh
$card$ where id = 'icab';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Cost and Management Accountants of Bangladesh (ICMAB), created under the Cost and Management Accountants Ordinance 1977 and continued under later legislation, is the statutory professional and membership body for cost and management accountants. It is headquartered in Dhaka; current member and student totals were not confirmed.
LEADERSHIP (as of 15 Jan 2026): Md. Kausar Alam was elected President, Abdul Matin Patwary and S.M. Zahir Uddin Haider Vice-Presidents, and Monjur Md. Shaiful Azam Secretary on 15 January 2026. No separate current chief executive was confirmed.
RECENT: October 2026: ICMAB held a two-day workshop to shape a long-term strategy using member feedback and global benchmarking. May 2026: its President’s Communique addressed sustainability standards, ethical governance and public-sector financial management.
CAPA LINK: Member of CAPA, IFAC and SAFA; Md. Abdur Rahman Khan chairs CAPA’s Public Sector Advisory Group for 2024–2027.
NOT KNOWN: Current membership/student totals and a separate chief executive were not confirmed.
SOURCES: https://icmab.gov.bd/office-bearers-2026/ ; https://icmab.gov.bd/news/141/ ; https://web.icmab.gov.bd/media/assets/uploads/precidents_communique/files/Presidents_Communique_May_2026.pdf ; https://www.ifac.org/about-ifac/membership/members/institute-cost-and-management-accountants-bangladesh ; https://www.capa-apac.org/about-us/groups/
$card$ where id = 'icmab';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Fiji Institute of Chartered Accountants (FICA), successor to the Fiji Institute of Accountants, operates under the Fiji Institute of Chartered Accountants Act 2021. It is both the statutory professional regulator and membership body, with about 1,000 members (May 2026), headquartered in Suva.
LEADERSHIP (as of May 2026): Ravinesh Singh became President and Mohit Raj Vice-President after the 54th AGM in May 2026, succeeding Sharvek Naidu (President 2025-2026). A current CEO/secretary-general and the officers’ exact commencement date were not stated.
RECENT: May 2026: FICA’s Congress drew more than 500 delegates and the Institute announced work to increase iTaukei participation, then about 14% of members. March 2026: its Congress launch highlighted training for AI, digital transformation and sustainability reporting.
CAPA LINK: Member of CAPA and IFAC; no current CAPA board or committee role was confirmed.
NOT KNOWN: Exact membership date beyond May 2026, current CEO and leadership start date were not confirmed.
SOURCES: https://fica.org.fj/institute/council-structure/ ; https://www.fijitimes.com.fj/singh-heads-chartered-accountants/ ; https://www.ifac.org/about-ifac/membership/profile/fiji ; https://www.fijivillage.com/news/fica-targets-stronger-itaukei-presence-in-accounting-profession-6e2b5e/ ; https://www.fbcnews.com.fj/news/fica-strengthens-role-in-national-development-and-global-accounting-landscape/
$card$ where id = 'fica';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Chartered Accountants of India (ICAI), established in 1949 under the Chartered Accountants Act 1949, is the statutory regulator and membership body for chartered accountants. It reported more than 1.5 million members and students (12 Feb 2026) and is headquartered in New Delhi.
LEADERSHIP (as of 12 Feb 2026): Prasanna Kumar D became President and Mangesh Pandurang Kinare Vice-President on 12 February 2026 for 2026–2027. Jai Kumar Batra is Secretary; the reviewed current page does not state his initial appointment date.
RECENT: October 2026: ICAI scheduled an ESG webinar on supply-chain due diligence and social-impact assessment. September 2026: it ran AI-for-Chartered-Accountants and sustainability/BRSR courses. February 2026: it joined the India AI Impact Summit discussion on ethical, human-centred AI.
CAPA LINK: Member of CAPA, IFAC and SAFA; Aniket Sunil Talati is a CAPA director and Mangesh Kinare serves on CAPA’s Member Development Committee.
NOT KNOWN: Separate member and student counts were not stated in the leadership release.
SOURCES: https://www.icai.org/post/icai-elects-new-leadership-for-the-year-2026-27 ; https://www.icai.org/post/secretary ; https://www.icai.org/post/president-message-march2026 ; https://sustainability.icai.org/ ; https://www.capa-apac.org/about-us/board-members/ ; https://www.capa-apac.org/about-us/committees/
$card$ where id = 'icai';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Cost Accountants of India (ICMAI), established in 1959 under the Cost and Works Accountants Act 1959, now the Cost and Management Accountants Act, is the statutory regulator and membership body for cost accountants. It is headquartered in Kolkata; a current dated member/student total was not confirmed.
LEADERSHIP (as of Aug 2026): Chittaranjan Chattopadhyay is President and Manoj Kumar Anand Vice-President for 2026–2027; the exact election date and current Secretary were not confirmed on the pages reviewed.
RECENT: August 2026: ICMAI announced its 2026–2027 leadership. August 2026: it held an “AI and Sustainability” webinar in its Vasudhaiva Kutumbakam series.
CAPA LINK: Member of CAPA, IFAC and SAFA; Manoj Kumar Anand is on CAPA’s Public Sector Advisory Group and Ashish P. Thatte is on its Member Development Committee.
NOT KNOWN: Current dated member/student totals, Secretary and a second independently sourced recent programme were not confirmed.
SOURCES: https://www.icmai.in/ClntAbout/VicePresident ; https://www.icmai.in/ClntAbout/CouncilCommitteee ; https://www.icmai.in/Home/Event/131 ; https://www.capa-apac.org/?action=view&data=WzMxOCwiM2M5ZDIwNTJhMTNkIiwzNTgsInFjNXljanFnaDF3b2NvOHNja2M4NGs0b2s4OGNjZ3N3IiwyMzksMF0&endpoint=view_in_browser&mailpoet_router= ; https://www.capa-apac.org/about-us/groups/ ; https://www.capa-apac.org/about-us/committees/
$card$ where id = 'icmai';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Japanese Institute of Certified Public Accountants (JICPA), founded in 1949 and reorganised as a special corporation under Japan’s Certified Public Accountants Act in 1966, is a mandatory membership and self-regulatory body for CPAs. It represents more than 45,000 members and associates (2025 report) and is headquartered in Tokyo.
LEADERSHIP (as of Jan 2026): Naruhito Minami is Chairman and President; Hisashi Sato is Chief Executive, in that role since 2020. Current Deputy Presidents and Minami’s exact start date were not confirmed in the English pages reviewed.
RECENT: July 2026: JICPA published an overview of its Professional Program in Sustainability. March 2026: it issued an English paper on lifelong development of CPA competence. January 2026: its leadership highlighted AI, digital technology and sustainability assurance.
CAPA LINK: Member of CAPA and IFAC; Chief Executive Hisashi Sato is a CAPA director.
NOT KNOWN: A 2026 dated membership total, Deputy Presidents and exact start date for the Chair were not confirmed.
SOURCES: https://jicpa.or.jp/english/who-we-are/message/ ; https://jicpa.or.jp/english/how-we-operate/organization/ ; https://jicpa.or.jp/english/news/ ; https://jicpa.or.jp/english/what-we-do/annualreports/ ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'jicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Mongolian Institute of Certified Public Accountants (MonICPA), established in 1996, is the professional and regulatory body for CPAs under Mongolia’s Accounting Law and related audit law. It is headquartered in Ulaanbaatar; a current membership/student total was not found.
LEADERSHIP (as of May 2025): Dashchirev Natsagdorj was elected President and Board Chair on 31 January 2025; Baasandorj Oyunbaatar was identified as CEO in May 2025. Current Vice-Presidents were not confirmed.
RECENT: September 2026: KICPA trained 32 MonICPA members on AI, digital transformation, data analytics and sustainability reporting. May 2026: MonICPA’s Leadership Academy drew more than 210 participants and included AI in finance, audit and Copilot workshops.
CAPA LINK: Member of CAPA and IFAC; no current CAPA board or committee role was confirmed.
NOT KNOWN: Current membership/student totals, Vice-Presidents and confirmation that the May 2025 CEO remained in office on 30 October 2026 were not found.
SOURCES: https://www.ifac.org/about-ifac/membership/members/mongolian-institute-certified-public-accountants ; https://www.monicpa.mn/c/576093?content=6551403 ; https://kicpa.org/portal/default/kicpa/main/en_pc.page ; https://www.capa-apac.org/?action=view&data=WzI3MSwiYmQxNzc5MzZlYWVkIiwzNTgsInFjNXljanFnaDF3b2NvOHNja2M4NGs0b2s4OGNjZ3N3IiwyMDUsMF0&endpoint=view_in_browser&mailpoet_router= ; https://www.theaccountant-online.com/news/acca-and-monicpa-renew-partnership/
$card$ where id = 'monicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Chartered Accountants of Nepal (ICAN), established under the Nepal Chartered Accountants Act 1997, is the statutory regulator and membership body for chartered accountants and registered auditors. It reported 9,623 members (FY ended 2024/25) and is headquartered in Lalitpur.
LEADERSHIP (as of 30 Sep 2026): Ananda Raj Sharma Wagle is President, Hem Kumar Kafle Vice-President and Bimal Dangol Executive Director. Their current pages do not state precise commencement dates.
RECENT: September 2026: ICAN and ICAI extended their mutual-recognition agreement to 20 October 2030. July 2026: a new-student orientation reached about 1,226 participants through physical and digital channels. January 2026: ICAN joined Chartered Accountants Worldwide.
CAPA LINK: Member of CAPA (since 1998), IFAC and SAFA; former President Yuddha Raj Oli is a CAPA director for 2025-2027 (confirmed by CAPA staff, 30 Oct 2026).
NOT KNOWN: Exact start dates for the current officers were not confirmed.
SOURCES: https://en.ican.org.np/site/show/the-council ; https://en.ican.org.np/site/show/management-team ; https://en.ican.org.np/site/view/ICAISign ; https://en.ican.org.np/site/view/Orientation ; https://en.ican.org.np/_browsable/file/resouces/81_82.pdf ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'ican';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Chartered Accountants Australia and New Zealand (CA ANZ) was formed on 31 December 2014 by amalgamating the Australian and New Zealand institutes and operates under corporate law and the New Zealand Institute of Chartered Accountants Act 1996. It is a membership and self-regulatory body with more than 140,000 members (20 Jan 2026), with principal offices in Sydney and Wellington.
LEADERSHIP (as of 20 Jan 2026): Sarah Petersen became Board Chair in January 2026; Naomi Walsh is President for 2026, with Matthew Green and Julia Fink as Vice-Presidents for Australia and New Zealand. CEO Ainslie van Onselen’s start date was not stated in the reviewed pages.
RECENT: September 2026: the annual report highlighted talent-pipeline work and investment in AI and sustainability capability. January 2026: the first woman Board Chair was elected with AI, sustainability, ethics and trust as priorities.
CAPA LINK: Member of CAPA and IFAC and associate member of AFA; Peter Vial is a CAPA director and Gill Cox serves on CAPA’s Public Sector Advisory Group.
NOT KNOWN: A more precise FY2026 membership total and CEO start date were not confirmed.
SOURCES: https://www.charteredaccountantsanz.com/news-and-analysis/news/annual-report-2026 ; https://www.charteredaccountantsanz.com/news-and-analysis/news/new-ca-anz-chair-announcement ; https://www.charteredaccountantsanz.com/news-and-analysis/news/2026-ca-anz-office-bearers-announced ; https://www.ifac.org/about-ifac/membership/profile/new-zealand ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'ca-anz';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Institute of Cost and Management Accountants of Pakistan, branded ICMA International, was founded in 1951 and is the statutory regulator and membership body under the Cost and Management Accountants Act 1966. It is headquartered in Karachi; a current dated membership/student total was not confirmed.
LEADERSHIP (as of 1 Oct 2026): Muhammad Yasin is President, Abdul Qayyum Vice-President and Intzar Hussain Secretary; the new office-bearers were announced on 1 October 2026, but the exact commencement date was not stated.
RECENT: October 2026: ICMA Pakistan announced new national office-bearers. August 2026: its Centre of Excellence ran programmes on AI for leaders and IFRS S1/S2 ESG reporting.
CAPA LINK: Member of CAPA, IFAC and SAFA; Zia ul Mustafa serves on CAPA’s Public Sector Advisory Group.
NOT KNOWN: Current membership/student totals and exact commencement dates for the current office-bearers were not confirmed.
SOURCES: https://icmap.com.pk/president.aspx ; https://icmap.com.pk/members_national_council.aspx ; https://www.icmap.com.pk/newsmanagement.aspx/images/pdfs/surveys/downloads/CBEPractice/pdfs/ExamNotice_PDF/national_council.aspx ; https://coe.icmainternational.com/Home/Event ; https://www.ifac.org/about-ifac/membership/profile/pakistan ; https://www.capa-apac.org/about-us/groups/
$card$ where id = 'icmap';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The Philippine Institute of Certified Public Accountants (PICPA), founded in 1929 and accredited by the Professional Regulation Commission on 2 October 1973, is the integrated professional membership organisation for Philippine CPAs, not the statutory regulator. It is headquartered in Mandaluyong City; a current membership total was not confirmed.
LEADERSHIP: Dionisio M. Villeta is the new National President (per CAPA staff, 30 Oct 2026; PICPA's website still lists Gerard Sanvictores, President FY2025–2026). Geraldine Apostol became Executive Director on 1 July 2025.
RECENT: October 2026: PICPA held its second National Tax Convention and opened registration for the November 2026 Annual National Convention on ethical leadership. May 2026: it completed its first voluntary sustainability report, covering July 2025–15 May 2026.
CAPA LINK: Member of CAPA, IFAC and AFA; Gerard Sanvictores is CAPA Deputy President for 2025–2027.
NOT KNOWN: Villeta's start date, current Vice-Presidents, member total and whether Geraldine Apostol remained Executive Director on 30 October.
SOURCES: https://picpa.com.ph/about-picpa-2/ ; https://picpa.com.ph/annual-report/ ; https://picpa.com.ph/category/events/ ; https://picpa.com.ph/ ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'picpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Certified Practising Accountants Papua New Guinea (CPA PNG) traces its origin to the Papua New Guinea Association of Accountants incorporated in 1974 and has statutory professional functions under the Accountants Act 1996. It is both a mandatory membership body for practising CPAs and part of the regulatory framework, headquartered in Port Moresby; current membership size was not confirmed.
LEADERSHIP (per CAPA staff, 30 Oct 2026): President James Popo Gore; Vice-President Pochon Lili; Yuwak is the Executive Director or CEO (exact title not confirmed).
RECENT: April 2026: CPA PNG’s Kokopo Conference included AI, IT-audit and future-finance-workforce sessions. October 2026: its current conference page promoted Mount Hagen as the next continuing-professional-education conference.
CAPA LINK: Member of CAPA (joined 1983, per its About page) and IFAC; former President Richard Kuna is a CAPA director for 2025–2027. Has an MOU with CPA Australia on reciprocal accreditation, and an MOU with IPA (August 2026).
NOT KNOWN: Current membership/student totals, the officers' start dates, and Yuwak's full name and title.
SOURCES: https://cpapng.org.pg/about-us ; https://cpapng.org.pg/cpa-program/continuing-professional-development/conference ; https://www.ifac.org/about-ifac/membership/profile/papua-new-guinea ; https://www.capa-apac.org/about-us/board-members/
$card$ where id = 'cpapng';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Federation of Accountants (IFAC), founded in 1977, is the global federation for the accountancy profession, supporting PAO development, adoption of international standards and a global professional voice. It comprised more than 188 member and associate PAOs in more than 143 jurisdictions (Jan 2026) and is headquartered in New York.
LEADERSHIP (as of 30 Oct 2026): Jean Bouquot became President in November 2024; Taryn Rulton is Deputy President; Lee White became CEO in March 2024.
RECENT: October 2026: IFAC issued global principles for fulfilling careers and a resilient profession. September 2026: it opened virtual registration for the Seoul World Congress of Accountants. June 2026: an IFAC/AICPA-CIMA study reported the early effects of mandatory sustainability requirements.
CAPA LINK: IFAC recognises CAPA, AFA and SAFA as network partners; IFAC itself is not listed as a CAPA member.
NOT KNOWN: The leadership page does not state when Taryn Rulton began as Deputy President.
SOURCES: https://www.ifac.org/who-we-are/leadership ; https://www.ifac.org/who-we-are/leadership/lee-white ; https://www.ifac.org/who-we-are/membership ; https://www.ifac.org/news
$card$ where id = 'ifac';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Accounting Standards Board (IASB), created in 2001 under the IFRS Foundation Constitution, is the independent board that develops IFRS Accounting Standards for capital-market financial reporting. It operates from the IFRS Foundation’s London base; it is a standard-setter, not a membership body or regulator.
LEADERSHIP (as of 1 Oct 2026): Sam Woods became Chair on 1 October 2026 for a five-year term; Linda Mezon-Hutter is Vice-Chair and Riana Wiesner is Executive Technical Director. The reviewed pages do not state the latter two officers’ current-term start dates.
RECENT: October 2026: the IASB’s active programme included IFRS 20 implementation and ongoing standard-setting. August 2026: Sam Woods was appointed Chair. October 2026: open consultations included Risk Mitigation Accounting, due 30 November 2026, and the IFRS 9 hedge-accounting post-implementation review, due 26 January 2027.
CAPA LINK: not found.
NOT KNOWN: Current-term start dates for the Vice-Chair and Executive Technical Director were not confirmed.
SOURCES: https://www.ifrs.org/news-and-events/news/2026/08/steven-maijoor-chair-trustees-sam-woods-chair-iasb/ ; https://www.ifrs.org/news-and-events/updates/nss-newsletter/national-standard-setters-newsletter-october-2026/ ; https://www.ifrs.org/projects/
$card$ where id = 'iasb';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Sustainability Standards Board (ISSB), established in November 2021 under the IFRS Foundation Constitution, develops the global baseline of IFRS Sustainability Disclosure Standards for investors. It uses a multi-location model with offices including Frankfurt, London, Montreal, Tokyo, Beijing and San Francisco; it is not a membership body or regulator.
LEADERSHIP (as of 30 Oct 2026): Emmanuel Faber began his second term as Chair on 1 January 2025, ending 31 December 2027; Sue Lloyd began a second four-year term as Vice-Chair on 1 March 2026. Bryan Esterly is Executive Technical Director; his start date was not confirmed.
RECENT: October 2026: ISSB issued a nature-related-disclosures exposure draft, open until 19 February 2027. September 2026: it renamed its human-capital project “Workforce-related Disclosures” and continued IFRS S1/S2 implementation support.
CAPA LINK: not found.
NOT KNOWN: The Executive Technical Director’s start date was not confirmed; Jingdong Hua’s Vice-Chair term ended 30 September 2026.
SOURCES: https://www.ifrs.org/groups/international-sustainability-standards-board/issb-frequently-asked-questions/ ; https://www.ifrs.org/news-and-events/news/2023/12/issb-at-cop-28-emmanuel-faber-to-continue-serving-as-issb-chair-2027/ ; https://www.ifrs.org/news-and-events/news/2025/09/updates-inaugural-issb-membership/ ; https://www.ifrs.org/news-and-events/news/2026/10/issb-consults-on-proposals-nature-related-disclosures/ ; https://www.ifrs.org/news-and-events/updates/issb/2026/issb-update-september-2026/
$card$ where id = 'issb';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Ethics Standards Board for Accountants (IESBA) is the independent global standard-setter for ethics and independence standards, including the International Code of Ethics, within the International Foundation for Ethics and Audit. It is not a membership body or regulator and is supported from New York.
LEADERSHIP (as of 30 Oct 2026): Gabriela Figueiredo Dias has chaired IESBA since January 2022; her current term runs from 1 January 2025 to 31 December 2026. Channa Wijesinghe is Vice-Chair; the board page does not state his appointment date.
RECENT: September 2026: IESBA published its 2026 Handbook and implementation Q&As for sustainability ethics and independence standards. July 2026: it issued guidance on ethical considerations for emerging technologies. October 2026: firm culture and governance remained an active project; no consultation was shown open on 30 October.
CAPA LINK: not found.
NOT KNOWN: A named current senior staff director and the Vice-Chair’s start date were not confirmed.
SOURCES: https://www.ethicsboard.org/about-iesba/iesba-board ; https://www.ethicsboard.org/news-events/2024-11/gabriela-figueiredo-dias-reappointed-new-term-chair-global-ethics-board ; https://www.ethicsboard.org/news ; https://www.ethicsboard.org/consultations-projects
$card$ where id = 'iesba';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Public Sector Accounting Standards Board (IPSASB) is an independent international board that develops accrual-based IPSAS and public-sector sustainability reporting standards under IFAC-supported governance and Public Interest Committee oversight. It is a standard-setter, not a membership body or regulator, supported from New York.
LEADERSHIP (as of 30 Oct 2026): Thomas Müller-Marqués Berger is Chair, Claudia Beier Deputy Chair and Ross Smith Program and Technical Director. Their public pages did not state precise commencement dates.
RECENT: September 2026: IPSASB added future projects after its work-program consultation and advanced a second climate-related public-policy disclosure standard. January 2026: it issued IPSASB SRS 1 Climate-related Disclosures. October 2026: no exposure draft was shown open on 30 October.
CAPA LINK: not found.
NOT KNOWN: Exact leadership start dates were not confirmed.
SOURCES: https://www.ipsasb.org/about-ipsasb ; https://www.ipsasb.org/about-ipsasb/ipsasb-staff ; https://www.ipsasb.org/news-events/2026-09/ipsasb-enews-september-2026 ; https://www.ipsasb.org/consultations-projects/ipsasb-consultations ; https://www.ipsasb.org/focus-areas/sustainability-reporting
$card$ where id = 'ipsasb';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The International Auditing and Assurance Standards Board (IAASB) is the independent global standard-setter for auditing, assurance, review, quality-management and related-services standards within the International Foundation for Ethics and Audit. It is not a membership body or regulator and is supported from New York.
LEADERSHIP (as of 30 Oct 2026): Tom Seidenstein is Chair and co-CEO of the Foundation; Willie Botha is Program and Senior Director. The current Vice-Chair and exact start dates were not shown on the reviewed page.
RECENT: July 2026: IAASB opened proposed revisions to ISA 330, ISA 500 and ISA 520, with comments due 15 December 2026. July–October 2026: it consulted on maintenance of the ISA for Less Complex Entities; that consultation closed 29 October. October 2026: its work programme included AI-enabled audit tools and sustainability assurance.
CAPA LINK: not found.
NOT KNOWN: Current Vice-Chair and leadership start dates were not confirmed.
SOURCES: https://www.iaasb.org/iaasb/about-iaasb ; https://www.iaasb.org/consultations-projects ; https://www.iaasb.org/news
$card$ where id = 'iaasb';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The ASEAN Federation of Accountants (AFA), established in 1977, is the regional federation and collective voice of recognised PAOs in the ten ASEAN member states. It is an ASEAN-accredited civil-society organisation and IFAC Network Partner, with 10 primary and 11 associate members (2024 report), and a permanent secretariat in Jakarta.
LEADERSHIP (as of 30 Oct 2026): Ardan Adiperdana took over as President on 30 October 2025 for the 2025–2027 leadership period; Siti Khadijah Moksin is Deputy President and Koh Wee Kwang Treasurer. Aucky Pratama is Executive Director; his start date was not confirmed.
RECENT: May 2026: the 142nd Council meeting advanced the 2024–2027 strategic plan and three-tier PAO-advancement programme. October 2025: AFA announced its 2025–2027 leadership and renewed focus on professional capacity, technology and sustainability.
CAPA LINK: IFAC Network Partner; public CAPA membership pages do not list AFA as a CAPA member.
NOT KNOWN: Executive Director start date and an official 2026 annual report were not found.
SOURCES: https://afa-accountants.org/files/Annual%20Report%202024.pdf ; https://web.iaiglobal.or.id/Berita-IAI/detail/iai_pimpin_asean_federation_of_accountants_tegaskan_peran_indonesia_di_kancah_regional ; https://www.ifac.org/who-we-are/aucky-pratama
$card$ where id = 'afa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: The South Asian Federation of Accountants (SAFA), established in 1984, is the regional federation of professional accountancy bodies in the SAARC region, promoting cooperation in education, training, technical and ethical standards. It comprises 11 PAOs across seven countries and represents more than 500,000 affiliated members (1 Jan 2026); its secretariat arrangements are not clearly stated on the current site.
LEADERSHIP (as of 1 Jan 2026): Mohammed Humayun Kabir became President and Prabin Kumar Jha Vice-President for 12 months from 1 January 2026. A current secretary-general or executive director was not identified.
RECENT: January 2026: SAFA held an international conference on ethical AI and sustainability reporting. September 2026: it scheduled an online programme on forensic accounting and investigation standards.
CAPA LINK: IFAC Network Partner; SAFA is not listed as a CAPA member.
NOT KNOWN: Headquarters, current chief executive/secretary-general and exact date of the website/LMS launch were not confirmed.
SOURCES: https://www.esafa.org/ ; https://www.esafa.org/Documents/SAFA_Press_Release_2026.pdf ; https://www.icab.org.bd/page/safa-int-conf-2026 ; https://www.thedailystar.net/business/organisation-news/news/humayun-kabir-becomes-president-safa-4070881
$card$ where id = 'safa';

-- ---- Members with only staff-provided facts so far (30 Oct 2026) ----

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Hong Kong Institute of Certified Public Accountants (HKICPA), Hong Kong's accountancy body. Rejoined CAPA's membership by 2026 (CAPA members page).
LEADERSHIP: Chief Executive and Registrar: Arthur Lee Kin (per CAPA staff, 30 Oct 2026).
RECENT: not researched yet.
CAPA LINK: Member of CAPA.
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'hkicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Chartered Accountants Maldives (CA Maldives). CAPA approved its Member application in September 2026.
LEADERSHIP: Ilyas Haneef leads it; whether as CEO or President is not confirmed (per CAPA staff, 30 Oct 2026).
RECENT: not researched yet.
CAPA LINK: Member of CAPA (approved September 2026).
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'ca-maldives';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Chinese Institute of Certified Public Accountants (CICPA), China's national professional accountancy organisation.
LEADERSHIP: Not recorded.
RECENT: not researched yet.
CAPA LINK: Member of CAPA. Its CAPA board seat is being refilled: Wan Wenxiang has left the board and CICPA is putting forward a new director (per CAPA staff, 30 Oct 2026).
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'cicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Korean Institute of Certified Public Accountants (KICPA), Korea's national professional accountancy organisation.
LEADERSHIP: Not recorded.
RECENT: not researched yet.
CAPA LINK: Member of CAPA. CAPA President Jhun Yong-Sok (since 3 December 2025) and CAPA director Kim Dong-Chul both come from KICPA (per CAPA staff, 30 Oct 2026). In September 2026 KICPA trained MonICPA members on AI and sustainability reporting.
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'kicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Association of Accounting Technicians of Sri Lanka (AAT Sri Lanka).
LEADERSHIP: President: Dr Chamara Bandara (per CAPA staff, 30 Oct 2026).
RECENT: not researched yet.
CAPA LINK: Member of CAPA.
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'aatsl';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Institute of Certified Management Accountants of Sri Lanka (CMA Sri Lanka).
LEADERSHIP: President: Prof Lakshman Watawala (per CAPA staff, 30 Oct 2026).
RECENT: not researched yet.
CAPA LINK: Member of CAPA.
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'cmasl';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: American Institute of CPAs (AICPA), part of AICPA & CIMA (Association of International Certified Professional Accountants).
LEADERSHIP: Not recorded.
RECENT: not researched yet.
CAPA LINK: Member of CAPA. James (Jim) Knafo of AICPA & CIMA is a CAPA director for 2025-2027 (per CAPA staff, 30 Oct 2026).
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'aicpa';

update paos set profile_checked = date '2026-10-30', profile = $card$
WHO: Vietnam Association of Certified Public Accountants (VACPA).
LEADERSHIP: Not recorded.
RECENT: not researched yet.
CAPA LINK: Member of CAPA. Dr Tran Khanh Lam of VACPA chairs CAPA's Governance and Audit Committee for 2024-2027 (not a board member).
NOT KNOWN: Everything else - this organisation has not been researched from public sources yet.
SOURCES: CAPA staff, 30 Oct 2026 ; https://www.capa-apac.org/about-us/members/
$card$ where id = 'vacpa';

notify pgrst, 'reload schema';
