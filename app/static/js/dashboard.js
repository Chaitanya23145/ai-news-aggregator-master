/* ==========================================================================
   SYNAPSE AI — BESPOKE FRONTEND APPLICATION LOGIC
   Engineered for Clarity, Seamless Performance & Bespoke Aesthetics
   ========================================================================== */

// --- Global Application State ---
const state = {
  digests: [],
  filters: {
    source: "all",
    search: "",
    hours: 168,
    bookmarksOnly: false
  },
  bookmarks: new Set(JSON.parse(localStorage.getItem("synapse_bookmarks") || "[]")),
  activeSpeechUtterance: null,
  speakingId: null,
  stats: {
    total_digests: 0,
    subscribers_count: 0,
    model: "llama-3.3-70b-versatile",
    db_type: "sqlite"
  }
};

// --- DOM Ready Lifecycle ---
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  setupScrollReveal();
  updateBookmarksBadge();

  // Parallel data loading
  await Promise.all([
    fetchStats(),
    fetchDigests()
  ]);
}

// ---------------- API Calls ----------------
async function fetchStats() {
  try {
    const res = await fetch("/api/stats");
    if (res.ok) {
      const data = await res.json();
      state.stats = data;
      renderStatsHeader(data);
    }
  } catch (err) {
    console.warn("Notice: Unable to fetch server stats:", err);
  }
}

async function fetchDigests() {
  const container = document.getElementById("articles-grid");
  const emptyState = document.getElementById("empty-state");

  try {
    const params = new URLSearchParams({
      hours: state.filters.hours,
      source: state.filters.source
    });

    const res = await fetch(`/api/digests?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to load briefings");

    const data = await res.json();
    state.digests = data.digests || [];
    renderArticles();
  } catch (err) {
    console.error("Error fetching digests:", err);
    if (container) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <h3>Connection Notice</h3>
          <p>Could not retrieve briefings. Please verify the server connection.</p>
          <button class="btn-ghost" onclick="fetchDigests()">Retry Connection</button>
        </div>
      `;
    }
    showToast("Failed to connect to briefing server.", "error");
  }
}

// ---------------- UI Rendering ----------------
function renderStatsHeader(stats) {
  // Update subscribers count badge
  const subBadge = document.getElementById("stat-subscribers-badge");
  if (subBadge) {
    subBadge.innerText = stats.subscribers_count || 0;
  }

  // Update hero model tag if available
  const modelTag = document.getElementById("hero-model-tag");
  if (modelTag && stats.model) {
    const friendlyName = stats.model.includes("llama-3.3") ? "Groq Llama-3.3-70B" : stats.model;
    modelTag.innerText = friendlyName;
  }

  // Footer status indicator
  const footerStatus = document.getElementById("footer-status-text");
  if (footerStatus) {
    footerStatus.innerText = `${stats.total_digests || 0} Briefings Curated • Engine Live`;
  }
}

function renderArticles() {
  const container = document.getElementById("articles-grid");
  const emptyState = document.getElementById("empty-state");
  if (!container) return;

  // Apply Client-Side Search and Bookmark filters
  let filtered = [...state.digests];

  if (state.filters.bookmarksOnly) {
    filtered = filtered.filter(item => state.bookmarks.has(item.id));
  }

  if (state.filters.search.trim()) {
    const query = state.filters.search.toLowerCase().trim();
    filtered = filtered.filter(item => {
      const title = (item.title || "").toLowerCase();
      const summary = (item.summary || item.full_summary || "").toLowerCase();
      const tags = (item.key_takeaways || []).join(" ").toLowerCase();
      return title.includes(query) || summary.includes(query) || tags.includes(query);
    });
  }

  if (filtered.length === 0) {
    container.style.display = "none";
    if (emptyState) emptyState.style.display = "block";
    return;
  }

  container.style.display = "grid";
  if (emptyState) emptyState.style.display = "none";

  container.innerHTML = filtered.map(item => createArticleCardHTML(item)).join("");

  // Re-observe newly rendered cards for smooth scroll entrance
  observeNewCards();
}

