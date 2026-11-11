// script.js — upload handling, API call, and dashboard rendering.

const dropzone = document.getElementById("dropzone");
const resumeInput = document.getElementById("resume-input");
const fileNameEl = document.getElementById("file-name");
const form = document.getElementById("analyze-form");
const jdInput = document.getElementById("jd-input");
const analyzeBtn = document.getElementById("analyze-btn");
const formError = document.getElementById("form-error");
const loading = document.getElementById("loading");
const inputPanel = document.getElementById("input-panel");
const results = document.getElementById("results");

let selectedFile = null;
const MAX_BYTES = 5 * 1024 * 1024;

// ---- File selection (click + drag & drop) --------------------------------
dropzone.addEventListener("click", () => resumeInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); resumeInput.click(); }
});
resumeInput.addEventListener("change", () => setFile(resumeInput.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

function setFile(file) {
  if (!file) return;
  const okType = /\.(pdf|docx)$/i.test(file.name);
  if (!okType) {
    showError("Unsupported file type. Please upload a PDF or DOCX file.");
    return;
  }
  if (file.size > MAX_BYTES) {
    showError("File is too large. Maximum size is 5 MB.");
    return;
  }
  selectedFile = file;
  fileNameEl.textContent = "✓ " + file.name;
  showError("");
}

// ---- Submit --------------------------------------------------------------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");

  if (!selectedFile) return showError("Please upload a resume file first.");
  if (!jdInput.value.trim()) return showError("Please paste a job description.");

  const data = new FormData();
  data.append("resume", selectedFile);
  data.append("job_description", jdInput.value.trim());

  setLoading(true);
  try {
    const res = await fetch("/analyze", { method: "POST", body: data });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Something went wrong.");
    render(json);
  } catch (err) {
    setLoading(false);
    showError(err.message);
  }
});

document.getElementById("reset-btn").addEventListener("click", () => {
  results.classList.add("hidden");
  inputPanel.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ---- UI helpers ----------------------------------------------------------
function showError(msg) { formError.textContent = msg; }
function setLoading(on) {
  analyzeBtn.disabled = on;
  loading.classList.toggle("hidden", !on);
  if (on) { inputPanel.classList.add("hidden"); results.classList.add("hidden"); }
}

function badge(text, cls) {
  const s = document.createElement("span");
  s.className = "badge " + cls;
  s.textContent = text;
  return s;
}

function fillBadges(el, items, cls, emptyMsg) {
  el.innerHTML = "";
  if (!items || !items.length) {
    el.innerHTML = `<span class="muted small">${emptyMsg}</span>`;
    return;
  }
  items.forEach((it) => el.appendChild(badge(it, cls)));
}

function fillList(el, items) {
  el.innerHTML = "";
  (items || []).forEach((it) => {
    const li = document.createElement("li");
    li.textContent = it;
    el.appendChild(li);
  });
}

// ---- Render dashboard ----------------------------------------------------
function render(d) {
  setLoading(false);
  inputPanel.classList.add("hidden");
  results.classList.remove("hidden");

  // Score ring + count-up
  animateScore(d.ats_score);
  document.getElementById("score-grade").textContent = "Grade " + d.grade;
  document.getElementById("score-level").textContent = d.level;
  document.getElementById("score-recommendation").textContent = d.recommendation;

  // Component bars
  const bars = document.getElementById("score-bars");
  bars.innerHTML = "";
  const comps = [
    ["TF-IDF", d.breakdown.tfidf],
    ["Keywords", d.breakdown.keywords],
    ["Sections", d.breakdown.sections],
  ];
  comps.forEach(([label, val]) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML =
      `<span>${label}</span><div class="bar-track"><div class="bar-fill"></div></div><span>${val}%</span>`;
    bars.appendChild(row);
    requestAnimationFrame(() => {
      row.querySelector(".bar-fill").style.width = Math.min(val, 100) + "%";
    });
  });

  // Keywords
  fillBadges(document.getElementById("matched-badges"), d.matched_keywords, "green",
    "No matched keywords.");
  fillBadges(document.getElementById("missing-badges"), d.missing_keywords, "red",
    "Nothing missing — great!");

  // Sections
  const secEl = document.getElementById("sections-list");
  secEl.innerHTML = "";
  const allSections = [...d.sections_found, ...d.sections_missing];
  allSections.forEach((sec) => {
    const present = d.sections_found.includes(sec);
    const chip = document.createElement("span");
    chip.className = "section-chip " + (present ? "present" : "absent");
    chip.textContent = (present ? "✓ " : "○ ") + sec;
    secEl.appendChild(chip);
  });
  fillBadges(document.getElementById("skills-badges"), d.resume_skills, "blue",
    "No known skills detected.");

  // AI feedback
  const fb = d.ai_feedback || {};
  const srcTag = document.getElementById("ai-source");
  if (fb.source === "claude") {
    srcTag.textContent = "Claude"; srcTag.className = "src-tag claude";
  } else {
    srcTag.textContent = "Offline mode"; srcTag.className = "src-tag fallback";
  }
  fillList(document.getElementById("strengths-list"), fb.strengths);
  fillList(document.getElementById("weaknesses-list"), fb.weaknesses);
  document.getElementById("improved-summary").value = fb.improved_summary || "";
  fillList(document.getElementById("rewrite-list"), fb.rewrite_suggestions);

  // Roadmap
  const road = document.getElementById("roadmap-list");
  road.innerHTML = "";
  if (!fb.skill_gap_roadmap || !fb.skill_gap_roadmap.length) {
    road.innerHTML = `<span class="muted small">No skill gaps identified.</span>`;
  } else {
    fb.skill_gap_roadmap.forEach((item) => {
      const div = document.createElement("div");
      div.className = "roadmap-item";
      div.innerHTML =
        `<strong>${item.skill || ""}</strong>` +
        (item.why ? `<p>${item.why}</p>` : "") +
        (item.resource ? `<p>📚 ${item.resource}</p>` : "");
      road.appendChild(div);
    });
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---- Animations ----------------------------------------------------------
function animateScore(score) {
  const ring = document.getElementById("ring-fg");
  const numberEl = document.getElementById("score-number");
  const circumference = 327; // 2πr, r=52

  // Color by grade band.
  const color =
    score >= 80 ? "#16a34a" : score >= 50 ? "#2563eb" :
    score >= 35 ? "#ea580c" : "#dc2626";
  ring.style.stroke = color;
  numberEl.style.color = color;

  requestAnimationFrame(() => {
    ring.style.strokeDashoffset = circumference * (1 - score / 100);
  });

  // Count-up number.
  const duration = 1200;
  const start = performance.now();
  function tick(now) {
    const p = Math.min((now - start) / duration, 1);
    numberEl.textContent = Math.round(p * score);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
