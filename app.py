import json
import os

from flask import Flask, jsonify, render_template, request

from backend.ai_summary import SummaryError, SummaryService
from backend.comparison import compare_scores, model_name
from backend.database import load_data, load_benchmark_catalog

app = Flask(__name__)

summary_service = SummaryService()

COMPANIES = {
    "cpu": {
        "intel": "Intel",
        "amd": "AMD",
        "apple": "Apple"
    },
    "gpu": {
        "nvidia": "NVIDIA",
        "amd": "AMD"
    }
}


def selected_value(name, choices, default = None, selections = None):
    value = (request.args if selections is None else selections).get(name)

    if value in choices:
        return value

    return default if default in choices else next(iter(choices), "")


def build_side(prefix, hardware, catalog, selections = None):
    companies = COMPANIES[hardware]
    company = selected_value(f"{prefix}_company", companies, "amd" if prefix == "b" else None, selections = selections)
    error = None
    try:
        data = load_data(hardware, company)
    except (OSError, json.JSONDecodeError):
        app.logger.exception("Could not load hardware database")
        data = {}
        error = "Hardware specifications could not be loaded."

    series = selected_value(f"{prefix}_series", data, selections = selections)
    models = {str(item["model"]): item for item in data.get(series, [])}
    model = selected_value(f"{prefix}_model", models, selections = selections)
    name = model_name(hardware, company, series, model) if model else "No model selected"
    record = catalog.get("models", {}).get(name)
    if record and record.get("type") != hardware.upper():
        record = None
    configurations = list(dict.fromkeys(row["description"] for row in (record.get("scores") or {}).values() if row.get("description"))) if record else []

    fields = []
    for key, label, options, selected in [
        ("company", "Company", companies, company),
        ("series", "Series", {key: key for key in data}, series),
        ("model", "Model", {key: key for key in models}, model)
    ]:
        fields.append({"name": f"{prefix}_{key}", "label": label, "options": options, "selected": selected})

    return {"prefix": prefix, "title": f"Model {prefix.upper()}", "name": name, "fields": fields, "specs": models.get(model), "benchmark": record, "configurations": configurations, "error": error}



@app.route("/")
def home():
    hardware = selected_value("hardware", {"cpu": "CPU", "gpu": "GPU"})
    catalog_error = None
    try:
        catalog = load_benchmark_catalog()
    except:
        app.logger.exception("Could not load benchmark catalog")
        catalog = {}
        catalog_error = "Benchmark data could not be loaded. Check database/benchmark_catalog.json."

    left = build_side("a", hardware, catalog)
    right = build_side("b", hardware, catalog)
    comparison = compare_scores(left["benchmark"], right["benchmark"], hardware)

    return render_template("index.html", hardware = hardware, sides = [left, right], comparison = comparison, catalog_error = catalog_error, generated_at = catalog.get("generatedAt", ""), ai_enabled = bool(os.environ.get("HACKCLUB_API_KEY", "").strip()))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.post("/api/summary")
def ai_summary():
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return jsonify(error = "Request a summary from the comparison page."), 403

    if request.content_length is None or request.content_length > 4096:
        return jsonify(error = "Invalid summary request."), 413

    selections = request.get_json(silent = True)
    expected = {"hardware"} | {
        f"{side}_{field}"
        for side in ("a", "b")
        for field in ("company", "series", "model")
    }

    if (
        not isinstance(selections, dict)
        or set(selections) != expected
        or any(
            not isinstance(value, str) or not value or len(value) > 128
            for value in selections.values() 
        )
        or selections["hardware"] not in COMPANIES
    ): 
        return jsonify(error = "Select two valid CPUs or GPUs first."), 400

    hardware = selections["hardware"]

    try:
        catalog = load_benchmark_catalog()
        sides = [
            build_side(prefix, hardware, catalog, selections)
            for prefix in ("a", "b")
        ]

        for side in sides:
            if side["error"]:
                return jsonify(error = "Hardware data is temporarily unavailable."), 503

            if not side["specs"] or any(
                selections[field["name"]] != field["selected"]
                for field in side["fields"]
            ):
                return jsonify(error = "This selection is not in the hardware database."), 400

        facts = {
            "hardware": hardware,
            "data_snapshot": catalog.get("generatedAt"),
            "models": [
                {
                    "label": side["title"],
                    "name": side["name"],
                    "specifications": side["specs"],
                    "benchmark": side["benchmark"],
                    "configuration": side["configurations"],
                }
                for side in sides
            ], 
            "comparison": compare_scores(
                sides[0]["benchmark"], sides[1]["benchmark"], hardware
            ),
        }

        response = jsonify(
            summary_service.generate(facts, request.remote_addr or "unknown")
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    except SummaryError as exc:
        return jsonify(error = str(exc)), exc.status

    except (OSError, json.JSONDecodeError):
        app.logger.exception("Could not load AI comparison data")
        return jsonify(error = "Comparison data is temporarily unavailable."), 503


if __name__ == "__main__":
    app.run()