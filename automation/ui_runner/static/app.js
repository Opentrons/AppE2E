const ROUTES = {
  setup: "/",
  run: "/run",
};

const state = {
  tests: new Map(),
  explicitSelection: new Set(),
  effectiveSelection: new Set(),
  requiredSelection: new Set(),
  rowInputs: new Map(),
  resultCards: new Map(),
  activeNodeId: null,
  runTotal: 0,
  runCompleted: 0,
  runCounts: {passed: 0, failed: 0, skipped: 0},
  loading: false,
  runState: "idle",
  cancellationRequested: false,
  route: "setup",
  socket: null,
  reconnectTimer: null,
  reconnectAttempt: 0,
};

const elements = {
  catalog: document.querySelector("#catalog"),
  catalogMessage: document.querySelector("#catalog-message"),
  selectionSummary: document.querySelector("#selection-summary"),
  selectAllApp: document.querySelector("#select-all-app"),
  selectAllOdd: document.querySelector("#select-all-odd"),
  runSummary: document.querySelector("#run-summary"),
  run: document.querySelector("#run"),
  cancel: document.querySelector("#cancel"),
  refresh: document.querySelector("#refresh"),
  flexReady: document.querySelector("#flex-ready"),
  headed: document.querySelector("#headed"),
  robotName: document.querySelector("#robot-name"),
  protocolName: document.querySelector("#protocol-name"),
  robotIp: document.querySelector("#robot-ip"),
  appPath: document.querySelector("#app-path"),
  connection: document.querySelector("#connection"),
  selectionCovers: document.querySelector("#selection-covers"),
  runProgress: document.querySelector("#run-progress"),
  progressFill: document.querySelector("#progress-fill"),
  progressLabel: document.querySelector("#progress-label"),
  currentTest: document.querySelector("#current-test"),
  emptyProgress: document.querySelector("#empty-progress"),
  results: document.querySelector("#results"),
  runActiveBanner: document.querySelector("#run-active-banner"),
  runActiveText: document.querySelector("#run-active-text"),
  navSetup: document.querySelector("#nav-setup"),
  navRun: document.querySelector("#nav-run"),
};

function routeFromPath(pathname = location.pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";
  return path === "/run" ? "run" : "setup";
}

function pathForRoute(route) {
  return route === "run" ? ROUTES.run : ROUTES.setup;
}

function applyRoute() {
  const route = routeFromPath();
  state.route = route;
  document.body.dataset.route = route;
  document.querySelectorAll("[data-view]").forEach((view) => {
    const active = view.dataset.view === route;
    view.hidden = !active;
    view.setAttribute("aria-hidden", active ? "false" : "true");
  });
  if (elements.navSetup) {
    elements.navSetup.setAttribute("aria-current", route === "setup" ? "page" : "false");
  }
  if (elements.navRun) {
    elements.navRun.setAttribute("aria-current", route === "run" ? "page" : "false");
  }
  document.title =
    route === "run" ? "Live run · Opentrons E2E Workflows" : "Select tests · Opentrons E2E Workflows";
  updateRunBanner();
}

function navigate(route, {replace = false} = {}) {
  const next = route === "run" ? "run" : "setup";
  const path = pathForRoute(next);
  if (routeFromPath() === next) {
    applyRoute();
    return;
  }
  history[replace ? "replaceState" : "pushState"]({route: next}, "", path);
  applyRoute();
}

function updateRunBanner() {
  const banner = elements.runActiveBanner;
  if (!banner) return;
  const busy = state.runState === "running" || state.runState === "starting" || state.runState === "cancelling";
  const show = busy && state.route === "setup";
  banner.classList.toggle("hidden", !show);
  if (elements.runActiveText) {
    elements.runActiveText.textContent =
      state.runState === "cancelling" ? "Cancelling run…" : "A run is in progress.";
  }
}

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

