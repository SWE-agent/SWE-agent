let currentFileName = null;
let trajectoryDirectory = "";
let timeoutIds = [];
let autoReloadInterval = null;

function toggleTheme() {
  const isDark = document.getElementById("themeToggle").checked;
  const themeName = isDark ? "apple-dark" : "apple-light";
  document.body.className = themeName;
  localStorage.setItem("theme", themeName);
}

function initTheme() {
  const savedTheme = localStorage.getItem("theme") || "apple-dark";
  document.body.className = savedTheme;
  const toggle = document.getElementById("themeToggle");
  if (toggle) {
    toggle.checked = (savedTheme === "apple-dark");
  }
}

function getBaseUrl() {
  const protocol = window.location.protocol;
  const host = window.location.hostname;
  const port = window.location.port;
  const defaultPort =
    protocol === "http:" && !port
      ? "80"
      : protocol === "https:" && !port
        ? "443"
        : port;
  return `${protocol}//${host}:${defaultPort}`;
}

function fetchFiles() {
  const baseUrl = getBaseUrl();
  fetch(`${baseUrl}/files`)
    .then((response) => response.json())
    .then((files) => {
      const fileList = document.getElementById("fileList");
      fileList.innerHTML = "";
      files.forEach((file) => {
        const fileParts = file.split("    "); // Separator from server.py (4 spaces)
        const relativePath = fileParts[0];
        const statusStr = fileParts[1] || "";
        
        const fileElement = document.createElement("li");
        
        // Minimalist status badges (no emojis)
        let statusBadge = "";
        if (statusStr.includes("✅")) {
          statusBadge = '<span class="list-status status-success">Resolved</span>';
        } else if (statusStr.includes("❌")) {
          let stepsText = "";
          const match = statusStr.match(/\((.*?)\)/);
          if (match) {
            stepsText = match[1];
          } else {
            stepsText = "Failed";
          }
          statusBadge = `<span class="list-status status-failed">${stepsText}</span>`;
        } else {
          statusBadge = `<span class="list-status status-unknown">Running</span>`;
        }

        const nameParts = relativePath.split("/");
        const fileName = nameParts[nameParts.length - 1].replace(".traj", "");

        fileElement.innerHTML = `
          <div class="list-item-content">
            <div class="list-item-title" title="${relativePath}">${fileName}</div>
            <div class="list-item-meta">
              <span class="list-item-path">${nameParts.slice(0, -1).join("/") || "."}</span>
              ${statusBadge}
            </div>
          </div>
        `;
        
        fileElement.onclick = () => viewFile(relativePath);
        fileList.appendChild(fileElement);
      });
      
      if (currentFileName) {
        highlightSelectedFile();
      }
    });
}

function highlightSelectedFile() {
  document.querySelectorAll("#fileList li").forEach((li) => {
    li.classList.remove("selected");
    const titleText = li.querySelector(".list-item-title").getAttribute("title");
    if (titleText === currentFileName) {
      li.classList.add("selected");
    }
  });
}

function filterFiles() {
  const query = document.getElementById("fileSearch").value.toLowerCase();
  const listItems = document.querySelectorAll("#fileList li");
  listItems.forEach((li) => {
    const text = li.querySelector(".list-item-title").textContent.toLowerCase() + " " + li.querySelector(".list-item-path").textContent.toLowerCase();
    if (text.includes(query)) {
      li.style.display = "";
    } else {
      li.style.display = "none";
    }
  });
}

function toggleAutoReload() {
  const enabled = document.getElementById("autoReload").checked;
  if (enabled) {
    autoReloadInterval = setInterval(() => {
      const baseUrl = getBaseUrl();
      fetch(`${baseUrl}/check_update`)
        .then((response) => {
          if (response.status === 200) {
            refreshCurrentFile();
          }
        })
        .catch((err) => console.log("Update check failed:", err));
    }, 3000);
  } else {
    if (autoReloadInterval) {
      clearInterval(autoReloadInterval);
      autoReloadInterval = null;
    }
  }
}

