if ("scrollRestoration" in history) history.scrollRestoration = "manual";
window.scrollTo(0, 0);
const state = { status: null, topic: "gta6", selected: null, analysis: null, selectedMoment: null, selectedDraft: null };
const $ = (selector) => document.querySelector(selector);
const browserSessionToggle = $("#browser-session-toggle");
browserSessionToggle.checked = window.localStorage.getItem("trendclip-browser-session") === "on";
browserSessionToggle.addEventListener("change", () => {
  window.localStorage.setItem("trendclip-browser-session", browserSessionToggle.checked ? "on" : "off");
  if (state.status) renderStories(state.status.discovery[state.topic]);
});

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.style.background = error ? "#ffd2db" : "#f4f6f9";
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3600);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function action(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-TrendClip-Action": "1" },
    body: JSON.stringify(body),
  });
}

function uniqueStories(report) {
  const seen = new Set();
  return (report?.candidates || []).filter((item) => {
    const key = item.title.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 12);
}

function compactNumber(value) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function updateRightsState() {
  const button = $("#analyze-button");
  const ready = Boolean(state.selected);
  button.disabled = !ready;
  button.textContent = ready ? "Download and find the best moments" : "Choose a video first";
  return { ready, message: ready ? "Ready" : "Choose a video first." };
}

function selectStory(candidate) {
  state.selected = candidate;
  state.analysis = null;
  state.selectedMoment = null;
  state.selectedDraft = null;
  $("#selection-empty").hidden = true;
  $("#selection-content").hidden = false;
  $("#selected-title").textContent = candidate.title;
  const velocity = candidate.views_per_hour != null ? `${compactNumber(candidate.views_per_hour)} views/hour` : (candidate.views != null ? `${compactNumber(candidate.views)} views · upload time unverified` : (candidate.discovery_kind === "manual-youtube-url" ? "manual source" : (candidate.score != null ? `evidence score ${Math.round(candidate.score)}` : "ranking unavailable")));
  $("#selected-source").textContent = `${candidate.source_name} · ${Math.round(candidate.age_hours || 0)} hours old · ${velocity}`;
  $("#selected-link").href = candidate.url;
  $("#step-story").className = "workflow-step done";
  $("#step-analyze").className = "workflow-step current";
  $("#step-create").className = "workflow-step";
  $("#moment-section").hidden = true;
  updateRightsState();
  $("#analysis-progress").textContent = "";
  $("#hook-input").value = candidate.title;
  renderStories(state.status.discovery[state.topic]);
}

function formatTime(seconds) {
  const value = Math.max(0, Math.round(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

function renderMoments(analysis) {
  state.analysis = analysis;
  const presented = (analysis.drafts || []).map((draft) => {
    const candidate = analysis.candidates.find((item) => item.n === draft.candidate_n);
    return candidate ? { draft, candidate } : null;
  }).filter(Boolean);
  const rows = presented;
  const list = $("#moment-list");
  list.replaceChildren();
  const semanticNote = $("#semantic-note");
  const assistance = analysis.codex_assistance || {};
  semanticNote.hidden = !assistance.used;
  semanticNote.textContent = assistance.used ? `Codex-assisted ordering: ${assistance.rationale}` : "";
  if (!rows.length) {
    state.selectedMoment = null;
    state.selectedDraft = null;
    const empty = document.createElement("div");
    empty.className = "selection-empty";
    empty.textContent = analysis.editorial_message || "No strong complete moment was found. Try another source.";
    list.append(empty);
    const renderButton = $("#render-source-button");
    renderButton.disabled = true;
    renderButton.textContent = "Choose another video";
    $("#moment-section").hidden = false;
    $("#step-analyze").className = "workflow-step done";
    $("#step-create").className = "workflow-step";
    return;
  }
  if (!rows.some((item) => item.candidate.n === state.selectedMoment?.n)) {
    state.selectedMoment = rows[0]?.candidate || null;
  }
  state.selectedDraft = rows.find((item) => item.candidate.n === state.selectedMoment?.n)?.draft || rows[0]?.draft || null;
  for (const entry of rows) {
    const moment = entry.candidate;
    const label = document.createElement("label");
    label.className = `moment${state.selectedMoment?.n === moment.n ? " selected" : ""}`;
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "moment";
    radio.checked = state.selectedMoment?.n === moment.n;
    radio.addEventListener("change", () => {
      state.selectedMoment = moment;
      state.selectedDraft = entry.draft;
      renderMoments({ ...analysis, candidates: analysis.candidates });
    });
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    const layoutName = { balanced: "Balanced story", punch: "Punchy action", clean: "Clean focus" }[entry.draft.layout] || "Balanced story";
    title.textContent = `${entry.draft.label} · ${layoutName} · ${formatTime(moment.start)}–${formatTime(moment.end)} · ${Math.round(moment.duration)} sec`;
    const detail = document.createElement("small");
    const warnings = (moment.warnings || []).length ? ` · Check: ${moment.warnings.join(", ")}` : "";
    detail.textContent = `${entry.draft.reason} · ${moment.why.join(", ")} · ${moment.text || "No speech detected"}${warnings}`;
    copy.append(title, detail);
    const score = document.createElement("span");
    score.className = "moment-score";
    score.textContent = moment.quality_score == null ? "Quality pending" : `Quality ${moment.quality_score}/10`;
    label.append(radio, copy, score);
    list.append(label);
  }
  const selectedDraft = rows.find((item) => item.candidate.n === state.selectedMoment?.n)?.draft;
  $("#render-source-button").disabled = false;
  $("#render-source-button").textContent = selectedDraft?.recommended ? "Create recommended draft" : "Create selected draft";
  $("#moment-section").hidden = false;
  $("#step-analyze").className = "workflow-step done";
  $("#step-create").className = "workflow-step current";
}

function renderStories(report) {
  const list = $("#story-list");
  list.replaceChildren();
  const stories = uniqueStories(report);
  $("#nav-story-count").textContent = String(stories.length);
  const generated = report?.generated_at ? new Date(report.generated_at) : null;
  $("#last-updated").textContent = generated ? `Updated ${generated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Not refreshed";
  if (!stories.length) {
    const empty = document.createElement("div");
    empty.className = "selection-empty";
    empty.textContent = "No GTA 6 videos are cached yet. Studio is searching automatically.";
    list.append(empty);
    return;
  }
  for (const story of stories) {
    const label = document.createElement("label");
    const needsSession = story.availability === "requires-sign-in";
    const unavailable = needsSession && !browserSessionToggle.checked;
    label.className = `story${state.selected?.url === story.url ? " selected" : ""}${unavailable ? " unavailable" : ""}`;
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "story";
    radio.disabled = unavailable;
    radio.checked = state.selected?.url === story.url;
    radio.addEventListener("change", () => selectStory(story));
    const image = document.createElement(story.thumbnail ? "img" : "span");
    image.className = `story-thumbnail${story.thumbnail ? "" : " placeholder"}`;
    if (story.thumbnail) {
      image.src = story.thumbnail;
      image.alt = "";
      image.loading = "lazy";
    }
    const copy = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = story.title;
    const meta = document.createElement("p");
    const age = story.age_hours == null ? "Age unavailable" : `${Math.round(story.age_hours)} hours ago`;
    meta.textContent = needsSession
      ? `${story.source_name} · Chrome sign-in required${unavailable ? "; enable it in Settings" : " · session enabled"}`
      : `${story.source_name} · ${age}`;
    copy.append(title, meta);
    const score = document.createElement("span");
    score.className = "story-score";
    score.textContent = story.views_per_hour != null ? `${compactNumber(story.views_per_hour)} views/h` : (story.views != null ? `${compactNumber(story.views)} views` : (story.discovery_kind === "manual-youtube-url" ? "Manual" : (story.score != null ? `Evidence ${Math.round(story.score)}` : "Unranked")));
    label.append(radio, image, copy, score);
    list.append(label);
  }
}

function renderExport(latest) {
  const exists = Boolean(latest);
  $("#nav-export-count").textContent = exists ? "1" : "0";
  $("#export-empty").hidden = exists;
  $("#export-content").hidden = !exists;
  if (!exists) return;
  const valid = Boolean(latest.validation?.valid);
  const chip = $("#validation-chip");
  chip.textContent = valid ? "Validated" : "Needs attention";
  chip.className = `chip${valid ? " valid" : ""}`;
  $("#video-preview").src = `${latest.video_url}?v=${latest.validation?.sha256 || Date.now()}`;
  $("#export-title").textContent = latest.metadata?.suggested_title || "Generated video";
  $("#export-date").textContent = `${latest.topic.toUpperCase()} · ${latest.date}`;
  $("#export-duration").textContent = `${latest.validation?.observed?.duration_seconds || "—"} sec`;
  $("#download-link").href = latest.video_url;
  const variations = $("#variation-list");
  variations.replaceChildren();
  for (const item of latest.variations || []) {
    const link = document.createElement("a");
    link.className = "variation-link";
    link.href = item.video_url;
    link.download = "";
    const label = item.kind.split("-").map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
    link.textContent = `${label} · ${item.layout}${item.valid ? " · validated" : ""}`;
    link.addEventListener("click", () => { $("#video-preview").src = item.video_url; });
    variations.append(link);
  }
  $("#step-review").className = "workflow-step done";
}

function renderJobs(jobs = []) {
  $("#nav-activity-count").textContent = String(jobs.length);
  const list = $("#jobs-list");
  list.replaceChildren();
  for (const job of jobs.slice(0, 10)) {
    const row = document.createElement("div");
    row.className = "job-record";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${job.profile || "Media"} · ${job.stage || "unknown"}`;
    const detail = document.createElement("small");
    detail.textContent = job.message || job.updated_at || job.job_id;
    copy.append(title, detail);
    row.append(copy);
    if (job.status === "active") {
      const cancel = document.createElement("button");
      cancel.className = "button secondary compact-button";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", async () => {
        try {
          const result = await action("/api/cancel-job", { job_id: job.job_id });
          renderStatus(result.status);
          showToast("Job cancelled; cached work is available for retry");
        } catch (error) { showToast(error.message, true); }
      });
      row.append(cancel);
    }
    list.append(row);
  }
}

function renderStatus(status) {
  state.status = status;
  const select = $("#topic-select");
  const current = state.topic;
  select.replaceChildren();
  const names = Object.fromEntries((status.profiles || []).map((profile) => [profile.slug, profile.name]));
  for (const topic of status.topics) {
    const option = document.createElement("option");
    option.value = topic;
    option.textContent = names[topic] || topic.toUpperCase();
    select.append(option);
  }
  state.topic = status.topics.includes(current) ? current : (select.value || "gta6");
  select.value = state.topic;
  select.disabled = status.topics.length === 1;
  renderStories(status.discovery[state.topic]);
  renderExport(status.latest_export);
  renderJobs(status.jobs);
  const codex = status.codex || {};
  $("#codex-toggle").checked = Boolean(codex.enabled);
  $("#codex-status").textContent = codex.enabled ? (codex.authenticated ? `Enabled · ${codex.version || "Codex CLI"}` : `Enabled but unavailable · ${codex.reason || "sign-in required"}`) : `Disabled by default${codex.available ? ` · ${codex.version || "Codex CLI detected"}` : ""}.`;
  $("#test-codex-button").disabled = !(codex.enabled && codex.authenticated);
}

$("#codex-toggle").addEventListener("change", async (event) => {
  const enabled = event.currentTarget.checked;
  try {
    const result = await action("/api/settings", { codex_enabled: enabled });
    renderStatus(result.status);
    showToast(enabled ? "Codex assistance enabled for bounded optional tasks" : "Codex assistance disabled");
  } catch (error) {
    event.currentTarget.checked = !enabled;
    showToast(error.message, true);
  }
});

$("#test-codex-button").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const result = $("#codex-test-result");
  button.disabled = true;
  button.textContent = "Testing…";
  result.hidden = true;
  try {
    const response = await action("/api/test-codex", {});
    result.textContent = `Passed · order ${response.result.ranked_candidate_ids.join(" → ")} · ${response.result.rationale}`;
    result.hidden = false;
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.textContent = "Test Codex safely";
    button.disabled = false;
  }
});