function nodeIdsForSuite(suite) {
  const prefix = suite === "odd" ? "tests/odd/" : "tests/app/";
  return [...state.tests.keys()].filter((nodeId) => nodeId.startsWith(prefix));
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

function targetsFilled() {
  return Boolean(
    elements.robotName.value.trim() &&
      elements.protocolName.value.trim() &&
      elements.robotIp.value.trim() &&
      elements.appPath.value.trim(),
  );
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
  setToggleState(elements.selectAllApp, nodeIdsForSuite("app"));
  setToggleState(elements.selectAllOdd, nodeIdsForSuite("odd"));

  const selectedCount = state.effectiveSelection.size;
  const requiredCount = state.requiredSelection.size;
  elements.selectionSummary.textContent =
    `${plural(selectedCount, "test")} selected` +
    (requiredCount ? ` · ${plural(requiredCount, "prerequisite")} locked` : "");
  elements.run.disabled =
    state.runState !== "idle" || selectedCount === 0 || state.loading || !targetsFilled();
  elements.cancel.disabled = state.runState !== "running";
  elements.cancel.textContent = state.runState === "cancelling" ? "Cancelling…" : "Cancel run";
  elements.refresh.disabled = state.runState !== "idle" || state.loading;
  elements.flexReady.disabled = state.runState !== "idle";
  elements.headed.disabled = state.runState !== "idle";
  elements.robotName.disabled = state.runState !== "idle";
  elements.protocolName.disabled = state.runState !== "idle";
  elements.robotIp.disabled = state.runState !== "idle";
  elements.appPath.disabled = state.runState !== "idle";
  updateRunBanner();
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
      openInEditor(test.file, test.line);
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

async function loadDefaults() {
  try {
    const response = await fetch("/api/defaults");
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json();
    if (!elements.robotName.value && payload.robot_name) {
      elements.robotName.value = payload.robot_name;
    }
    if (!elements.protocolName.value && payload.protocol_name) {
      elements.protocolName.value = payload.protocol_name;
    }
    if (!elements.robotIp.value && payload.robot_ip) {
      elements.robotIp.value = payload.robot_ip;
    }
    if (!elements.appPath.value && payload.app_path) {
      elements.appPath.value = payload.app_path;
    }
  } catch {
    // Prefill is best-effort; the form still accepts manual values.
  } finally {
    updateControls();
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

function updateProgressBar() {
  const total = state.runTotal;
  const completed = state.runCompleted;
  const pct = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;
  elements.progressFill.style.width = `${pct}%`;
  elements.progressLabel.textContent = total ? `${completed} / ${total}` : "0 / 0";
  elements.runProgress.classList.toggle("hidden", total === 0 && state.runState === "idle");
  elements.runProgress.setAttribute("aria-hidden", total === 0 && state.runState === "idle" ? "true" : "false");
}

function resetRunOutput() {
  state.resultCards.clear();
  state.activeNodeId = null;
  state.runTotal = 0;
  state.runCompleted = 0;
  state.runCounts = {passed: 0, failed: 0, skipped: 0};
  elements.results.replaceChildren();
  elements.currentTest.classList.add("hidden");
  elements.emptyProgress.classList.add("hidden");
  updateProgressBar();
}

function formatRunCounts() {
  const {passed, failed, skipped} = state.runCounts;
  const parts = [
    `${passed} passed`,
    `${failed} failed`,
    ...(skipped ? [`${skipped} skipped`] : []),
  ];
  return parts.join(", ");
}

function shortNodeId(nodeId = "") {
  return String(nodeId).split("::").slice(-1)[0] || nodeId;
}

async function openInEditor(file, line) {
  if (!file) return;
  try {
    const params = new URLSearchParams({path: file});
    if (line) params.set("line", String(line));
    const response = await fetch(`/api/source?${params}`);
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json();
    const absolute = payload.absolute_path;
    if (!absolute) return;
    const suffix = line || payload.line ? `:${line || payload.line}` : "";
    window.location.href = `vscode://file${absolute.startsWith("/") ? "" : "/"}${absolute}${suffix}`;
  } catch (error) {
    console.warn("Could not open source in editor", error);
  }
}

function ensureResultCard(nodeId, label = "") {
  if (!nodeId) return null;
  let card = state.resultCards.get(nodeId);
  if (card) {
    if (label) card.querySelector(".result-title").textContent = label;
    return card;
  }
  const fragment = document.querySelector("#result-template").content.cloneNode(true);
  card = fragment.querySelector(".result-card");
  card.dataset.nodeId = nodeId;
  const test = state.tests.get(nodeId);
  card.querySelector(".result-title").textContent = label || test?.label || shortNodeId(nodeId);
  elements.results.append(fragment);
  state.resultCards.set(nodeId, card);
  card.scrollIntoView({block: "nearest"});
  return card;
}

function setResultStatus(card, status, detail = "") {
  if (!card) return;
  card.dataset.status = status || "running";
  const statusNode = card.querySelector(".result-status");
  const label =
    status === "passed" ? "Passed" : status === "failed" ? "Failed" : status === "skipped" ? "Skipped" : "Running";
  statusNode.textContent = detail ? `${label} · ${detail}` : label;
}

async function startRun() {
  if (state.runState !== "idle" || !state.effectiveSelection.size) return;
  const robotName = elements.robotName.value.trim();
  const protocolName = elements.protocolName.value.trim();
  const robotIp = elements.robotIp.value.trim();
  const appPath = elements.appPath.value.trim();
  if (!robotName || !protocolName || !robotIp || !appPath) {
    elements.runSummary.textContent = "Enter robot name, protocol name, robot IP, and app path before running.";
    updateControls();
    return;
  }
  state.cancellationRequested = false;
  setRunState("starting");
  resetRunOutput();
  state.runTotal = state.effectiveSelection.size;
  updateProgressBar();
  navigate("run");
  elements.runSummary.textContent = `Starting run for ${robotName} · ${protocolName} · ${robotIp}…`;
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        node_ids: [...state.effectiveSelection],
        robot_name: robotName,
        protocol_name: protocolName,
        robot_ip: robotIp,
        app_path: appPath,
        flex_ready: elements.flexReady.checked,
        headed: elements.headed.checked,
      }),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const body = await response.json();
    state.runTotal = Array.isArray(body.node_ids) ? body.node_ids.length : state.runTotal;
    updateProgressBar();
    setRunState("running");
    elements.runSummary.textContent =
      `Running ${plural(body.node_ids.length, "test")} · ${robotName} · ${protocolName} · ${robotIp}`;
  } catch (error) {
    setRunState("idle");
    state.runTotal = 0;
    updateProgressBar();
    elements.emptyProgress.classList.remove("hidden");
    elements.runSummary.textContent = `Run could not start: ${error.message}`;
    navigate("setup");
    showCatalogMessage(`Run could not start: ${error.message}`, "error");
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

function renderResultMedia(nodeId, artifacts = {}, failure = "") {
  const card = nodeId ? ensureResultCard(nodeId) : null;
  if (!card) return;

  const videoPath = artifacts.video_path;
  const video = card.querySelector(".result-video");
  const caption = card.querySelector(".result-caption");
  const url = videoPath ? artifactUrl(videoPath) : null;
  if (url) {
    video.src = url;
    video.classList.remove("hidden");
  }
  if (videoPath && caption) {
    caption.textContent = videoPath;
    caption.classList.remove("hidden");
  }

  const block = card.querySelector(".result-failure");
  if (failure) {
    block.textContent = failure;
    block.classList.remove("hidden");
  }
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function finishRun(summary) {
  setRunState("idle");
  elements.currentTest.classList.add("hidden");
  const counts = formatRunCounts();
  elements.runSummary.textContent = counts ? `${summary} · ${counts}` : summary;
  updateProgressBar();
}

function handleEvent(event) {
  if (!event || typeof event.type !== "string") return;
  if (event.type === "session_start") {
    if (state.runState === "idle") setRunState("running");
    elements.emptyProgress.classList.add("hidden");
    if (!state.runTotal) {
      state.runTotal = state.effectiveSelection.size;
      updateProgressBar();
    }
  } else if (event.type === "test_start") {
    const test = state.tests.get(event.node_id);
    const testLabel = test?.label || event.label || event.node_id;
    state.activeNodeId = event.node_id || null;
    const card = ensureResultCard(event.node_id, testLabel);
    setResultStatus(card, "running");
    elements.currentTest.textContent = testLabel || "Starting test";
    elements.currentTest.classList.remove("hidden");
  } else if (
    event.type === "step_start" ||
    event.type === "step_done" ||
    event.type === "log" ||
    event.type === "artifact"
  ) {
    // Intentionally ignored — keep the progress panel to bar + finished video/stack.
  } else if (event.type === "test_end") {
    const status = event.status || "completed";
    const test = state.tests.get(event.node_id);
    const testLabel = test?.label || shortNodeId(event.node_id);
    const card = ensureResultCard(event.node_id, testLabel);
    const duration = `${numberOrZero(event.duration).toFixed(1)}s`;
    setResultStatus(card, status, duration);
    renderResultMedia(event.node_id, event.artifacts || {}, event.failure || "");
    if (status === "passed" || status === "failed" || status === "skipped") {
      state.runCounts[status] += 1;
    }
    state.runCompleted += 1;
    updateProgressBar();
    state.activeNodeId = null;
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
      console.warn("Progress message ignored", error);
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
elements.selectAllApp.addEventListener("change", () => {
  applyBulkSelection(nodeIdsForSuite("app"), elements.selectAllApp.checked);
});
elements.selectAllOdd.addEventListener("change", () => {
  applyBulkSelection(nodeIdsForSuite("odd"), elements.selectAllOdd.checked);
});
elements.flexReady.addEventListener("change", reconcileSelection);
elements.robotName.addEventListener("input", updateControls);
elements.protocolName.addEventListener("input", updateControls);
elements.robotIp.addEventListener("input", updateControls);
elements.appPath.addEventListener("input", updateControls);
document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-nav]");
  if (!link) return;
  event.preventDefault();
  navigate(link.dataset.nav);
});
window.addEventListener("popstate", applyRoute);
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

applyRoute();
loadDefaults();
loadCatalog();
connectEvents();
