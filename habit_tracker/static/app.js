document.querySelectorAll(".orbit-log-card").forEach((card) => {
  const checkbox = card.querySelector('input[type="checkbox"]');
  const quantityInput = card.querySelector("[data-quantity]");

  if (!checkbox || !quantityInput) {
    return;
  }

  const sync = () => {
    if (checkbox.checked && (!quantityInput.value || quantityInput.value === "0")) {
      quantityInput.value = "1";
    }
    if (!checkbox.checked && quantityInput.value === "1") {
      quantityInput.value = "0";
    }
  };

  checkbox.addEventListener("change", sync);
  sync();
});