async function refreshStatus() {
  renderStatus(await request("/api/status"));
}

$("#topic-select").addEventListener("change", (event) => {
  state.topic = event.target.value;
  state.selected = null;
  state.analysis = null;
  state.selectedMoment = null;
  $("#selection-empty").hidden = false;
  $("#selection-content").hidden = true;
  $("#moment-section").hidden = true;
  $("#query-input").value = "";
  renderStories(state.status.discovery[state.topic]);
  if (!state.status.discovery[state.topic]) refreshDiscovery();
});

async function refreshDiscovery(button = null) {
  const activeButton = button || $("#refresh-button");
  const requestedTopic = state.topic;
  activeButton.disabled = true;
  activeButton.textContent = "Searching…";
  $("#last-updated").textContent = "Searching YouTube…";
  const list = $("#story-list");
  list.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "selection-empty discovery-loading";
  loading.textContent = "Checking recent uploads, view counts, and video details…";
  list.append(loading);
  try {
    const result = await action("/api/discover", { topic: requestedTopic, query: $("#query-input").value.trim() });
    state.status.discovery[requestedTopic] = result.report;
    if (state.topic !== requestedTopic) return;
    state.selected = null;
    state.analysis = null;
    state.selectedMoment = null;
    renderStories(result.report);
    $("#selection-empty").hidden = false;
    $("#selection-content").hidden = true;
    $("#moment-section").hidden = true;
    showToast(`${result.report.candidate_count} current videos found`);
  } catch (error) {
    if (state.topic === requestedTopic) renderStories(state.status.discovery[requestedTopic]);
    showToast(error.message, true);
  } finally {
    activeButton.disabled = false;
    activeButton.textContent = "Refresh stories";
  }
}

