const state = {
  tests: new Map(),
  explicitSelection: new Set(),
  effectiveSelection: new Set(),
  requiredSelection: new Set(),
  rowInputs: new Map(),
  loading: false,
  runState: "idle",
  cancellationRequested: false,
  socket: null,
  reconnectTimer: null,
  reconnectAttempt: 0,
};

const elements = {
  catalog: document.querySelector("#catalog"),
  catalogMessage: document.querySelector("#catalog-message"),
  selectionSummary: document.querySelector("#selection-summary"),
  selectAll: document.querySelector("#select-all"),
  runSummary: document.querySelector("#run-summary"),
  run: document.querySelector("#run"),
  cancel: document.querySelector("#cancel"),
  refresh: document.querySelector("#refresh"),
  flexReady: document.querySelector("#flex-ready"),
  headed: document.querySelector("#headed"),
  connection: document.querySelector("#connection"),
  selectionCovers: document.querySelector("#selection-covers"),
  currentTest: document.querySelector("#current-test"),
  emptyProgress: document.querySelector("#empty-progress"),
  events: document.querySelector("#events"),
  sourceRegion: document.querySelector("#source-region"),
  sourcePath: document.querySelector("#source-path"),
  sourceCode: document.querySelector("#source-code"),
  sourceOpenEditor: document.querySelector("#source-open-editor"),
  sourceClose: document.querySelector("#source-close"),
  artifactRegion: document.querySelector("#artifact-region"),
  artifacts: document.querySelector("#artifacts"),
};

function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

function formatCase(caseEntry) {
  if (!caseEntry) return "";
  const title = caseEntry.title || "";
  const id = caseEntry.id || "";
  if (title && id) return `${title} (${id})`;
  return title || id;
}

function casesFor(testOrNodeId) {
  const test = typeof testOrNodeId === "string" ? state.tests.get(testOrNodeId) : testOrNodeId;
  return Array.isArray(test?.cases) ? test.cases : [];
}

