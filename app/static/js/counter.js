function animateCounter(el) {
  const target = parseInt(el.dataset.value, 10) || 0;
  const duration = 700;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(eased * target);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-counter]").forEach(animateCounter);
});