$("#refresh-button").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  await refreshDiscovery(button);
});

$("#analyze-button").addEventListener("click", async (event) => {
  if (!state.selected) return;
  const rightsState = updateRightsState();
  if (!rightsState.ready) {
    showToast(rightsState.message, true);
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Downloading and analyzing…";
  $("#analysis-progress").textContent = "Downloading source, extracting audio, transcribing speech, and scoring moments. The first transcription may take several minutes.";
  $("#step-analyze").className = "workflow-step current";
  try {
    const result = await action("/api/analyze-source", {
      topic: state.topic,
      candidate_url: state.selected.url,
      rights: {
        category: "third-party-review-draft",
        permission_reference: "",
        allowed_platforms: ["youtube", "facebook", "tiktok"],
        commercial_use_scope: "unknown",
        attribution_required: false,
        attribution_note: "",
      },
      use_browser_cookies: browserSessionToggle.checked,
      max_minutes: 90,
    });
    state.status = result.status;
    renderMoments(result.analysis);
    if (result.analysis.editorial_status === "no-suitable-moment") {
      $("#analysis-progress").textContent = result.analysis.editorial_message;
      showToast("Analysis complete—try another source for a stronger moment");
    } else {
      $("#analysis-progress").textContent = `${result.analysis.drafts?.length || 0} ready drafts assembled from ${result.analysis.candidates.length} candidate moments using transcription, loudness${result.analysis.signals.heatmap ? ", and replay data" : ""}.`;
      showToast("Analysis complete—the recommended draft is ready to create");
    }
  } catch (error) {
    showToast(error.message, true);
    $("#analysis-progress").textContent = "Analysis failed. Review the message and try another source.";
  } finally {
    button.disabled = false;
    button.textContent = "Download and find the best moments";
  }
});

$("#render-source-button").addEventListener("click", async (event) => {
  if (!state.analysis || !state.selectedMoment) return;
  const destinations = [...document.querySelectorAll('input[name="destination"]:checked')].map((input) => input.value);
  if (!destinations.length) {
    showToast("Choose at least one publishing destination", true);
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Creating and validating clip…";
  try {
    const result = await action("/api/render-source-clip", {
      job_id: state.analysis.job_id,
      pick: state.selectedMoment.n,
      topic: state.topic,
      date: new Date().toISOString().slice(0, 10),
      hook: $("#hook-input").value.trim(),
      draft_kind: state.selectedDraft?.kind || "best-story",
      layout: state.selectedDraft?.layout || "balanced",
      destinations,
    });
    renderStatus(result.status);
    $("#step-create").className = "workflow-step done";
    $("#step-review").className = "workflow-step current";
    showToast("Your source clip is ready for review");
    $("#review").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    const currentDraft = (state.analysis?.drafts || []).find((item) => item.candidate_n === state.selectedMoment?.n);
    button.textContent = currentDraft?.recommended ? "Create recommended draft" : "Create selected draft";
  }
});

$("#show-upload-button").addEventListener("click", () => {
  showToast("Download the reviewed package and upload it manually on your chosen platform.");
});

refreshStatus().catch((error) => showToast(error.message, true));
window.setInterval(() => refreshStatus().catch(() => {}), 30000);

