"use strict";

const code = document.getElementById("code");
const checkButton = document.getElementById("check");
const copyButton = document.getElementById("copy");
const clearButton = document.getElementById("clear");
const statusLine = document.getElementById("status");
const summary = document.getElementById("summary");
const findingsList = document.getElementById("findings");

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function showStatus(text) {
  statusLine.textContent = text;
}

function resetResults(text) {
  summary.textContent = text;
  findingsList.replaceChildren();
}

// The checker reports 1-based lines and 0-based columns.
function jumpTo(line, col) {
  const lines = code.value.split("\n");
  let offset = col;
  for (let i = 0; i < line - 1 && i < lines.length; i += 1) {
    offset += lines[i].length + 1;
  }
  code.focus();
  code.setSelectionRange(offset, offset);
}

function findingItem(finding) {
  const item = document.createElement("li");
  item.className = `finding ${finding.severity}`;

  const badge = document.createElement("span");
  badge.className = `badge ${finding.severity}`;
  badge.textContent = finding.severity === "error" ? "Error" : "Warning";

  const rule = document.createElement("span");
  rule.className = "rule";
  rule.textContent = finding.rule;

  const place = document.createElement("button");
  place.type = "button";
  place.className = "place";
  place.textContent = `Line ${finding.line}, column ${finding.col + 1}`;
  place.title = "Show this position in the code";
  place.addEventListener("click", () => jumpTo(finding.line, finding.col));

  const message = document.createElement("p");
  message.className = "message";
  message.textContent = finding.message;

  item.append(badge, rule, place, message);
  return item;
}

function showFindings(result) {
  if (result.findings.length === 0) {
    resetResults("No known problems found. That does not prove the script compiles.");
    return;
  }
  let text = `${plural(result.errors, "error")}, ${plural(result.warnings, "warning")}.`;
  if (result.errors === 0) {
    text += " Warnings are provisional, not confirmed compile errors.";
  }
  resetResults(text);
  findingsList.append(...result.findings.map(findingItem));
}

async function checkCode() {
  checkButton.disabled = true;
  showStatus("Checking…");
  try {
    const response = await fetch("/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code.value }),
    });
    const body = await response.json().catch(() => ({}));
    if (response.ok) {
      showFindings(body);
      showStatus("");
    } else if (response.status === 422 && typeof body.detail === "string") {
      resetResults("The code was not checked.");
      showStatus(body.detail);
    } else {
      resetResults("The code was not checked.");
      showStatus("The checker failed on this input. Try again or shorten the code.");
    }
  } catch {
    showStatus("The checker could not be reached. Is the local server running?");
  } finally {
    checkButton.disabled = false;
  }
}

async function copyCode() {
  if (!code.value) {
    showStatus("There is no code to copy.");
    return;
  }
  try {
    await navigator.clipboard.writeText(code.value);
    showStatus("Code copied.");
  } catch {
    showStatus("Copy failed. Select the code and copy it manually.");
  }
}

function clearCode() {
  code.value = "";
  resetResults("Run a check to see findings.");
  showStatus("");
  code.focus();
}

checkButton.addEventListener("click", checkCode);
copyButton.addEventListener("click", copyCode);
clearButton.addEventListener("click", clearCode);
code.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    checkCode();
  }
});