function renderSelectionCovers() {
  const panel = elements.selectionCovers;
  if (!panel) return;
  panel.replaceChildren();
  if (!state.effectiveSelection.size) {
    panel.classList.add("hidden");
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = "Cases covered by selection";
  panel.append(heading);

  const list = document.createElement("div");
  list.className = "covers-list";
  for (const nodeId of state.effectiveSelection) {
    const test = state.tests.get(nodeId);
    if (!test) continue;
    const block = document.createElement("article");
    block.className = "cover-block";
    const title = document.createElement("strong");
    title.textContent = test.label;
    block.append(title);
    const cases = casesFor(test);
    if (!cases.length) {
      const empty = document.createElement("small");
      empty.textContent = "No TestRail cases mapped yet";
      block.append(empty);
    } else {
      const ul = document.createElement("ul");
      for (const entry of cases) {
        const li = document.createElement("li");
        li.textContent = formatCase(entry);
        ul.append(li);
      }
      block.append(ul);
    }
    list.append(block);
  }
  panel.append(list);
  panel.classList.remove("hidden");
}

function isCalibration(test) {
  // Mirrors the current server-side readiness rule.
  return test.node_id.includes("/calibration/");
}

function prerequisiteChainIsAvailable(nodeId, visiting = new Set()) {
  if (visiting.has(nodeId)) return false;
  const test = state.tests.get(nodeId);
  if (!test || (isCalibration(test) && !elements.flexReady.checked)) return false;
  if (!test.requires) return true;
  visiting.add(nodeId);
  const available = prerequisiteChainIsAvailable(test.requires, visiting);
  visiting.delete(nodeId);
  return available;
}

function unavailableReason(test) {
  if (!test.implemented) return test.skip_reason || "This workflow is a skipped placeholder.";
  if (isCalibration(test) && !elements.flexReady.checked) return "Confirm Flex readiness above to select this test.";
  if (test.requires && !state.tests.has(test.requires)) return "Its prerequisite is missing from the catalog.";
  if (test.requires && !prerequisiteChainIsAvailable(test.requires)) {
    return "Its prerequisite is not currently available.";
  }
  return "";
}

function addPrerequisiteClosure(nodeId, selection, visiting = new Set()) {
  if (visiting.has(nodeId)) return;
  const test = state.tests.get(nodeId);
  if (!test || !prerequisiteChainIsAvailable(nodeId)) return;
  selection.add(nodeId);
  if (test.requires) {
    visiting.add(nodeId);
    addPrerequisiteClosure(test.requires, selection, visiting);
    visiting.delete(nodeId);
  }
}

function collectRequiredNodes(nodeId, required, visiting = new Set()) {
  if (visiting.has(nodeId)) return;
  const test = state.tests.get(nodeId);
  if (!test?.requires || !state.tests.has(test.requires)) return;
  visiting.add(nodeId);
  required.add(test.requires);
  collectRequiredNodes(test.requires, required, visiting);
  visiting.delete(nodeId);
}

function reconcileSelection() {
  for (const nodeId of [...state.explicitSelection]) {
    if (!prerequisiteChainIsAvailable(nodeId)) state.explicitSelection.delete(nodeId);
  }

  const effective = new Set();
  for (const nodeId of state.explicitSelection) addPrerequisiteClosure(nodeId, effective);
  state.effectiveSelection = effective;
  const required = new Set();
  for (const nodeId of effective) collectRequiredNodes(nodeId, required);
  state.requiredSelection = required;
  updateControls();
  renderSelectionCovers();
}

function setToggleState(toggle, nodeIds) {
  const available = nodeIds.filter((nodeId) => prerequisiteChainIsAvailable(nodeId));
  const checkedCount = available.filter((nodeId) => state.effectiveSelection.has(nodeId)).length;
  toggle.checked = available.length > 0 && checkedCount === available.length;
  toggle.indeterminate = checkedCount > 0 && checkedCount < available.length;
  toggle.disabled = state.runState !== "idle" || available.length === 0;
}

function updateControls() {
  for (const [nodeId, input] of state.rowInputs) {
    const test = state.tests.get(nodeId);
    const available = prerequisiteChainIsAvailable(nodeId);
    const required = state.requiredSelection.has(nodeId);
    input.checked = state.effectiveSelection.has(nodeId);
    input.disabled = state.runState !== "idle" || !available || required;

    const row = input.closest(".test-row");
    row.classList.toggle("locked", required);
    row.classList.toggle("unavailable", !available);
    const lock = row.querySelector(".lock-note");
    lock.textContent = required ? "Selected and locked as a prerequisite" : unavailableReason(test);
    lock.hidden = !lock.textContent;
  }

  document.querySelectorAll("[data-group-toggle]").forEach((toggle) => {
    setToggleState(toggle, JSON.parse(toggle.dataset.nodeIds));
  });
  document.querySelectorAll("[data-section-toggle]").forEach((toggle) => {
    setToggleState(toggle, JSON.parse(toggle.dataset.nodeIds));
  });
  setToggleState(elements.selectAll, [...state.tests.keys()]);

  const selectedCount = state.effectiveSelection.size;
  const requiredCount = state.requiredSelection.size;
  elements.selectionSummary.textContent =
    `${plural(selectedCount, "test")} selected` +
    (requiredCount ? ` · ${plural(requiredCount, "prerequisite")} locked` : "");
  elements.run.disabled = state.runState !== "idle" || selectedCount === 0 || state.loading;
  elements.cancel.disabled = state.runState !== "running";
  elements.cancel.textContent = state.runState === "cancelling" ? "Cancelling…" : "Cancel run";
  elements.refresh.disabled = state.runState !== "idle" || state.loading;
  elements.flexReady.disabled = state.runState !== "idle";
  elements.headed.disabled = state.runState !== "idle";
}

function applyBulkSelection(nodeIds, checked) {
  for (const nodeId of nodeIds) {
    if (!prerequisiteChainIsAvailable(nodeId)) continue;
    if (checked) state.explicitSelection.add(nodeId);
    else state.explicitSelection.delete(nodeId);
  }
  reconcileSelection();
}

function makeToggle(attribute, value, nodeIds, label) {
  const wrapper = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.dataset[attribute] = value;
  input.dataset.nodeIds = JSON.stringify(nodeIds);
  input.addEventListener("change", () => applyBulkSelection(nodeIds, input.checked));
  const text = document.createElement("span");
  text.textContent = label;
  wrapper.append(input, text);
  return wrapper;
}

function makeTestRow(test) {
  const row = document.createElement("div");
  row.className = "test-row";
  const label = document.createElement("label");
  label.className = "test-select";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.dataset.nodeId = test.node_id;
  input.addEventListener("change", () => {
    if (input.checked) state.explicitSelection.add(test.node_id);
    else state.explicitSelection.delete(test.node_id);
    reconcileSelection();
  });
  state.rowInputs.set(test.node_id, input);

  const copy = document.createElement("span");
  copy.className = "test-copy";
  const title = document.createElement("strong");
  title.textContent = test.label;
  const note = document.createElement("small");
  note.className = "lock-note";
  note.hidden = true;
  copy.append(title, note);
  label.append(input, copy);
  row.append(label);

  if (test.file) {
    const source = document.createElement("button");
    source.type = "button";
    source.className = "catalog-source";
    source.textContent = "Code";
    source.title = test.line ? `${test.file}:${test.line}` : test.file;
    source.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openSource(test.file, test.line);
    });
    row.append(source);
  }

  if (!test.implemented) {
    const placeholder = document.createElement("em");
    placeholder.className = "chip neutral";
    placeholder.textContent = "Placeholder";
    row.append(placeholder);
  } else if (isCalibration(test)) {
    const readiness = document.createElement("em");
    readiness.className = "chip warning";
    readiness.textContent = "Flex readiness";
    row.append(readiness);
  } else if (test.requires) {
    const dependency = document.createElement("em");
    dependency.className = "chip dependency";
    dependency.textContent = "Has prerequisite";
    row.append(dependency);
  }
  return row;
}

