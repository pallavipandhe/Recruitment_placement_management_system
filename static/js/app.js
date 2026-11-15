const state = {
  user: null,
  route: "dashboard",
  candidateId: null,
  search: "",
  caches: {},
};

const pageMeta = {
  dashboard: ["Your placement pulse", "A little progress goes a long way.", "HOME"],
  candidates: ["Your talent pool", "Find the right person for the right opportunity.", "PEOPLE"],
  "candidate-form": ["Candidate profile", "A thoughtful profile is the start of a great match.", "PEOPLE"],
  "candidate-details": ["Candidate profile", "A closer look at their journey so far.", "PEOPLE"],
  companies: ["Partner companies", "Build better relationships with every hiring partner.", "DIRECTORY"],
  jobs: ["Find the next great fit", "Every open role is a new possibility.", "OPPORTUNITIES"],
  "job-form": ["Create an opportunity", "Give candidates a clear picture of what comes next.", "OPPORTUNITIES"],
  applications: ["Applications", "Keep every candidate moving with confidence.", "PIPELINE"],
  interviews: ["Interviews", "Make every conversation count.", "PIPELINE"],
  "placement-process": ["Offers & placements", "Turn a great conversation into a great beginning.", "OUTCOMES"],
  reports: ["The bigger picture", "See the momentum behind every placement.", "INSIGHTS"],
};
const routeLabels = {
  dashboard: "Overview",
  candidates: "Candidates",
  "candidate-form": "Add candidate",
  "candidate-details": "Candidate profile",
  companies: "Companies",
  jobs: "Job openings",
  "job-form": "Create job",
  applications: "Applications",
  interviews: "Interviews",
  "placement-process": "Offers & placements",
  reports: "Reports",
};
const roleRoutes = {
  ADMIN: Object.keys(routeLabels),
  RECRUITER: ["dashboard", "candidates", "candidate-form", "candidate-details", "companies", "jobs", "job-form", "applications", "interviews"],
  PLACEMENT_OFFICER: ["dashboard", "placement-process"],
};

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));
const money = (value) => value == null ? "—" : `${Number(value).toFixed(1)} LPA`;
const dateLabel = (value, options = {}) => {
  if (!value) return "—";
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? esc(value) : new Intl.DateTimeFormat("en-IN", options).format(parsed);
};
const initials = (value) => String(value || "?").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
const statusClass = (value) => {
  const status = String(value || "pending").toLowerCase().replace(/[^a-z0-9]+/g, "_");
  if (["open", "shortlisted", "interview_scheduled", "interviewed"].includes(status)) return "blue";
  if (["active", "joined", "eligible", "accepted", "placed", "selected"].includes(status)) return "green";
  if (["pending", "scheduled", "offered", "on_hold", "next_round"].includes(status)) return "amber";
  if (["rejected", "not_eligible", "inactive", "cancelled", "not_joined", "no_show"].includes(status)) return "red";
  if (["closed", "draft", "withdrawn", "completed"].includes(status)) return "neutral";
  return "";
};
const badge = (value) => `<span class="status-pill ${statusClass(value)}">${esc(String(value || "Pending").replaceAll("_", " ").toLowerCase())}</span>`;
const avatar = (name, index = 0) => `<span class="table-avatar ${["", "green", "peach", "blue"][index % 4]}">${esc(initials(name))}</span>`;

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  let payload = {};
  try { payload = await response.json(); } catch { /* Empty responses are handled by status below. */ }
  if (!response.ok) {
    if (response.status === 401 && !url.includes("/auth/login")) showLogin();
    throw new Error(payload.error || `Request failed (${response.status}).`);
  }
  return payload;
}

function toast(message, type = "success") {
  const root = document.getElementById("toast-root");
  const item = document.createElement("div");
  item.className = `toast ${type === "error" ? "toast-error" : type === "info" ? "toast-info" : ""}`;
  item.textContent = message;
  root.appendChild(item);
  window.setTimeout(() => item.remove(), 3700);
}

function showLogin() {
  state.user = null;
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app-shell").classList.add("hidden");
  document.getElementById("modal-root").replaceChildren();
  setAuthView("login");
}

function setAuthView(view) {
  const registering = view === "register";
  document.getElementById("login-view").classList.toggle("hidden", registering);
  document.getElementById("register-view").classList.toggle("hidden", !registering);
}

function showWorkspace(user) {
  state.user = user;
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
  const name = user.name || "Workspace user";
  document.getElementById("sidebar-name").textContent = name;
  document.getElementById("top-name").textContent = name;
  document.getElementById("sidebar-role").textContent = user.role_name || "Team member";
  document.getElementById("top-role").textContent = user.role_name || "Team member";
  document.getElementById("sidebar-avatar").textContent = initials(name);
  document.getElementById("top-avatar").textContent = initials(name);
  const allowedRoutes = new Set(roleRoutes[user.role] || ["dashboard"]);
  document.querySelectorAll(".side-nav [data-route]").forEach((link) => {
    link.style.display = allowedRoutes.has(link.dataset.route) ? "" : "none";
  });
  document.querySelectorAll(".side-nav .nav-caption").forEach((caption) => {
    const nextLinks = [];
    for (let sibling = caption.nextElementSibling; sibling && !sibling.classList.contains("nav-caption"); sibling = sibling.nextElementSibling) {
      if (sibling.matches("[data-route]")) nextLinks.push(sibling);
    }
    caption.style.display = nextLinks.some((link) => allowedRoutes.has(link.dataset.route)) ? "" : "none";
  });
  routeTo(["/login", "/register", "/"].includes(location.pathname) ? "/dashboard" : location.pathname, false);
}

