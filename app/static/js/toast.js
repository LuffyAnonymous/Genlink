function showToast(message, type) {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }

  const toast = document.createElement("div");
  toast.className = `toast is-${type === "success" ? "success" : "error"}`;
  toast.setAttribute("role", "alert");
  toast.textContent = message;
  stack.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
    // Fallback in case the animation never fires (e.g. reduced motion).
    setTimeout(() => toast.remove(), 400);
  }, 4500);
}