function renderCatalog(payload) {
  if (!payload || !Array.isArray(payload.groups) || !Array.isArray(payload.tests)) {
    throw new Error("Catalog response is missing groups or tests.");
  }

  state.tests = new Map(payload.tests.map((test) => [test.node_id, test]));
  state.rowInputs.clear();
  state.explicitSelection = new Set(
    [...state.explicitSelection].filter((nodeId) => state.tests.has(nodeId)),
  );
  elements.catalog.replaceChildren();

  const orderedGroups = [...payload.groups].sort((left, right) => left.order - right.order);
  for (const group of orderedGroups) {
    const tests = payload.tests.filter((test) => test.group === group.id);
    if (!tests.length) continue;

    const article = document.createElement("article");
    article.className = "workflow";
    const groupHeader = document.createElement("div");
    groupHeader.className = "workflow-header";
    groupHeader.append(makeToggle("groupToggle", group.id, tests.map((test) => test.node_id), group.label));
    const count = document.createElement("small");
    count.textContent = plural(tests.length, "test");
    groupHeader.append(count);
    article.append(groupHeader);

    const sections = new Map();
    for (const test of tests) {
      if (!sections.has(test.section)) sections.set(test.section, []);
      sections.get(test.section).push(test);
    }
    for (const [sectionName, sectionTests] of sections) {
      const section = document.createElement("section");
      section.className = "workflow-section";
      const sectionHeader = document.createElement("div");
      sectionHeader.className = "section-header";
      sectionHeader.append(
        makeToggle(
          "sectionToggle",
          `${group.id}:${sectionName}`,
          sectionTests.map((test) => test.node_id),
          sectionName,
        ),
      );
      section.append(sectionHeader);
      for (const test of sectionTests) section.append(makeTestRow(test));
      article.append(section);
    }
    elements.catalog.append(article);
  }

  if (!state.tests.size) {
    showCatalogMessage("No workflow tests were found.", "neutral");
  } else {
    hideCatalogMessage();
  }
  elements.catalog.setAttribute("aria-busy", "false");
  reconcileSelection();
}

