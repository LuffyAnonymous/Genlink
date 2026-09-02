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
    entryCount.textContent = `${count} ${count === 1 ? "entry" : "entries"}`;
    generateBtn.disabled = count === 0;
  }

  textarea.addEventListener("input", updateCount);
  updateCount();

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
