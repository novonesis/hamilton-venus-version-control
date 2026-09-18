/* ================================================================
   Hamilton Method Versionator — Main Application JavaScript
   ================================================================ */

"use strict";

// Wait for pywebview API to be available
window.addEventListener("pywebviewready", function () {
  initTabs();
  initUsageGuide();
  initFolderCreator();
  initFolderSync();
  initFileConverter();
  initLabwareSync();
  initLibrarySync();
  initFileSearch();
});


/* ── Tab Switching ──────────────────────────────────────────────── */

function initTabs() {
  const strip = document.getElementById("tabStrip");
  const links = strip.querySelectorAll("a[data-tab]");

  links.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      var tabId = this.getAttribute("data-tab");

      // Deactivate all
      links.forEach(function (l) { l.classList.remove("active"); });
      document.querySelectorAll(".tab-panel").forEach(function (p) {
        p.classList.remove("active");
      });

      // Activate selected
      this.classList.add("active");
      var panel = document.getElementById("panel-" + tabId);
      if (panel) panel.classList.add("active");
    });
  });
}


/* ── Log Polling Engine ─────────────────────────────────────────── */

var _logPollers = {};

function startLogPoller(tab, domElement) {
  if (_logPollers[tab]) return; // already running
  var cursor = 0;
  _logPollers[tab] = setInterval(function () {
    pywebview.api.poll_logs(tab, cursor).then(function (data) {
      if (data.lines.length > 0) {
        data.lines.forEach(function (line) {
          var container = document.createElement("div");
          container.className = "log-line";

          // Parse: "HH:mm:ss | LEVEL | message"
          var parts = line.split(" | ");
          if (parts.length >= 3) {
            var time = parts[0];
            var level = parts[1].trim().toLowerCase();
            var msg = parts.slice(2).join(" | ");

            var timeSpan = document.createElement("span");
            timeSpan.className = "log-timestamp";
            timeSpan.textContent = time;
            container.appendChild(timeSpan);

            var levelSpan = document.createElement("span");
            levelSpan.className = "log-level level-" + level;
            levelSpan.textContent = level;
            container.appendChild(levelSpan);

            var msgSpan = document.createElement("span");
            msgSpan.className = "log-message" + (level === "error" ? " msg-error" : level === "success" ? " msg-success" : level === "warning" ? " msg-warning" : "");
            msgSpan.textContent = msg;
            container.appendChild(msgSpan);
          } else {
            container.textContent = line;
          }

          domElement.appendChild(container);
        });
        domElement.scrollTop = domElement.scrollHeight;
      }
      cursor = data.cursor;
    });
  }, 200);
}

function stopLogPoller(tab) {
  if (_logPollers[tab]) {
    clearInterval(_logPollers[tab]);
    delete _logPollers[tab];
  }
}


/* ── Task Polling (disable/enable buttons) ──────────────────────── */

function pollTaskUntilDone(tab, onDone) {
  var interval = setInterval(function () {
    pywebview.api.is_task_running(tab).then(function (running) {
      if (!running) {
        clearInterval(interval);
        if (onDone) onDone();
      }
    });
  }, 300);
}


/* ── Clipboard Helper ───────────────────────────────────────────── */

function copyToClipboard(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text);
  } else {
    // Fallback
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }
}


/* ── Toast Notification ────────────────────────────────────────── */

var _toastTimer = null;

function showToast(message) {
  var toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("visible");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function () {
    toast.classList.remove("visible");
    _toastTimer = null;
  }, 2000);
}


/* ── Dependency Tree Renderer ───────────────────────────────────── */