function showCatalogMessage(message, tone = "error") {
  elements.catalogMessage.textContent = message;
  elements.catalogMessage.className = `message ${tone}`;
}

function hideCatalogMessage() {
  elements.catalogMessage.className = "message hidden";
  elements.catalogMessage.textContent = "";
}

async function responseError(response) {
  const text = await response.text();
  try {
    const body = JSON.parse(text);
    return body.detail || JSON.stringify(body);
  } catch {
    return text || `${response.status} ${response.statusText}`;
  }
}

async function loadCatalog(refresh = false) {
  state.loading = true;
  elements.catalog.setAttribute("aria-busy", "true");
  elements.selectionSummary.textContent = refresh ? "Refreshing catalog…" : "Loading catalog…";
  hideCatalogMessage();
  updateControls();
  try {
    const response = await fetch(`/api/catalog${refresh ? "?refresh=true" : ""}`);
    if (!response.ok) throw new Error(await responseError(response));
    renderCatalog(await response.json());
  } catch (error) {
    showCatalogMessage(`Could not load catalog: ${error.message}`);
    elements.catalog.setAttribute("aria-busy", "false");
    elements.selectionSummary.textContent = "Catalog unavailable";
  } finally {
    state.loading = false;
    updateControls();
  }
}

function setRunState(runState) {
  state.runState = runState;
  updateControls();
}

function resetRunOutput() {
  elements.events.replaceChildren();
  elements.artifacts.replaceChildren();
  elements.artifactRegion.classList.add("hidden");
  closeSource();
  elements.currentTest.classList.add("hidden");
  elements.emptyProgress.classList.add("hidden");
}

function editorUrl(absolutePath, line) {
  if (!absolutePath) return null;
  const suffix = line ? `:${line}` : "";
  return `vscode://file${absolutePath.startsWith("/") ? "" : "/"}${absolutePath}${suffix}`;
}

function closeSource() {
  elements.sourceRegion.classList.add("hidden");
  elements.sourcePath.textContent = "";
  elements.sourceCode.replaceChildren();
  elements.sourceOpenEditor.hidden = true;
  elements.sourceOpenEditor.removeAttribute("href");
}

async function openSource(file, line) {
  if (!file) return;
  elements.sourceRegion.classList.remove("hidden");
  elements.sourcePath.textContent = "Loading…";
  elements.sourceCode.replaceChildren();
  elements.sourceOpenEditor.hidden = true;
  try {
    const params = new URLSearchParams({path: file});
    if (line) params.set("line", String(line));
    const response = await fetch(`/api/source?${params}`);
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json();
    renderSource(payload);
  } catch (error) {
    elements.sourcePath.textContent = `Could not open ${file}`;
    elements.sourceCode.textContent = error.message;
  }
}

function renderSource(payload) {
  const highlight = Number(payload.line) || null;
  elements.sourcePath.textContent = highlight ? `${payload.path}:${highlight}` : payload.path;
  const openHref = editorUrl(payload.absolute_path, highlight);
  if (openHref) {
    elements.sourceOpenEditor.href = openHref;
    elements.sourceOpenEditor.hidden = false;
  } else {
    elements.sourceOpenEditor.hidden = true;
  }

  const lines = payload.content.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  const fragment = document.createDocumentFragment();
  let highlighted = null;
  lines.forEach((text, index) => {
    const lineNumber = index + 1;
    const row = document.createElement("div");
    row.className = "source-line";
    row.dataset.line = String(lineNumber);
    if (highlight === lineNumber) {
      row.classList.add("highlight");
      highlighted = row;
    }
    const lineno = document.createElement("span");
    lineno.className = "source-lineno";
    lineno.textContent = String(lineNumber);
    const code = document.createElement("span");
    code.className = "source-text";
    code.textContent = text || " ";
    row.append(lineno, code);
    fragment.append(row);
  });
  elements.sourceCode.replaceChildren(fragment);
  if (highlighted) highlighted.scrollIntoView({block: "center"});
}

