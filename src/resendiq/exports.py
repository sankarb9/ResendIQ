import csv, io, json, re
from dataclasses import asdict
from .models import SimulationResult

def result_to_dict(result: SimulationResult) -> dict:
    return {
        "protocol": result.protocol, "success": result.success,
        "config": asdict(result.config), "metrics": result.metrics,
        "original_text": result.original_text, "reconstructed_text": result.reconstructed_text,
        "integrity_ok": result.integrity_ok,
        "events": [asdict(e) for e in result.events],
    }

def export_json(result: SimulationResult) -> str:
    return json.dumps(result_to_dict(result), indent=2)

def export_events_csv(result: SimulationResult) -> str:
    stream = io.StringIO()
    fields = ["time_ms", "event_type", "message", "packet_id", "sequence_number"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for event in result.events:
        writer.writerow({key: getattr(event, key) for key in fields})
    return stream.getvalue()

def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return cleaned[:60] or "resendiq_export"