function viewFile(fileName) {
  currentFileName = fileName;
  timeoutIds.forEach((timeoutId) => clearTimeout(timeoutId));
  timeoutIds = [];

  const baseUrl = getBaseUrl();
  const showDemos = document.getElementById("showDemos").checked;

  fetch(`${baseUrl}/trajectory/${fileName}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((content) => {
      const titleParts = fileName.split("/");
      const displayTitle = titleParts[titleParts.length - 1];

      // Render all steps in a clean vertical timeline flow
      const container = document.getElementById("fileContent");
      container.innerHTML = "";

      // Append trajectory title directly at the top of the scrollable content
      const headerHtml = `
        <header class="trajectory-scroll-header">
          <h1 class="trajectory-title">${displayTitle}</h1>
        </header>
      `;
      container.innerHTML += headerHtml;

      // Render statistics dashboard inside the scrollable container
      if (content.info) {
        const info = content.info;
        const stats = info.model_stats || {};
        const cost = stats.instance_cost !== undefined ? `$${Number(stats.instance_cost).toFixed(4)}` : 'N/A';
        const sent = stats.tokens_sent !== undefined ? stats.tokens_sent.toLocaleString() : 'N/A';
        const received = stats.tokens_received !== undefined ? stats.tokens_received.toLocaleString() : 'N/A';
        const calls = stats.api_calls !== undefined ? stats.api_calls.toLocaleString() : 'N/A';
        const status = info.exit_status || 'N/A';
        
        let statusClass = 'status-unknown';
        if (status.includes('submitted') || status.includes('success')) statusClass = 'status-success';
        else if (status.includes('fail') || status.includes('error') || status.includes('limit') || status.includes('timeout')) statusClass = 'status-danger';

        const statsHtml = `
          <div class="stats-panel">
            <div class="stats-card">
              <span class="stats-label">Exit Status</span>
              <span class="stats-value badge ${statusClass}">${status}</span>
            </div>
            <div class="stats-card">
              <span class="stats-label">Cost</span>
              <span class="stats-value">${cost}</span>
            </div>
            <div class="stats-card">
              <span class="stats-label">API Calls</span>
              <span class="stats-value">${calls}</span>
            </div>
            <div class="stats-card">
              <span class="stats-label">Tokens (Sent / Recv)</span>
              <span class="stats-value">${sent} / ${received}</span>
            </div>
          </div>
        `;
        container.innerHTML += statsHtml;
      }

      if (content.trajectory && Array.isArray(content.trajectory)) {
        content.trajectory.forEach((item, index) => {
          container.innerHTML += createTrajectoryItem(item, index);
        });

        // Highlight syntax of code blocks
        container.querySelectorAll("pre code").forEach((block) => {
          hljs.highlightElement(block);
        });

        // Initialize images overlays
        initializeImageHandlers();
      } else {
        container.innerHTML += `
          <div class="empty-state">
            <h3>Empty Trajectory</h3>
            <p>No steps found in this trajectory.</p>
          </div>
        `;
      }
    })
    .catch((error) => {
      console.error("Error fetching file:", error);
      document.getElementById("fileContent").innerHTML = `
        <div class="empty-state">
          <h3>Error Loading File</h3>
          <p>${error.message}</p>
        </div>
      `;
    });

  highlightSelectedFile();
}

function createTrajectoryItem(item, index) {
  const isOldFormat = item.messages && !item.query;
  if (isOldFormat) item.query = item.messages;

  const escapeHtml = (text) => {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  const processImagesInObservation = (observation) => {
    if (!observation) return { processedText: "", images: [] };
    const imageRegex = /!\[([^\]]*)\]\(data:image\/([^;]+);base64,([^)]+)\)/g;
    const images = [];
    let processedText = observation;
    let match;

    while ((match = imageRegex.exec(observation)) !== null) {
      const [fullMatch, altText, format, base64Data] = match;
      const imageObj = {
        altText: altText || "Image",
        format: format,
        dataUrl: `data:image/${format};base64,${base64Data}`,
        id: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      };
      images.push(imageObj);
      processedText = processedText.replace(fullMatch, `[IMAGE: ${imageObj.altText}]`);
    }
    return { processedText, images };
  };

  const { processedText: processedObservation, images: observationImages } =
    processImagesInObservation(item.observation);

  const observationImagesPane =
    observationImages.length > 0
      ? `<div class="step-section" data-title="Observation Images">
        <div class="content-wrapper">
          <div class="observation-images">
            ${observationImages
              .map(
                (img) =>
                  `<div class="observation-image-container">
                <img src="${img.dataUrl}" alt="${escapeHtml(img.altText)}" class="observation-image" id="${img.id}">
                <div class="image-caption">${escapeHtml(img.altText)}</div>
              </div>`,
              )
              .join("")}
          </div>
        </div>
      </div>`
      : "";

  let badgeText = "Step " + (index + 1);
  let stepClass = "default";
  
  if (item.messages && item.messages.length > 0 && item.messages[0].content === "Problem Statement placeholder") {
    badgeText = "Problem Statement";
    stepClass = "problem";
  } else if (item.action === "Model Submission" || item.action === "submit") {
    badgeText = "Submission";
    stepClass = "submit";
  } else if (item.action) {
    const match = item.action.trim().match(/^([a-zA-Z0-9_-]+)/);
    badgeText = match ? match[1] : "Action";
    stepClass = badgeText.toLowerCase();
  } else if (item.thought) {
    badgeText = "Thought";
    stepClass = "thought";
  }

  return `
    <article class="trajectory-step step-type-${stepClass}">
        <header class="step-header">
            <span class="step-badge">${escapeHtml(badgeText)}</span>
            <span class="step-number">Step ${index + 1}</span>
            ${item.execution_time ? `<span class="step-time">${Number(item.execution_time).toFixed(2)}s</span>` : ''}
        </header>
        
        <div class="step-body">
            ${item.thought ? `
            <div class="step-section" data-title="Reasoning">
                <div class="step-thought-text">${escapeHtml(item.thought.trim())}</div>
            </div>
            ` : ''}
            
            ${item.action && item.action !== "Model Submission" ? `
            <div class="step-section" data-title="Action Command">
                <div class="content-wrapper">
                    <pre><code class="language-bash">${escapeHtml(item.action.trim())}</code></pre>
                </div>
            </div>
            ` : ''}

            ${processedObservation ? `
            <div class="step-section" data-title="Environment Output">
                <div class="content-wrapper">
                    <pre><code class="language-plaintext">${escapeHtml(processedObservation.trim())}</code></pre>
                </div>
            </div>
            ` : ''}

            ${observationImagesPane}
        </div>
    </article>
  `;
}

function initializeImageHandlers() {
  const existingOverlay = document.querySelector(".image-overlay");
  if (existingOverlay) {
    existingOverlay.remove();
  }

  const overlay = document.createElement("div");
  overlay.className = "image-overlay";
  document.body.appendChild(overlay);

  document.querySelectorAll(".observation-image").forEach((img) => {
    img.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();

      if (this.classList.contains("expanded")) {
        this.classList.remove("expanded");
        overlay.classList.remove("active");
      } else {
        document.querySelectorAll(".observation-image.expanded").forEach((otherImg) => {
          otherImg.classList.remove("expanded");
        });
        this.classList.add("expanded");
        overlay.classList.add("active");
      }
    });
  });

  overlay.addEventListener("click", function () {
    document.querySelectorAll(".observation-image.expanded").forEach((img) => {
      img.classList.remove("expanded");
    });
    overlay.classList.remove("active");
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll(".observation-image.expanded").forEach((img) => {
        img.classList.remove("expanded");
      });
      overlay.classList.remove("active");
    }
  });
}

function refreshCurrentFile() {
  if (currentFileName) {
    const container = document.getElementById("fileContent");
    const currentScrollPosition = container ? container.scrollTop : 0;
    viewFile(currentFileName);
    setTimeout(() => {
      const newContainer = document.getElementById("fileContent");
      if (newContainer) {
        newContainer.scrollTop = currentScrollPosition;
      }
    }, 100);
  }
}

function fetchDirectoryInfo() {
  const baseUrl = getBaseUrl();
  fetch(`${baseUrl}/directory_info`)
    .then((response) => response.json())
    .then((data) => {
      if (data.directory) {
        trajectoryDirectory = data.directory;
        document.title = `Trajectory Inspector: ${data.directory}`;
        const dirEl = document.getElementById("directoryInfo");
        if (dirEl) {
          dirEl.textContent = `Directory: ${data.directory}`;
        }
      }
    })
    .catch((error) => console.error("Error fetching directory info:", error));
}

window.onload = function () {
  initTheme();
  fetchFiles();
  fetchDirectoryInfo();
};