function locationFrom(eventOrTest) {
  if (!eventOrTest?.file) return null;
  return {file: eventOrTest.file, line: eventOrTest.line || null};
}

async function startRun() {
  if (state.runState !== "idle" || !state.effectiveSelection.size) return;
  state.cancellationRequested = false;
  setRunState("starting");
  resetRunOutput();
  elements.runSummary.textContent = "Starting run…";
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        node_ids: [...state.effectiveSelection],
        flex_ready: elements.flexReady.checked,
        headed: elements.headed.checked,
      }),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const body = await response.json();
    setRunState("running");
    elements.runSummary.textContent = `Running ${plural(body.node_ids.length, "test")}`;
  } catch (error) {
    setRunState("idle");
    elements.emptyProgress.classList.remove("hidden");
    elements.runSummary.textContent = `Run could not start: ${error.message}`;
  }
}

async function cancelRun() {
  if (state.runState !== "running") return;
  state.cancellationRequested = true;
  setRunState("cancelling");
  elements.runSummary.textContent = "Cancelling run…";
  try {
    const response = await fetch("/api/cancel", {method: "POST"});
    if (!response.ok) throw new Error(await responseError(response));
    const body = await response.json();
    if (!body.cancelled) {
      state.cancellationRequested = false;
      setRunState("idle");
      elements.runSummary.textContent = "No active run was available to cancel.";
    }
  } catch (error) {
    if (state.runState === "idle") return;
    state.cancellationRequested = false;
    setRunState("running");
    elements.runSummary.textContent = `Cancel failed: ${error.message}`;
  }
}

function appendEvent(label, detail = "", status = "", location = null) {
  const fragment = document.querySelector("#event-template").content.cloneNode(true);
  const item = fragment.querySelector("li");
  if (status) item.classList.add(status);
  const title = item.querySelector("strong");
  if (location?.file) {
    item.classList.add("has-source");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "source-link";
    button.textContent = label || "Progress update";
    button.title = location.line ? `${location.file}:${location.line}` : location.file;
    button.addEventListener("click", (event) => {
      event.preventDefault();
      openSource(location.file, location.line);
    });
    item.addEventListener("click", (event) => {
      if (event.target.closest("button, a")) return;
      openSource(location.file, location.line);
    });
    title.replaceWith(button);
  } else {
    title.textContent = label || "Progress update";
  }
  const detailNode = item.querySelector("small");
  if (status === "log" && detail) {
    const url = artifactUrl(detail);
    if (url) {
      detailNode.textContent = "";
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = detail;
      detailNode.append(link);
    } else {
      detailNode.textContent = detail;
    }
  } else {
    detailNode.textContent = detail;
  }
  elements.events.append(fragment);
  item.scrollIntoView({block: "nearest"});
}

function appendCoversEvent(testLabel, cases, location = null) {
  const fragment = document.querySelector("#event-template").content.cloneNode(true);
  const item = fragment.querySelector("li");
  item.classList.add("covers");
  item.querySelector("strong").textContent = testLabel;
  const detail = item.querySelector("small");
  if (!cases.length) {
    detail.textContent = "No TestRail cases mapped";
  } else {
    detail.textContent = "";
    const intro = document.createElement("span");
    intro.textContent = "Covers:";
    detail.append(intro);
    const ul = document.createElement("ul");
    ul.className = "event-covers";
    for (const entry of cases) {
      const li = document.createElement("li");
      li.textContent = formatCase(entry);
      ul.append(li);
    }
    detail.append(ul);
  }
  if (location?.file) {
    item.classList.add("has-source");
    item.title = location.line ? `${location.file}:${location.line}` : location.file;
    item.addEventListener("click", (event) => {
      if (event.target.closest("button, a")) return;
      openSource(location.file, location.line);
    });
  }
  elements.events.append(fragment);
  item.scrollIntoView({block: "nearest"});
}

