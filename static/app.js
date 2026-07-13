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
    const summary = analysis.summary || {};
    const msgAnalysis = analysis.messaging_analysis || {};
    const prodPos = analysis.product_positioning || {};
    
    document.getElementById("overview-elevator-pitch").textContent = summary.elevator_pitch || "--";
    document.getElementById("meta-domain").textContent = urlToDomain(data.url);
    document.getElementById("meta-title").textContent = data.title || "No Title Extracted";
    document.getElementById("overview-primary-tagline").textContent = msgAnalysis.primary_tagline || "--";
    document.getElementById("overview-target-audience").textContent = summary.target_audience || "--";
    document.getElementById("overview-category-strategy").textContent = summary.category_strategy || "--";
    document.getElementById("overview-problem-solved").textContent = msgAnalysis.problem_solved || "--";
    document.getElementById("overview-pricing-approach").textContent = prodPos.pricing_approach || "--";
    
    // Positioning & Narrative Tab
    const ps = analysis.positioning_statement || {};
    document.getElementById("ps-target-audience").textContent = ps.target_audience || "--";
    document.getElementById("ps-product-category").textContent = ps.product_category || "--";
    document.getElementById("ps-key-benefit").textContent = ps.key_benefit || "--";
    document.getElementById("ps-reason-to-believe").textContent = ps.reason_to_believe || "--";
    
    // Features list
    const featuresList = document.getElementById("positioning-features-list");
    featuresList.innerHTML = "";
    const features = prodPos.features_emphasized || [];
    if (features.length > 0) {
      features.forEach(f => {
        const li = document.createElement("li");
        li.textContent = f;
        featuresList.appendChild(li);
      });
    } else {
      featuresList.innerHTML = "<li>No featured product elements identified.</li>";
    }
    
    // Differentiators list
    const diffsList = document.getElementById("positioning-differentiators-list");
    diffsList.innerHTML = "";
    const diffs = prodPos.claimed_differentiators || [];
    if (diffs.length > 0) {
      diffs.forEach(d => {
        const li = document.createElement("li");
        li.textContent = d;
        diffsList.appendChild(li);
      });
    } else {
      diffsList.innerHTML = "<li>No primary differentiators extracted.</li>";
    }
    
    // Narrative Arc
    const narrative = analysis.narrative_arc || {};
    document.getElementById("narrative-villain").textContent = narrative.villain || "--";
    document.getElementById("narrative-hero").textContent = narrative.hero || "--";
    document.getElementById("narrative-transformation").textContent = narrative.transformation || "--";
    document.getElementById("narrative-stakes").textContent = narrative.stakes || "--";
    
    // SWOT Grid
    const swot = analysis.swot_analysis || {};
    const renderSwotList = (listId, items) => {
      const el = document.getElementById(listId);
      el.innerHTML = "";
      (items || []).forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        el.appendChild(li);
      });
      if (!items || items.length === 0) {
        el.innerHTML = "<li>None identified.</li>";
      }
    };
    renderSwotList("swot-strengths-list", swot.strengths);
    renderSwotList("swot-weaknesses-list", swot.weaknesses);
    renderSwotList("swot-opportunities-list", swot.opportunities);
    renderSwotList("swot-threats-list", swot.threats);
    
    // Tone tags
    const toneContainer = document.getElementById("messaging-tone-tags");
    toneContainer.innerHTML = "";
    const tones = msgAnalysis.tone_of_voice || [];
    tones.forEach(t => {
      const span = document.createElement("span");
      span.textContent = t;
      toneContainer.appendChild(span);
    });
    if (tones.length === 0) {
      toneContainer.innerHTML = "<span>Analytical</span><span>Professional</span>";
    }
    
    // Messaging Themes
    const themesContainer = document.getElementById("messaging-themes-container");
    themesContainer.innerHTML = "";
    const themes = msgAnalysis.messaging_themes || [];
    themes.forEach(t => {
      const div = document.createElement("div");
      div.className = "value-prop-item";
      div.innerHTML = `
        <h4>${t.theme || "Messaging Theme"}</h4>
        <p>${t.description || "--"}</p>
      `;
      themesContainer.appendChild(div);
    });
    if (themes.length === 0) {
      themesContainer.innerHTML = '<div class="sub-description">No core messaging themes extracted.</div>';
    }
    
    // Messaging Audit
    const audit = analysis.messaging_audit || {};
    document.getElementById("audit-clarity").textContent = audit.clarity || "--";
    document.getElementById("audit-differentiation").textContent = audit.differentiation || "--";
    document.getElementById("audit-proof").textContent = audit.proof || "--";
    document.getElementById("audit-resonance").textContent = audit.resonance || "--";
    
    // Sales Battlecard Objections Table
    const objectionTbody = document.getElementById("battlecard-objection-tbody");
    objectionTbody.innerHTML = "";
    const objections = analysis.sales_battlecard?.objection_handling || [];
    if (objections.length > 0) {
      objections.forEach(obj => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><strong>${obj.objection}</strong></td>
          <td>${obj.response}</td>
        `;
        objectionTbody.appendChild(row);
      });
    } else {
      objectionTbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: var(--text-muted);">No objection playbook generated.</td></tr>';
    }
    
    // Sales Battlecard Landmines Table
    const landminesTbody = document.getElementById("battlecard-landmines-tbody");
    landminesTbody.innerHTML = "";
    const landmines = analysis.sales_battlecard?.landmines_to_set || [];
    if (landmines.length > 0) {
      landmines.forEach(lm => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><strong>${lm.question}</strong></td>
          <td>${lm.goal}</td>
        `;
        landminesTbody.appendChild(row);
      });
    } else {
      landminesTbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: var(--text-muted);">No landmines suggested.</td></tr>';
    }
    
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
    
    // Critique text fields and Overall Impression
    const critique = analysis.design_critique || {};
    document.getElementById("critique-overall-impression").textContent = critique.overall_impression || "--";

    // Setup Split Visual Design Critique Playbook
    const assetsColumn = document.getElementById("critique-assets-column");
    const commentsColumn = document.getElementById("critique-comments-column");
    assetsColumn.innerHTML = "";
    commentsColumn.innerHTML = "";

    const images = data.images || {};
    const imgKeys = Object.keys(images).filter(k => images[k]);

    if (imgKeys.length > 0) {
      // 1. Populate Assets Column
      const hasScreenshot = !!images.full_page_screenshot;
      
      if (hasScreenshot) {
        let imgUrl = images.full_page_screenshot;
        if (imgUrl.startsWith("/static/")) {
          imgUrl = imgUrl.substring(7);
        }
        
        const card = document.createElement("div");
        card.className = "critique-asset-card full-page-mockup-card active";
        card.id = "critique-asset-full_page_screenshot";
        card.setAttribute("data-asset-key", "full_page_screenshot");
        
        card.innerHTML = `
          <div class="critique-asset-header">
            <strong>Full Webpage Mockup</strong>
            <span class="tag">Active Scroll View</span>
          </div>
          <div class="critique-asset-image-wrapper full-page-image-wrapper">
            <img src="${imgUrl}" alt="Full page screenshot mockup" crossorigin="anonymous">
          </div>
        `;
        assetsColumn.appendChild(card);
      } else {
        // Fallback: render individual assets as cards
        imgKeys.forEach(key => {
          if (key === "full_page_screenshot") return;
          const card = document.createElement("div");
          card.className = "critique-asset-card";
          card.id = `critique-asset-${key}`;
          card.setAttribute("data-asset-key", key);

          let imgUrl = images[key];
          if (imgUrl && imgUrl.startsWith("/static/")) {
            imgUrl = imgUrl.substring(7);
          }

          card.innerHTML = `
            <div class="critique-asset-header">
              <strong>${key.toUpperCase().replace("_", " ")}</strong>
              <span class="tag">Visual Target</span>
            </div>
            <div class="critique-asset-image-wrapper">
              <img src="${imgUrl}" alt="${key} asset" crossorigin="anonymous">
            </div>
          `;
          assetsColumn.appendChild(card);
        });
      }

      // 2. Populate Comments Column with Word-Style Bubbles
      let bubbleCount = 0;
      
      const createBubble = (type, title, body, recommendation, targetAsset, severityText = "") => {
        bubbleCount++;
        const bubble = document.createElement("div");
        let sevClass = "";
        if (severityText) {
          const s = severityText.toLowerCase();
          if (severityText.includes("🔴") || s.includes("critical")) sevClass = "sev-critical";
          else if (severityText.includes("🟡") || s.includes("moderate")) sevClass = "sev-moderate";
          else if (severityText.includes("🟢") || s.includes("minor")) sevClass = "sev-minor";
        }
        bubble.className = `comment-bubble type-${type} ${sevClass}`;
        bubble.id = `comment-bubble-${bubbleCount}`;
        bubble.setAttribute("data-target-asset", targetAsset);

        let recHtml = "";
        if (recommendation) {
          recHtml = `<div class="comment-bubble-recommendation"><strong>Actionable Play:</strong> ${recommendation}</div>`;
        }

        let badgeHtml = "";
        if (severityText) {
          let badgeColor = "minor";
          if (sevClass === "sev-critical") badgeColor = "critical";
          else if (sevClass === "sev-moderate") badgeColor = "moderate";
          badgeHtml = `<span class="severity-badge ${badgeColor}">${severityText}</span>`;
        }

        bubble.innerHTML = `
          <div class="comment-bubble-header">
            <span class="comment-bubble-title">${type.toUpperCase()}: ${title}</span>
            ${badgeHtml}
          </div>
          <div class="comment-bubble-body">${body}</div>
          ${recHtml}
        `;

        // Interaction event: click bubble -> scroll image into view
        bubble.addEventListener("click", () => {
          // Highlight active state
          document.querySelectorAll(".comment-bubble").forEach(b => b.classList.remove("active"));
          document.querySelectorAll(".critique-asset-card").forEach(c => c.classList.remove("active"));
          
          bubble.classList.add("active");
          
          if (hasScreenshot) {
            const mockupCard = document.getElementById("critique-asset-full_page_screenshot");
            if (mockupCard) {
              mockupCard.classList.add("active");
              
              // Calculate target scroll height based on comment keywords & type
              let scrollRatio = 0.0; // Hero
              const t = type.toLowerCase();
              const bText = (body + " " + title).toLowerCase();
              
              if (bText.includes("footer") || bText.includes("copyright") || bText.includes("bottom")) {
                scrollRatio = 1.0;
              } else if (t === "accessibility" || bText.includes("accessibility") || bText.includes("contrast") || bText.includes("touch")) {
                scrollRatio = 0.75;
              } else if (t === "consistency" || bText.includes("font") || bText.includes("style") || bText.includes("align")) {
                scrollRatio = 0.50;
              } else if (bText.includes("flow") || bText.includes("reading") || bText.includes("hierarchy") || bText.includes("first impression")) {
                scrollRatio = 0.25;
              }
              
              const imgWrapper = mockupCard.querySelector(".critique-asset-image-wrapper");
              if (imgWrapper) {
                const targetScrollY = (imgWrapper.scrollHeight - imgWrapper.clientHeight) * scrollRatio;
                imgWrapper.scrollTo({
                  top: targetScrollY,
                  behavior: "smooth"
                });
              }
            }
          } else {
            const targetCard = document.getElementById(`critique-asset-${targetAsset}`);
            if (targetCard) {
              targetCard.classList.add("active");
              targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
          }
        });

        commentsColumn.appendChild(bubble);
      };

      // Helper function to guess which image key fits a critique text segment
      const guessTargetAsset = (text) => {
        const t = (text || "").toLowerCase();
        if (t.includes("logo") || t.includes("branding icon") || t.includes("iconography")) {
          return imgKeys.includes("logo") ? "logo" : imgKeys[0];
        }
        if (t.includes("hero") || t.includes("headline") || t.includes("h1") || t.includes("first impression") || t.includes("fold")) {
          return imgKeys.includes("hero") ? "hero" : imgKeys[0];
        }
        if (t.includes("og") || t.includes("open graph") || t.includes("banner") || t.includes("social")) {
          if (imgKeys.includes("og_image")) return "og_image";
          if (imgKeys.includes("hero")) return "hero";
        }
        return imgKeys[0]; // fallback
      };

      // Add Usability bubbles
      const usabilityFindings = critique.usability_findings || [];
      usabilityFindings.forEach(item => {
        const target = guessTargetAsset(item.issue + " " + item.recommendation);
        createBubble("usability", "Usability Audit", item.issue, item.recommendation, target, item.severity);
      });

      // Add Visual Hierarchy bubbles
      const vh = critique.visual_hierarchy || {};
      if (vh.first_impression) {
        const target = guessTargetAsset(vh.first_impression);
        createBubble("hierarchy", "First Impression Focus", `First impression focus is: <strong>${vh.first_impression}</strong>.`, `Is focus correct? ${vh.is_first_impression_correct}`, target);
      }
      if (vh.reading_flow) {
        const target = guessTargetAsset(vh.reading_flow);
        createBubble("hierarchy", "Reading Flow Pattern", vh.reading_flow, `CTA Emphasis critique: ${vh.emphasis_critique}`, target);
      }

      // Add Consistency bubbles
      const consistencyFindings = critique.consistency_findings || [];
      consistencyFindings.forEach(item => {
        const target = guessTargetAsset(item.element + " " + item.issue);
        createBubble("consistency", `${item.element} Consistency`, item.issue, item.recommendation, target);
      });

      // Add Accessibility bubbles
      const access = critique.accessibility || {};
      if (access.color_contrast) {
        createBubble("accessibility", "Color Contrast Audit", `Core color contrast assessment: <strong>${access.color_contrast}</strong>`, `Readability: ${access.text_readability}`, guessTargetAsset("color contrast"));
      }
      if (access.touch_targets) {
        createBubble("accessibility", "Touch Target Sizes", `Touch target mobile sizing is: <strong>${access.touch_targets}</strong>`, `Text Readability: ${access.text_readability}`, guessTargetAsset("touch target mobile"));
      }

      // Add hover highlights on image cards (links left to right)
      document.querySelectorAll(".critique-asset-card").forEach(card => {
        card.addEventListener("mouseenter", () => {
          const key = card.getAttribute("data-asset-key");
          card.classList.add("active");
          // highlight matching comments
          let firstMatch = null;
          document.querySelectorAll(".comment-bubble").forEach(bubble => {
            if (bubble.getAttribute("data-target-asset") === key) {
              bubble.classList.add("active");
              if (!firstMatch) firstMatch = bubble;
            } else {
              bubble.classList.remove("active");
            }
          });
          if (firstMatch) {
            firstMatch.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        });

        card.addEventListener("mouseleave", () => {
          card.classList.remove("active");
          document.querySelectorAll(".comment-bubble").forEach(b => b.classList.remove("active"));
        });
      });

    } else {
      assetsColumn.innerHTML = '<div class="sub-description" style="text-align: center; padding: 40px 0; width:100%;">No visual assets could be loaded for split-screen audit.</div>';
      commentsColumn.innerHTML = '<div class="sub-description" style="text-align: center; padding: 40px 0; width:100%;">No visual comments generated.</div>';
    }

    // What Works Well List
    const worksWellContainer = document.getElementById("works-well-list");
    worksWellContainer.innerHTML = "";
    const worksWell = critique.what_works_well || [];
    if (worksWell.length > 0) {
      worksWell.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        worksWellContainer.appendChild(li);
      });
    } else {
      worksWellContainer.innerHTML = '<li style="color: var(--text-muted);">No positive observations recorded.</li>';
    }

    // Priority Recommendations List
    const priorityContainer = document.getElementById("priority-recommendations-list");
    priorityContainer.innerHTML = "";
    const priorities = critique.priority_recommendations || [];
    if (priorities.length > 0) {
      priorities.forEach(item => {
        const cleanedItem = item.replace(/^\d+[\.\s]*/, "");
        const li = document.createElement("li");
        li.innerHTML = `<p>${cleanedItem}</p>`;
        priorityContainer.appendChild(li);
      });
    } else {
      priorityContainer.innerHTML = '<li style="color: var(--text-muted);">No priority recommendations recorded.</li>';
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
    let md = `# Competitor Strategy Audit & Battlecard: ${data.title || urlToDomain(data.url)}\n`;
    md += `**Target URL:** ${data.url}\n`;
    md += `**Scraped Title:** ${data.title || "N/A"}\n`;
    md += `**Meta Description:** ${data.meta_description || "Not provided"}\n\n`;
    
    // Overview Section
    const summary = analysis.summary || {};
    const msgAnalysis = analysis.messaging_analysis || {};
    const prodPos = analysis.product_positioning || {};
    
    md += `## 1. Competitor Overview\n`;
    md += `- **Elevator Pitch:** ${summary.elevator_pitch || "N/A"}\n`;
    md += `- **Core Target Audience:** ${summary.target_audience || "N/A"}\n`;
    md += `- **Category Strategy:** ${summary.category_strategy || "N/A"}\n`;
    md += `- **Primary Tagline:** ${msgAnalysis.primary_tagline || "N/A"}\n`;
    md += `- **Problem Solved:** ${msgAnalysis.problem_solved || "N/A"}\n`;
    md += `- **Pricing Approach:** ${prodPos.pricing_approach || "N/A"}\n\n`;
    
    // Positioning Statement
    const ps = analysis.positioning_statement || {};
    md += `## 2. Reverse-Engineered Positioning Statement\n`;
    md += `> **For** ${ps.target_audience || "[target audience]"}\n`;
    md += `> **is the** ${ps.product_category || "[product category]"}\n`;
    md += `> **that** ${ps.key_benefit || "[key benefit]"}\n`;
    md += `> **because** ${ps.reason_to_believe || "[reason to believe]"}\n\n`;
    
    // Narrative Arc
    const narrative = analysis.narrative_arc || {};
    md += `## 3. Brand Storytelling & Narrative Arc\n`;
    md += `- **The Villain (Enemy):** ${narrative.villain || "N/A"}\n`;
    md += `- **The Hero:** ${narrative.hero || "N/A"}\n`;
    md += `- **The Transformation:** ${narrative.transformation || "N/A"}\n`;
    md += `- **The Stakes:** ${narrative.stakes || "N/A"}\n\n`;
    
    // Solution Positioning
    md += `## 4. Product Features & Differentiators\n`;
    md += `### Features Emphasized\n`;
    (prodPos.features_emphasized || []).forEach(f => {
      md += `- ${f}\n`;
    });
    md += `\n### Claimed Differentiators\n`;
    (prodPos.claimed_differentiators || []).forEach(d => {
      md += `- ${d}\n`;
    });
    md += `\n`;
    
    // SWOT
    const swot = analysis.swot_analysis || {};
    md += `## 5. SWOT Analysis\n\n`;
    md += `### Strengths (Competitor)\n`;
    (swot.strengths || []).forEach(s => { md += `- ${s}\n`; });
    md += `\n### Weaknesses (Competitor)\n`;
    (swot.weaknesses || []).forEach(w => { md += `- ${w}\n`; });
    md += `\n### Opportunities (For You)\n`;
    (swot.opportunities || []).forEach(o => { md += `- ${o}\n`; });
    md += `\n### Threats (To You)\n`;
    (swot.threats || []).forEach(t => { md += `- ${t}\n`; });
    md += `\n`;
    
    // Messaging Themes & Audit
    md += `## 6. Messaging Themes & Quality Audit\n\n`;
    md += `### Core Messaging Themes\n`;
    (msgAnalysis.messaging_themes || []).forEach(t => {
      md += `* **${t.theme}:** ${t.description}\n`;
    });
    md += `\n### Tone of Voice\n`;
    md += `${(msgAnalysis.tone_of_voice || []).join(", ") || "N/A"}\n\n`;
    
    const audit = analysis.messaging_audit || {};
    md += `### Messaging Quality Audit\n`;
    md += `- **Clarity:** ${audit.clarity || "N/A"}\n`;
    md += `- **Differentiation:** ${audit.differentiation || "N/A"}\n`;
    md += `- **Proof & Evidence:** ${audit.proof || "N/A"}\n`;
    md += `- **Resonance:** ${audit.resonance || "N/A"}\n\n`;
    
    // Sales Battlecard
    md += `## 7. Sales Battlecard (Against this Competitor)\n\n`;
    md += `### Objection Handling Playbook\n`;
    md += `| Prospect Objection / Competitor Claim | Sales Response Playbook |\n`;
    md += `|---------------------------------------|-------------------------|\n`;
    const objections = analysis.sales_battlecard?.objection_handling || [];
    if (objections.length > 0) {
      objections.forEach(obj => {
        md += `| ${obj.objection} | ${obj.response} |\n`;
      });
    } else {
      md += `| N/A | N/A |\n`;
    }
    md += `\n`;
    
    md += `### Landmines to Set\n`;
    md += `| Landmine Question to Suggest | Strategic Goal / Why Ask It |\n`;
    md += `|------------------------------|----------------------------|\n`;
    const landmines = analysis.sales_battlecard?.landmines_to_set || [];
    if (landmines.length > 0) {
      landmines.forEach(lm => {
        md += `| ${lm.question} | ${lm.goal} |\n`;
      });
    } else {
      md += `| N/A | N/A |\n`;
    }
    md += `\n`;
    
    // Design Critique
    const critique = analysis.design_critique || {};
    md += `## 8. Design Critique & Visual Audit\n\n`;
    md += `- **Overall Impression:** ${critique.overall_impression || "N/A"}\n`;
    md += `- **Visual Theme:** ${critique.visual_theme || "N/A"}\n`;
    md += `- **Color Palette Feedback:** ${critique.color_palette_feedback || "N/A"}\n\n`;
    
    md += `### Usability Audit\n`;
    md += `| Finding | Severity | Recommendation |\n`;
    md += `|---------|----------|----------------|\n`;
    const usability = critique.usability_findings || [];
    if (usability.length > 0) {
      usability.forEach(item => {
        md += `| ${item.issue} | ${item.severity} | ${item.recommendation} |\n`;
      });
    } else {
      md += `| No usability issues found | Minor | N/A |\n`;
    }
    md += `\n`;
    
    md += `### Visual Hierarchy & Accessibility\n`;
    const vh = critique.visual_hierarchy || {};
    md += `- **First Impression:** ${vh.first_impression || "N/A"}\n`;
    md += `- **Is Focus Correct?** ${vh.is_first_impression_correct || "N/A"}\n`;
    md += `- **Reading Flow:** ${vh.reading_flow || "N/A"}\n`;
    md += `- **Contrast:** ${critique.accessibility?.color_contrast || "N/A"}\n`;
    md += `- **Mobile Touch Targets:** ${critique.accessibility?.touch_targets || "N/A"}\n`;
    md += `- **Readability:** ${critique.accessibility?.text_readability || "N/A"}\n\n`;
    
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
