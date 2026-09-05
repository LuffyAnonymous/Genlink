document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("generate-link-form");

  const bulkForm = document.getElementById("bulk-upload-form");
  const bulkSubmitBtn = document.getElementById("bulk-upload-submit");

  if (bulkForm && bulkSubmitBtn) {
    let bulkSubmitting = false;

    bulkForm.addEventListener("submit", (e) => {
      if (bulkSubmitting) {
        e.preventDefault();
        return;
      }

      bulkSubmitting = true;

      bulkSubmitBtn.disabled = true;
      bulkSubmitBtn.textContent = "Running...";
    });
  }

  if (!form) return;

  const resultBox = document.getElementById("generate-link-result");
  const submitBtn = document.getElementById("generate-link-submit");

  const matchName = form.dataset.matchName || null;
  const matchId = form.dataset.matchId || null;
  const club = form.dataset.club || null;

  let isSubmitting = false;


  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (isSubmitting) return;
    isSubmitting = true;

    submitBtn.disabled = true;
    submitBtn.textContent = "Running...";

    resultBox.classList.remove("hidden");

    resultBox.innerHTML = `
      <p class="text-sm" style="color:var(--muted)">
        Calling the link generator...
      </p>
    `;


    const email = document.getElementById("account_email").value.trim();
    const password = document.getElementById("account_password").value;
    const proxy = document.getElementById("account_proxy").value.trim();

    const csrfElement = document.querySelector(
      'meta[name="csrf-token"]'
    );

    const csrfToken = csrfElement ? csrfElement.content : "";


    try {

      const res = await fetch("/api/generate-link", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },

        body: JSON.stringify({
          email: email,
          password: password,
          proxy: proxy || null,
          match_name: matchName,
          match_id: matchId,
          club: club,
        }),
      });


      const data = await res.json();


      if (data.success) {

        let reuseNote;
        let toastMessage;
        if (data.reused) {
          reuseNote = `
            <div class="flash flash-success">
              Existing link reused - no credit charged.
              Balance: ${data.credits_remaining}
            </div>
          `;
          toastMessage = "Link ready - existing link reused, no credit charged.";
        } else if (data.unlimited) {
          reuseNote = `
            <div class="flash flash-success">
              Success - unlimited access, no credit charged.
            </div>
          `;
          toastMessage = "Link generated - unlimited access, no credit charged.";
        } else {
          reuseNote = `
            <div class="flash flash-success">
              Success - 1 credit consumed.
              Balance: ${data.credits_remaining}
            </div>
          `;
          toastMessage = "Link generated successfully.";
        }

        showToast(toastMessage, "success");


        /*
         * Create a unique result row.
         *
         * This keeps the Supporter ID/email mapped to
         * the specific generated link.
         */

        const resultItem = document.createElement("div");

        resultItem.className = "ticket-row mt-4";

        resultItem.innerHTML = `
          ${reuseNote}

          <div class="mt-4">

            <p
              class="text-xs mb-1"
              style="color:var(--muted)"
            >
              Account
            </p>

            <p class="text-sm font-medium mb-3">
              ${escapeHtml(email)}
            </p>


            <p
              class="text-xs mb-1"
              style="color:var(--muted)"
            >
              Generated link
            </p>


            <div class="flex items-center gap-2">

              <input
                type="text"
                readonly
                class="generated-link-input"
                style="
                  flex:1;
                  min-width:0;
                  background:var(--surface-2);
                  border:1px solid var(--border);
                  color:var(--accent-2);
                  padding:0.65rem 0.75rem;
                  border-radius:4px;
                  font-size:0.85rem;
                "
              >


              <button
                type="button"
                class="btn btn-ghost copy-link-btn"
                style="white-space:nowrap;"
              >
                Copy
              </button>

            </div>

          </div>
        `;


        /*
         * Copy button for this specific link.
         */

        const copyBtn = resultItem.querySelector(
          ".copy-link-btn"
        );

        const linkInput = resultItem.querySelector(
          ".generated-link-input"
        );

        // Set as a DOM property rather than templating it into the HTML
        // attribute above - the link comes from a third-party API response,
        // so it isn't a value this app fully controls.
        linkInput.value = data.link;

        copyBtn.addEventListener("click", async () => {

          try {

            await navigator.clipboard.writeText(data.link);

            copyBtn.textContent = "Copied!";

            setTimeout(() => {
              copyBtn.textContent = "Copy";
            }, 2000);

          } catch (err) {

            /*
             * Fallback for browsers where
             * navigator.clipboard is unavailable.
             */

            linkInput.focus();
            linkInput.select();

            document.execCommand("copy");

            copyBtn.textContent = "Copied!";

            setTimeout(() => {
              copyBtn.textContent = "Copy";
            }, 2000);
          }

        });


        /*
         * Replace the "Calling generator..." message
         * with the generated result.
         */

        resultBox.innerHTML = "";

        resultBox.appendChild(resultItem);


        /*
         * Reset the form after successful generation.
         */

        form.reset();


        /*
         * Update credit counter.
         */

        const counter = document.querySelector(
          "[data-counter]"
        );


        if (counter) {

          counter.dataset.value =
            data.credits_remaining;

          if (typeof animateCounter === "function") {
            animateCounter(counter);
          } else {
            counter.textContent =
              data.credits_remaining;
          }

        }

      } else {

        resultBox.classList.add("hidden");
        resultBox.innerHTML = "";

        showToast(
          data.message ||
            data.error ||
            "That attempt failed. No credit was charged.",
          "error"
        );

      }


    } catch (err) {

      console.error("Generate link error:", err);

      resultBox.classList.add("hidden");
      resultBox.innerHTML = "";

      showToast("Network error - no credit was charged.", "error");

    } finally {

      isSubmitting = false;

      submitBtn.disabled = false;

      submitBtn.textContent =
        "Run this account (1 credit)";

      // Resets the *visible* Generate button (this hidden form's own
      // button never shows) - a no-op if this page doesn't have the
      // generator card (setGeneratorLoadingState is only defined there).
      if (typeof window.setGeneratorLoadingState === "function") {
        window.setGeneratorLoadingState(false);
      }

    }

  });


  /*
   * Escape HTML so Supporter IDs and links
   * cannot accidentally be interpreted as HTML.
   */

  function escapeHtml(value) {

    const div = document.createElement("div");

    div.textContent = value ?? "";

    return div.innerHTML;

  }

});