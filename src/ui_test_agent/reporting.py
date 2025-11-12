from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, select_autoescape


@dataclass
class StepResult:
    index: int
    action: str
    payload: Any
    status: str
    duration_ms: int
    error: Optional[str] = None
    screenshot: Optional[str] = None
    context: Optional[str] = None


@dataclass
class RunReport:
    scenario_path: str
    meta: Dict[str, Any]
    status: str
    started_at: datetime
    finished_at: datetime
    steps: List[StepResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat()
        return data


def save_report(report: RunReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, indent=2)


def render_html(report_json: Path, output_html: Path) -> None:
    with report_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    env.filters["format_json"] = lambda value: json.dumps(value, indent=2, ensure_ascii=False)
    template = env.from_string(_HTML_TEMPLATE)
    html = template.render(report=data)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")


_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>UI Test Agent Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { border: 1px solid #ddd; padding: 0.5rem; }
    th { background: #f5f5f5; }
    .failed { color: #c62828; }
    .passed { color: #2e7d32; }
  </style>
</head>
<body>
  <h1>{{ report.meta.name or 'Scenario' }}</h1>
  <p>Status: <strong class="{{ report.status }}">{{ report.status }}</strong></p>
  <p>Started: {{ report.started_at }}<br />Finished: {{ report.finished_at }}</p>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Action</th>
        <th>Payload</th>
        <th>Status</th>
        <th>Duration (ms)</th>
        <th>Error</th>
        <th>Screenshot</th>
        <th>Context</th>
      </tr>
    </thead>
    <tbody>
      {% for step in report.steps %}
      <tr>
        <td>{{ step.index }}</td>
        <td>{{ step.action }}</td>
        <td><pre>{{ step.payload | format_json }}</pre></td>
        <td class="{{ step.status }}">{{ step.status }}</td>
        <td>{{ step.duration_ms }}</td>
        <td>{{ step.error or '' }}</td>
        <td>{% if step.screenshot %}<a href="{{ step.screenshot }}">view</a>{% endif %}</td>
        <td><pre>{{ step.context or '' }}</pre></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""
