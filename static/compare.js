const form = document.getElementById("compare-form");
const compareStatus = document.getElementById("compare-status");

form.addEventListener("change", (event) => {
    compareStatus.textContent = event.submitter
        ? "Loading benchmarks..."
        : "Updating model options...";
});

window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        compareStatus.textContent =
            "Click Compare models to load scores for these selections.";
    }
});

form.addEventListener("change", (event) => {
    const changed = event.target;

    if (changed.tagName !== "SELECT") return;

    if (changed.name.endsWith("_model")) {
        compareStatus.textContent =
            "Click Compare models to load scores for these selections.";
        return;
    }

    if (changed.name === "hardware") {
        form.querySelectorAll("[data-side] select").forEach((select) => {
            select.disabled = true;
        });
    } else {
        const card = changed.closest("[data-side]");
        if (!card) return;

        const dropdowns = [...card.querySelectorAll("select")];
        const index = dropdowns.indexOf(changed);

        dropdowns.slice(index + 1).forEach((select) => {
            select.disabled = true;
        });
    }

    form.requestSubmit();
})