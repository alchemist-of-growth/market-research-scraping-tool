document.addEventListener("DOMContentLoaded", () => {
  // --- UI Elements ---
  const inputStage = document.getElementById("input-stage");
  const loadingStage = document.getElementById("loading-stage");
  const errorStage = document.getElementById("error-stage");
  const resultsStage = document.getElementById("results-stage");
  
  const analysisForm = document.getElementById("analysis-form");
  const targetUrlInput = document.getElementById("target-url");
  const activeUrlDisplay = document.getElementById("active-url-display");
  const btnNewAnalysis = document.getElementById("btn-new-analysis");
  const btnTryAgain = document.getElementById("btn-try-again");
  const historyList = document.getElementById("history-list");
  
  // Settings Elements
  const btnOpenSettings = document.getElementById("btn-open-settings");
  const btnOpenSettingsError = document.getElementById("btn-open-settings-error");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const settingsModal = document.getElementById("settings-modal");
  const geminiKeyInput = document.getElementById("gemini-key-input");
  const btnSaveKey = document.getElementById("btn-save-key");
  const btnClearKey = document.getElementById("btn-clear-key");
  const apiStatusText = document.getElementById("api-status-text");
  
  // Tab Elements
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  
  // Checklists (Loading indicators)
  const checkScrape = document.getElementById("check-scrape");
  const checkImages = document.getElementById("check-images");
  const checkGemini = document.getElementById("check-gemini");
  const checkRender = document.getElementById("check-render");
  
  // --- Data State ---
  let currentAnalysisData = null;
  let activeTab = "tab-overview";
  
  // --- Initialize App ---
  loadApiKey();
  renderHistory();
  
  // --- Event Listeners ---
  
  // Form submission (URL lookup)
  analysisForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const url = targetUrlInput.value.strip ? targetUrlInput.value.strip() : targetUrlInput.value;
    if (url) {
      triggerAnalysis(url);
    }
  });
  
  btnNewAnalysis.addEventListener("click", () => {
    showStage("input");
    targetUrlInput.value = "";
    targetUrlInput.focus();
    activeUrlDisplay.innerHTML = `
      <h2>Get Started</h2>
      <p>Analyze any product website instantly</p>
    `;
  });
  
  btnTryAgain.addEventListener("click", () => {
    const url = targetUrlInput.value;
    if (url) triggerAnalysis(url);
    else showStage("input");
  });
  
  // Modal toggle listeners
  btnOpenSettings.addEventListener("click", () => settingsModal.classList.add("active"));
  btnOpenSettingsError.addEventListener("click", () => settingsModal.classList.add("active"));
  btnCloseSettings.addEventListener("click", () => settingsModal.classList.remove("active"));
  
  // Save API Key
  btnSaveKey.addEventListener("click", () => {
    const key = geminiKeyInput.value.trim();
    if (key) {
      localStorage.setItem("gemini_api_key", key);
      apiStatusText.textContent = "Using Custom Key";
      apiStatusText.parentElement.querySelector(".status-indicator").style.backgroundColor = "#10b981"; // Online
      settingsModal.classList.remove("active");
      alert("Custom Gemini API Key saved successfully.");
    } else {
      alert("Please enter a valid key.");
    }
  });
  
  // Clear API key
  btnClearKey.addEventListener("click", () => {
    localStorage.removeItem("gemini_api_key");
    geminiKeyInput.value = "";
    apiStatusText.textContent = "Using Server Key";
    settingsModal.classList.remove("active");
    alert("Custom key cleared. Defaulting to Server API key (if configured).");
  });
  
  // Tabs Navigation
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      
      btn.classList.add("active");
      document.getElementById(targetTab).classList.add("active");
      activeTab = targetTab;
    });
  });
  
  // --- Stages UI Swapper ---
  function showStage(stageName) {
    inputStage.classList.remove("active");
    loadingStage.classList.remove("active");
    errorStage.classList.remove("active");
    resultsStage.classList.remove("active");
    
    if (stageName === "input") inputStage.classList.add("active");
    else if (stageName === "loading") loadingStage.classList.add("active");
    else if (stageName === "error") errorStage.classList.add("active");
    else if (stageName === "results") resultsStage.classList.add("active");
  }
  
  // --- Manage API Key State ---
  function loadApiKey() {
    const savedKey = localStorage.getItem("gemini_api_key");
    if (savedKey) {
      geminiKeyInput.value = savedKey;
      apiStatusText.textContent = "Using Custom Key";
    } else {
      apiStatusText.textContent = "Using Server Key";
    }
  }
  
  // --- Trigger Strategic Analysis ---
  async function triggerAnalysis(url) {
    showStage("loading");
    resetChecklist();
    
    activeUrlDisplay.innerHTML = `
      <h2>Analyzing Website</h2>
      <p>Crawling assets from: ${url}</p>
    `;
    
    // Simulate loading milestones animation
    let loadingInterval = animateLoadingSteps();
    
    const customKey = localStorage.getItem("gemini_api_key");
    const headers = { "Content-Type": "application/json" };
    if (customKey) {
      headers["X-Gemini-API-Key"] = customKey;
    }
    
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ url: url })
      });
      
      clearInterval(loadingInterval);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Server analysis error");
      }
      
      const data = await response.json();
      currentAnalysisData = data;
      
      // Store in localStorage history
      saveToHistory(url, data);
      
      // Render components
      renderResults(data);
      
      // Mark loading checklist fully done and transition
      markChecklistAllDone();
      setTimeout(() => {
        showStage("results");
        renderHistory();
      }, 500);
      
    } catch (err) {
      clearInterval(loadingInterval);
      console.error(err);
      document.getElementById("error-message-text").textContent = err.message || "Failed to parse landing page colors and content.";
      showStage("error");
    }
  }
  
  // --- Loading checklist animation helpers ---
  function resetChecklist() {
    checkScrape.className = "checking";
    checkImages.className = "pending";
    checkGemini.className = "pending";
    checkRender.className = "pending";
  }
  
  function animateLoadingSteps() {
    let step = 0;
    return setInterval(() => {
      step++;
      if (step === 3) {
        checkScrape.className = "done";
        checkImages.className = "checking";
      } else if (step === 6) {
        checkImages.className = "done";
        checkGemini.className = "checking";
      } else if (step === 9) {
        checkGemini.className = "done";
        checkRender.className = "checking";
      }
    }, 1000);
  }
  
  function markChecklistAllDone() {
    checkScrape.className = "done";
    checkImages.className = "done";
    checkGemini.className = "done";
    checkRender.className = "done";
  }
  
  // --- History Management ---
  function saveToHistory(url, data) {
    let history = JSON.parse(localStorage.getItem("audit_history") || "[]");
    
    // Check if domain is already in history, remove duplicate so it bumps to top
    history = history.filter(item => item.url.toLowerCase() !== url.toLowerCase());
    
    const historyItem = {
      url: url,
      title: data.title || url,
      timestamp: new Date().toLocaleDateString(),
      data: data
    };
    
    history.unshift(historyItem);
    // Keep max 15 audits in local cache
    if (history.length > 15) {
      history.pop();
    }
    
    localStorage.setItem("audit_history", JSON.stringify(history));
  }
  
  function renderHistory() {
    const history = JSON.parse(localStorage.getItem("audit_history") || "[]");
    historyList.innerHTML = "";
    
    if (history.length === 0) {
      historyList.innerHTML = '<div class="empty-history">No past analyses. Input a URL to begin.</div>';
      return;
    }
    
    history.forEach(item => {
      const cleanDomain = urlToDomain(item.url);
      const div = document.createElement("div");
      div.className = "history-item";
      div.innerHTML = `
        <span class="domain-name">${cleanDomain}</span>
        <span class="audit-date">${item.timestamp}</span>
      `;
      div.addEventListener("click", () => {
        currentAnalysisData = item.data;
        targetUrlInput.value = item.url;
        activeUrlDisplay.innerHTML = `
          <h2>Strategic Audit</h2>
          <p>Loaded from cache: ${item.url}</p>
        `;
        renderResults(item.data);
        showStage("results");
      });
      historyList.appendChild(div);
    });
  }
  
  function urlToDomain(url) {
    try {
      const parsed = new URL(url);
      return parsed.hostname.replace("www.", "");
    } catch {
      return url;
    }
  }
  
  // --- Render Strategic Output Tabs ---
  function renderResults(data) {
    const analysis = data.analysis || {};
    
    // Overview Tab
    document.getElementById("overview-elevator-pitch").textContent = analysis.positioning?.elevator_pitch || "--";
    document.getElementById("meta-domain").textContent = urlToDomain(data.url);
    document.getElementById("meta-title").textContent = data.title || "No Title Extracted";
    document.getElementById("overview-category").textContent = analysis.positioning?.core_category || "--";
    document.getElementById("overview-differentiation").textContent = analysis.positioning?.differentiation || "--";
    
    // GTM Details
    document.getElementById("gtm-motion").textContent = analysis.gtm_strategy?.gtm_motion || "--";
    document.getElementById("gtm-pricing").textContent = analysis.gtm_strategy?.pricing_strategy || "--";
    
    // Conversion list
    const conversionList = document.getElementById("gtm-conversion-list");
    conversionList.innerHTML = "";
    const tactics = analysis.gtm_strategy?.conversion_tactics || [];
    if (tactics.length > 0) {
      tactics.forEach(t => {
        const li = document.createElement("li");
        li.textContent = t;
        conversionList.appendChild(li);
      });
    } else {
      conversionList.innerHTML = "<li>No specific growth/conversion loops identified.</li>";
    }
    
    // Target Personas Tab
    const personasContainer = document.getElementById("personas-container");
    personasContainer.innerHTML = "";
    const personas = analysis.target_personas || [];
    personas.forEach(p => {
      const pCard = document.createElement("div");
      pCard.className = "persona-card";
      
      let painPointsHtml = "";
      if (Array.isArray(p.pain_points)) {
        p.pain_points.forEach(pt => {
          painPointsHtml += `<li>${pt}</li>`;
        });
      }
      
      pCard.innerHTML = `
        <div class="persona-header">
          <h3 class="persona-role">${p.role || "Target Persona"}</h3>
          <span class="persona-meta">Strategic Profile</span>
        </div>
        <div class="persona-section">
          <h4>Core Pain Points Addressed</h4>
          <ul class="styled-list">
            ${painPointsHtml || "<li>Pain points analysis not available.</li>"}
          </ul>
        </div>
        <div class="persona-section">
          <h4>Value Delivered</h4>
          <p>${p.value_delivered || "--"}</p>
        </div>
      `;
      personasContainer.appendChild(pCard);
    });
    
    // Value Props & Messaging Tab
    document.getElementById("messaging-hero-tagline").textContent = `"${analysis.messaging_strategy?.hero_tagline || data.title}"`;
    document.getElementById("messaging-framework").textContent = analysis.messaging_strategy?.communication_framework || "--";
    
    // Tone tags
    const toneContainer = document.getElementById("messaging-tone-tags");
    toneContainer.innerHTML = "";
    const tones = analysis.messaging_strategy?.tone_of_voice || [];
    tones.forEach(t => {
      const span = document.createElement("span");
      span.textContent = t;
      toneContainer.appendChild(span);
    });
    if (tones.length === 0) {
      toneContainer.innerHTML = "<span>Analytical</span><span>Professional</span>";
    }
    
    // Value props list
    const valuePropsContainer = document.getElementById("value-props-container");
    valuePropsContainer.innerHTML = "";
    const valueProps = analysis.value_propositions || [];
    valueProps.forEach(vp => {
      const div = document.createElement("div");
      div.className = "value-prop-item";
      
      let featuresHtml = "";
      const features = vp.supporting_features || [];
      features.forEach(f => {
        featuresHtml += `<span class="feature-tag">${f}</span>`;
      });
      
      div.innerHTML = `
        <h4>${vp.title || "Value Proposition"}</h4>
        <p>${vp.description || "--"}</p>
        <div class="features-tags">
          ${featuresHtml}
        </div>
      `;
      valuePropsContainer.appendChild(div);
    });
    
    // Visual Identity Tab
    // Extracted colors
    const colorsPalette = document.getElementById("colors-palette-container");
    colorsPalette.innerHTML = "";
    const colors = data.colors || [];
    colors.forEach(hex => {
      const block = document.createElement("div");
      block.className = "color-block";
      block.innerHTML = `
        <div class="color-sample" style="background-color: ${hex};"></div>
        <div class="color-hex">${hex}</div>
      `;
      block.addEventListener("click", () => {
        navigator.clipboard.writeText(hex);
        alert(`Copied hex code: ${hex}`);
      });
      colorsPalette.appendChild(block);
    });
    if (colors.length === 0) {
      colorsPalette.innerHTML = '<div class="empty-history" style="grid-column: span 6;">No colors detected in stylesheet styles.</div>';
    }
    
    // CSS Variables List table
    const cssVarsContainer = document.getElementById("css-variables-container");
    cssVarsContainer.innerHTML = "";
    const cssVars = data.css_variables || {};
    const cssKeys = Object.keys(cssVars);
    if (cssKeys.length > 0) {
      cssKeys.forEach(k => {
        const row = document.createElement("div");
        row.className = "css-var-row";
        row.innerHTML = `
          <span class="css-var-name">${k}</span>
          <span class="css-var-value" style="color: ${cssVars[k]}">${cssVars[k]}</span>
        `;
        cssVarsContainer.appendChild(row);
      });
    } else {
      cssVarsContainer.innerHTML = '<div class="sub-description" style="text-align: center;">No CSS variable declarations extracted.</div>';
    }
    
    // Critique text fields
    document.getElementById("visuals-theme").textContent = analysis.design_branding?.visual_theme || "--";
    document.getElementById("visuals-feedback").textContent = analysis.design_branding?.color_palette_feedback || "--";
    document.getElementById("visuals-ux-critique").textContent = analysis.design_branding?.ux_ui_critique || "--";
    
    // Visual Graphics images
    const assetsContainer = document.getElementById("assets-preview-container");
    assetsContainer.innerHTML = "";
    const images = data.images || {};
    
    // We render previews for logo and hero image if URLs were scraped
    for (const [key, imgUrl] of Object.entries(images)) {
      if (imgUrl) {
        const card = document.createElement("div");
        card.className = "asset-preview-card";
        card.innerHTML = `
          <div class="asset-preview-title">${key.replace("_", " ")}</div>
          <div class="asset-image-box">
            <img src="${imgUrl}" alt="${key} branding asset" crossorigin="anonymous">
          </div>
        `;
        assetsContainer.appendChild(card);
      }
    }
    if (assetsContainer.children.length === 0) {
      assetsContainer.innerHTML = `
        <div class="empty-history" style="grid-column: span 3;">
          No branding asset graphics could be downloaded.
        </div>
      `;
    }
    
    // Raw Exports Tab
    const mdOutput = generateMarkdownBrief(data);
    document.getElementById("markdown-preview-text").textContent = mdOutput;
    
    // Set up download buttons
    const btnDownloadMd = document.getElementById("btn-download-md");
    btnDownloadMd.onclick = () => downloadFile(mdOutput, `${urlToDomain(data.url)}_gtm_brief.md`, "text/markdown");
    
    const btnDownloadJson = document.getElementById("btn-download-json");
    btnDownloadJson.onclick = () => downloadFile(JSON.stringify(data, null, 2), `${urlToDomain(data.url)}_marketing_schema.json`, "application/json");
    
    const btnCopyMd = document.getElementById("btn-copy-md");
    btnCopyMd.onclick = () => {
      navigator.clipboard.writeText(mdOutput);
      alert("Markdown brief copied to clipboard.");
    };
  }
  
  // --- Markdown Report Generator ---
  function generateMarkdownBrief(data) {
    const analysis = data.analysis || {};
    let md = `# Strategy Brief & Product Audit: ${data.title || urlToDomain(data.url)}\n`;
    md += `**Domain:** ${data.url}\n`;
    md += `**Meta Description:** ${data.meta_description || "Not provided"}\n\n`;
    
    md += `## 1. Core Positioning\n`;
    md += `- **Elevator Pitch:** ${analysis.positioning?.elevator_pitch || "N/A"}\n`;
    md += `- **Core Category:** ${analysis.positioning?.core_category || "N/A"}\n`;
    md += `- **Differentiation:** ${analysis.positioning?.differentiation || "N/A"}\n\n`;
    
    md += `## 2. Value Propositions\n`;
    const valueProps = analysis.value_propositions || [];
    valueProps.forEach((vp, idx) => {
      md += `### VP ${idx + 1}: ${vp.title || "Value Proposition"}\n`;
      md += `${vp.description || "N/A"}\n`;
      if (Array.isArray(vp.supporting_features) && vp.supporting_features.length > 0) {
        md += `*Supporting Features:* ${vp.supporting_features.join(", ")}\n`;
      }
      md += `\n`;
    });
    
    md += `## 3. Target Personas\n`;
    const personas = analysis.target_personas || [];
    personas.forEach(p => {
      md += `### Persona: ${p.role || "Target Profile"}\n`;
      md += `**Value Delivered:** ${p.value_delivered || "N/A"}\n`;
      if (Array.isArray(p.pain_points) && p.pain_points.length > 0) {
        md += `**Pain Points Addressed:**\n`;
        p.pain_points.forEach(pt => {
          md += `- ${pt}\n`;
        });
      }
      md += `\n`;
    });
    
    md += `## 4. Go-To-Market & Conversion\n`;
    md += `- **GTM Motion:** ${analysis.gtm_strategy?.gtm_motion || "N/A"}\n`;
    md += `- **Pricing Summary:** ${analysis.gtm_strategy?.pricing_strategy || "N/A"}\n`;
    if (Array.isArray(analysis.gtm_strategy?.conversion_tactics) && analysis.gtm_strategy.conversion_tactics.length > 0) {
      md += `**Key Conversion Tactics:**\n`;
      analysis.gtm_strategy.conversion_tactics.forEach(ct => {
        md += `- ${ct}\n`;
      });
    }
    md += `\n`;
    
    md += `## 5. Visual Branding & Design System\n`;
    md += `- **Visual Theme:** ${analysis.design_branding?.visual_theme || "N/A"}\n`;
    md += `- **Color Palette Feedback:** ${analysis.design_branding?.color_palette_feedback || "N/A"}\n`;
    md += `- **UX / UI Critique:** ${analysis.design_branding?.ux_ui_critique || "N/A"}\n`;
    
    return md;
  }
  
  // File download helper
  function downloadFile(content, filename, contentType) {
    const a = document.createElement("a");
    const file = new Blob([content], { type: contentType });
    a.href = URL.createObjectURL(file);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }
});
