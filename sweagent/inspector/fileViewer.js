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
                        <pre><code class="language-python">${escapeHtml(item.observation)}</code></pre>
                    </div>
                </div>
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