function routeTo(path, push = true) {
  let cleanPath = state.user && ["/login", "/register", "/"].includes(path)
    ? "/dashboard"
    : path || "/dashboard";
  if (state.user) {
    const requestedRoute = cleanPath.split("?")[0].replace(/^\/+|\/+$/g, "") || "dashboard";
    if (!(roleRoutes[state.user.role] || ["dashboard"]).includes(requestedRoute)) cleanPath = "/dashboard";
  }
  if (push && location.pathname + location.search !== cleanPath) history.pushState({}, "", cleanPath);
  window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
  const sidebarNavigation = document.querySelector(".side-nav");
  if (sidebarNavigation) sidebarNavigation.scrollTop = 0;
  state.route = cleanPath.split("?")[0].replace(/^\/+|\/+$/g, "") || "dashboard";
  const query = new URLSearchParams(cleanPath.split("?")[1] || location.search.slice(1));
  state.candidateId = query.get("id") || null;
  state.search = query.get("q") || "";
  document.querySelectorAll(".side-nav [data-route]").forEach((link) => {
    const active = link.dataset.route === state.route
      || (["candidate-form", "candidate-details"].includes(state.route) && link.dataset.route === "candidates")
      || (state.route === "job-form" && link.dataset.route === "jobs");
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const meta = pageMeta[state.route] || pageMeta.dashboard;
  document.getElementById("breadcrumb-current").textContent = routeLabels[state.route] || "Overview";
  renderPage().catch((error) => {
    document.getElementById("page-content").innerHTML = `<section class="panel empty-state"><strong>We couldn't load this page.</strong>${esc(error.message)}<br><button class="button button-secondary" data-action="retry-page" style="margin-top:12px">Try again</button></section>`;
  });
}

function heading(title, subtitle, actions = "", kicker) {
  return `<div class="page-heading"><div><span class="heading-eyebrow">${esc(kicker || pageMeta[state.route]?.[2] || "WORKSPACE")}</span><h1>${title}</h1><p>${subtitle}</p></div><div class="page-heading-actions">${actions}</div></div>`;
}

function pageLoading() {
  document.getElementById("page-content").innerHTML = '<div class="panel loading">Loading your workspace…</div>';
}

async function renderPage() {
  pageLoading();
  const content = document.getElementById("page-content");
  content.classList.toggle("dashboard-page", state.route === "dashboard");
  ["admin", "recruiter", "placement_officer"].forEach((role) => content.classList.remove(`role-${role}`));
  if (state.user?.role) content.classList.add(`role-${state.user.role.toLowerCase()}`);
  const renderers = {
    dashboard: renderDashboard,
    candidates: renderCandidates,
    "candidate-form": renderCandidateFormPage,
    "candidate-details": renderCandidateDetails,
    companies: renderCompanies,
    jobs: renderJobs,
    "job-form": renderJobFormPage,
    applications: renderApplications,
    interviews: renderInterviews,
    "placement-process": renderPlacement,
    reports: renderReports,
  };
  await (renderers[state.route] || renderDashboard)();
}

function statCard(label, value, note, icon, tone = "") {
  return `<article class="stat-card"><div class="stat-top"><span class="stat-label">${label}</span><span class="stat-icon ${tone}">${icon}</span></div><strong class="stat-value">${value}</strong><span class="stat-foot">${note}</span></article>`;
}

function dashboardChart() {
  return `<svg class="line-chart" viewBox="0 0 640 160" preserveAspectRatio="none" role="img" aria-label="Applications and placements trend for the last eight months">
    <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8469ee" stop-opacity=".18"/><stop offset="1" stop-color="#8469ee" stop-opacity="0"/></linearGradient></defs>
    <path class="grid-line" d="M22 18H630M22 53H630M22 88H630M22 123H630"/>
    <path class="area-fill" d="M22 112 C55 104 59 95 92 100 S137 77 168 84 S216 57 245 70 S291 47 322 58 S367 35 399 48 S447 27 475 41 S523 20 553 31 S598 15 630 22 L630 138 L22 138Z"/>
    <path class="line-secondary" d="M22 125 C55 121 62 112 92 116 S137 98 168 106 S216 87 245 94 S291 78 322 87 S367 66 399 78 S447 60 475 69 S523 52 553 62 S598 44 630 51"/>
    <path class="line-primary" d="M22 112 C55 104 59 95 92 100 S137 77 168 84 S216 57 245 70 S291 47 322 58 S367 35 399 48 S447 27 475 41 S523 20 553 31 S598 15 630 22"/>
    <circle class="chart-point" cx="399" cy="48" r="3.5"/><circle class="chart-point" cx="553" cy="31" r="3.5"/><circle class="chart-point" cx="630" cy="22" r="3.5"/>
  </svg>`;
}

async function renderDashboard() {
  const data = await api("/api/dashboard");
  const c = data.counts;
  const role = state.user?.role || "RECRUITER";
  const isPlacement = role === "PLACEMENT_OFFICER";
  const isRecruiter = role === "RECRUITER";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const todayLabel = new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase();
  const stages = isPlacement
    ? [["Selected", c.selected || 0], ["Offers", c.offers || 0], ["Accepted", c.accepted_offers || 0], ["Joined", c.placed || 0]]
    : [["Applied", c.applications || 0], ["Shortlisted", data.funnel.SHORTLISTED || 0], ["Interviewed", (data.funnel.INTERVIEWED || 0) + (data.funnel.INTERVIEW_SCHEDULED || 0)], ["Selected", c.selected || 0]];
  const maxStage = Math.max(...stages.map((item) => item[1]), 1);
  const actions = isPlacement
    ? [["✳", "Manage offers & placements", "/placement-process"]]
    : isRecruiter
      ? [["＋", "Add candidate", "/candidate-form"], ["▤", "Create a job", "/job-form"], ["◷", "Schedule interview", "/interviews"]]
      : [["＋", "Add candidate", "/candidate-form"], ["▤", "Create a job", "/job-form"], ["◷", "Schedule interview", "/interviews"], ["▥", "View reports", "/reports"]];
  const statCards = isPlacement
    ? [
      statCard("Selected candidates", c.selected.toLocaleString(), "Ready for placement follow-up", "✦"),
      statCard("Offers issued", c.offers.toLocaleString(), "In the placement pipeline", "▧", "teal"),
      statCard("Offers accepted", c.accepted_offers.toLocaleString(), "Candidates ready to join", "◎", "peach"),
      statCard("Successfully joined", c.placed.toLocaleString(), "Completed placements", "↗", "blue"),
    ]
    : isRecruiter
      ? [
        statCard("Your candidates", c.candidates.toLocaleString(), "Profiles you manage", "♙"),
        statCard("Active candidates", c.active_candidates.toLocaleString(), "Ready for their next step", "✦", "teal"),
        statCard("Open roles", c.open_jobs.toLocaleString(), "Shared opportunities", "▤", "peach"),
        statCard("Your applications", c.applications.toLocaleString(), "Assigned to your account", "▧", "blue"),
      ]
      : [
        statCard("Total candidates", c.candidates.toLocaleString(), "Across all recruiter accounts", "♙"),
        statCard("Active candidates", c.active_candidates.toLocaleString(), "Ready for their next step", "✦", "teal"),
        statCard("Partner companies", c.companies, "Hiring partners", "▦", "peach"),
        statCard("Applications", c.applications.toLocaleString(), "Across the full pipeline", "▧", "blue"),
      ];
  const funnelPanel = `<article class="panel"><div class="panel-header"><div><h2 class="panel-title">${isPlacement ? "Placement progress" : "Recruitment funnel"}</h2><p class="panel-subtitle">${isPlacement ? "Track offers from selection to joining." : "Your candidates, moving forward."}</p></div><button class="panel-link" data-action="navigate" data-path="${isPlacement ? "/placement-process" : "/applications"}">${isPlacement ? "Manage placements" : "See pipeline"} →</button></div><div class="funnel-list">${stages.map(([label, total]) => `<div class="funnel-row"><div class="funnel-head"><span>${label}</span><strong>${Number(total).toLocaleString()}</strong></div><div class="funnel-track"><div class="funnel-fill" style="width:${Math.max(4, Math.round(total / maxStage * 100))}%"></div></div></div>`).join("")}</div></article>`;
  const interviewPanel = `<article class="panel"><div class="panel-header"><div><h2 class="panel-title">Upcoming conversations</h2><p class="panel-subtitle">A chance to find the next great fit.</p></div><button class="panel-link" data-action="navigate" data-path="/interviews">All interviews →</button></div><div class="card-list">${data.upcoming.length ? data.upcoming.map((item) => `<div class="schedule-row"><div class="date-tile"><strong>${dateLabel(item.scheduled_date, { day: "2-digit" })}</strong><small>${dateLabel(item.scheduled_date, { month: "short" })}</small></div><div class="schedule-copy"><strong>${esc(item.candidate)} <span class="table-secondary" style="display:inline">· ${esc(item.round_type)}</span></strong><small>${esc(item.company)} · ${esc(item.job_title)}</small></div><span class="schedule-time">${esc(item.scheduled_time || "Time TBD")}</span></div>`).join("") : '<div class="empty-state">No upcoming interviews just yet.</div>'}</div></article>`;
  const jobsPanel = `<article class="panel"><div class="panel-header"><div><h2 class="panel-title">New opportunities</h2><p class="panel-subtitle">Fresh roles ready for a great match.</p></div><button class="panel-link" data-action="navigate" data-path="/jobs">Explore jobs →</button></div><div class="card-list">${data.jobs.slice(0, 4).map((item) => `<div class="mini-summary"><span class="mini-summary-icon">▤</span><span class="mini-summary-copy"><strong>${esc(item.job_title)}</strong><small>${esc(item.company_name)} · ${esc(item.location)}</small></span><span class="table-secondary" style="margin:0">${item.openings} spots</span></div>`).join("") || '<div class="empty-state">New roles will show up here.</div>'}</div></article>`;
  const placementPanel = `<article class="panel"><div class="panel-header"><div><h2 class="panel-title">Recent placements</h2><p class="panel-subtitle">The latest candidates starting a new chapter.</p></div><button class="panel-link" data-action="navigate" data-path="/placement-process">View offers →</button></div><div class="card-list">${data.placements.length ? data.placements.map((item) => `<div class="mini-summary"><span class="mini-summary-icon">✳</span><span class="mini-summary-copy"><strong>${esc(item.candidate)}</strong><small>${esc(item.company_name)} · ${esc(item.designation)}</small></span><span class="status-pill green">Joined</span></div>`).join("") : '<div class="empty-state">Completed placements will appear here.</div>'}</div></article>`;
  const dashboardPanels = isPlacement
    ? `<section class="dashboard-grid">${funnelPanel}${placementPanel}</section>`
    : isRecruiter
      ? `<section class="dashboard-grid">${funnelPanel}${jobsPanel}</section><section class="dashboard-grid secondary">${interviewPanel}</section>`
      : `<section class="dashboard-grid"><article class="panel chart-panel"><div class="panel-header"><div><h2 class="panel-title">Placement momentum</h2><p class="panel-subtitle">A little progress, month by month.</p></div><div class="chart-legend"><span class="legend-item"><i class="legend-dot"></i>Applications</span><span class="legend-item"><i class="legend-dot soft"></i>Placements</span></div></div><div class="chart-area">${dashboardChart()}<div class="chart-labels"><span>May</span><span>Jun</span><span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span></div></div></article>${funnelPanel}</section><section class="dashboard-grid secondary">${interviewPanel}${jobsPanel}</section><section class="dashboard-grid">${placementPanel}</section>`;
  const heroMetrics = isPlacement
    ? [[c.offers, "offers issued"], [c.accepted_offers, "offers accepted"], [c.placed, "candidates joined"]]
    : isRecruiter
      ? [[c.interviews_today, "interviews today"], [c.open_jobs, "open roles"]]
      : [[c.interviews_today, "interviews today"], [c.open_jobs, "open roles"], [c.placed, "joined talent"]];
  const title = isPlacement ? "Placement outcomes, at a glance." : isRecruiter ? "Your recruitment, at a glance." : "Every connection moves us forward.";
  const subtitle = isPlacement
    ? "A focused view of selected candidates, offers and successful joins."
    : isRecruiter
      ? "Your candidates and applications, all in one place."
      : "Here's what's happening across the full placement workspace today.";
  document.getElementById("page-content").innerHTML = `
    ${heading(`${greeting}, <span class='text-violet'>${esc((state.user?.name || "there").split(" ")[0])}</span> ☀`, subtitle, `<button class="button button-secondary" data-action="refresh">↻ <span>Refresh</span></button>${!isPlacement ? '<button class="button button-primary" data-action="candidate-add">＋ Add candidate</button>' : ""}`, `${todayLabel} · A LITTLE MOMENTUM`)}
    <section class="hero-banner"><div class="hero-copy"><span class="heading-eyebrow">${isPlacement ? "YOUR PLACEMENT PULSE" : isRecruiter ? "YOUR RECRUITMENT PULSE" : "WORKSPACE OVERVIEW"}</span><h2>${title}</h2><p>${isPlacement ? "Keep every offer moving toward a successful start." : isRecruiter ? "Every candidate you manage gets a focused path forward." : "Your team's work is making a real difference. Keep the good things going."}</p></div><div class="hero-figure">${heroMetrics.map(([value, label]) => `<div><strong>${Number(value || 0).toLocaleString()}</strong><small>${label}</small></div>`).join("")}</div></section>
    <section class="stats-grid">${statCards.join("")}</section>
    ${dashboardPanels}
    ${actions.length ? `<article class="panel dashboard-shortcuts"><div class="panel-header"><div><h2 class="panel-title">A few shortcuts</h2><p class="panel-subtitle">Keep the work flowing.</p></div></div><div class="quick-actions">${actions.map(([icon, text, path]) => `<button class="quick-action" data-action="${path === "/candidate-form" ? "candidate-add" : path === "/job-form" ? "job-add" : "navigate"}" data-path="${path}"><span>${icon}</span>${text}</button>`).join("")}</div></article>` : ""}`;
}

async function renderCandidates() {
  const search = encodeURIComponent(state.search);
  const [data, jobs] = await Promise.all([api(`/api/candidates?q=${search}`), api("/api/jobs")]);
  state.caches.candidates = data.items;
  state.caches.jobs = jobs.items;
  document.getElementById("candidate-count").textContent = data.items.length;
  const technologySet = [...new Set(data.items.map((item) => item.primary_technology).filter(Boolean))].sort();
  document.getElementById("page-content").innerHTML = `
    ${heading("A great fit is out there.", "Your people, their possibilities — all in one place.", '<button class="button button-secondary" data-action="export-candidates">↓ Export</button><button class="button button-primary" data-action="candidate-add">＋ Add candidate</button>', "CANDIDATE DIRECTORY")}
    <section class="stats-grid">
      ${statCard("Everyone in your corner", data.items.length.toLocaleString(), "Profiles in your workspace", "♙")}
      ${statCard("Ready for a match", data.items.filter((item) => item.profile_status === "ACTIVE").length, "Active candidate profiles", "✦", "teal")}
      ${statCard("Graduating class", new Set(data.items.map((item) => item.passing_year)).size, "Pass-out years represented", "◎", "peach")}
      ${statCard("Different superpowers", technologySet.length, "Technologies & skill paths", "⌘", "blue")}
    </section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Search name, ID, email or mobile..."></label><select class="filter-select" id="technology-filter"><option value="">All technologies</option>${technologySet.map((item) => `<option>${esc(item)}</option>`).join("")}</select><select class="filter-select" id="candidate-status-filter"><option value="">All profiles</option><option>ACTIVE</option><option>ON_HOLD</option><option>PLACED</option><option>INACTIVE</option></select></div>
      <div class="filter-meta"><span><strong class="table-primary">${data.items.length}</strong> people ready for their next chapter</span><span>Updated just now</span></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>Technology</th><th>Education</th><th>Batch</th><th>Score</th><th>Profile</th><th>Placement</th><th></th></tr></thead><tbody>${data.items.map((item, index) => `<tr><td>${avatar(item.full_name, index)}<span class="table-primary">${esc(item.full_name)}</span><span class="table-secondary" style="margin-left:34px">${esc(item.candidate_code)} · ${esc(item.email)}</span></td><td>${esc(item.primary_technology || "—")}</td><td>${esc(item.qualification)}<span class="table-secondary">${esc(item.college || "College not added")}</span></td><td>${esc(item.passing_year)}</td><td>${item.percentage == null ? "—" : `${Number(item.percentage).toFixed(1)}%`}</td><td>${badge(item.profile_status)}</td><td>${badge(item.placement_status)}</td><td><div class="table-actions"><button class="table-action" data-action="candidate-view" data-id="${item.candidate_id}">View</button><button class="table-action" data-action="candidate-edit" data-id="${item.candidate_id}">Edit</button></div></td></tr>`).join("") || '<tr><td colspan="8"><div class="empty-state"><strong>No candidates found</strong>Try a different search or add someone new.</div></td></tr>'}</tbody></table></div>
      <div class="table-footer"><span>Showing ${data.items.length ? 1 : 0}–${data.items.length} of ${data.items.length} candidates</span><div class="pagination"><button class="page-button active">1</button></div></div>
    </article>`;
  bindSearch("#page-search", () => renderCandidates());
  document.getElementById("technology-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[1].textContent.includes(event.target.value)));
  });
  document.getElementById("candidate-status-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[5].textContent.toUpperCase().includes(event.target.value)));
  });
}

