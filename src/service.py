from __future__ import annotations

from typing import Any, Dict, Optional

from .domain import (ConflictError, ensure_role, normalize_severity,
                     require_number, require_text)
from .repository import Repository
from .rules import (AUDIT_ROLES, CREATE_ROLES, ENTITY, FEEDBACK_KIND,
                    RECORD_ROLES, REVIEW_KIND, TITLE, VIEW_ROLES,
                    authorization_blockers, completion_blockers,
                    escalation_required, priority_score, record_close_roles,
                    response_deadline_hours, role_for_transition,
                    validate_transition)


class Service:
    def __init__(self, repository: Repository):
        self.repository = repository

    def _view(self, role: str) -> None:
        ensure_role(role, VIEW_ROLES)

    def create_item(self, payload: Dict[str, Any], actor: str, role: str) -> Dict[str, Any]:
        ensure_role(role, CREATE_ROLES)
        actor = require_text(actor, "actor", 100)
        title = require_text(payload.get("title"), "title", 200)
        description = require_text(payload.get("description"), "description")
        severity = normalize_severity(payload.get("severity"))
        quantity = require_number(payload.get("quantity", 0), "quantity")
        threshold = require_number(payload.get("threshold", 1), "threshold", 0.000001)
        external_ref = payload.get("external_ref")
        if external_ref is not None:
            external_ref = require_text(external_ref, "external_ref", 100)
        item = self.repository.create_item(title, description, severity, quantity,
                                           threshold, external_ref, actor)
        self.repository.append_audit("create", ENTITY, item["id"], actor, {
            "title": title, "severity": severity, "quantity": quantity,
            "priority": priority_score(severity, quantity, threshold),
        })
        return self.enrich(item)

    def add_record(self, item_id: int, payload: Dict[str, Any], actor: str,
                   role: str) -> Dict[str, Any]:
        ensure_role(role, RECORD_ROLES)
        actor = require_text(actor, "actor", 100)
        kind = require_text(payload.get("kind"), "kind", 100)
        detail = require_text(payload.get("detail"), "detail")
        status = payload.get("status", "open")
        if status not in ("open", "closed"):
            raise ValueError("status必须是open或closed")
        external_ref = payload.get("external_ref")
        if external_ref is not None:
            external_ref = require_text(external_ref, "external_ref", 100)
        record = self.repository.add_record(item_id, kind, detail, status,
                                            external_ref, actor)
        self.repository.append_audit("record", ENTITY, item_id, actor, {
            "record_id": record["id"], "kind": kind, "status": status,
        })
        return record

    def transition(self, item_id: int, target: str, expected_version: int,
                   actor: str, role: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        actor = require_text(actor, "actor", 100)
        item = self.repository.get_item(item_id)
        validate_transition(item["status"], target)
        ensure_role(role, role_for_transition(target))
        if not isinstance(expected_version, int) or expected_version < 1:
            raise ValueError("expected_version必须是正整数")
        blockers = authorization_blockers(
            target, self.repository.closed_record_count(item_id, REVIEW_KIND))
        blockers += completion_blockers(
            target, self.repository.open_record_count(item_id),
            self.repository.open_record_count(item_id, FEEDBACK_KIND))
        if blockers:
            raise ConflictError("；".join(blockers))
        side = self._side_record(target, payload)
        updated = self.repository.transition_item(item_id, target, expected_version, actor)
        if side is not None:
            record = self.repository.add_record(item_id, side["kind"], side["detail"],
                                                "open", None, side["created_by"])
            self.repository.append_audit("record", ENTITY, item_id, actor, {
                "record_id": record["id"], "kind": side["kind"], "status": "open",
                "created_by": side["created_by"],
            })
        self.repository.append_audit("transition", ENTITY, item_id, actor, {
            "from": item["status"], "to": target,
            "escalation_required": escalation_required(
                item["severity"], item["quantity"], item["threshold"]),
        })
        return self.enrich(updated)

    @staticmethod
    def _side_record(target: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if target == "checked":
            reviewer = require_text(payload.get("reviewer"), "reviewer", 100)
            opinion = require_text(payload.get("opinion"), "opinion")
            return {"kind": REVIEW_KIND, "detail": opinion, "created_by": reviewer}
        if target == "executed":
            contact = require_text(payload.get("contact"), "contact", 100)
            discharge = require_number(payload.get("discharge"), "discharge")
            return {"kind": FEEDBACK_KIND,
                    "detail": f"现场联系人：{contact}；泄量：{discharge}",
                    "created_by": contact}
        return None

    def close_record(self, item_id: int, record_id: int, actor: str,
                     role: str) -> Dict[str, Any]:
        actor = require_text(actor, "actor", 100)
        record = self.repository.get_record(item_id, record_id)
        ensure_role(role, record_close_roles(record["kind"]))
        closed = self.repository.close_record(item_id, record_id)
        self.repository.append_audit("close_record", ENTITY, item_id, actor, {
            "record_id": closed["id"], "kind": closed["kind"],
        })
        return closed

    def get_item(self, item_id: int, role: str) -> Dict[str, Any]:
        self._view(role)
        return self.enrich(self.repository.get_item(item_id))

    def list_items(self, role: str, status: Optional[str] = None) -> list:
        self._view(role)
        return [self.enrich(item) for item in self.repository.list_items(status)]

    def list_records(self, item_id: int, role: str) -> list:
        self._view(role)
        return self.repository.list_records(item_id)

    def audit(self, role: str, item_id: Optional[int] = None) -> list:
        ensure_role(role, AUDIT_ROLES)
        return self.repository.list_audit(item_id)

    def enrich(self, item: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(item)
        result["priority"] = priority_score(
            item["severity"], item["quantity"], item["threshold"])
        result["deadline_hours"] = response_deadline_hours(
            item["severity"], item["quantity"], item["threshold"])
        result["escalation_required"] = escalation_required(
            item["severity"], item["quantity"], item["threshold"])
        review = self.repository.latest_record_by_kind(item["id"], REVIEW_KIND)
        result["reviewer"] = review["created_by"] if review else None
        feedback = self.repository.latest_record_by_kind(item["id"], FEEDBACK_KIND)
        result["last_feedback_by"] = feedback["created_by"] if feedback else None
        return result
