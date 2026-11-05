(() => {
    const button = document.getElementById("ai-summary-button");
    const form = document.getElementById("compare-form");
    const status = document.getElementById("ai-summary-status");
    const output = document.getElementById("ai-summary-output");

    if (!button || !form || !status || !output) {
        return;
    }

    let activeRequest;
    let selectionVersion = 0;

    const renderedSelection = Object.fromEntries(
        new FormData(form).entries()
    );

    form.addEventListener("change", () => {
        selectionVersion += 1;
        activeRequest?.abort();

        output.hidden = true;
        output.textContent = "";
        button.disabled = true;
        status.textContent = "Updating comparison...";
    });

    button.addEventListener("click", async () => {
        const version = selectionVersion;

        activeRequest = new AbortController();

        const timer = setTimeout(
            () => activeRequest.abort(),
            45000
        );

        button.disabled = true;
        output.hidden = true;
        output.textContent = "";
        output.setAttribute("aria-busy", "true");

        status.textContent = 
            "Generating summary for the two selected models..."
        
        try {
            const response = await fetch(button.dataset.endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(renderedSelection),
                signal: activeRequest.signal
            });

            if (!response.headers.get("content-type")?.includes("application/json")) {
                throw new Error(`Summary endpoint returned HTTP ${response.status} instead of JSON.`);
            }

            const data = await response.json();

            if (version !== selectionVersion) {
                return;
            }

            if (!response.ok) {
                throw new Error(
                    data.error || "Could not generate a summary."
                );
            }

            if (
                typeof data.summary !== "string"
                || !data.summary.trim()
            ) {
                throw new Error(
                    "The AI returned an empty summary. Please try again."
                );
            }

            output.textContent = data.summary;
            output.hidden = false;

            status.textContent = 
                `Generated with ${data.model}` +
                (data.cached ? " · saved summary" : "") + 
                ".";

            button.textContent = "Show AI summary agian";
        } catch (error) {
            if (version !== selectionVersion) return;

            console.error("AI summary failed:", error);

            status.textContent = error.name === "AbortError"
                ? "The summary took too long. Please try again."
                : error.message;

        } finally {
            clearTimeout(timer);
            output.removeAttribute("aria-busy");

            if (version === selectionVersion) {
                button.disabled = false;
            }
        }
    });
})();