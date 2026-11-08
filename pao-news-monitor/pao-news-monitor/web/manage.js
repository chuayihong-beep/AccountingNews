/* Members (admins), People (admins) and Import (team + admins).
 * The database enforces the same rules, so hiding buttons here is only for tidiness.
 */
(() => {
  "use strict";
  const A = window.PAOApp;
  if (!A) return;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = A.esc;
  const XLSX_JS = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
  const GROUPS = ["Member", "Associate", "Affiliate", "Stakeholder", "Regional network"];
  const CSV_COLS = ["id", "group", "jurisdiction", "name", "abbr", "website", "news_url", "feed_url", "search_terms",
    "news_locale", "link_selector", "active", "notes", "facebook", "leadership_url", "contact_url"];

  const isAdmin = () => A.state.role === "admin";
  const can = (p) => A.can(p);
  const canEdit = () => can("add_items");
  const seesAdminTab = () => isAdmin() || can("manage_members") || can("manage_mailing_list");
  const me = () => A.state.user?.email || "";

  function loadScript(src) {
    if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve();
    return new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => fail(new Error("Could not load " + src));
      document.head.appendChild(s);
    });
  }
  const friendly = (e) => {
    const m = e?.message || String(e);
    if (/column|schema cache|function .* does not exist|Could not find/i.test(m))
      return m + " - the database needs updating: paste supabase/update-2.sql into Supabase > SQL Editor and Run.";
    if (/row-level security|permission denied/i.test(m)) return "You don't have permission for this (" + m + ")";
    return m;
  };
  document.addEventListener("click", (e) => {
    const c = e.target.closest("[data-close]");
    if (c) c.closest("dialog").close();
  });

  // show/hide header buttons once the role is known
  new MutationObserver(() => {
    document.querySelectorAll(".admin-only").forEach((el) => (el.hidden = !seesAdminTab()));
    document.querySelectorAll(".edit-only").forEach((el) => (el.hidden = !canEdit()));
  }).observe(document.body, { attributes: true, attributeFilter: ["data-role"] });
  document.querySelectorAll(".admin-only, .edit-only").forEach((el) => (el.hidden = true));

  // ================= Members =================
  let members = [];
  async function loadMembers() {
    if (A.DEMO) { members = A.state.paos.filter((p) => p.id !== "_unmatched_email"); return; }
    const { data, error } = await A.db.from("paos").select("*").neq("id", "_unmatched_email").order("sort_order");
    if (error) throw error;
    members = data;
  }
  function renderMembers() {
    const rows = [...members].sort((a, b) =>
      (GROUPS.indexOf(a.grp) - GROUPS.indexOf(b.grp)) || ((a.sort_order ?? 0) - (b.sort_order ?? 0)));
    $("#members-table").innerHTML = `<thead><tr><th>Abbr</th><th>Name</th><th>Group</th><th>Country</th><th>Website</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${rows.map((p) => `<tr class="${p.active === false ? "inactive" : ""}">
        <td><b>${esc(p.abbr || "")}</b></td><td>${esc(p.name)}</td><td>${esc(p.grp || "")}</td><td>${esc(p.jurisdiction || "")}</td>
        <td>${p.website ? `<a href="${esc(p.website)}" target="_blank" rel="noopener">${esc(p.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "").slice(0, 40))}</a>` : ""}</td>
        <td>${p.active === false ? "Deactivated" : "Active"}</td>
        <td class="row-tools"><button class="link small" data-edit="${esc(p.id)}" type="button">Edit</button>
          <button class="link small" data-toggle="${esc(p.id)}" type="button">${p.active === false ? "Reactivate" : "Deactivate"}</button></td>
      </tr>`).join("")}</tbody>`;
  }
  async function showMembers() {
    $("#members-table").innerHTML = "<tbody><tr><td>Loading…</td></tr></tbody>";
    try { await loadMembers(); renderMembers(); } catch (e) { $("#members-table").innerHTML = `<tbody><tr><td class="error-box">${esc(friendly(e))}</td></tr></tbody>`; }
  }

  // ================= Admin tab =================
  function openAdmin() {
    $("#admin-view").hidden = false;
    $("#status-view").hidden = true;
    $("#brief-view").hidden = true;
    $("#ask-view").hidden = true;
    document.querySelector(".filters").hidden = true;
    document.querySelector(".layout").hidden = true;
    window.scrollTo(0, 0);
    $("#panel-people").hidden = $("#panel-roles").hidden = !isAdmin();
    $("#panel-mailing").hidden = !can("manage_mailing_list");
    $("#panel-members").hidden = !can("manage_members");
    $("#usage-panel").hidden = !isAdmin();
    if (isAdmin()) A.loadUsage();
    if (isAdmin()) { showRoles().then(showPeople); }
    if (can("manage_mailing_list")) showMailingList();
    if (can("manage_members")) showMembers();
    showPatchNotes();
  }
  // Patch notes: dates and titles from CHANGES.md (built into patch-notes.json by tests/make_patch_notes.py)
  let patchNotes = null, patchAll = false;
  async function showPatchNotes() {
    const list = $("#patch-list"), more = $("#patch-more");
    if (!patchNotes) {
      try { const r = await fetch("patch-notes.json", { cache: "no-cache" }); patchNotes = r.ok ? await r.json() : []; }
      catch (e) { patchNotes = []; }
    }
    if (!patchNotes.length) { list.innerHTML = '<li class="muted small">No patch notes found.</li>'; more.hidden = true; return; }
    const shown = patchAll ? patchNotes : patchNotes.slice(0, 10);
    list.innerHTML = shown.map((n) => {
      const d = new Date(n.date + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
      return `<li><time datetime="${esc(n.date)}">${esc(d)}</time><span>${esc(n.title)}</span></li>`;
    }).join("");
    more.hidden = patchNotes.length <= 10;
    more.textContent = patchAll ? "Show fewer" : `Show all ${patchNotes.length}`;
  }
  $("#patch-more").addEventListener("click", () => { patchAll = !patchAll; showPatchNotes(); });

  function closeAdmin() {
    $("#admin-view").hidden = true;
    document.querySelector(".filters").hidden = false;
    document.querySelector(".layout").hidden = false;
    document.querySelector("#search-wrap").hidden = false;
  }
  $("#admin-btn").addEventListener("click", openAdmin);
  $("#admin-back").addEventListener("click", closeAdmin);
  const slug = (s) => (s || "").toLowerCase().normalize("NFKD").replace(/[^\w]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 30);

  let editing = null;  // member row being edited, or null for a new one
  function openMemberForm(p) {
    editing = p || null;
    const f = $("#member-form");
    f.reset();
    $("#member-form-title").textContent = p ? `Edit ${p.abbr || p.name}` : "Add member";
    $("#member-delete").hidden = !p;
    $("#member-form-msg").textContent = p ? `id: ${p.id}${p.updated_by ? ` · last changed by ${p.updated_by}` : ""}` : "";
    for (const el of f.elements) {
      if (!el.name || el.type === "submit") continue;
      if (el.type === "checkbox") el.checked = p ? p[el.name] !== false : true;
      else el.value = p ? (p[el.name] ?? "") : (el.name === "grp" ? "Member" : "");
    }
    $("#member-dialog").showModal();
  }
  // suggest Google News searches for a new member
  $("#member-form").addEventListener("input", (e) => {
    if (editing || !["name", "abbr"].includes(e.target.name)) return;
    const f = $("#member-form"), st = f.elements.search_terms;
    if (st.dataset.touched) return;
    const n = f.elements.name.value.trim(), a = f.elements.abbr.value.trim();
    st.value = [n && `"${n}"`, a && a !== n && `"${a}"`].filter(Boolean).join("|");
  });
  $("#member-form").elements.search_terms.addEventListener("input", (e) => (e.target.dataset.touched = "1"));

  $("#member-dialog").addEventListener("close", async () => {
    const action = $("#member-dialog").returnValue;
    const f = $("#member-form");
    if (action === "delete" && editing) return deleteMember(editing);
    if (action !== "save") return;
    const v = {};
    for (const el of f.elements) {
      if (!el.name || el.type === "submit") continue;
      v[el.name] = el.type === "checkbox" ? el.checked : (el.value.trim() || null);
    }
    v.lang = (v.news_locale || "en").split("-")[0].toLowerCase();
    v.updated_by = me(); v.updated_at = new Date().toISOString(); v.config_seeded = true;
    try {
      if (editing) {
        if (!A.DEMO) { const { error } = await A.db.from("paos").update(v).eq("id", editing.id); if (error) throw error; }
        Object.assign(editing, v);
      } else {
        let id = slug(v.abbr || v.name) || "pao";
        while (members.some((m) => m.id === id)) id += "-2";
        const row = { id, ...v, sort_order: Math.max(0, ...members.map((m) => m.sort_order || 0)) + 1 };
        if (!A.DEMO) { const { error } = await A.db.from("paos").insert(row); if (error) throw error; }
        members.push(row);
      }
      renderMembers();
      A.toast(editing ? "Saved. The next collection uses the new settings." : "Added. It will be collected from the next run (first scan is hidden).");
      if (A.DEMO) syncDemo(); else A.reload();
    } catch (e) { A.toast("Couldn't save: " + friendly(e), true); }
  });

  async function toggleMember(id) {
    const p = members.find((m) => m.id === id);
    const active = p.active === false;
    if (!active && !confirm(`Deactivate ${p.abbr || p.name}? It will be hidden and no longer collected. Past items are kept; you can reactivate any time.`)) return;
    try {
      if (!A.DEMO) {
        const { error } = await A.db.from("paos").update({ active, updated_by: me(), updated_at: new Date().toISOString() }).eq("id", id);
        if (error) throw error;
      }
      p.active = active; renderMembers();
      A.toast(active ? "Reactivated" : "Deactivated");
      if (A.DEMO) syncDemo(); else A.reload();
    } catch (e) { A.toast("Couldn't change: " + friendly(e), true); }
  }

  async function deleteMember(p) {
    const typed = prompt(`This permanently deletes ${p.name} AND every item collected for it, including your team's tags. ` +
      `It can't be undone. (To just hide it, use Deactivate instead.)\n\nType ${p.abbr || p.id} to confirm:`);
    if (typed === null) return;
    if (typed.trim().toLowerCase() !== (p.abbr || p.id).toLowerCase()) return A.toast("Not deleted - the text didn't match", true);
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("delete_pao", { target_id: p.id }); if (error) throw error; }
      members = members.filter((m) => m.id !== p.id);
      renderMembers(); A.toast("Deleted");
      if (A.DEMO) syncDemo(); else A.reload();
    } catch (e) { A.toast("Couldn't delete: " + friendly(e), true); }
  }

  function syncDemo() {  // demo mode: reflect changes on the page without a database
    A.state.paos = members.filter((m) => m.active !== false).concat(A.state.paos.filter((p) => p.id === "_unmatched_email"));
    A.render();
  }

  function downloadMembersCsv() {
    const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [CSV_COLS.join(",")].concat(members.map((p) => CSV_COLS.map((c) =>
      cell(c === "group" ? p.grp : c === "active" ? (p.active === false ? "no" : "yes") : p[c])).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = `members-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
  }

  $("#member-add").addEventListener("click", () => openMemberForm(null));
  $("#members-csv").addEventListener("click", downloadMembersCsv);
  $("#members-table").addEventListener("click", (e) => {
    const ed = e.target.closest("[data-edit]");
    if (ed) return openMemberForm(members.find((m) => m.id === ed.dataset.edit));
    const tg = e.target.closest("[data-toggle]");
    if (tg) return toggleMember(tg.dataset.toggle);
  });

  // ================= People =================
  let ROLES = { admin: "Admin", team: "Team", viewer: "Viewer", removed: "No access" };
  let roleRows = [], rolePerms = {}, roleUse = {};
  const PERM_LABEL = {
    tag_items: ["Tag items", "Regional / country / PAO-specific / not relevant, category, notes, type"],
    add_items: ["Add items", "+ Add item, Import, screenshots"],
    remove_items: ["Remove items", "Hide junk items everywhere (can be restored)"],
    edit_briefs: ["Edit briefs", "Change the brief text"],
    approve_briefs: ["Approve briefs", "Approve a brief or move it back to draft"],
    send_briefs: ["Send briefs", "Email approved briefs to the mailing list"],
    manage_mailing_list: ["Mailing list", "Add, pause, remove recipients"],
    ask_ai: ["Ask AI", "Ask the AI real-time questions about a PAO"],
    manage_members: ["Members", "Add, edit, deactivate PAOs"],
  };
  let demoRoles = [{ name: "admin", label: "Admin", builtin: true }, { name: "team", label: "Team", builtin: true }, { name: "viewer", label: "Viewer", builtin: true }];
  let demoPerms = [{ role: "team", permission: "tag_items" }, { role: "team", permission: "add_items" }, { role: "team", permission: "edit_briefs" }];
  async function loadRoles() {
    let rows, perms;
    if (A.DEMO) { rows = demoRoles; perms = demoPerms; }
    else {
      const r = await A.db.from("roles").select("*").order("created_at");
      if (r.error) {   // before update-8: fixed roles
        rows = demoRoles; perms = demoPerms; rolesReady = false;
      } else {
        const p = await A.db.from("role_permissions").select("*");
        if (p.error) throw p.error;
        rows = r.data; perms = p.data; rolesReady = true;
      }
    }
    roleRows = rows;
    rolePerms = {};
    for (const x of perms) (rolePerms[x.role] ||= new Set()).add(x.permission);
    ROLES = Object.fromEntries(rows.map((x) => [x.name, x.label]).concat([["removed", "No access"]]));
    $("#person-role").innerHTML = rows.filter((x) => x.name !== "admin").concat(rows.filter((x) => x.name === "admin"))
      .map((x) => `<option value="${esc(x.name)}">${esc(x.label)}</option>`).join("");
  }
  let rolesReady = true;
  async function showRoles() {
    $("#roles-table").innerHTML = "<tbody><tr><td>Loading…</td></tr></tbody>";
    try { await loadRoles(); } catch (e) { $("#roles-table").innerHTML = `<tbody><tr><td class="error-box">${esc(friendly(e))}</td></tr></tbody>`; return; }
    const perms = Object.keys(PERM_LABEL);
    $("#roles-table").innerHTML = (rolesReady ? "" : `<caption class="warn-text small">Run supabase/update-8.sql to create roles and change permissions.</caption>`) +
      `<thead><tr><th>Role</th>${perms.map((p) => `<th title="${esc(PERM_LABEL[p][1])}">${esc(PERM_LABEL[p][0])}</th>`).join("")}<th>People</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>` +
      roleRows.map((r) => {
        const isAdm = r.name === "admin";
        return `<tr><td><b>${esc(r.label)}</b>${r.builtin ? "" : " <span class='muted small'>(custom)</span>"}</td>
          ${perms.map((p) => `<td class="perm-cell"><input type="checkbox" data-perm="${p}" data-role="${esc(r.name)}"
            ${isAdm || rolePerms[r.name]?.has(p) ? "checked" : ""} ${isAdm || !rolesReady ? "disabled" : ""} aria-label="${esc(r.label)}: ${esc(PERM_LABEL[p][0])}"></td>`).join("")}
          <td class="muted small">${roleUse[r.name] || 0}</td>
          <td>${isAdm ? "<span class='muted small'>always everything</span>" : `<button class="link small" data-role-delete="${esc(r.name)}" type="button">Delete</button>`}</td></tr>`;
      }).join("") + "</tbody>";
  }
  $("#roles-table").addEventListener("change", async (e) => {
    const cb = e.target.closest("[data-perm]");
    if (!cb) return;
    const role = cb.dataset.role, perm = cb.dataset.perm, on = cb.checked;
    try {
      if (A.DEMO) { if (on) demoPerms.push({ role, permission: perm }); else demoPerms = demoPerms.filter((x) => !(x.role === role && x.permission === perm)); }
      else { const { error } = await A.db.rpc("set_role_permission", { role_name: role, perm, granted: on }); if (error) throw error; }
      (rolePerms[role] ||= new Set())[on ? "add" : "delete"](perm);
      A.toast(`${ROLES[role]}: "${PERM_LABEL[perm][0]}" ${on ? "allowed" : "removed"}`);
    } catch (err) { cb.checked = !on; A.toast("Couldn't change: " + friendly(err), true); }
  });
  $("#roles-table").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-role-delete]");
    if (!b) return;
    const role = b.dataset.roleDelete;
    if (!confirm(`Delete the role "${ROLES[role]}"? (Only possible when nobody has it.)`)) return;
    try {
      if (A.DEMO) { if (roleUse[role]) throw new Error("Some people still have this role - give them another role first"); demoRoles = demoRoles.filter((x) => x.name !== role); }
      else { const { error } = await A.db.rpc("delete_role", { role_name: role }); if (error) throw error; }
      A.toast("Role deleted"); await showRoles(); showPeople();
    } catch (err) { A.toast("Couldn't delete: " + friendly(err), true); }
  });
  $("#role-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const label = e.target.elements.label.value.trim();
    const name = label.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 30);
    if (name.length < 2 || name === "removed") return A.toast("Please use a different name", true);
    try {
      if (A.DEMO) { if (demoRoles.some((x) => x.name === name)) throw new Error("A role with that name already exists"); demoRoles.push({ name, label, builtin: false }); }
      else { const { error } = await A.db.rpc("create_role", { role_name: name, role_label: label }); if (error) throw error; }
      e.target.reset(); A.toast(`Created "${label}" - now tick what it may do`); await showRoles(); showPeople();
    } catch (err) { A.toast("Couldn't create: " + friendly(err), true); }
  });
  let demoPeople = [
    { email: "demo@example.org", role: "admin", signed_up: true, last_sign_in_at: new Date().toISOString() },
    { email: "colleague@example.org", role: "team", signed_up: true },
    { email: "boss@example.org", role: "viewer", signed_up: false },
  ];
  async function showPeople() {
    $("#people-table").innerHTML = "<tbody><tr><td>Loading…</td></tr></tbody>";
    try {
      const people = A.DEMO ? demoPeople
        : await (async () => { const { data, error } = await A.db.rpc("list_people"); if (error) throw error; return data; })();
      roleUse = {};
      for (const p of people) roleUse[p.role] = (roleUse[p.role] || 0) + 1;
      document.querySelectorAll("#roles-table tbody tr").forEach((tr, i) => { const r = roleRows[i]; if (r && tr.cells[tr.cells.length - 2]) tr.cells[tr.cells.length - 2].textContent = roleUse[r.name] || 0; });
      $("#people-table").innerHTML = `<thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Role last changed</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>${people.map((p) => `<tr class="${p.role === "removed" ? "inactive" : ""}">
          <td>${esc(p.email)}${p.email === me() ? " <span class='muted small'>(you)</span>" : ""}</td>
          <td><select data-role-for="${esc(p.email)}" aria-label="Role for ${esc(p.email)}">${Object.entries(ROLES).map(([r, label]) => `<option value="${r}"${p.role === r ? " selected" : ""}>${label}</option>`).join("")}</select></td>
          <td class="muted small">${p.role === "removed" ? "Access removed" : p.signed_up === false ? "Not signed up yet" : p.last_sign_in_at ? "Last signed in " + new Date(p.last_sign_in_at).toLocaleDateString() : "Signed up"}</td>
          <td class="muted small">${p.role_updated_by ? `${esc(p.role_updated_by)}, ${new Date(p.role_updated_at).toLocaleDateString()}` : ""}</td>
          <td>${p.email === me() ? "" : `<button class="link small danger" type="button" data-person-delete="${esc(p.email)}" data-signed-up="${p.signed_up === false ? "0" : "1"}">Delete</button>`}</td>
        </tr>`).join("")}</tbody>`;
    } catch (e) { $("#people-table").innerHTML = `<tbody><tr><td class="error-box">${esc(friendly(e))}</td></tr></tbody>`; }
  }
  // Delete a row (update-16.sql). Someone who already signed up keeps their Supabase login, so they stay
  // listed as "Access removed" (still no access) until the login is deleted in Supabase > Authentication > Users.
  async function deletePerson(email) {
    if (A.DEMO) {
      const p = demoPeople.find((x) => x.email === email);
      if (p && p.role === "admin" && !demoPeople.some((x) => x.role === "admin" && x.email !== email)) throw new Error("There must always be at least one admin");
      demoPeople = demoPeople.filter((x) => x.email !== email || x.signed_up);
      if (p && p.signed_up) p.role = "removed";
      return;
    }
    const { error } = await A.db.rpc("delete_person", { target_email: email });
    if (error) {
      if (/delete_person|function .* does not exist|Could not find/i.test(error.message)) throw new Error("Deleting needs a quick database update: paste supabase/update-16.sql into Supabase > SQL Editor and Run.");
      throw error;
    }
  }
  $("#people-table").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-person-delete]");
    if (!b) return;
    const email = b.dataset.personDelete, signedUp = b.dataset.signedUp === "1";
    const msg = signedUp
      ? `Delete ${email}?\n\nThey have already signed up, so their login still exists: they'll stay listed as "Access removed" (they can't see anything). To remove the login completely, delete it in Supabase > Authentication > Users.`
      : `Delete ${email} from the list? They haven't signed up, so this removes them completely. You can add them again any time.`;
    if (!confirm(msg)) return;
    try {
      await deletePerson(email);
      A.toast(`${email} deleted`);
      showPeople();
    } catch (err) { A.toast("Couldn't delete: " + friendly(err), true); }
  });

  async function setRole(email, role) {
    if (A.DEMO) {
      const p = demoPeople.find((x) => x.email === email);
      if (p) p.role = role; else demoPeople.push({ email, role, signed_up: false });
      if (role !== "admin" && !demoPeople.some((x) => x.role === "admin" && x.email !== email)) { if (p) p.role = "admin"; throw new Error("There must always be at least one admin"); }
      return;
    }
    const { error } = await A.db.rpc("set_role", { target_email: email, new_role: role });
    if (error) throw error;
  }
  $("#person-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, email = f.elements.email.value.trim().toLowerCase(), role = f.elements.role.value;
    try {
      await setRole(email, role);
      A.toast(`${email} can now sign up as ${ROLES[role]}: ask them to open this page and click "First time here".`);
      f.reset(); showPeople();
    } catch (err) { A.toast("Couldn't add: " + friendly(err), true); }
  });
  $("#people-table").addEventListener("change", async (e) => {
    const sel = e.target.closest("[data-role-for]");
    if (!sel) return;
    const email = sel.dataset.roleFor, role = sel.value;
    if (email === me() && role !== "admin" && !confirm("Remove your own admin rights? You won't be able to use this Admin tab afterwards.")) {
      sel.value = "admin"; return;
    }
    if (role === "removed" && !confirm(`Remove ${email}'s access? They won't be able to see anything. You can give access back any time.`)) {
      showPeople(); return;
    }
    try {
      await setRole(email, role);
      A.toast(`${email}: ${ROLES[role]}`);
      if (email === me()) { setTimeout(() => location.reload(), 800); }   // reload with the new permissions
      showPeople();
    } catch (err) { A.toast("Couldn't change role: " + friendly(err), true); showPeople(); }
  });

  // ================= Mailing list =================
  let mailing = [];
  const EMAIL_RX = /[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  async function loadMailingList() {
    if (A.DEMO) { mailing = A._demoMailing ||= [{ email: "boss@capa-apac.org", name: "Boss", organisation: "CAPA", active: true }]; return mailing; }
    const { data, error } = await A.db.from("mailing_list").select("*").order("organisation", { nullsFirst: true }).order("email");
    if (error) throw error;
    mailing = data; return mailing;
  }
  async function showMailingList() {
    $("#ml-table").innerHTML = "<tbody><tr><td>Loading…</td></tr></tbody>";
    try {
      await loadMailingList();
      const on = mailing.filter((m) => m.active).length;
      $("#ml-count").textContent = `${on} receiving${mailing.length > on ? `, ${mailing.length - on} paused` : ""}`;
      $("#ml-table").innerHTML = mailing.length ? `<thead><tr><th>Name</th><th>Email</th><th>Organisation</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${mailing.map((m) => `
        <tr class="${m.active ? "" : "inactive"}"><td>${esc(m.name || "")}</td><td>${esc(m.email)}</td><td>${esc(m.organisation || "")}</td>
        <td>${m.active ? "Receiving" : "Paused"}</td>
        <td class="row-tools"><button class="link small" data-ml-toggle="${esc(m.email)}" type="button">${m.active ? "Pause" : "Resume"}</button>
          <button class="link small" data-ml-remove="${esc(m.email)}" type="button">Remove</button></td></tr>`).join("")}</tbody>`
        : "<tbody><tr><td class='muted'>Nobody on the list yet.</td></tr></tbody>";
    } catch (e) { $("#ml-table").innerHTML = `<tbody><tr><td class="error-box">${esc(/mailing_list|schema cache|does not exist/i.test(e.message) ? "The database needs updating: paste supabase/update-5.sql into Supabase > SQL Editor and Run." : friendly(e))}</td></tr></tbody>`; }
  }
  async function addToList(rows) {
    rows = rows.filter((r) => r.email).map((r) => ({ ...r, email: r.email.toLowerCase().trim(), added_by: me(), active: true }));
    if (!rows.length) return 0;
    if (A.DEMO) { for (const r of rows) if (!mailing.some((m) => m.email === r.email)) mailing.push(r); return rows.length; }
    const { data, error } = await A.db.from("mailing_list").upsert(rows, { onConflict: "email", ignoreDuplicates: true }).select("email");
    if (error) throw error;
    return data.length;
  }
  $("#ml-add").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const n = await addToList([{ email: f.elements.email.value, name: f.elements.name.value.trim() || null, organisation: f.elements.organisation.value.trim() || null }]);
      A.toast(n ? "Added" : "Already on the list"); f.reset(); showMailingList();
    } catch (err) { A.toast("Couldn't add: " + friendly(err), true); }
  });
  $("#ml-paste-add").addEventListener("click", async () => {
    const text = $("#ml-paste").value;
    const rows = [];
    for (const part of text.split(/[;\n,]+/)) {           // "Jane Tan <jane@x.org>" keeps the name
      const emails = part.match(EMAIL_RX) || [];
      for (const email of emails) {
        const name = emails.length === 1 ? part.replace(EMAIL_RX, "").replace(/[<>"()]/g, "").trim() : "";
        rows.push({ email, name: name || null, organisation: null });
      }
    }
    if (!rows.length) return A.toast("No email addresses found in that text", true);
    try { const n = await addToList(rows); A.toast(`Added ${n} (${rows.length - n} were already on the list)`); $("#ml-paste").value = ""; showMailingList(); }
    catch (err) { A.toast("Couldn't add: " + friendly(err), true); }
  });
  $("#ml-table").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-ml-toggle]"), r = e.target.closest("[data-ml-remove]");
    if (!t && !r) return;
    const email = (t || r).dataset[t ? "mlToggle" : "mlRemove"];
    const m = mailing.find((x) => x.email === email);
    try {
      if (t) {
        if (!A.DEMO) { const { error } = await A.db.from("mailing_list").update({ active: !m.active }).eq("email", email); if (error) throw error; }
        m.active = !m.active;
      } else {
        if (!confirm(`Remove ${email} from the mailing list?`)) return;
        if (!A.DEMO) { const { error } = await A.db.from("mailing_list").delete().eq("email", email); if (error) throw error; }
        mailing = mailing.filter((x) => x.email !== email); if (A.DEMO) A._demoMailing = mailing;
      }
      showMailingList();
    } catch (err) { A.toast("Couldn't change: " + friendly(err), true); }
  });
  A.loadMailingList = loadMailingList;

  // ================= Import =================
  // Column names accepted (case-insensitive). The OCR page writes the first name of each.
  const HEAD = {
    pao: ["pao", "pao id", "organisation", "organization", "member", "abbr"],
    date: ["date", "published", "posted on", "published at"],
    type: ["type", "kind", "category type"],
    title: ["title", "headline", "subject"],
    content: ["content", "text", "post", "body", "description"],
    poster: ["posted by", "poster", "author", "source", "by"],
    link: ["link", "url"],
    language: ["language", "lang"],
  };
  const TYPE_MAP = { news: "news", event: "events", events: "events", publication: "publications", publications: "publications",
    newsletter: "articles", newsletters: "articles", article: "articles", articles: "articles", "newsletter / article": "articles", "newsletter/article": "articles",
    comment: "comment", "opportunity to comment": "comment", consultation: "comment", "exposure draft": "comment" };
  let pending = [];

  function findPao(v) {
    const s = String(v ?? "").trim().toLowerCase();
    if (!s) return null;
    const ps = A.state.paos;
    return ps.find((p) => p.id.toLowerCase() === s) || ps.find((p) => (p.abbr || "").toLowerCase() === s)
      || ps.find((p) => p.name.toLowerCase() === s) || null;
  }
  function parseDate(v) {
    if (v == null || v === "") return null;
    if (v instanceof Date && !isNaN(v)) return new Date(Date.UTC(v.getFullYear(), v.getMonth(), v.getDate())).toISOString();
    const s = String(v).trim();
    let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return new Date(Date.UTC(+m[1], m[2] - 1, +m[3])).toISOString();
    m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})/);   // day first (dd/mm/yyyy)
    if (m) return new Date(Date.UTC(+m[3], m[2] - 1, +m[1])).toISOString();
    const t = Date.parse(s);
    return isNaN(t) ? null : new Date(t).toISOString();
  }
  async function sha(text) {
    const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
  }

  async function readFile(file) {
    await loadScript(XLSX_JS);
    const wb = window.XLSX.read(await file.arrayBuffer(), { cellDates: true });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    return window.XLSX.utils.sheet_to_json(sheet, { defval: "", raw: true });
  }

  async function toItems(records) {
    if (!records.length) return [];
    const keys = Object.keys(records[0]);
    const col = {};
    for (const [field, names] of Object.entries(HEAD)) col[field] = keys.find((k) => names.includes(k.trim().toLowerCase()));
    const now = new Date().toISOString();
    const out = [];
    for (const [i, r] of records.entries()) {
      const get = (f) => (col[f] ? String(r[col[f]] ?? "").trim() : "");
      const pao = findPao(col.pao ? r[col.pao] : "");
      const content = get("content");
      const title = (get("title") || content.split("\n").find((l) => l.trim()) || "").trim().slice(0, 300);
      const row = { line: i + 2, paoText: get("pao"), pao, title, problem: "" };
      if (!pao) row.problem = get("pao") ? `PAO "${get("pao")}" not found` : "No PAO";
      else if (!title) row.problem = "No title or content";
      if (!row.problem) {
        const published = parseDate(col.date ? r[col.date] : "");
        row.item = {
          id: "import-" + await sha([pao.id, title, content, published || ""].join("|")),
          pao_id: pao.id, source: "manual", title, url: get("link") || null, published_at: published,
          snippet: content.slice(0, 500) || null, content: content || null,
          source_name: get("poster") || `Imported by ${me() || "team"}`,
          language: get("language") || null, kind: TYPE_MAP[get("type").toLowerCase()] || "news",
          first_seen_at: now, is_baseline: false,
        };
      }
      out.push(row);
    }
    return out;
  }

  function renderPreview() {
    const ok = pending.filter((r) => r.item), bad = pending.filter((r) => !r.item);
    const byPao = {};
    for (const r of ok) byPao[r.pao.abbr || r.pao.name] = (byPao[r.pao.abbr || r.pao.name] || 0) + 1;
    $("#import-preview").innerHTML = `
      <p><b>${ok.length}</b> row(s) ready${ok.length ? ": " + Object.entries(byPao).map(([k, n]) => `${n} ${esc(k)}`).join(", ") : ""}.
        ${bad.length ? `<span class="warn-text">${bad.length} row(s) will be skipped.</span>` : ""}</p>
      <div class="table-wrap"><table class="grid"><thead><tr><th>Row</th><th>PAO</th><th>Type</th><th>Date</th><th>Title</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
      ${pending.slice(0, 300).map((r) => `<tr class="${r.item ? "" : "bad"}"><td>${r.line}</td><td>${esc(r.pao ? (r.pao.abbr || r.pao.name) : r.paoText)}</td>
        <td>${r.item ? esc(A.kindLabel[r.item.kind]) : ""}</td><td>${r.item?.published_at ? r.item.published_at.slice(0, 10) : ""}</td>
        <td>${esc(r.title)}</td><td class="warn-text small">${esc(r.problem)}</td></tr>`).join("")}
      </tbody></table></div>`;
    $("#import-save").disabled = !ok.length;
  }

  $("#import-btn").addEventListener("click", () => {
    pending = []; $("#import-file").value = ""; $("#import-preview").innerHTML = ""; $("#import-save").disabled = true;
    $("#import-dialog").showModal();
  });
  $("#import-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    $("#import-preview").innerHTML = "<p>Reading…</p>";
    try { pending = await toItems(await readFile(file)); renderPreview(); }
    catch (err) { $("#import-preview").innerHTML = `<p class="error-box">Couldn't read the file: ${esc(err.message)}</p>`; }
  });
  $("#import-save").addEventListener("click", async () => {
    const rows = pending.filter((r) => r.item).map((r) => r.item);
    $("#import-save").disabled = true;
    try {
      const n = await saveItems(rows);
      $("#import-dialog").close();
      A.toast(`Added ${n} item(s)` + (n < rows.length ? ` (${rows.length - n} were already in the tracker)` : ""));
      if (!A.DEMO) A.reload();
    } catch (e) { A.toast("Couldn't import: " + friendly(e), true); $("#import-save").disabled = false; }
  });

  /** Insert manual items, skipping ones already there. Returns how many were new. Used by Import and OCR. */
  async function saveItems(rows) {
    if (A.DEMO) {
      const have = new Set(A.state.items.map((i) => i.id));
      const fresh = rows.filter((r) => !have.has(r.id));
      A.state.items.unshift(...fresh.map((r) => ({ ...r, relevance: null, category: null, notes: null })));
      A.render();
      return fresh.length;
    }
    let n = 0;
    for (let i = 0; i < rows.length; i += 200) {
      let chunk = rows.slice(i, i + 200);
      let res = await A.db.from("items").upsert(chunk, { onConflict: "id", ignoreDuplicates: true }).select("id");
      if (res.error && /kind/.test(res.error.message)) {   // database not updated yet: save without the type
        chunk = chunk.map(({ kind, ...rest }) => rest);
        res = await A.db.from("items").upsert(chunk, { onConflict: "id", ignoreDuplicates: true }).select("id");
      }
      if (res.error) throw res.error;
      n += res.data.length;
    }
    return n;
  }
  A.saveItems = saveItems;
  A.toImportItems = toItems;
})();