function createArticleCardHTML(item) {
  const isBookmarked = state.bookmarks.has(item.id);
  const formattedDate = formatDate(item.published_at || item.created_at);
  const sourceLabel = formatSourceLabel(item.article_type);
  const preview = cleanSummaryPreview(item.summary || item.full_summary || "Executive research synthesis available in briefing.");

  // Escape attributes for inline modal openers
  const safeTitle = escapeHTML(item.title);

  return `
    <article class="article-card reveal-on-scroll" data-id="${item.id}">
      <div>
        <div class="card-top-row">
          <span class="card-source-pill">${sourceLabel}</span>
          <span class="card-date">${formattedDate}</span>
        </div>

        <h3 class="card-title">
          <a href="#" class="card-title-link" onclick="openArticleModal('${item.id}'); return false;">
            ${safeTitle}
          </a>
        </h3>

        <p class="card-preview">${escapeHTML(preview)}</p>
      </div>

      <div class="card-footer-row">
        <button class="btn-read-briefing" onclick="openArticleModal('${item.id}')">
          <span>Read Briefing</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </button>

        <div class="card-actions-slot">
          <button
            class="card-action-btn ${isBookmarked ? 'active' : ''}"
            onclick="toggleBookmark('${item.id}', this)"
            title="${isBookmarked ? 'Remove Bookmark' : 'Save Bookmark'}"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
            </svg>
          </button>

          <a
            href="${item.url || '#'}"
            target="_blank"
            rel="noopener noreferrer"
            class="card-action-btn"
            title="Open Original Publication ↗"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg>
          </a>
        </div>
      </div>
    </article>
  `;
}

// ---------------- 1-Click Subscription Handler ----------------
async function handleHeroSubscribe(event, source = "hero") {
  if (event) event.preventDefault();

  const isBottom = source === "bottom";
  const emailInput = document.getElementById(isBottom ? "bottom-subscribe-email" : "hero-subscribe-email");
  const submitBtn = event?.target?.querySelector("button[type='submit']") || document.getElementById("btn-hero-subscribe");
  const feedback = document.getElementById("hero-subscribe-feedback");

  const email = emailInput?.value?.trim();

  if (!email || !email.includes("@")) {
    showToast("Please enter a valid email address.", "error");
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = "Activating...";
  }

  try {
    const res = await fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Subscription failed. Please retry.");
    }

    if (feedback) {
      feedback.style.display = "block";
      feedback.innerText = `✓ Automated briefing dispatched to ${email}. Check your inbox!`;
    }

    showToast(`✓ Subscribed! Daily AI briefings activated for ${email}`, "success");
    if (emailInput) emailInput.value = "";

    // Refresh stats counter
    await fetchStats();
  } catch (err) {
    showToast(err.message, "error");
    if (feedback) {
      feedback.style.display = "block";
      feedback.style.background = "rgba(239, 68, 68, 0.1)";
      feedback.style.borderColor = "rgba(239, 68, 68, 0.3)";
      feedback.style.color = "#F87171";
      feedback.innerText = `Notice: ${err.message}`;
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Subscribe Free</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
    }
  }
}

// ---------------- Article Reader Modal ----------------
function openArticleModal(id) {
  const item = state.digests.find(d => d.id === id);
  if (!item) return;

  const modal = document.getElementById("article-modal");
  const title = document.getElementById("modal-article-title");
  const sourceTag = document.getElementById("modal-article-source-tag");
  const meta = document.getElementById("modal-article-meta");
  const body = document.getElementById("modal-article-body");
  const originalLink = document.getElementById("modal-article-link");

  if (title) title.innerText = item.title || "Untitled Research";
  if (sourceTag) sourceTag.innerText = formatSourceLabel(item.article_type);
  if (meta) {
    meta.innerHTML = `
      <span>Published: ${formatDate(item.published_at || item.created_at)}</span>
      <span>•</span>
      <span>Relevance Score: ${item.relevance_score ? Number(item.relevance_score).toFixed(1) : '9.2'}/10</span>
      <span>•</span>
      <span>Curated via Groq LPU</span>
    `;
  }

  // Construct structured body
  let prose = "";
  if (item.summary) {
    prose += `<p>${escapeHTML(item.summary)}</p>`;
  }
  if (item.key_takeaways && item.key_takeaways.length > 0) {
    prose += `<h4>Key Findings & Architecture:</h4><ul>`;
    item.key_takeaways.forEach(point => {
      prose += `<li>${escapeHTML(point)}</li>`;
    });
    prose += `</ul>`;
  }
  if (item.full_summary && item.full_summary !== item.summary) {
    prose += `<h4>Deep Technical Analysis:</h4><p>${escapeHTML(item.full_summary)}</p>`;
  }

  if (body) body.innerHTML = prose || "<p>Detailed executive summary is loading...</p>";
  if (originalLink) originalLink.href = item.url || "#";

  state.activeModalItem = item;
  if (modal) modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeArticleModal() {
  const modal = document.getElementById("article-modal");
  if (modal) modal.classList.remove("open");
  document.body.style.overflow = "";

  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
  }
}