function renderDependencyTree(container, treeData) {
  container.innerHTML = "";

  if (!treeData || !treeData.dependencies || treeData.dependencies.length === 0) {
    container.innerHTML = '<span class="text-muted">No dependencies found.</span>';
    return;
  }

  // Header with expand/collapse toggle
  var header = document.createElement("div");
  header.className = "tree-header";

  var headerText = document.createElement("span");
  headerText.textContent = treeData.source_file_name + " (" +
    treeData.primary_count + " primary, " +
    treeData.total_unique + " total, " +
    treeData.max_level + " levels)";
  header.appendChild(headerText);

  var toggleBtn = document.createElement("button");
  toggleBtn.className = "tree-toggle-btn";
  toggleBtn.textContent = "Collapse All";
  toggleBtn.addEventListener("click", function () {
    var allDetails = container.querySelectorAll("details");
    var shouldOpen = toggleBtn.textContent === "Expand All";
    allDetails.forEach(function (d) { d.open = shouldOpen; });
    toggleBtn.textContent = shouldOpen ? "Collapse All" : "Expand All";
  });
  header.appendChild(toggleBtn);

  container.appendChild(header);

  // Track currently selected row (single-select)
  var selectedRow = null;

  function selectRow(row, node) {
    if (selectedRow) selectedRow.classList.remove("selected");
    row.classList.add("selected");
    selectedRow = row;
    if (node.resolved_path) {
      copyToClipboard(node.resolved_path);
      showToast("Copied: " + (node.file_name || node.resolved_path));
    }
  }

  var counter = 0;

  function buildNodeRow(node, label) {
    var row = document.createElement("div");
    row.className = "node-row";

    var nameSpan = document.createElement("span");
    nameSpan.className = "node-name " + (node.resolved ? "node-resolved" : "node-unresolved");
    nameSpan.textContent = label;
    nameSpan.title = node.resolved_path || "UNRESOLVED";
    row.appendChild(nameSpan);

    if (!node.resolved) {
      var badge = document.createElement("span");
      badge.style.color = "var(--color-status-error)";
      badge.style.fontSize = "var(--font-size-xs)";
      badge.textContent = "[UNRESOLVED]";
      row.appendChild(badge);
    }

    // Copy icon (appears on hover via CSS)
    if (node.resolved_path) {
      var copyIcon = document.createElement("span");
      copyIcon.className = "copy-icon";
      copyIcon.textContent = "\u{1F4CB}";
      row.appendChild(copyIcon);
    }

    // Path hint (shown on hover via CSS)
    if (node.resolved_path) {
      var hint = document.createElement("div");
      hint.className = "node-path-hint";
      hint.textContent = node.resolved_path;
      row.appendChild(hint);
    }

    row.addEventListener("click", function (e) {
      e.stopPropagation();
      selectRow(row, node);
    });

    return row;
  }

  function renderNode(node, parentEl, isTopLevel) {
    var hasChildren = node.children && node.children.length > 0;
    var label = node.file_name || "[UNKNOWN]";
    if (isTopLevel) {
      counter++;
      label = counter + ". " + label;
    }

    if (hasChildren) {
      var details = document.createElement("details");
      details.open = true;

      var summary = document.createElement("summary");
      var row = buildNodeRow(node, label);
      summary.appendChild(row);

      // Prevent row click from toggling details
      row.addEventListener("click", function (e) {
        e.preventDefault();
      });

      details.appendChild(summary);

      node.children.forEach(function (child) {
        renderNode(child, details, false);
      });

      parentEl.appendChild(details);
    } else {
      var leaf = document.createElement("div");
      leaf.className = "leaf";
      var row = buildNodeRow(node, label);
      leaf.appendChild(row);
      parentEl.appendChild(leaf);
    }
  }

  treeData.dependencies.forEach(function (dep) {
    renderNode(dep, container, dep.level === 1);
  });
}


/* ================================================================
   Tab Implementations
   ================================================================ */


/* ── Tab 1: Usage Guide ─────────────────────────────────────────── */

function initUsageGuide() {
  pywebview.api.get_usage_guide_markdown().then(function (md) {
    var container = document.getElementById("usageGuideContent");
    if (typeof marked !== "undefined" && marked.parse) {
      container.innerHTML = marked.parse(md);
    } else {
      container.textContent = md;
    }
  });
}


/* ── Tab 2: Folder Creator ──────────────────────────────────────── */

function initFolderCreator() {
  var destInput = document.getElementById("fcDestPath");
  var nameInput = document.getElementById("fcMethodName");
  var medInput = document.getElementById("fcMedFile");
  var dialog = document.getElementById("fcConfirmDialog");

  document.getElementById("fcBrowseDest").addEventListener("click", function () {
    pywebview.api.browse_folder_creation().then(function (path) {
      if (path) destInput.value = path;
    });
  });

  document.getElementById("fcBrowseMed").addEventListener("click", function () {
    pywebview.api.browse_med_file().then(function (path) {
      if (path) medInput.value = path;
    });
  });

  document.getElementById("fcCreate").addEventListener("click", function () {
    var dest = destInput.value.trim();
    var name = nameInput.value.trim();
    var med = medInput.value.trim();

    if (!dest || !name) {
      alert("Both Destination Path and Method Name are required.");
      return;
    }

    pywebview.api.create_folder_structure(dest, name, med, false).then(function (result) {
      if (result.status === "success") {
        alert(result.message);
      } else if (result.status === "error") {
        alert("Error: " + result.message);
      } else if (result.status === "confirm_needed") {
        document.getElementById("fcConfirmMessage").textContent = result.message;
        dialog.showModal();
      }
    });
  });

  document.getElementById("fcConfirmYes").addEventListener("click", function () {
    dialog.close();
    var dest = destInput.value.trim();
    var name = nameInput.value.trim();
    var med = medInput.value.trim();
    pywebview.api.create_folder_structure(dest, name, med, true).then(function (result) {
      if (result.status === "success") {
        alert(result.message);
      } else {
        alert("Error: " + result.message);
      }
    });
  });

  document.getElementById("fcConfirmNo").addEventListener("click", function () {
    dialog.close();
  });
}