function artifactUrl(path) {
  if (typeof path !== "string" || !path) return null;
  const normalized = path.replaceAll("\\", "/");
  const artifactMarker = "/artifacts/";
  const resultsMarker = "/test-results/";
  let servedPath;
  if (normalized.startsWith("artifacts/") || normalized.startsWith("test-results/")) {
    servedPath = normalized;
  } else if (normalized.includes(artifactMarker)) {
    servedPath = `artifacts/${normalized.split(artifactMarker).pop()}`;
  } else if (normalized.includes(resultsMarker)) {
    servedPath = `test-results/${normalized.split(resultsMarker).pop()}`;
  } else {
    return null;
  }
  return `/${servedPath.split("/").map(encodeURIComponent).join("/")}`;
}

function renderArtifacts(artifacts = {}, nodeId = "") {
  for (const [kind, path] of Object.entries(artifacts || {})) {
    const url = artifactUrl(path);
    if (!url) {
      appendEvent("Artifact unavailable", `${kind}: path is outside a served artifact directory`, "warning");
      continue;
    }

    const card = document.createElement("article");
    card.className = "artifact-card";
    const title = document.createElement("strong");
    title.textContent = kind.replace("_path", "").replaceAll("_", " ");
    if (kind === "screenshot_path") {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      const image = document.createElement("img");
      image.src = url;
      image.alt = `Screenshot artifact for ${nodeId || "test"}`;
      image.loading = "lazy";
      link.append(image);
      card.append(link, title);
    } else if (kind === "video_path") {
      const video = document.createElement("video");
      video.src = url;
      video.controls = true;
      video.preload = "metadata";
      card.append(video, title);
    } else {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = kind === "trace_path" ? "Open Playwright trace" : `Open ${title.textContent}`;
      card.append(title, link);
    }
    elements.artifacts.append(card);
    elements.artifactRegion.classList.remove("hidden");
    const kindLabel = kind === "video_path" ? "Playwright video" : kind.replace("_path", "").replaceAll("_", " ");
    appendEvent(kindLabel, path, "log", null);
  }
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function finishRun(summary) {
  setRunState("idle");
  elements.currentTest.classList.add("hidden");
  elements.runSummary.textContent = summary;
}

function handleEvent(event) {
  if (!event || typeof event.type !== "string") return;
  if (event.type === "session_start") {
    if (state.runState === "idle") setRunState("running");
    elements.emptyProgress.classList.add("hidden");
  } else if (event.type === "test_start") {
    const test = state.tests.get(event.node_id);
    const testLabel = test?.label || event.label || event.node_id;
    const location = locationFrom(event) || locationFrom(test);
    const cases = Array.isArray(event.cases) && event.cases.length ? event.cases : casesFor(test);
    elements.currentTest.textContent = testLabel || "Starting test";
    elements.currentTest.classList.remove("hidden");
    if (location) {
      elements.currentTest.classList.add("has-source");
      elements.currentTest.title = location.line ? `${location.file}:${location.line}` : location.file;
      elements.currentTest.onclick = () => openSource(location.file, location.line);
    } else {
      elements.currentTest.classList.remove("has-source");
      elements.currentTest.removeAttribute("title");
      elements.currentTest.onclick = null;
    }
    appendCoversEvent(testLabel, cases, location);
  } else if (event.type === "step_start") {
    appendEvent(event.label, "In progress", "", locationFrom(event));
  } else if (event.type === "step_done") {
    const detail = event.seconds == null ? "Done" : `${numberOrZero(event.seconds).toFixed(1)}s`;
    appendEvent(event.label, detail, "passed", locationFrom(event));
  } else if (event.type === "log") {
    const kind = event.kind || "info";
    const pathMatch = typeof event.label === "string" ? event.label.match(/:\s*(.+)$/) : null;
    const pathDetail = kind === "video" || kind === "trace" || kind === "path" ? (pathMatch?.[1] || "") : kind;
    appendEvent(event.label, pathDetail, "log", locationFrom(event));
  } else if (event.type === "artifact") {
    const kindLabel =
      event.kind === "video_path" ? "Playwright video" : (event.kind || "artifact").replace("_path", "").replaceAll("_", " ");
    appendEvent(kindLabel, event.path || "", "log");
  } else if (event.type === "test_end") {
    const status = event.status || "completed";
    const test = state.tests.get(event.node_id);
    const testLabel = test?.label || event.node_id;
    const detail =
      status === "failed"
        ? `failed · ${numberOrZero(event.duration).toFixed(1)}s · continuing to next test`
        : `${status} · ${numberOrZero(event.duration).toFixed(1)}s`;
    appendEvent(testLabel, detail, status, locationFrom(test));
    renderArtifacts(event.artifacts, event.node_id);
  } else if (event.type === "run_cancelled") {
    finishRun("Run cancelled");
  } else if (event.type === "runner_end") {
    if (!state.cancellationRequested) {
      const exitStatus = numberOrZero(event.exit_status);
      finishRun(exitStatus === 0 ? "Run finished" : `Run finished with exit status ${exitStatus}`);
    }
  } else if (event.type === "session_end" && !state.cancellationRequested) {
    const exitStatus = numberOrZero(event.exit_status);
    elements.runSummary.textContent =
      exitStatus === 0 ? "Tests complete; finalizing…" : `Tests ended with exit status ${exitStatus}; finalizing…`;
  }
}

function setConnection(label, tone) {
  elements.connection.textContent = label;
  elements.connection.className = `chip ${tone}`;
}

function scheduleReconnect() {
  if (state.reconnectTimer) return;
  const delay = Math.min(1000 * (2 ** state.reconnectAttempt), 15000);
  state.reconnectAttempt += 1;
  setConnection(`Reconnecting in ${Math.ceil(delay / 1000)}s`, "warning");
  state.reconnectTimer = window.setTimeout(() => {
    state.reconnectTimer = null;
    connectEvents();
  }, delay);
}

function connectEvents() {
  if (state.socket && [WebSocket.CONNECTING, WebSocket.OPEN].includes(state.socket.readyState)) return;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/events`);
  state.socket = socket;
  setConnection(state.reconnectAttempt ? "Reconnecting…" : "Connecting…", "neutral");

  socket.addEventListener("open", () => {
    if (state.socket !== socket) return;
    state.reconnectAttempt = 0;
    setConnection("Live updates connected", "success");
  });
  socket.addEventListener("message", ({data}) => {
    if (state.socket !== socket) return;
    try {
      handleEvent(JSON.parse(data));
    } catch (error) {
      appendEvent("Progress message ignored", error.message, "warning");
    }
  });
  socket.addEventListener("error", () => socket.close());
  socket.addEventListener("close", () => {
    if (state.socket !== socket) return;
    state.socket = null;
    scheduleReconnect();
  });
}

elements.run.addEventListener("click", startRun);
elements.cancel.addEventListener("click", cancelRun);
elements.refresh.addEventListener("click", () => loadCatalog(true));
elements.sourceClose.addEventListener("click", closeSource);
elements.selectAll.addEventListener("change", () => {
  applyBulkSelection([...state.tests.keys()], elements.selectAll.checked);
});
elements.flexReady.addEventListener("change", reconcileSelection);
window.addEventListener("online", () => {
  state.reconnectAttempt = 0;
  if (state.reconnectTimer) {
    window.clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  connectEvents();
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") connectEvents();
});

loadCatalog();
connectEvents();