function handleBackdropClick(event) {
  if (event.target.classList.contains("modal-backdrop")) {
    event.target.classList.remove("open");
    document.body.style.overflow = "";
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }
  }
}

// ---------------- Text-to-Speech Audio ----------------
function toggleModalSpeech() {
  if (!window.speechSynthesis) {
    showToast("Text-to-speech audio is not supported in this browser.", "info");
    return;
  }

  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    showToast("Audio playback stopped.", "info");
    return;
  }

  const item = state.activeModalItem;
  if (!item) return;

  const textToRead = `${item.title}. ${item.summary || ""}. Key takeaways: ${(item.key_takeaways || []).join(". ")}`;
  const utterance = new SpeechSynthesisUtterance(textToRead);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;

  utterance.onend = () => {
    showToast("Audio briefing finished.", "info");
  };

  window.speechSynthesis.speak(utterance);
  showToast("Playing synthesized audio briefing...", "info");
}

// ---------------- Filters & Search Handling ----------------
function setupEventListeners() {
  // Search input
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      state.filters.search = e.target.value;
      if (clearBtn) clearBtn.style.display = e.target.value ? "block" : "none";
      renderArticles();
    });
  }

  // Keyboard navigation for Modal (ESC to close)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeArticleModal();
      closePipelineModal();
      closeSendEmailModal();
    }
  });
}

function clearSearch() {
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");
  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.style.display = "none";
  state.filters.search = "";
  renderArticles();
}

function setSourceFilter(source) {
  state.filters.source = source;

  // Update chip active classes
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.classList.toggle("active", chip.getAttribute("data-source") === source);
  });

  fetchDigests();
}

function handleTimeWindowChange(hours) {
  state.filters.hours = parseInt(hours, 10);
  fetchDigests();
}

function toggleBookmarksFilter() {
  state.filters.bookmarksOnly = !state.filters.bookmarksOnly;
  const btn = document.getElementById("btn-bookmarks-filter");
  if (btn) btn.classList.toggle("active", state.filters.bookmarksOnly);
  renderArticles();
}

function resetFilters() {
  state.filters.source = "all";
  state.filters.search = "";
  state.filters.bookmarksOnly = false;

  const searchInput = document.getElementById("search-input");
  if (searchInput) searchInput.value = "";

  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.classList.toggle("active", chip.getAttribute("data-source") === "all");
  });

  const btn = document.getElementById("btn-bookmarks-filter");
  if (btn) btn.classList.remove("active");

  fetchDigests();
}

// ---------------- Bookmarks System ----------------
function toggleBookmark(id, buttonEl) {
  if (state.bookmarks.has(id)) {
    state.bookmarks.delete(id);
    if (buttonEl) buttonEl.classList.remove("active");
    showToast("Removed from saved bookmarks.", "info");
  } else {
    state.bookmarks.add(id);
    if (buttonEl) buttonEl.classList.add("active");
    showToast("Saved to your personal bookmarks.", "success");
  }

  localStorage.setItem("synapse_bookmarks", JSON.stringify([...state.bookmarks]));
  updateBookmarksBadge();

  if (state.filters.bookmarksOnly) {
    renderArticles();
  }
}

function updateBookmarksBadge() {
  const pill = document.getElementById("bookmarks-count-pill");
  if (pill) {
    pill.innerText = state.bookmarks.size;
  }
}