/* ── Tab 3: Folder Sync ─────────────────────────────────────────── */

function initFolderSync() {
  var csvPath = null;
  var csvLabel = document.getElementById("fsCsvLabel");
  var freqInput = document.getElementById("fsFrequency");
  var toggleBtn = document.getElementById("fsToggle");
  var statusLabel = document.getElementById("fsStatus");
  var monitoring = false;
  var statusPollInterval = null;

  document.getElementById("fsSelectCsv").addEventListener("click", function () {
    pywebview.api.select_csv_file().then(function (path) {
      if (path) {
        csvPath = path;
        csvLabel.textContent = "CSV: " + path;
        statusLabel.textContent = "Status: Ready";
        statusLabel.className = "status-label ready";
      }
    });
  });

  toggleBtn.addEventListener("click", function () {
    if (!monitoring) {
      // Start
      if (!csvPath) {
        alert("Please select a CSV file first.");
        return;
      }
      var freq = parseInt(freqInput.value, 10) || 10;
      pywebview.api.start_monitoring(csvPath, freq).then(function (result) {
        if (result.ok) {
          monitoring = true;
          toggleBtn.textContent = "Stop Monitoring";
          statusLabel.textContent = "Status: Running";
          statusLabel.className = "status-label running";
          // Poll status
          statusPollInterval = setInterval(function () {
            pywebview.api.get_monitoring_status().then(function (s) {
              statusLabel.textContent = "Status: " + s;
              if (s === "Stopped" || s.startsWith("Error")) {
                statusLabel.className = "status-label stopped";
                monitoring = false;
                toggleBtn.textContent = "Start Monitoring";
                clearInterval(statusPollInterval);
              }
            });
          }, 1000);
        } else {
          alert(result.message);
        }
      });
    } else {
      // Stop
      pywebview.api.stop_monitoring().then(function (result) {
        monitoring = false;
        toggleBtn.textContent = "Start Monitoring";
        statusLabel.textContent = "Status: Stopped";
        statusLabel.className = "status-label stopped";
        if (statusPollInterval) clearInterval(statusPollInterval);
      });
    }
  });
}


/* ── Tab 4: File Converter ──────────────────────────────────────── */

function initFileConverter() {
  var folderPath = null;
  var pathDisplay = document.getElementById("cvPathDisplay");
  var logArea = document.getElementById("cvLogArea");
  var startBtn = document.getElementById("cvStartConversion");

  document.getElementById("cvSelectFolder").addEventListener("click", function () {
    pywebview.api.select_conversion_folder().then(function (path) {
      if (path) {
        folderPath = path;
        pathDisplay.textContent = path;
        pathDisplay.classList.add("has-path");
        startBtn.disabled = false;
        logArea.innerHTML = "";
      }
    });
  });

  startBtn.addEventListener("click", function () {
    if (!folderPath) return;
    startBtn.disabled = true;
    startBtn.classList.add("flashing");
    logArea.innerHTML = "";

    pywebview.api.start_conversion(folderPath).then(function (result) {
      if (result.ok) {
        startLogPoller("conversion", logArea);
        pollTaskUntilDone("conversion", function () {
          stopLogPoller("conversion");
          startBtn.disabled = false;
          startBtn.classList.remove("flashing");
        });
      } else {
        alert(result.message);
        startBtn.disabled = false;
        startBtn.classList.remove("flashing");
      }
    });
  });
}


/* ── Tab 5: Labware Sync ────────────────────────────────────────── */

function initLabwareSync() {
  var pathDisplay = document.getElementById("lwPathDisplay");
  var logArea = document.getElementById("lwLogArea");
  var processBtn = document.getElementById("lwProcess");
  var selectBtn = document.getElementById("lwSelectFolder");

  selectBtn.addEventListener("click", function () {
    logArea.innerHTML = "";
    pywebview.api.select_labware_folder().then(function (result) {
      if (result) {
        pathDisplay.textContent = result.folder;
        pathDisplay.classList.add("has-path");
        processBtn.disabled = false;
        startLogPoller("labware", logArea);
      }
    });
  });

  processBtn.addEventListener("click", function () {
    processBtn.disabled = true;
    selectBtn.disabled = true;
    processBtn.classList.add("flashing");
    logArea.innerHTML = "";
    startLogPoller("labware", logArea);

    pywebview.api.start_labware_processing().then(function (result) {
      if (result.ok) {
        pollTaskUntilDone("labware", function () {
          stopLogPoller("labware");
          processBtn.disabled = false;
          selectBtn.disabled = false;
          processBtn.classList.remove("flashing");
        });
      } else {
        alert(result.message);
        processBtn.disabled = false;
        selectBtn.disabled = false;
        processBtn.classList.remove("flashing");
      }
    });
  });
}