function bindSearch(selector, rerender) {
  const input = document.querySelector(selector);
  let timer;
  input?.addEventListener("input", (event) => {
    window.clearTimeout(timer);
    state.search = event.target.value;
    timer = window.setTimeout(rerender, 220);
  });
}

async function renderCandidateFormPage() {
  const id = state.candidateId;
  const candidate = id ? (state.caches.candidates || await api("/api/candidates").then((response) => response.items)).find((item) => String(item.candidate_id) === String(id)) : null;
  const secondarySkills = (candidate?.skills || "").split(",").map((skill) => skill.trim()).filter((skill) => skill && skill.toLowerCase() !== String(candidate?.primary_technology || "").toLowerCase()).join(", ");
  document.getElementById("page-content").innerHTML = `
    ${heading(candidate ? "A profile with possibility." : "Say hello to someone new.", candidate ? `Update ${esc(candidate.full_name)}’s profile.` : "A few thoughtful details help us make a better match.", '<button class="button button-secondary" data-action="navigate" data-path="/candidates">← Back to candidates</button>', "CANDIDATE PROFILE")}
    <form class="panel page-form" data-form="candidate" data-id="${candidate?.candidate_id || ""}">
      <div class="panel-header"><div><h2 class="panel-title">Let’s get to know them</h2><p class="panel-subtitle">Required fields keep this profile ready for matching.</p></div><span class="status-pill green">● Private profile</span></div>
      <div class="modal-body field-grid">
        <div class="section-label">Personal information</div>
        <label>Full name *<input name="full_name" value="${esc(candidate?.full_name)}" placeholder="e.g. Rahul Patil" required></label>
        <label>Email address *<input name="email" type="email" value="${esc(candidate?.email)}" placeholder="name@email.com" required></label>
        <label>Mobile number *<input name="mobile" inputmode="numeric" pattern="[0-9]{10}" maxlength="10" value="${esc(candidate?.mobile)}" placeholder="10 digit number" required></label>
        <label>Date of birth<input name="date_of_birth" type="date" value="${esc(candidate?.date_of_birth)}"></label>
        <label>Gender<select name="gender"><option value="">Prefer not to say</option>${["Female", "Male", "Non-binary", "Other"].map((item) => `<option ${candidate?.gender === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <div class="section-label">Academic journey</div>
        <label>Qualification *<select name="qualification" required><option value="">Choose qualification</option>${["BE", "BTech", "MCA", "BSc", "MSc", "BCA", "MBA", "Other"].map((item) => `<option ${candidate?.qualification === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <label>Passing year *<input name="passing_year" type="number" min="1990" max="2100" value="${esc(candidate?.passing_year || new Date().getFullYear())}" required></label>
        <label>College / Institute *<input name="college" value="${esc(candidate?.college)}" placeholder="College or university name" required></label>
        <label>University<input name="university" value="${esc(candidate?.university)}" placeholder="University name"></label>
        <label>Percentage<input name="percentage" type="number" min="0" max="100" step=".01" value="${esc(candidate?.percentage)}" placeholder="0–100"></label>
        <label>CGPA<input name="cgpa" type="number" min="0" max="10" step=".01" value="${esc(candidate?.cgpa)}" placeholder="0–10"></label>
        <label>Backlog count *<input name="backlog_count" type="number" min="0" value="${esc(candidate?.backlog_count ?? 0)}" required></label>
        <div class="section-label">Skills &amp; aspirations</div>
        <label>Primary technology<select name="primary_technology"><option value="">Choose a path</option>${["Java", "Python", "Data Analytics", "Testing", "JavaScript", "React", "SQL", "AWS"].map((item) => `<option ${candidate?.primary_technology === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <label>Skill level<select name="skill_level">${["BASIC", "INTERMEDIATE", "ADVANCED"].map((item) => `<option ${item === "INTERMEDIATE" ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <label class="full-width">Other skills<span class="field-hint">Separate each skill with a comma.</span><input name="secondary_skills" value="${esc(secondarySkills)}" placeholder="SQL, Git, React"></label>
        <label>Profile status<select name="profile_status">${["ACTIVE", "ON_HOLD", "INACTIVE", "BLACKLISTED"].map((item) => `<option ${candidate?.profile_status === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <label>Current location<input name="current_location" value="${esc(candidate?.current_location)}" placeholder="e.g. Pune"></label>
        <label>Preferred location<input name="preferred_location" value="${esc(candidate?.preferred_location)}" placeholder="e.g. Bengaluru"></label>
      </div>
      <div class="modal-footer"><span>* Required information · Duplicate email/mobile is not allowed.</span><div class="modal-actions"><button type="button" class="button button-secondary" data-action="navigate" data-path="/candidates">Cancel</button><button class="button button-primary" type="submit">${candidate ? "Save profile" : "Add to talent pool"} <span>→</span></button></div></div>
    </form>`;
}

async function renderCandidateDetails() {
  const candidates = state.caches.candidates || (await api("/api/candidates")).items;
  const candidate = candidates.find((item) => String(item.candidate_id) === String(state.candidateId)) || candidates[0];
  if (!candidate) {
    document.getElementById("page-content").innerHTML = `${heading("A profile with possibility.", "Add a candidate to start their journey.", '<button class="button button-primary" data-action="candidate-add">＋ Add candidate</button>')}<div class="panel empty-state"><strong>No profiles just yet</strong>Your candidates will appear here.</div>`;
    return;
  }
  const applications = await api("/api/applications?q=" + encodeURIComponent(candidate.full_name));
  const related = applications.items.filter((item) => Number(item.candidate_id) === Number(candidate.candidate_id));
  const historyItems = [];
  for (const item of related.slice(0, 4)) {
    const list = await api(`/api/applications/${item.application_id}/history`);
    historyItems.push(...list.items);
  }
  document.getElementById("page-content").innerHTML = `
    ${heading("A profile with possibility.", "A closer look at their journey so far.", `<button class="button button-secondary" data-action="navigate" data-path="/candidates">← All candidates</button><button class="button button-primary" data-action="candidate-edit" data-id="${candidate.candidate_id}">✎ Edit profile</button>`, "CANDIDATE 360°")}
    <section class="panel" style="padding:18px;margin-bottom:13px"><div class="profile-card">${avatar(candidate.full_name)}<div><strong>${esc(candidate.full_name)}</strong><small>${esc(candidate.candidate_code)} · ${esc(candidate.primary_technology || "Open to opportunities")} · ${esc(candidate.current_location || "Location not added")}</small></div><span style="margin-left:auto">${badge(candidate.profile_status)}</span></div><div class="detail-grid"><div class="detail-item"><small>Email address</small><strong>${esc(candidate.email)}</strong></div><div class="detail-item"><small>Mobile</small><strong>${esc(candidate.mobile)}</strong></div><div class="detail-item"><small>Education</small><strong>${esc(candidate.qualification)} · ${esc(candidate.passing_year)}</strong></div><div class="detail-item"><small>Academic score</small><strong>${candidate.percentage == null ? "Not added" : `${Number(candidate.percentage).toFixed(1)}%`} · ${candidate.backlog_count} backlogs</strong></div><div class="detail-item"><small>College</small><strong>${esc(candidate.college || "Not added")}</strong></div><div class="detail-item"><small>Placement status</small><strong>${badge(candidate.placement_status)}</strong></div></div></section>
    <section class="content-grid"><article class="panel"><div class="panel-header"><div><h2 class="panel-title">Applications</h2><p class="panel-subtitle">${related.length} opportunities explored so far.</p></div><button class="panel-link" data-action="navigate" data-path="/applications">View pipeline →</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Opportunity</th><th>Company</th><th>Applied</th><th>Status</th></tr></thead><tbody>${related.map((item) => `<tr><td><span class="table-primary">${esc(item.job_title)}</span><span class="table-secondary">${esc(item.application_code)}</span></td><td>${esc(item.company_name)}</td><td>${dateLabel(item.applied_at)}</td><td>${badge(item.application_status)}</td></tr>`).join("") || '<tr><td colspan="4"><div class="empty-state">No applications yet.</div></td></tr>'}</tbody></table></div></article>
    <article class="panel"><div class="panel-header"><div><h2 class="panel-title">A little history</h2><p class="panel-subtitle">Important moments along the way.</p></div></div><div class="card-list timeline">${historyItems.slice(0, 8).map((item) => `<div class="timeline-item"><strong>${esc(String(item.new_status).replaceAll("_", " "))}</strong><small>${esc(item.remarks || "Application update")} · ${dateLabel(item.changed_at)}</small></div>`).join("") || '<div class="empty-state">Activity will show here as this profile progresses.</div>'}</div></article></section>`;
}

async function renderCompanies() {
  const [data, jobs] = await Promise.all([api(`/api/companies?q=${encodeURIComponent(state.search)}`), api("/api/jobs")]);
  state.caches.companies = data.items;
  state.caches.jobs = jobs.items;
  const active = data.items.filter((item) => item.status === "ACTIVE").length;
  const canManageCompanies = state.user?.role === "ADMIN";
  document.getElementById("page-content").innerHTML = `
    ${heading("Good people, great partnerships.", "Your hiring partners — the start of something wonderful.", `<button class="button button-secondary" data-action="export-companies">↓ Export</button>${canManageCompanies ? '<button class="button button-primary" data-action="company-add">＋ Add company</button>' : ""}`, "COMPANY DIRECTORY")}
    <section class="stats-grid">${statCard("Hiring partners", data.items.length, "Companies in your corner", "▦")}${statCard("Ready to hire", active, "Active partnerships", "✦", "teal")}${statCard("Open opportunities", jobs.items.filter((item) => item.status === "OPEN").length, "Roles to match today", "▤", "peach")}${statCard("Industries", new Set(data.items.map((item) => item.industry)).size, "Different spaces to grow", "◎", "blue")}</section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Search a company, industry or code..."></label><span class="status-pill neutral">${data.items.length} partners</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Company</th><th>Industry</th><th>Location</th><th>Hiring contact</th><th>Open roles</th><th>Partnership</th><th></th></tr></thead><tbody>${data.items.map((item, index) => `<tr><td>${`<span class="company-badge b${index % 6}">${esc(initials(item.company_name).slice(0, 2))}</span>`}<span class="table-primary">${esc(item.company_name)}</span><span class="table-secondary" style="margin-left:34px">${esc(item.company_code)}</span></td><td>${esc(item.industry || "—")}</td><td>${esc(item.location || "—")}</td><td>${esc(item.hr_name || "—")}<span class="table-secondary">${esc(item.hr_email || "")}</span></td><td><button class="table-action" data-action="company-jobs" data-id="${item.company_id}">${item.open_jobs} open ${item.open_jobs === 1 ? "role" : "roles"} →</button></td><td>${badge(item.status)}</td><td>${canManageCompanies ? `<div class="table-actions"><button class="table-action" data-action="company-edit" data-id="${item.company_id}">Edit</button><button class="table-action" data-action="company-status" data-id="${item.company_id}" data-status="${item.status === "ACTIVE" ? "INACTIVE" : "ACTIVE"}">${item.status === "ACTIVE" ? "Pause" : "Reactivate"}</button></div>` : ""}</td></tr>`).join("") || '<tr><td colspan="7"><div class="empty-state"><strong>No partners found</strong>Add a company to open your first opportunity.</div></td></tr>'}</tbody></table></div><div class="table-footer"><span>Showing ${data.items.length} hiring partners</span><span>People make partnerships.</span></div></article>`;
  bindSearch("#page-search", () => renderCompanies());
}

async function renderJobs() {
  const [data, companies] = await Promise.all([api(`/api/jobs?q=${encodeURIComponent(state.search)}`), api("/api/companies")]);
  state.caches.jobs = data.items;
  state.caches.companies = companies.items;
  const open = data.items.filter((item) => item.status === "OPEN").length;
  const applications = data.items.reduce((sum, item) => sum + Number(item.applications_count || 0), 0);
  const canCreateJobs = ["ADMIN", "RECRUITER"].includes(state.user?.role);
  document.getElementById("page-content").innerHTML = `
    ${heading("A great opportunity starts here.", "Create a role worth getting excited about.", `<button class="button button-secondary" data-action="export-jobs">↓ Export</button>${canCreateJobs ? '<button class="button button-primary" data-action="job-add">＋ Create job</button>' : ""}`, "JOB BOARD")}
    <section class="stats-grid">${statCard("All opportunities", data.items.length, "Across your partners", "▤")}${statCard("Open right now", open, "Taking applications", "✦", "teal")}${statCard("Candidate interest", applications, "Applications received", "▧", "peach")}${statCard("Hiring partners", companies.items.length, "Ready to welcome talent", "▦", "blue")}</section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Search roles, companies or locations..."></label><select class="filter-select" id="job-status-filter"><option value="">All job statuses</option><option>OPEN</option><option>DRAFT</option><option>CLOSED</option><option>CANCELLED</option></select><span class="status-pill green">${open} roles open</span></div>    <div class="table-wrap"><table class="data-table"><thead><tr><th>Role</th><th>Hiring partner</th><th>Location</th><th>Salary range</th><th>Openings</th><th>Deadline</th><th>Applicants</th><th>Status</th><th></th></tr></thead><tbody>${data.items.map((item, index) => {
      const canManage = state.user?.role === "ADMIN" || (state.user?.role === "RECRUITER" && Number(item.created_by) === Number(state.user.id));
      return `<tr><td><span class="table-primary">${esc(item.job_title)}</span><span class="table-secondary">${esc(item.job_code)} · ${esc(item.employment_type.replaceAll("_", " "))}</span></td><td>${esc(item.company_name)}</td><td>${esc(item.location)}</td><td>${money(item.min_package_lpa)}–${money(item.max_package_lpa)}</td><td><strong class="table-primary">${item.openings}</strong></td><td>${dateLabel(item.application_deadline, { day: "2-digit", month: "short" })}</td><td><button class="table-action" data-action="job-applications" data-id="${item.job_id}">${item.applications_count} people →</button></td><td>${badge(item.status)}</td><td>${canManage ? `<div class="table-actions"><button class="table-action" data-action="job-edit" data-id="${item.job_id}">Edit</button><button class="table-action" data-action="job-status" data-id="${item.job_id}" data-status="${item.status === "OPEN" ? "CLOSED" : "OPEN"}">${item.status === "OPEN" ? "Close" : "Reopen"}</button></div>` : ""}</td></tr>`;
    }).join("") || '<tr><td colspan="9"><div class="empty-state"><strong>No roles found</strong>Try another search or create a new opportunity.</div></td></tr>'}</tbody></table></div><div class="table-footer"><span>Showing ${data.items.length} opportunities</span><span>Every role is a new possibility.</span></div></article>`;
  bindSearch("#page-search", () => renderJobs());
  document.getElementById("job-status-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[7].textContent.toUpperCase().includes(event.target.value)));
  });
}

async function renderJobFormPage() {
  const companies = state.caches.companies || (await api("/api/companies")).items;
  const job = state.candidateId ? (state.caches.jobs || await api("/api/jobs").then((response) => response.items)).find((item) => String(item.job_id) === String(state.candidateId)) : null;
  const existingSkills = (job?.required_skills || "").split(",").map((skill) => skill.trim()).filter((skill) => skill && skill.toLowerCase() !== String(job?.primary_technology || "").toLowerCase()).join(", ");
  document.getElementById("page-content").innerHTML = `
    ${heading(job ? "Shape this opportunity." : "Create an opportunity.", job ? "Keep the role clear and the right people close." : "Clear expectations lead to the right kind of hello.", '<button class="button button-secondary" data-action="navigate" data-path="/jobs">← Back to jobs</button>', job ? "EDIT JOB OPENING" : "NEW JOB OPENING")}
    <form class="panel page-form" data-form="job" data-id="${job?.job_id || ""}"><div class="panel-header"><div><h2 class="panel-title">${job ? "Update the role" : "Tell us about the role"}</h2><p class="panel-subtitle">A few details help us find a meaningful match.</p></div><span class="status-pill green">Ready to post</span></div>
      <div class="modal-body field-grid"><div class="section-label">The opportunity</div>
        <label>Hiring company *<select name="company_id" required><option value="">Choose a partner</option>${companies.filter((item) => item.status === "ACTIVE").map((item) => `<option value="${item.company_id}" ${Number(job?.company_id) === Number(item.company_id) ? "selected" : ""}>${esc(item.company_name)}</option>`).join("")}</select></label>
        <label>Role title *<input name="job_title" value="${esc(job?.job_title)}" required placeholder="e.g. Associate Java Developer"></label>
        <label>Employment type<select name="employment_type">${[["FULL_TIME", "Full time"], ["INTERNSHIP", "Internship"], ["CONTRACT", "Contract"]].map(([value, label]) => `<option value="${value}" ${job?.employment_type === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
        <label>Location *<input name="location" value="${esc(job?.location)}" required placeholder="e.g. Pune"></label>
        <label>Number of openings *<input name="openings" type="number" min="1" value="${esc(job?.openings || 5)}" required></label>
        <label>Job status<select name="status">${[["OPEN", "Open to applications"], ["DRAFT", "Save as draft"], ["CLOSED", "Closed"], ["CANCELLED", "Cancelled"]].map(([value, label]) => `<option value="${value}" ${job?.status === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
        <div class="section-label">The details</div>
        <label>Minimum package (LPA)<input name="min_package_lpa" type="number" min="0" step=".1" value="${esc(job?.min_package_lpa)}" placeholder="e.g. 4.5"></label>
        <label>Maximum package (LPA)<input name="max_package_lpa" type="number" min="0" step=".1" value="${esc(job?.max_package_lpa)}" placeholder="e.g. 7"></label>
        <label>Minimum eligibility (%) *<input name="min_percentage" type="number" min="0" max="100" step=".1" value="${esc(job?.min_percentage ?? 60)}" required></label>
        <label>Maximum backlogs *<input name="max_backlogs" type="number" min="0" value="${esc(job?.max_backlogs ?? 0)}" required></label>
        <label>Passing year — from<input name="min_passing_year" type="number" min="1990" max="2100" value="${esc(job?.min_passing_year)}" placeholder="e.g. 2024"></label>
        <label>Passing year — to<input name="max_passing_year" type="number" min="1990" max="2100" value="${esc(job?.max_passing_year)}" placeholder="e.g. 2026"></label>
        <label>Qualifications accepted<input name="qualification_rule" value="${esc(job?.qualification_rule)}" placeholder="e.g. BE / BTech"></label>
        <label>Required technology *<select name="required_technology" required><option value="">Choose a skill path</option>${["Java", "Python", "Data Analytics", "Testing", "JavaScript", "React", "SQL", "AWS", "Manual Testing"].map((item) => `<option ${job?.primary_technology === item ? "selected" : ""}>${item}</option>`).join("")}</select></label>
        <label>Additional skills<span class="field-hint">Separate each skill with a comma.</span><input name="required_skills" value="${esc(existingSkills)}" placeholder="e.g. SQL, Git, React"></label>
        <label>Posted date *<input name="posted_date" type="date" value="${esc(job?.posted_date || new Date().toISOString().slice(0, 10))}" required></label>
        <label>Application deadline *<input name="application_deadline" type="date" value="${esc(job?.application_deadline || new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10))}" required></label>
        <p class="inline-note full-width">We’ll automatically check each applicant against your eligibility criteria. You can still review every profile with care.</p>
      </div><div class="modal-footer"><span>* Required information · Deadlines must follow the posted date.</span><div class="modal-actions"><button type="button" class="button button-secondary" data-action="navigate" data-path="/jobs">Cancel</button><button class="button button-primary" type="submit">${job ? "Save opportunity" : "Post opportunity"} <span>→</span></button></div></div>
    </form>`;
}

async function renderApplications() {
  const [data, candidates, jobs] = await Promise.all([
    api(`/api/applications?q=${encodeURIComponent(state.search)}`),
    api("/api/candidates"),
    api("/api/jobs"),
  ]);
  state.caches.applications = data.items;
  state.caches.candidates = candidates.items;
  state.caches.jobs = jobs.items;
  const stages = ["APPLIED", "ELIGIBILITY_VERIFIED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "SELECTED"];
  document.getElementById("page-content").innerHTML = `
    ${heading("Good things are in motion.", "Every application is a possibility waiting to unfold.", '<button class="button button-secondary" data-action="export-applications">↓ Export</button><button class="button button-primary" data-action="application-add">＋ New application</button>', "APPLICATION PIPELINE")}
    <section class="stats-grid">${statCard("In the pipeline", data.items.length, "Applications to nurture", "▧")}${statCard("Ready for a hello", data.items.filter((item) => item.eligibility_status === "ELIGIBLE").length, "Eligible for a next step", "✦", "teal")}${statCard("Conversations started", data.items.reduce((sum, item) => sum + Number(item.interview_count || 0), 0), "Interview rounds created", "◷", "peach")}${statCard("Next chapter", data.items.filter((item) => ["SELECTED", "OFFERED", "JOINED"].includes(item.application_status)).length, "Selected, offered or joined", "◎", "blue")}</section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Search candidate, role or company..."></label><select class="filter-select" id="application-status-filter"><option value="">Every stage</option>${[...new Set(data.items.map((item) => item.application_status))].sort().map((status) => `<option>${esc(status)}</option>`).join("")}</select><button class="button button-secondary button-small" data-action="application-add">＋ Application</button></div>
      <div class="panel-header"><div><h2 class="panel-title">The candidate journey</h2><p class="panel-subtitle">Move each application forward, one good step at a time.</p></div></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>Opportunity</th><th>Company</th><th>Applied</th><th>Eligibility</th><th>Current stage</th><th>Rounds</th><th>Actions</th></tr></thead><tbody>${data.items.map((item, index) => `<tr><td>${avatar(item.candidate, index)}<button class="table-action" data-action="candidate-view" data-id="${item.candidate_id}">${esc(item.candidate)}</button><span class="table-secondary" style="margin-left:34px">${esc(item.candidate_code)}</span></td><td><span class="table-primary">${esc(item.job_title)}</span><span class="table-secondary">${esc(item.job_code)}</span></td><td>${esc(item.company_name)}</td><td>${dateLabel(item.applied_at, { day: "2-digit", month: "short" })}</td><td>${badge(item.eligibility_status)}</td><td>${badge(item.application_status)}</td><td>${item.interview_count || 0}</td><td><div class="table-actions">${item.eligibility_status === "ELIGIBLE" && ["ELIGIBILITY_VERIFIED", "APPLIED"].includes(item.application_status) ? `<button class="table-action" data-action="application-status" data-id="${item.application_id}" data-status="SHORTLISTED">Shortlist</button>` : ""}${item.eligibility_status === "ELIGIBLE" && !["REJECTED", "WITHDRAWN", "JOINED"].includes(item.application_status) ? `<button class="table-action" data-action="schedule-interview" data-id="${item.application_id}">Interview</button>` : ""}<button class="table-action" data-action="application-history" data-id="${item.application_id}">History</button></div></td></tr>`).join("") || '<tr><td colspan="8"><div class="empty-state"><strong>No applications yet</strong>Start by matching a candidate to an open role.</div></td></tr>'}</tbody></table></div>
      <div class="table-footer"><span>${data.items.length} candidate journeys</span><span>${stages.map((item) => `${item.replaceAll("_", " ")} ${data.items.filter((row) => row.application_status === item).length}`).join(" · ")}</span></div></article>`;
  bindSearch("#page-search", () => renderApplications());
  document.getElementById("application-status-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[5].textContent.toUpperCase().includes(event.target.value)));
  });
}

async function renderInterviews() {
  const data = await api(`/api/interviews?q=${encodeURIComponent(state.search)}`);
  state.caches.interviews = data.items;
  const upcoming = data.items.filter((item) => item.status === "SCHEDULED").length;
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById("page-content").innerHTML = `
    ${heading("Make every conversation count.", "A little preparation can change someone's whole story.", '<button class="button button-secondary" data-action="export-interviews">↓ Export</button><button class="button button-primary" data-action="interview-add">＋ Schedule interview</button>', "INTERVIEW STUDIO")}
    <section class="stats-grid">${statCard("On the calendar", upcoming, "Upcoming conversations", "◷")}${statCard("Today", data.items.filter((item) => item.scheduled_date === today && item.status === "SCHEDULED").length, "People meeting today", "✦", "teal")}${statCard("Conversations done", data.items.filter((item) => item.status === "COMPLETED").length, "Feedback captured", "✓", "peach")}${statCard("Average impression", averageRating(data.items), "Across completed interviews", "★", "blue")}</section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Search people, partners or roles..."></label><select id="interview-status-filter" class="filter-select"><option value="">All conversations</option>${["SCHEDULED", "COMPLETED", "RESCHEDULED", "NO_SHOW", "CANCELLED"].map((item) => `<option>${item}</option>`).join("")}</select></div><div class="panel-header"><div><h2 class="panel-title">Interview calendar</h2><p class="panel-subtitle">Keep the human part of hiring at the heart of every step.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>Role &amp; company</th><th>Round</th><th>Date &amp; time</th><th>Format</th><th>Interviewer</th><th>Feedback</th><th>Status</th><th></th></tr></thead><tbody>${data.items.map((item, index) => `<tr><td>${avatar(item.candidate, index)}<span class="table-primary">${esc(item.candidate)}</span><span class="table-secondary" style="margin-left:34px">${esc(item.candidate_code)}</span></td><td>${esc(item.job_title)}<span class="table-secondary">${esc(item.company_name)}</span></td><td>${esc(item.round_type)}<span class="table-secondary">Round ${item.round_number}</span></td><td>${dateLabel(item.scheduled_date, { day: "2-digit", month: "short", year: "numeric" })}<span class="table-secondary">${esc(item.scheduled_time || "Time TBD")}</span></td><td>${esc(item.mode)}</td><td>${esc(item.interviewer_name || "To be assigned")}</td><td>${item.overall_rating == null ? '<span class="table-secondary">Not added yet</span>' : `<strong class="table-primary">★ ${Number(item.overall_rating).toFixed(1)}</strong>`}</td><td>${badge(item.status)}</td><td><div class="table-actions">${item.status !== "COMPLETED" ? `<button class="table-action" data-action="interview-feedback" data-id="${item.interview_id}">Feedback</button>` : ""}${item.status === "SCHEDULED" ? `<button class="table-action" data-action="interview-noshow" data-id="${item.interview_id}">No show</button>` : ""}</div></td></tr>`).join("") || '<tr><td colspan="9"><div class="empty-state"><strong>No conversations scheduled</strong>Schedule an interview to give someone their next opportunity.</div></td></tr>'}</tbody></table></div><div class="table-footer"><span>${data.items.length} interview rounds</span><span>Be kind. Be curious. Be prepared.</span></div></article>`;
  bindSearch("#page-search", () => renderInterviews());
  document.getElementById("interview-status-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[7].textContent.toUpperCase().includes(event.target.value)));
  });
}

function averageRating(items) {
  const ratings = items.map((item) => Number(item.overall_rating)).filter((item) => Number.isFinite(item) && item > 0);
  return ratings.length ? `${(ratings.reduce((sum, item) => sum + item, 0) / ratings.length).toFixed(1)}/5` : "—";
}

async function renderPlacement() {
  const [data, applications] = await Promise.all([api("/api/placements"), api("/api/applications")]);
  state.caches.placements = data.items;
  state.caches.applications = applications.items;
  const joined = data.items.filter((item) => item.joining_status === "JOINED").length;
  document.getElementById("page-content").innerHTML = `
    ${heading("Here’s to a new beginning.", "Celebrate the little steps that turn into big chapters.", '<button class="button button-secondary" data-action="export-placements">↓ Export</button><button class="button button-primary" data-action="offer-add">＋ Create offer</button>', "THE NEXT CHAPTER")}
    <section class="stats-grid">${statCard("Offers extended", data.items.length, "A new opportunity, shared", "✉")}${statCard("Said yes", data.items.filter((item) => item.offer_status === "ACCEPTED").length, "Accepted with excitement", "✦", "teal")}${statCard("New beginnings", joined, "Candidates who have joined", "◎", "peach")}${statCard("Offer to join", data.items.length ? `${Math.round(joined / data.items.length * 100)}%` : "0%", "Every yes is a milestone", "↗", "blue")}</section>
    <section class="hero-banner"><div class="hero-copy"><span class="heading-eyebrow">THE GOOD NEWS BOARD</span><h2>Every offer is a door opening.</h2><p>A little extra care makes the transition from “yes” to “first day” feel special.</p></div><div class="hero-figure"><div><strong>${data.items.filter((item) => item.offer_status === "OFFERED").length}</strong><small>awaiting a reply</small></div><div><strong>${joined}</strong><small>starting fresh</small></div></div></section>
    <article class="panel"><div class="filter-bar"><label class="filter-search"><span>⌕</span><input id="page-search" type="search" value="${esc(state.search)}" placeholder="Find a candidate, company or role..."></label><select class="filter-select" id="offer-status-filter"><option value="">All offer stages</option>${["OFFERED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"].map((item) => `<option>${item}</option>`).join("")}</select></div><div class="panel-header"><div><h2 class="panel-title">The offers &amp; placements</h2><p class="panel-subtitle">A thoughtful follow-through goes a long way.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>New role</th><th>Company</th><th>Package</th><th>Offer date</th><th>Offer status</th><th>Joining</th><th>Actions</th></tr></thead><tbody>${data.items.map((item, index) => `<tr><td>${avatar(item.candidate, index)}<span class="table-primary">${esc(item.candidate)}</span><span class="table-secondary" style="margin-left:34px">${esc(item.offer_code)}</span></td><td>${esc(item.designation)}</td><td>${esc(item.company_name)}</td><td><strong class="table-primary">${money(item.offered_package_lpa)}</strong></td><td>${dateLabel(item.offer_date, { day: "2-digit", month: "short" })}</td><td>${badge(item.offer_status)}</td><td>${item.joining_status ? badge(item.joining_status) : '<span class="table-secondary">Not confirmed</span>'}</td><td><div class="table-actions">${item.offer_status === "OFFERED" ? `<button class="table-action" data-action="offer-status" data-id="${item.offer_id}" data-status="ACCEPTED">Accepted</button><button class="table-action" data-action="offer-status" data-id="${item.offer_id}" data-status="REJECTED">Declined</button>` : ""}${item.offer_status === "ACCEPTED" && !item.placement_id ? `<button class="table-action" data-action="placement-confirm" data-id="${item.offer_id}">Confirm joining</button>` : ""}</div></td></tr>`).join("") || '<tr><td colspan="8"><div class="empty-state"><strong>The next chapter starts here</strong>Create an offer for a selected candidate to begin.</div></td></tr>'}</tbody></table></div><div class="table-footer"><span>${data.items.length} offer records</span><span>Every new beginning deserves a celebration.</span></div></article>`;
  bindSearch("#page-search", () => renderPlacement());
  document.getElementById("offer-status-filter").addEventListener("change", (event) => {
    document.querySelectorAll(".data-table tbody tr").forEach((row) => row.classList.toggle("hidden", event.target.value && !row.children[5].textContent.toUpperCase().includes(event.target.value)));
  });
}

async function renderReports() {
  const data = await api("/api/reports");
  const funnel = data.funnel;
  const pipelineStages = [
    ["Applied", (funnel.APPLIED || 0) + (funnel.ELIGIBILITY_VERIFIED || 0)],
    ["Shortlisted", funnel.SHORTLISTED || 0],
    ["In conversation", (funnel.INTERVIEW_SCHEDULED || 0) + (funnel.INTERVIEWED || 0)],
    ["Selected", (funnel.SELECTED || 0) + (funnel.OFFERED || 0)],
    ["Joined", funnel.JOINED || 0],
  ];
  const max = Math.max(...pipelineStages.map((item) => item[1]), 1);
  document.getElementById("page-content").innerHTML = `
    ${heading("A little perspective.", "The story behind every number is a person moving forward.", '<button class="button button-secondary" data-action="print-report">⎙ Print</button><button class="button button-primary" data-action="export-report">↓ Export report</button>', "PLACEMENT INSIGHTS")}
    <section class="stats-grid stats-five">${statCard("Applications", data.counts.applications.toLocaleString(), "People raising their hands", "▧")}${statCard("Interviews", data.counts.interviews.toLocaleString(), "Conversations started", "◷", "teal")}${statCard("Selected", data.counts.selected.toLocaleString(), "Ready for their next step", "✦", "peach")}${statCard("Joined", data.counts.joined.toLocaleString(), "New chapters started", "◎", "blue")}${statCard("Placement rate", `${data.counts.placement_rate}%`, "Offer to joining", "↗", "teal")}</section>
    <section class="content-grid"><article class="panel"><div class="panel-header"><div><h2 class="panel-title">The candidate journey</h2><p class="panel-subtitle">How people are moving through the pipeline.</p></div></div><div class="bar-list">${pipelineStages.map(([label, total]) => `<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, total / max * 100)}%"></div></div><strong>${total}</strong></div>`).join("")}</div><div class="panel-header" style="border-top:1px solid #f0f1f5"><div><h2 class="panel-title">Joined by technology</h2><p class="panel-subtitle">Where new careers are taking off.</p></div></div><div class="bar-list">${data.technologies.map((item) => `<div class="bar-row"><span>${esc(item.label)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, Number(item.total) / Math.max(...data.technologies.map((row) => Number(row.total)), 1) * 100)}%"></div></div><strong>${item.total}</strong></div>`).join("") || '<span class="empty-state">No placement data yet.</span>'}</div></article>
    <article class="panel"><div class="panel-header"><div><h2 class="panel-title">Partners building futures</h2><p class="panel-subtitle">Successful joins by hiring company.</p></div></div><div class="bar-list">${data.companies.map((item) => `<div class="bar-row"><span>${esc(item.label)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, Number(item.total) / Math.max(...data.companies.map((row) => Number(row.total)), 1) * 100)}%"></div></div><strong>${item.total}</strong></div>`).join("")}</div><div class="panel-header" style="border-top:1px solid #f0f1f5"><div><h2 class="panel-title">Recruiter impact</h2><p class="panel-subtitle">Applications nurtured by the team.</p></div></div><div class="bar-list">${data.recruiters.map((item) => `<div class="bar-row"><span>${esc(item.label.split(" ")[0])}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, Number(item.total) / Math.max(...data.recruiters.map((row) => Number(row.total)), 1) * 100)}%"></div></div><strong>${item.total}</strong></div>`).join("") || '<span class="empty-state">Recruiter activity will show here.</span>'}</div></article></section>
    <section class="content-grid" style="margin-top:13px"><article class="panel"><div class="panel-header"><div><h2 class="panel-title">A few upcoming conversations</h2><p class="panel-subtitle">People making time to meet.</p></div><button class="panel-link" data-action="navigate" data-path="/interviews">Interview calendar →</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Candidate</th><th>Opportunity</th><th>Round</th><th>Date</th></tr></thead><tbody>${data.pending_interviews.map((item, index) => `<tr><td>${avatar(item.candidate, index)}<span class="table-primary">${esc(item.candidate)}</span></td><td>${esc(item.job_title)}<span class="table-secondary">${esc(item.company_name)}</span></td><td>${esc(item.round_type)}</td><td>${dateLabel(item.scheduled_date, { day: "2-digit", month: "short" })}</td></tr>`).join("") || '<tr><td colspan="4"><div class="empty-state">Your calendar has a little breathing room.</div></td></tr>'}</tbody></table></div></article><article class="panel"><div class="panel-header"><div><h2 class="panel-title">Open roles, gently aging</h2><p class="panel-subtitle">A friendly nudge for roles open the longest.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Opportunity</th><th>Partner</th><th>Open for</th></tr></thead><tbody>${data.job_aging.map((item) => `<tr><td><span class="table-primary">${esc(item.job_title)}</span><span class="table-secondary">${esc(item.job_code)}</span></td><td>${esc(item.company_name)}</td><td><strong>${item.age_days} days</strong><span class="table-secondary">${item.openings} openings</span></td></tr>`).join("") || '<tr><td colspan="3"><div class="empty-state">No open roles are aging. Nice work!</div></td></tr>'}</tbody></table></div></article></section>
    <p class="table-secondary" style="margin:14px 2px">Numbers reflect all records in this workspace. Refresh any time for the latest picture.</p>`;
  state.caches.report = data;
}

function openModal({ title, subtitle = "", form, body, submitLabel = "Save changes", wide = false, hint = "" }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `<div class="modal-backdrop" data-action="backdrop-close"><section class="modal ${wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><span class="heading-eyebrow">A THOUGHTFUL NEXT STEP</span><h2 id="modal-title">${title}</h2><p>${subtitle}</p></div><button class="modal-close" type="button" aria-label="Close dialog" data-action="modal-close">×</button></header><form class="modal-form" data-form="${form}"><div class="modal-body">${body}<div class="modal-error" role="alert"></div></div><footer class="modal-footer"><span>${hint}</span><div class="modal-actions"><button class="button button-secondary" type="button" data-action="modal-close">Cancel</button><button class="button button-primary" type="submit">${submitLabel} <span>→</span></button></div></footer></form></section></div>`;
  root.querySelector(".modal-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) closeModal();
  });
  root.querySelector(".modal-close").focus();
}

function closeModal() {
  document.getElementById("modal-root").replaceChildren();
}

function companyForm(company = null) {
  return `<div class="field-grid">
    <label>Company name *<input name="company_name" value="${esc(company?.company_name)}" required placeholder="e.g. Infosys"></label>
    <label>Industry *<input name="industry" value="${esc(company?.industry)}" required placeholder="e.g. IT Services"></label>
    <label>Primary location *<input name="location" value="${esc(company?.location)}" required placeholder="e.g. Pune"></label>
    <label>Company type<select name="company_type">${[["MNC", "MNC"], ["STARTUP", "Startup"], ["MID_SIZE", "Mid-size"], ["CONSULTANCY", "Consultancy"]].map(([value, label]) => `<option value="${value}" ${company?.company_type === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    <div class="section-label">Let’s keep in touch</div>
    <label>HR contact *<input name="hr_name" value="${esc(company?.hr_name)}" required placeholder="Contact person"></label>
    <label>HR email<input name="hr_email" value="${esc(company?.hr_email)}" type="email" placeholder="talent@company.com"></label>
    <label>HR mobile<input name="hr_mobile" value="${esc(company?.hr_mobile)}" placeholder="Contact number"></label>
    <label>Website<input name="website" value="${esc(company?.website)}" type="url" placeholder="https://company.com"></label>
    ${company ? `<label>Status<select name="status"><option ${company.status === "ACTIVE" ? "selected" : ""}>ACTIVE</option><option ${company.status === "INACTIVE" ? "selected" : ""}>INACTIVE</option></select></label>` : ""}
  </div>`;
}

function applicationForm() {
  const candidates = state.caches.candidates || [];
  const jobs = (state.caches.jobs || []).filter((item) => item.status === "OPEN");
  return `<div class="field-grid"><label>Candidate *<select name="candidate_id" required><option value="">Choose someone</option>${candidates.filter((item) => item.profile_status === "ACTIVE").map((item) => `<option value="${item.candidate_id}">${esc(item.full_name)} · ${esc(item.primary_technology || "Open to opportunities")}</option>`).join("")}</select></label><label>Opportunity *<select name="job_id" required><option value="">Choose a role</option>${jobs.map((item) => `<option value="${item.job_id}">${esc(item.job_title)} · ${esc(item.company_name)}</option>`).join("")}</select></label><label>How did they find us?<select name="source"><option>Recruiter</option><option>Portal</option><option>Referral</option><option>Internal</option></select></label><p class="inline-note full-width">We’ll check eligibility as soon as the application is created. Duplicate applications are prevented automatically.</p></div>`;
}

function interviewForm(applicationId = "") {
  const applications = (state.caches.applications || []).filter((item) => item.eligibility_status === "ELIGIBLE" && !["REJECTED", "WITHDRAWN", "JOINED"].includes(item.application_status));
  const chosen = applications.find((item) => String(item.application_id) === String(applicationId));
  const defaultDate = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  return `<div class="field-grid"><label class="full-width">Application *<select name="application_id" required><option value="">Choose a candidate &amp; role</option>${applications.map((item) => `<option value="${item.application_id}" ${String(item.application_id) === String(applicationId) ? "selected" : ""}>${esc(item.candidate)} · ${esc(item.job_title)} — ${esc(item.company_name)}</option>`).join("")}</select></label><label>Interview round *<select name="round_type" required><option>APTITUDE</option><option>TECHNICAL</option><option>MANAGERIAL</option><option>HR</option></select></label><label>Format *<select name="mode"><option>ONLINE</option><option>OFFLINE</option><option>TELEPHONIC</option></select></label><label>Date *<input name="scheduled_date" type="date" min="${defaultDate}" value="${defaultDate}" required></label><label>Time<input name="scheduled_time" type="time" value="11:30"></label><label>Interviewer<input name="interviewer_name" placeholder="Name of interviewer"></label><label>Meeting link or location<input name="meeting_or_location" placeholder="Meeting link / office address"></label><p class="inline-note full-width">${chosen ? `Scheduling for ${esc(chosen.candidate)} — ${esc(chosen.job_title)}.` : "Choose an eligible application. Each new round is added to its candidate’s history."}</p></div>`;
}

function feedbackForm(interviewId) {
  return `<input type="hidden" name="interview_id" value="${interviewId}"><div class="field-grid"><label>Interview result *<select name="recommendation"><option value="NEXT_ROUND">Invite to next round</option><option value="SELECTED">Selected</option><option value="ON_HOLD">Keep in consideration</option><option value="REJECTED">Not moving forward</option></select></label><label>Technical rating<input name="technical_rating" type="number" min="0" max="5" step=".1" placeholder="0–5"></label><label>Communication rating<input name="communication_rating" type="number" min="0" max="5" step=".1" placeholder="0–5"></label><label>Problem-solving rating<input name="problem_solving_rating" type="number" min="0" max="5" step=".1" placeholder="0–5"></label><label>Overall rating<input name="overall_rating" type="number" min="0" max="5" step=".1" placeholder="0–5"></label><label class="full-width">A few notes<textarea name="remarks" placeholder="Share thoughtful, useful feedback…"></textarea></label></div>`;
}

function offerForm() {
  const applications = (state.caches.applications || []).filter((item) => item.application_status === "SELECTED");
  const today = new Date().toISOString().slice(0, 10);
  return `<div class="field-grid"><label class="full-width">Selected candidate *<select name="application_id" required><option value="">Choose a selected application</option>${applications.map((item) => `<option value="${item.application_id}">${esc(item.candidate)} · ${esc(item.job_title)} — ${esc(item.company_name)}</option>`).join("")}</select></label><label>Designation *<input name="designation" required placeholder="e.g. Java Developer"></label><label>Offered package (LPA) *<input name="offered_package_lpa" type="number" min=".1" step=".1" required placeholder="e.g. 5.2"></label><label>Offer date *<input name="offer_date" type="date" value="${today}" required></label><label>Expected joining date<input name="expected_joining_date" type="date"></label><label class="full-width">A note for the file<textarea name="remarks" placeholder="Optional offer notes…"></textarea></label><p class="inline-note full-width">${applications.length ? "This offer will be linked to the candidate’s application and tracked through joining." : "There are no selected applications right now. Select a candidate in the application pipeline first."}</p></div>`;
}

function offerStatusForm(offerId, status) {
  return `<input type="hidden" name="offer_id" value="${offerId}"><label>Offer decision<select name="offer_status">${["OFFERED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"].map((item) => `<option ${item === status ? "selected" : ""}>${item}</option>`).join("")}</select></label>`;
}

function placementForm(offerId) {
  return `<input type="hidden" name="offer_id" value="${offerId}"><div class="field-grid"><label>Joining outcome *<select name="joining_status"><option value="JOINED">Joined</option><option value="DEFERRED">Joining deferred</option><option value="NOT_JOINED">Did not join</option><option value="NO_SHOW">Did not show</option></select></label><label>Actual joining date<input name="actual_joining_date" type="date" value="${new Date().toISOString().slice(0, 10)}"></label><p class="inline-note full-width">A joined placement will update the candidate profile and application history together.</p></div>`;
}

function valuesFrom(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function submitForm(form) {
  const kind = form.dataset.form;
  const values = valuesFrom(form);
  if (kind === "no-submit") {
    closeModal();
    return;
  }
  const errorBox = form.querySelector(".modal-error");
  if (errorBox) {
    errorBox.classList.remove("visible");
    errorBox.textContent = "";
  }
  try {
    if (kind === "candidate") {
      const id = form.dataset.id;
      await api(id ? `/api/candidates/${id}` : "/api/candidates", { method: id ? "PATCH" : "POST", body: JSON.stringify(values) });
      toast(id ? "Candidate profile updated." : "A new candidate joined your talent pool.");
      state.caches.candidates = null;
      routeTo(id ? `/candidate-details?id=${id}` : "/candidates");
    } else if (kind === "job") {
      const id = form.dataset.id;
      await api(id ? `/api/jobs/${id}` : "/api/jobs", { method: id ? "PATCH" : "POST", body: JSON.stringify(values) });
      toast(id ? "Opportunity details updated." : "Your new opportunity is ready.");
      state.caches.jobs = null;
      routeTo("/jobs");
    } else if (kind === "company") {
      const id = form.dataset.id;
      if (!id) values.status = "ACTIVE";
      await api(id ? `/api/companies/${id}` : "/api/companies", { method: id ? "PATCH" : "POST", body: JSON.stringify(values) });
      toast(id ? "Company profile updated." : "A new hiring partner was added.");
      closeModal();
      state.caches.companies = null;
      await renderPage();
    } else if (kind === "application") {
      const result = await api("/api/applications", { method: "POST", body: JSON.stringify(values) });
      toast(result.item.eligibility_status === "ELIGIBLE" ? "Application added — this candidate is eligible." : `Application added for review: ${result.item.eligibility_reason}`, result.item.eligibility_status === "ELIGIBLE" ? "success" : "info");
      closeModal();
      state.caches.applications = null;
      await renderPage();
    } else if (kind === "interview") {
      await api("/api/interviews", { method: "POST", body: JSON.stringify(values) });
      toast("The interview is on the calendar.");
      closeModal();
      state.caches.interviews = null;
      await renderPage();
    } else if (kind === "feedback") {
      const id = values.interview_id;
      await api(`/api/interviews/${id}/feedback`, { method: "POST", body: JSON.stringify(values) });
      toast("Feedback saved. The application moved to its next step.");
      closeModal();
      state.caches.interviews = null;
      state.caches.applications = null;
      await renderPage();
    } else if (kind === "offer") {
      await api("/api/offers", { method: "POST", body: JSON.stringify(values) });
      toast("Offer created — here’s to a new beginning.");
      closeModal();
      state.caches.placements = null;
      state.caches.applications = null;
      await renderPage();
    } else if (kind === "offer-status") {
      await api(`/api/offers/${values.offer_id}`, { method: "PATCH", body: JSON.stringify(values) });
      toast(`Offer marked ${values.offer_status.toLowerCase()}.`);
      closeModal();
      state.caches.placements = null;
      await renderPage();
    } else if (kind === "placement") {
      await api(`/api/placements/${values.offer_id}`, { method: "POST", body: JSON.stringify(values) });
      toast(values.joining_status === "JOINED" ? "Joining confirmed — congratulations!" : "Placement outcome recorded.");
      closeModal();
      state.caches.placements = null;
      await renderPage();
    }
  } catch (error) {
    if (errorBox) {
      errorBox.textContent = error.message;
      errorBox.classList.add("visible");
    } else {
      toast(error.message, "error");
    }
  }
}

function downloadCsv(filename, rows) {
  if (!rows.length) {
    toast("There is nothing to export yet.", "info");
    return;
  }
  const columns = Object.keys(rows[0]);
  const csv = [columns.join(","), ...rows.map((row) => columns.map((key) => `"${String(row[key] ?? "").replaceAll('"', '""')}"`).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  toast("Your CSV is ready.");
}

async function handleAction(button) {
  const action = button.dataset.action;
  const id = button.dataset.id;
  if (action === "show-register") {
    setAuthView("register");
    history.pushState({}, "", "/register");
    return;
  }
  if (action === "show-login") {
    setAuthView("login");
    history.pushState({}, "", "/login");
    return;
  }
  if (action === "navigate") return routeTo(button.dataset.path || "/dashboard");
  if (action === "candidate-add") return routeTo("/candidate-form");
  if (action === "candidate-view") return routeTo(`/candidate-details?id=${encodeURIComponent(id)}`);
  if (action === "candidate-edit") {
    state.caches.candidates = await api("/api/candidates").then((response) => response.items);
    return routeTo(`/candidate-form?id=${encodeURIComponent(id)}`);
  }
  if (action === "job-add") {
    state.caches.companies = await api("/api/companies").then((response) => response.items);
    return routeTo("/job-form");
  }
  if (action === "job-edit") {
    const [jobs, companies] = await Promise.all([api("/api/jobs"), api("/api/companies")]);
    state.caches.jobs = jobs.items;
    state.caches.companies = companies.items;
    return routeTo(`/job-form?id=${encodeURIComponent(id)}`);
  }
  if (action === "company-add") {
    openModal({ title: "Let’s welcome a new partner.", subtitle: "A few details help us build a thoughtful relationship.", form: "company", body: companyForm(), submitLabel: "Add company", hint: "* Required information" });
    return;
  }
  if (action === "company-edit") {
    const company = (state.caches.companies || []).find((item) => String(item.company_id) === String(id));
    if (!company) throw new Error("Company details are no longer available. Refresh the page and try again.");
    openModal({ title: "Let’s keep this partnership current.", subtitle: "Update the details your team uses to stay connected.", form: "company", body: companyForm(company), submitLabel: "Save company", hint: "Company records are retained for history." });
    document.querySelector('.modal-form[data-form="company"]').dataset.id = id;
    return;
  }
  if (action === "application-add") {
    const [candidates, jobs] = await Promise.all([api("/api/candidates"), api("/api/jobs")]);
    state.caches.candidates = candidates.items;
    state.caches.jobs = jobs.items;
    openModal({ title: "Start a new connection.", subtitle: "Match a candidate with an opportunity worth exploring.", form: "application", body: applicationForm(), submitLabel: "Create application", hint: "Duplicate candidate–job pairs are blocked." });
    return;
  }
  if (action === "interview-add" || action === "schedule-interview") {
    const appData = await api("/api/applications");
    state.caches.applications = appData.items;
    const preset = action === "schedule-interview" ? id : "";
    openModal({ title: "Let’s make time to talk.", subtitle: "Schedule a thoughtful conversation with the right people.", form: "interview", body: interviewForm(preset), submitLabel: "Add to calendar", hint: "Interview date cannot be in the past." });
    return;
  }
  if (action === "feedback" || action === "interview-feedback") {
    return openModal({ title: "Every conversation teaches us something.", subtitle: "Share clear, kind feedback that helps the candidate move forward.", form: "feedback", body: feedbackForm(id), submitLabel: "Save feedback", hint: "Ratings are optional · Use a 0–5 scale." });
  }
  if (action === "offer-add") {
    const apps = await api("/api/applications");
    state.caches.applications = apps.items;
    openModal({ title: "Make the good news official.", subtitle: "Create an offer for a selected candidate.", form: "offer", body: offerForm(), submitLabel: "Create offer", hint: "Only selected applications can receive an offer." });
    return;
  }
  if (action === "offer-status") {
    if (button.dataset.status) {
      const current = button.dataset.status;
      if (current === "REJECTED" && !window.confirm("Mark this offer as declined?")) return;
      await api(`/api/offers/${id}`, { method: "PATCH", body: JSON.stringify({ offer_status: current }) });
      toast(`Offer marked ${current.toLowerCase()}.`);
      state.caches.placements = null;
      return renderPage();
    }
    return openModal({ title: "Update the offer journey.", subtitle: "Keep the latest decision reflected in this candidate’s history.", form: "offer-status", body: offerStatusForm(id, button.dataset.status || "OFFERED"), submitLabel: "Save decision" });
  }
  if (action === "placement-confirm") {
    return openModal({ title: "A new beginning.", subtitle: "Confirm what happened after the offer was accepted.", form: "placement", body: placementForm(id), submitLabel: "Confirm outcome", hint: "An actual joining date is needed for a joined placement." });
  }
  if (action === "application-status") {
    await api(`/api/applications/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status, remarks: "Moved forward from the application pipeline." }) });
    toast(`Application moved to ${button.dataset.status.replaceAll("_", " ").toLowerCase()}.`);
    state.caches.applications = null;
    return renderPage();
  }
  if (action === "application-history") {
    const history = await api(`/api/applications/${id}/history`);
    const rows = history.items.map((item) => `<div class="timeline-item"><strong>${esc(String(item.new_status).replaceAll("_", " "))}</strong><small>${esc(item.remarks || "Application update")} · ${dateLabel(item.changed_at)} · ${esc(item.changed_by_name || "System")}</small></div>`).join("") || '<p class="empty-state">No history yet.</p>';
    return openModal({ title: "A little history.", subtitle: "The important steps along this candidate’s journey.", form: "no-submit", body: `<div class="timeline">${rows}</div>`, submitLabel: "Done" });
  }
  if (action === "interview-noshow") {
    if (!window.confirm("Mark this interview as a no-show?")) return;
    await api(`/api/interviews/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: "NO_SHOW" }) });
    toast("Interview marked as a no-show.", "info");
    state.caches.interviews = null;
    return renderPage();
  }
  if (action === "job-status") {
    const next = button.dataset.status;
    await api(`/api/jobs/${id}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
    toast(`Opportunity ${next === "OPEN" ? "reopened" : "closed"}.`);
    state.caches.jobs = null;
    return renderPage();
  }
  if (action === "company-status") {
    await api(`/api/companies/${id}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status }) });
    toast(`Company ${button.dataset.status === "ACTIVE" ? "reactivated" : "paused"}.`);
    state.caches.companies = null;
    return renderPage();
  }
  if (action === "company-jobs") {
    const company = (state.caches.companies || []).find((item) => String(item.company_id) === String(id));
    return routeTo(`/jobs?q=${encodeURIComponent(company?.company_name || "")}`);
  }
  if (action === "job-applications") {
    const job = (state.caches.jobs || []).find((item) => String(item.job_id) === String(id));
    return routeTo(`/applications?q=${encodeURIComponent(job?.job_title || "")}`);
  }
  if (action === "refresh" || action === "retry-page") {
    state.caches = {};
    return renderPage();
  }
  if (action === "logout") {
    await api("/api/auth/logout", { method: "POST" });
    history.pushState({}, "", "/login");
    showLogin();
    toast("You’ve signed out. See you soon!", "info");
    return;
  }
  if (action === "notifications") return toast("You’re all caught up. More good things soon.", "info");
  if (action === "profile") return openProfile();
  if (action === "demo-access") {
    toast("Choose your workspace role above; the demo password is pre-filled.", "info");
    return;
  }
  if (action === "modal-close") return closeModal();
  if (action === "export-candidates") {
    const items = state.caches.candidates || [];
    return downloadCsv("orbit-hire-candidates.csv", items.map(({ candidate_code, full_name, email, mobile, qualification, passing_year, percentage, primary_technology, profile_status, placement_status }) => ({ candidate_code, full_name, email, mobile, qualification, passing_year, percentage, primary_technology, profile_status, placement_status })));
  }
  if (action === "export-companies") {
    const items = state.caches.companies || [];
    return downloadCsv("orbit-hire-companies.csv", items.map(({ company_code, company_name, industry, location, hr_name, hr_email, status, open_jobs }) => ({ company_code, company_name, industry, location, hr_name, hr_email, status, open_jobs })));
  }
  if (action === "export-jobs") {
    const items = state.caches.jobs || [];
    return downloadCsv("orbit-hire-opportunities.csv", items.map(({ job_code, job_title, company_name, location, openings, min_package_lpa, max_package_lpa, application_deadline, status }) => ({ job_code, job_title, company_name, location, openings, min_package_lpa, max_package_lpa, application_deadline, status })));
  }
  if (action === "export-applications") {
    const items = state.caches.applications || [];
    return downloadCsv("orbit-hire-applications.csv", items.map(({ application_code, candidate, candidate_code, company_name, job_code, job_title, eligibility_status, application_status, applied_at }) => ({ application_code, candidate, candidate_code, company_name, job_code, job_title, eligibility_status, application_status, applied_at })));
  }
  if (action === "export-interviews") {
    const items = state.caches.interviews || [];
    return downloadCsv("orbit-hire-interviews.csv", items.map(({ candidate, company_name, job_title, round_type, scheduled_date, scheduled_time, mode, interviewer_name, status }) => ({ candidate, company_name, job_title, round_type, scheduled_date, scheduled_time, mode, interviewer_name, status })));
  }
  if (action === "export-placements") {
    const items = state.caches.placements || [];
    return downloadCsv("orbit-hire-placements.csv", items.map(({ offer_code, candidate, designation, company_name, offered_package_lpa, offer_date, offer_status, joining_status, actual_joining_date }) => ({ offer_code, candidate, designation, company_name, offered_package_lpa, offer_date, offer_status, joining_status, actual_joining_date })));
  }
  if (action === "export-report") {
    const report = state.caches.report;
    if (!report) return toast("Refresh the report and try again.", "error");
    return downloadCsv("orbit-hire-report.csv", [...report.funnel.map((item) => ({ section: "Application stage", label: item.label, total: item.total })), ...report.companies.map((item) => ({ section: "Company placements", label: item.label, total: item.total })), ...report.technologies.map((item) => ({ section: "Technology placements", label: item.label, total: item.total }))]);
  }
  if (action === "print-report") return window.print();
  if (action === "export") return toast("Choose a module to export its records.", "info");
}

