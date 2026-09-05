/*
 * Drives the visible "paste your credentials" generator card by feeding
 * the original, untouched single-account form (#generate-link-form,
 * handled by generate_link.js) and bulk CSV form (#bulk-upload-form,
 * posted straight to the server) - both stay exactly as they were, this
 * file just decides which one to submit and fills it in first.
 */
document.addEventListener("DOMContentLoaded", () => {
  const textarea = document.getElementById("credentials-input");
  if (!textarea) return;

  const entryCount = document.getElementById("entry-count");
  const generateBtn = document.getElementById("generate-submit");
  const generateBtnLabel = generateBtn.querySelector(".btn-generate-label");
  const generateBtnSpinner = generateBtn.querySelector(".btn-spinner");

  const proxyToggle = document.getElementById("proxy-toggle");
  const proxyPanel = document.getElementById("proxy-panel");
  const proxyInput = document.getElementById("credentials-proxy");
  const proxyArrow = proxyToggle.querySelector(".gen-disclosure-arrow");

  const csvToggle = document.getElementById("show-csv-upload");
  const csvPanel = document.getElementById("csv-upload-panel");
  const csvVisibleInput = document.getElementById("csv_file_visible");
  const csvVisibleSubmit = document.getElementById("csv-upload-visible-submit");

  function parseLines() {
    return textarea.value
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }

  function updateCount() {
    const count = parseLines().length;
    entryCount.textContent = `${count} ${count === 1 ? "Account" : "Accounts"}`;
    generateBtn.disabled = count === 0;
  }

  textarea.addEventListener("input", updateCount);
  updateCount();

  // Toggles the visible Generate button's loading state - called here right
  // before handing off to whichever hidden form actually submits, and again
  // by generate_link.js once the single-account AJAX request finishes (the
  // bulk/CSV path navigates to a new page instead, so never needs to reset).
  function setGeneratingState(isGenerating) {
    if (isGenerating) {
      generateBtn.disabled = true;
      generateBtnSpinner.classList.remove("hidden");
      generateBtnLabel.textContent = "Generating...";
    } else {
      generateBtnSpinner.classList.add("hidden");
      generateBtnLabel.textContent = "Generate Ticket Links";
      updateCount(); // restores the correct disabled state for current input
    }
  }
  window.setGeneratorLoadingState = setGeneratingState;

  proxyToggle.addEventListener("click", () => {
    const willShow = proxyPanel.classList.contains("hidden");
    proxyPanel.classList.toggle("hidden");
    proxyArrow.textContent = willShow ? "▾" : "▶";
  });

  csvToggle.addEventListener("click", () => {
    csvPanel.classList.toggle("hidden");
  });

  function csvEscape(value) {
    return `"${String(value ?? "").replace(/"/g, '""')}"`;
  }

  function setFileInput(input, file) {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    input.files = dataTransfer.files;
  }

  generateBtn.addEventListener("click", () => {
    const lines = parseLines();
    if (!lines.length) return;

    const proxy = proxyInput.value.trim();

    const rows = lines
      .map((line) => {
        const commaIndex = line.indexOf(",");
        if (commaIndex === -1) return null;
        return {
          account: line.slice(0, commaIndex).trim(),
          password: line.slice(commaIndex + 1).trim(),
        };
      })
      .filter(Boolean);

    if (!rows.length) {
      alert("Each line needs an account and password separated by a comma, e.g. 1245678,mypassword");
      return;
    }

    setGeneratingState(true);

    if (rows.length === 1) {
      document.getElementById("account_email").value = rows[0].account;
      document.getElementById("account_password").value = rows[0].password;
      document.getElementById("account_proxy").value = proxy;
      document.getElementById("generate-link-submit").click();
      return;
    }

    const csvRows = rows.map((row) =>
      [row.account, row.password, proxy, GENERATOR_MATCH_NAME].map(csvEscape).join(",")
    );
    const csvContent = ["email,password,proxy,match_name", ...csvRows].join("\r\n");
    const file = new File([csvContent], "credentials.csv", { type: "text/csv" });

    setFileInput(document.getElementById("csv_file"), file);
    document.getElementById("bulk-upload-submit").click();
  });

  if (csvVisibleSubmit) {
    csvVisibleSubmit.addEventListener("click", () => {
      if (!csvVisibleInput.files.length) {
        alert("Choose a CSV file first.");
        return;
      }
      setFileInput(document.getElementById("csv_file"), csvVisibleInput.files[0]);
      document.getElementById("bulk-upload-submit").click();
    });
  }
});
