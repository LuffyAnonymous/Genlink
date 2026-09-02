document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("club-search");
  const grid = document.getElementById("clubs-grid");
  const noResults = document.getElementById("no-results");
  if (!input || !grid) return;

  const cards = Array.from(grid.querySelectorAll(".club-card"));

  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();
    let visibleCount = 0;

    cards.forEach((card) => {
      const matches = card.dataset.name.includes(query);
      card.style.display = matches ? "" : "none";
      if (matches) visibleCount += 1;
    });

    noResults.classList.toggle("hidden", visibleCount !== 0);
  });
});