// ---------------- Pipeline Modal ----------------
function openPipelineModal() {
  const modal = document.getElementById("pipeline-modal");
  if (modal) modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closePipelineModal() {
  const modal = document.getElementById("pipeline-modal");
  if (modal) modal.classList.remove("open");
  document.body.style.overflow = "";
}

async function triggerPipeline() {
  const hoursSelect = document.getElementById("pipeline-hours");
  const hours = parseInt(hoursSelect?.value || "24", 10);
  const statusBox = document.getElementById("pipeline-status-box");
  const btn = document.getElementById("btn-run-pipeline-confirm");

  if (btn) btn.disabled = true;
  if (statusBox) {
    statusBox.style.display = "block";
    statusBox.style.background = "rgba(255, 255, 255, 0.05)";
    statusBox.style.color = "#E2E8F0";
    statusBox.innerText = "Running autonomous scrapers & Groq Llama-3.3-70B synthesis...";
  }

  try {
    const res = await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours: hours, top_n: 10 })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Pipeline run failed");

    if (statusBox) {
      statusBox.style.background = "rgba(16, 185, 129, 0.1)";
      statusBox.style.color = "#34D399";
      statusBox.innerText = "✓ Sync completed! Refreshing research briefings...";
    }
    showToast("✓ Research pipeline sync finished successfully!", "success");

    setTimeout(() => {
      closePipelineModal();
      fetchDigests();
      fetchStats();
    }, 1400);
  } catch (err) {
    if (statusBox) {
      statusBox.style.background = "rgba(239, 68, 68, 0.1)";
      statusBox.style.color = "#F87171";
      statusBox.innerText = `Error: ${err.message}`;
    }
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------------- Email Digest Modal ----------------
function openSendEmailModal() {
  const modal = document.getElementById("send-email-modal");
  if (modal) modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeSendEmailModal() {
  const modal = document.getElementById("send-email-modal");
  if (modal) modal.classList.remove("open");
  document.body.style.overflow = "";
}

async function dispatchDigestEmail() {
  const recipientInput = document.getElementById("digest-email-recipient");
  const limitSelect = document.getElementById("digest-email-limit");
  const statusBox = document.getElementById("digest-email-status");
  const btn = document.getElementById("btn-send-digest-confirm");

  const recipient = recipientInput?.value?.trim() || null;
  const limit = parseInt(limitSelect?.value || "10", 10);

  if (btn) btn.disabled = true;
  if (statusBox) {
    statusBox.innerHTML = `<span style="color:#94A3B8; font-size:13px;">Connecting to SMTP server & formatting briefing...</span>`;
  }

  try {
    const res = await fetch("/api/digest/send-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_email: recipient,
        hours: 168,
        limit: limit
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Dispatch failed");

    if (statusBox) {
      statusBox.innerHTML = `
        <span style="color:#34D399; font-weight:600; font-size:13px;">✓ DISPATCHED TO ${data.recipients_count} SUBSCRIBERS</span>
      `;
    }
    showToast(`✓ Digest sent to ${data.recipients_count} subscriber(s)!`, "success");

    setTimeout(() => {
      closeSendEmailModal();
    }, 1600);
  } catch (err) {
    if (statusBox) {
      statusBox.innerHTML = `<span style="color:#F87171; font-size:13px;">Error: ${err.message}</span>`;
    }
    showToast(err.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------------- Micro-Interactions & Scroll Reveal ----------------
function setupScrollReveal() {
  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll(".reveal-on-scroll").forEach(el => observer.observe(el));
}

function observeNewCards() {
  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });

  document.querySelectorAll(".article-card.reveal-on-scroll:not(.revealed)").forEach(el => observer.observe(el));
}

// ---------------- Toast System ----------------
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const icon = type === "success" ? "✓" : (type === "error" ? "✕" : "ℹ");
  toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${escapeHTML(message)}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.25s ease";
    setTimeout(() => toast.remove(), 260);
  }, 3600);
}

// ---------------- Utilities ----------------
function formatSourceLabel(rawSource) {
  const map = {
    "arxiv_ai": "arXiv CS.AI",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "huggingface": "Hugging Face",
    "techcrunch_ai": "TechCrunch",
    "youtube": "YouTube AI"
  };
  return map[rawSource] || (rawSource ? rawSource.toUpperCase() : "RESEARCH");
}

function formatDate(isoStr) {
  if (!isoStr) return "Recent";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric"
    });
  } catch {
    return "Recent";
  }
}

function cleanSummaryPreview(text) {
  if (!text) return "";
  return text.replace(/[#*`_]/g, "").trim();
}

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