/* ── Tab 6: Library Sync ────────────────────────────────────────── */

function initLibrarySync() {
  var hslPath = null;
  var pathDisplay = document.getElementById("lsPathDisplay");
  var logArea = document.getElementById("lsLogArea");
  var treeArea = document.getElementById("lsDepTree");
  var startBtn = document.getElementById("lsStartSync");
  var selectBtn = document.getElementById("lsSelectFile");

  selectBtn.addEventListener("click", function () {
    pywebview.api.select_hsl_file().then(function (path) {
      if (path) {
        if (!path.toLowerCase().endsWith(".hsl")) {
          alert("Please select a .hsl file.");
          return;
        }
        hslPath = path;
        pathDisplay.textContent = path;
        pathDisplay.classList.add("has-path");
        startBtn.disabled = false;
        treeArea.innerHTML = '<span class="text-muted">Dependency tree will appear here after sync.</span>';
      }
    });
  });

  startBtn.addEventListener("click", function () {
    if (!hslPath) return;
    startBtn.disabled = true;
    selectBtn.disabled = true;
    startBtn.classList.add("flashing");
    logArea.innerHTML = "";
    treeArea.innerHTML = '<span class="text-muted">Syncing...</span>';

    pywebview.api.start_library_sync(hslPath).then(function (result) {
      if (result.ok) {
        startLogPoller("library", logArea);
        pollTaskUntilDone("library", function () {
          stopLogPoller("library");
          startBtn.disabled = false;
          selectBtn.disabled = false;
          startBtn.classList.remove("flashing");
          // Fetch tree data
          pywebview.api.get_library_tree_data().then(function (data) {
            if (data) {
              renderDependencyTree(treeArea, data);
            } else {
              treeArea.innerHTML = '<span class="text-muted">No dependency data available.</span>';
            }
          });
        });
      } else {
        alert(result.message);
        startBtn.disabled = false;
        selectBtn.disabled = false;
        startBtn.classList.remove("flashing");
      }
    });
  });
}


/* ── Tab 7: File Search ─────────────────────────────────────────── */

function initFileSearch() {
  var queryInput = document.getElementById("srQuery");
  var auxCheckbox = document.getElementById("srIncludeAux");
  var resultsBody = document.getElementById("srResultsBody");
  var pathDisplay = document.getElementById("srPathDisplay");
  var searchFolder = null;
  var selectedRow = null;

  // Step 1: Select folder
  document.getElementById("srSelectFolder").addEventListener("click", function () {
    pywebview.api.select_search_folder().then(function (folder) {
      if (folder) {
        searchFolder = folder;
        pathDisplay.textContent = folder;
        pathDisplay.classList.add("has-path");
      }
    });
  });

  // Step 2: Search within already-selected folder
  document.getElementById("srSearch").addEventListener("click", function () {
    if (!searchFolder) {
      alert("Please select a search folder first.");
      return;
    }
    var query = queryInput.value.trim();
    if (!query) {
      alert("Please enter a search string.");
      return;
    }

    resultsBody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center; padding:20px;">Searching...</td></tr>';
    selectedRow = null;

    pywebview.api.search_files(searchFolder, query, auxCheckbox.checked).then(function (results) {
      resultsBody.innerHTML = "";

      if (results.length === 0) {
        resultsBody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center; padding:20px;">No results found.</td></tr>';
        return;
      }

      results.forEach(function (r) {
        var tr = document.createElement("tr");

        var tdPath = document.createElement("td");
        tdPath.textContent = r.path;
        tdPath.title = r.path;
        tr.appendChild(tdPath);

        var tdLine = document.createElement("td");
        tdLine.textContent = r.line;
        tdLine.style.textAlign = "center";
        tr.appendChild(tdLine);

        var tdContent = document.createElement("td");
        tdContent.textContent = r.content;
        tdContent.className = "clickable";
        tdContent.title = "Click to copy line content";
        tdContent.addEventListener("click", function (e) {
          e.stopPropagation();
          copyToClipboard(r.content);
          showToast("Copied line content");
        });
        tr.appendChild(tdContent);

        // Row click → select, copy path, toast
        tr.addEventListener("click", function () {
          if (selectedRow) selectedRow.classList.remove("selected");
          tr.classList.add("selected");
          selectedRow = tr;
          copyToClipboard(r.path);
          showToast("Copied: " + r.path);
        });

        resultsBody.appendChild(tr);
      });
    });
  });

  // Allow Enter key to trigger search
  queryInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      document.getElementById("srSearch").click();
    }
  });
}