function openProfile() {
  const user = state.user || {};
  openModal({
    title: "Your workspace, your way.",
    subtitle: "A quick look at the account you’re signed in with.",
    form: "no-submit",
    body: `<div class="profile-card">${avatar(user.name)}<div><strong>${esc(user.name)}</strong><small>${esc(user.role_name)} · ${esc(user.email)}</small></div></div><div class="detail-grid"><div class="detail-item"><small>Workspace</small><strong>Kiran Academy</strong></div><div class="detail-item"><small>Access level</small><strong>${esc(user.role_name)}</strong></div></div><div style="display:flex;justify-content:flex-end;margin-top:12px"><button class="button button-danger" type="button" data-action="logout">↪ Sign out of this workspace</button></div>`,
    submitLabel: "Done",
  });
}

function selectDemoAccount(role, email) {
  const form = document.getElementById("login-form");
  if (!form) return;
  const isRecruiter = role === "RECRUITER";
  form.elements.namedItem("email").value = isRecruiter ? "" : email;
  form.elements.namedItem("password").value = isRecruiter ? "" : "demo123";
  form.elements.namedItem("role").value = role;
  document.querySelectorAll(".demo-role-option").forEach((button) => {
    const selected = button.dataset.demoRole === role;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  document.getElementById("login-error").textContent = "";
}

function setupEvents() {
  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = document.getElementById("login-error");
    error.textContent = "";
    const submitButton = event.currentTarget.querySelector('button[type="submit"]');
    const submitLabel = submitButton.querySelector("span");
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
    submitLabel.textContent = "Checking your workspace…";
    const values = valuesFrom(event.currentTarget);
    try {
      const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(values) });
      history.pushState({}, "", "/dashboard");
      showWorkspace(result.user);
    } catch (loginError) {
      error.textContent = loginError.message;
    } finally {
      submitButton.disabled = false;
      submitButton.removeAttribute("aria-busy");
      submitLabel.textContent = "Sign in to workspace";
    }
  });
  document.getElementById("register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = document.getElementById("register-error");
    error.textContent = "";
    const values = valuesFrom(form);
    if (values.password !== values.confirm_password) {
      error.textContent = "Passwords do not match.";
      form.elements.namedItem("confirm_password").focus();
      return;
    }
    const submitButton = form.querySelector('button[type="submit"]');
    const submitLabel = submitButton.querySelector("span");
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
    submitLabel.textContent = "Creating your account…";
    delete values.confirm_password;
    try {
      const result = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(values),
      });
      history.pushState({}, "", "/dashboard");
      showWorkspace(result.user);
      toast("Your recruiter account is ready.");
    } catch (registrationError) {
      error.textContent = registrationError.message;
    } finally {
      submitButton.disabled = false;
      submitButton.removeAttribute("aria-busy");
      submitLabel.textContent = "Create account";
    }
  });
  document.getElementById("login-form").elements.namedItem("email").addEventListener("input", (event) => {
    const account = [...document.querySelectorAll(".demo-role-option")].find(
      (button) => button.dataset.demoEmail.toLowerCase() === event.target.value.trim().toLowerCase(),
    );
    if (account && account.dataset.demoRole !== "RECRUITER") {
      selectDemoAccount(account.dataset.demoRole, account.dataset.demoEmail);
    }
  });
  document.querySelectorAll(".password-toggle").forEach((toggle) => toggle.addEventListener("click", (event) => {
    const input = event.currentTarget.closest(".input-icon").querySelector("input");
    input.type = input.type === "password" ? "text" : "password";
    event.currentTarget.textContent = input.type === "password" ? "Show" : "Hide";
  }));
  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-form]");
    if (!form) return;
    event.preventDefault();
    submitForm(form);
  });
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-route]");
    if (link) {
      event.preventDefault();
      routeTo(link.getAttribute("href"));
      return;
    }
    const action = event.target.closest("[data-action]");
    if (!action) return;
    if (action.dataset.action === "demo-role") {
      selectDemoAccount(action.dataset.demoRole, action.dataset.demoEmail);
      return;
    }
    handleAction(action).catch((error) => toast(error.message, "error"));
  });
  document.getElementById("global-search").addEventListener("input", (event) => {
    const value = event.target.value.trim();
    if (["candidates", "companies", "jobs", "applications", "interviews", "placement-process"].includes(state.route)) {
      state.search = value;
      clearTimeout(window.searchTimer);
      window.searchTimer = setTimeout(() => renderPage().catch((error) => toast(error.message, "error")), 250);
    } else if (value) {
      routeTo(`/candidates?q=${encodeURIComponent(value)}`);
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      document.getElementById("global-search").focus();
    }
    if (event.key === "Escape") closeModal();
  });
  window.addEventListener("popstate", () => {
    if (state.user) routeTo(location.pathname + location.search, false);
    else {
      showLogin();
      if (location.pathname === "/register") setAuthView("register");
    }
  });
}

async function initialize() {
  document.getElementById("footer-year").textContent = new Date().getFullYear();
  setupEvents();
  try {
    const result = await api("/api/auth/me");
    if (result.user) showWorkspace(result.user);
    else {
      showLogin();
      if (location.pathname === "/register") setAuthView("register");
    }
  } catch (error) {
    document.getElementById("login-error").textContent = `Workspace unavailable: ${error.message}`;
  }
}

document.addEventListener("DOMContentLoaded", initialize);
