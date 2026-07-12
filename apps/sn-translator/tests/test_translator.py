"""Unit tests for the Alert → ServiceNow field mapping."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Alert  # noqa: E402
from translator import (  # noqa: E402
    alert_to_incident_payload,
    map_namespace_to_category,
    map_severity_to_urgency,
    resolve_payload,
)


def make_alert(**overrides) -> Alert:
    base = {
        "status": "firing",
        "labels": {"alertname": "DiskSpaceLow", "severity": "critical", "instance": "star-garden"},
        "annotations": {"summary": "Disk space low", "description": "Root filesystem is 91% full."},
        "startsAt": "2026-07-12T00:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
        "generatorURL": "http://prometheus/graph",
        "fingerprint": "abc123",
    }
    base.update(overrides)
    return Alert(**base)


class TestCategoryMapping:
    def test_none_namespace_falls_back_to_inquiry(self):
        assert map_namespace_to_category(None) == "inquiry"

    def test_unknown_namespace_falls_back_to_inquiry(self):
        assert map_namespace_to_category("does-not-exist") == "inquiry"

    def test_ecosystem_maps_to_software(self):
        assert map_namespace_to_category("ecosystem") == "software"

    def test_mapping_is_case_insensitive(self):
        assert map_namespace_to_category("ECOSYSTEM") == "software"

    def test_env_extension_merges_over_defaults(self, monkeypatch):
        # config reads SN_NAMESPACE_CATEGORIES at import; simulate the merge
        import config

        monkeypatch.setitem(config.NAMESPACE_TO_CATEGORY, "private-ns", "software")
        assert map_namespace_to_category("private-ns") == "software"


class TestUrgencyMapping:
    def test_critical_is_high(self):
        assert map_severity_to_urgency("critical") == 1

    def test_warning_is_medium(self):
        assert map_severity_to_urgency("warning") == 2

    def test_unknown_and_missing_are_low(self):
        assert map_severity_to_urgency("weird") == 3
        assert map_severity_to_urgency(None) == 3


class TestIncidentPayload:
    def test_basic_fields(self):
        payload = alert_to_incident_payload(make_alert())
        assert payload["short_description"] == "Disk space low"
        assert payload["urgency"] == 1
        assert payload["impact"] == 1
        assert payload["category"] == "inquiry"
        assert payload["cmdb_ci"] == "star-garden"
        assert "Fingerprint: abc123" in payload["description"]

    def test_short_description_capped_at_160(self):
        alert = make_alert(annotations={"summary": "x" * 500})
        assert len(alert_to_incident_payload(alert)["short_description"]) == 160

    def test_missing_summary_falls_back_to_alertname(self):
        alert = make_alert(annotations={})
        assert alert_to_incident_payload(alert)["short_description"] == "DiskSpaceLow"

    def test_chaos_signal_label_enriches_description(self):
        alert = make_alert(
            labels={"alertname": "PodKilled", "severity": "warning", "chaos_signal": "pod-kill"}
        )
        assert "Chaos type: pod-kill" in alert_to_incident_payload(alert)["description"]

    def test_legacy_chaos_type_label_still_accepted(self):
        alert = make_alert(
            labels={"alertname": "PodKilled", "severity": "warning", "chaos_type": "pod-kill"}
        )
        assert "Chaos type: pod-kill" in alert_to_incident_payload(alert)["description"]

    def test_no_chaos_line_without_chaos_labels(self):
        assert "Chaos type:" not in alert_to_incident_payload(make_alert())["description"]


class TestResolvePayload:
    def test_resolve_fields(self):
        payload = resolve_payload("closed by test")
        assert payload["incident_state"] == 6
        assert payload["close_notes"] == "closed by test"
