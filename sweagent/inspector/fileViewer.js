let currentFileName = null;
let trajectoryDirectory = "";
let timeoutIds = [];

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
        const fileElement = document.createElement("li");
        fileElement.textContent = file;
        fileElement.onclick = () => viewFile(file.split(" ")[0]);
        fileList.appendChild(fileElement);
      });
    });
}

function createTrajectoryItem(item, index) {
  const elementId = `trajectoryItem${index}`;

  // Check for old format and log a warning
  const isOldFormat = item.messages && !item.query;
  if (isOldFormat) {
    console.log(
      `Found old format using 'messages' instead of 'query' in item ${index}`,
    );
    // Migrate old format to new format
    item.query = item.messages;
  }

  const hasMessages = item.query && item.query.length > 0;

  const escapeHtml = (text) => {
    if (!text) {
      return "";
    }
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  const processImagesInObservation = (observation) => {
    if (!observation) {
      return { processedText: "", images: [] };
    }

    // regex to match markdown-style base64 images: ![alt text](data:image/<format>;base64,<base64-data>)
    const imageRegex = /!\[([^\]]*)\]\(data:image\/([^;]+);base64,([^)]+)\)/g;
    const images = [];
    let processedText = observation;
    let match;

    while ((match = imageRegex.exec(observation)) !== null) {
      const [fullMatch, altText, format, base64Data] = match;

      // create image object
      const imageObj = {
        altText: altText || "Image",
        format: format,
        dataUrl: `data:image/${format};base64,${base64Data}`,
        id: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      };

      images.push(imageObj);

      // replace the full base64 string with a placeholder
      processedText = processedText.replace(
        fullMatch,
        `[IMAGE: ${imageObj.altText}]`,
      );
    }

    return { processedText, images };
  };

  const getMessageContent = (msg) => {
    if (!msg.content) {
      return "";
    }

    // Handle content as a string
    if (typeof msg.content === "string") {
      return msg.content;
    }

    // Handle content as an array with a dictionary containing 'text' key
    if (
      Array.isArray(msg.content) &&
      msg.content.length > 0 &&
      msg.content[0].text
    ) {
      return msg.content[0].text;
    }

    // Fallback to stringifying the content
    return JSON.stringify(msg.content);
  };

  const messagesContent = hasMessages
    ? item.query
        .map((msg, msgIndex) => {
          let content = `----Item ${msgIndex}-----\n`;
          content += `role: ${msg.role}\n`;
          content += `content: |\n${escapeHtml(getMessageContent(msg))}\n`;

          if (msg.tool_calls && msg.tool_calls.length > 0) {
            msg.tool_calls.forEach((tool, idx) => {
              content += `- tool call ${idx + 1}:\n`;
              if (tool.function) {
                content += `    - name: ${tool.function.name}\n`;
                // Handle arguments based on type
                let args = tool.function.arguments;
                try {
                  if (typeof args === "string") {
                    args = JSON.parse(args);
                  }
                  content += `    - arguments: ${JSON.stringify(args, null, 2).replace(/\n/g, "\n    ")}\n`;
                } catch (e) {
                  content += `    - arguments: ${escapeHtml(String(args))}\n`;
                }
              }
              content += `    - id: ${tool.id}\n`;
            });
          }

          if (msg.is_demo) {
            return `<span class="demo-message">${content}</span>`;
          }
          return content;
        })
        .join("\n")
    : "";

  // Process images in observation
  const { processedText: processedObservation, images: observationImages } =
    processImagesInObservation(item.observation);

  // Create separate image pane HTML if there are images
  const observationImagesPane =
    observationImages.length > 0
      ? `<div class="observation-images-section" data-title="Observation Images">
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

  return `
        <div class="trajectory-item fade-in" id="${elementId}">
            <div class="trajectory-main">
                <div class="response-section" data-title="Response">
                    <div class="content-wrapper">
                        <pre><code class="language-python">Response:
${escapeHtml(item.response)}

Action:
${escapeHtml(item.action)}</code></pre>
                    </div>
                </div>
                <div class="observation-section" data-title="Environment Observation">
                    <div class="content-wrapper">
                        <pre><code class="language-python">${escapeHtml(processedObservation)}</code></pre>
                    </div>
                </div>
                ${observationImagesPane}
                ${
                  item.execution_time
                    ? `<div class="execution-time">Execution time: ${item.execution_time}s</div>`
                    : ""
                }
            </div>
            ${
              hasMessages
                ? `
                <div class="messages-section" data-title="Messages">
                    <div class="content-wrapper">
                        <pre>${messagesContent}</pre>
                    </div>
                </div>
            `
                : ""
            }
        </div>
    `;
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
      const container = document.getElementById("fileContent");
      container.innerHTML = "";

      if (content.trajectory && Array.isArray(content.trajectory)) {
        content.trajectory.forEach((item, index) => {
          container.innerHTML += createTrajectoryItem(item, index);

          // Highlight code blocks after adding them
          const newItem = document.getElementById(`trajectoryItem${index}`);
          newItem.querySelectorAll("pre code").forEach((block) => {
            hljs.highlightElement(block);
          });
        });

        // Initialize image click handlers after all items are added
        initializeImageHandlers();
      } else {
        container.textContent = "No trajectory content found.";
      }
    })
    .catch((error) => {
      console.error("Error fetching file:", error);
      document.getElementById("fileContent").textContent =
        "Error loading content. " + error;
    });

  // Highlight selected file
  document.querySelectorAll("#fileList li").forEach((li) => {
    li.classList.remove("selected");
    if (li.textContent.split(" ")[0] === fileName) {
      li.classList.add("selected");
    }
  });
}

function initializeImageHandlers() {
  // Remove existing overlay if present
  const existingOverlay = document.querySelector(".image-overlay");
  if (existingOverlay) {
    existingOverlay.remove();
  }

  // Create overlay element
  const overlay = document.createElement("div");
  overlay.className = "image-overlay";
  document.body.appendChild(overlay);

  // Add click handlers to all observation images
  document.querySelectorAll(".observation-image").forEach((img) => {
    img.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();

      // Toggle expanded state
      if (this.classList.contains("expanded")) {
        this.classList.remove("expanded");
        overlay.classList.remove("active");
      } else {
        // Remove expanded class from all other images
        document
          .querySelectorAll(".observation-image.expanded")
          .forEach((otherImg) => {
            otherImg.classList.remove("expanded");
          });

        // Add expanded class to clicked image
        this.classList.add("expanded");
        overlay.classList.add("active");
      }
    });
  });

  // Close expanded image when clicking overlay
  overlay.addEventListener("click", function () {
    document.querySelectorAll(".observation-image.expanded").forEach((img) => {
      img.classList.remove("expanded");
    });
    overlay.classList.remove("active");
  });

  // Close expanded image when pressing Escape key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document
        .querySelectorAll(".observation-image.expanded")
        .forEach((img) => {
          img.classList.remove("expanded");
        });
      overlay.classList.remove("active");
    }
  });
}

function refreshCurrentFile() {
  if (currentFileName) {
    const currentScrollPosition =
      document.documentElement.scrollTop || document.body.scrollTop;
    viewFile(currentFileName.split(" ")[0]);
    setTimeout(() => {
      window.scrollTo(0, currentScrollPosition);
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
        document.title = `Trajectory Viewer: ${data.directory}`;
        document.getElementById("directoryInfo").textContent =
          `Directory: ${data.directory}`;
      }
    })
    .catch((error) => console.error("Error fetching directory info:", error));
}

window.onload = function () {
  fetchFiles();
  fetchDirectoryInfo();
};
