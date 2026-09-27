"""Source-grounded AI repair proposal contracts for BookIR."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from book.domain.models import Book, BookNode, Patch, PatchOperation
from book.quality import QualityIssue
from book.repair.patch_engine import PatchValidationError, PatchValidator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AIRepairProposalError(ValueError):
    """Raised when a model response cannot become a safe BookIR patch."""


@dataclass(frozen=True)
class AIRepairProposal:
    """A model-authored patch proposal that still requires human approval."""

    id: str
    issue_id: str
    issue: Dict[str, Any]
    patch: Patch
    provider: str
    model: str
    rationale: str
    evidence_node_ids: Tuple[str, ...]
    evidence_source_ids: Tuple[str, ...]
    grounding_hash: str
    confidence: float
    input_mode: str = "text"
    source_image_refs: Tuple[str, ...] = ()
    status: str = "pending"
    created_at: str = field(default_factory=_utc_now)
    reviewed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("proposal id must not be empty")
        if not self.issue_id:
            raise ValueError("proposal issue_id must not be empty")
        if self.status not in {"pending", "accepted", "rejected", "superseded"}:
            raise ValueError("invalid AI repair proposal status")
        if self.input_mode not in {"text", "vision"}:
            raise ValueError("AI proposal input_mode must be text or vision")
        if self.input_mode == "vision" and not self.source_image_refs:
            raise ValueError("vision AI proposal requires source_image_refs")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposal confidence must be in [0, 1]")
        if not self.evidence_node_ids:
            raise ValueError("AI proposal requires evidence_node_ids")
        if not self.evidence_source_ids:
            raise ValueError("AI proposal requires evidence_source_ids")

    def with_status(self, status: str) -> "AIRepairProposal":
        return replace(self, status=status, reviewed_at=_utc_now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "issue": self.issue,
            "patch": self.patch.to_dict(),
            "provider": self.provider,
            "model": self.model,
            "rationale": self.rationale,
            "evidence_node_ids": list(self.evidence_node_ids),
            "evidence_source_ids": list(self.evidence_source_ids),
            "grounding_hash": self.grounding_hash,
            "confidence": self.confidence,
            "input_mode": self.input_mode,
            "source_image_refs": list(self.source_image_refs),
            "status": self.status,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AIRepairProposal":
        return cls(
            id=str(value["id"]),
            issue_id=str(value["issue_id"]),
            issue=dict(value.get("issue", {})),
            patch=Patch.from_dict(value["patch"]),
            provider=str(value.get("provider", "")),
            model=str(value.get("model", "")),
            rationale=str(value.get("rationale", "")),
            evidence_node_ids=tuple(
                str(item) for item in value.get("evidence_node_ids", [])
            ),
            evidence_source_ids=tuple(
                str(item) for item in value.get("evidence_source_ids", [])
            ),
            grounding_hash=str(value.get("grounding_hash", "")),
            confidence=float(value.get("confidence", 1.0)),
            input_mode=str(value.get("input_mode", "text")),
            source_image_refs=tuple(
                str(item) for item in value.get("source_image_refs", [])
            ),
            status=str(value.get("status", "pending")),
            created_at=str(value.get("created_at") or _utc_now()),
            reviewed_at=(
                str(value["reviewed_at"])
                if value.get("reviewed_at") is not None
                else None
            ),
        )


class AIRepairProposalGenerator:
    """Build grounded prompts and convert strict model JSON into validated patches."""

    ALLOWED_OPERATIONS = {
        PatchOperation.REPLACE_CONTENT,
        PatchOperation.SET_ATTRIBUTE,
    }
    SAFE_ATTRIBUTE_KEYS = {"level"}

    def __init__(
        self,
        *,
        patch_validator: Optional[PatchValidator] = None,
        context_radius: int = 1,
        max_node_chars: int = 4000,
        max_replacement_chars: int = 8000,
    ) -> None:
        if context_radius < 0:
            raise ValueError("context_radius must be >= 0")
        self.patch_validator = patch_validator or PatchValidator()
        self.context_radius = context_radius
        self.max_node_chars = max_node_chars
        self.max_replacement_chars = max_replacement_chars

    def build_prompt(self, book: Book, issue: QualityIssue) -> str:
        context = self.build_context(book, issue)
        schema = {
            "operation": "replace_content | set_attribute",
            "target_node_id": "must be one of issue.node_ids",
            "payload": {
                "content": "required for replace_content",
                "key": "level only for set_attribute",
                "value": "heading level 1..6 for set_attribute",
            },
            "reason": "short source-grounded rationale",
            "confidence": "number from 0 to 1",
            "evidence_node_ids": ["ids copied from context_nodes"],
            "evidence_source_ids": ["source_id values copied from cited nodes"],
        }
        instructions = {
            "goal": (
                "Propose exactly one minimal repair for the quality issue. "
                "Do not rewrite unrelated text."
            ),
            "constraints": [
                "Return one JSON object only. No Markdown fences or prose.",
                "Never invent node ids or source ids.",
                "Target only a node listed in issue.node_ids.",
                "Use only replace_content or set_attribute.",
                "set_attribute may only set key=level with integer value 1..6.",
                "Cite at least one evidence node and one source_id from context.",
                "Do not claim evidence that is not present in the supplied context.",
                "If evidence is insufficient, return an object with operation=null.",
            ],
            "response_schema": schema,
        }
        return (
            "You are a conservative BookIR repair proposer.\n"
            + json.dumps(instructions, ensure_ascii=False, indent=2)
            + "\nGROUNDING_CONTEXT\n"
            + json.dumps(context, ensure_ascii=False, indent=2)
        )

    def build_context(self, book: Book, issue: QualityIssue) -> Dict[str, Any]:
        if not issue.node_ids:
            raise AIRepairProposalError(
                f"Issue {issue.id!r} has no target nodes for AI repair"
            )

        nodes = list(book.walk())
        index_by_id = {node.id: index for index, node in enumerate(nodes)}
        missing = [node_id for node_id in issue.node_ids if node_id not in index_by_id]
        if missing:
            raise AIRepairProposalError(
                f"Issue references missing BookIR nodes: {sorted(missing)}"
            )

        selected_indexes = set()
        for node_id in issue.node_ids:
            index = index_by_id[node_id]
            start = max(0, index - self.context_radius)
            end = min(len(nodes), index + self.context_radius + 1)
            selected_indexes.update(range(start, end))

        context_nodes = [
            self._serialize_node(nodes[index]) for index in sorted(selected_indexes)
        ]
        context = {
            "book": {
                "title": book.metadata.title,
                "author": book.metadata.author,
                "language": book.metadata.language,
                "source_path": book.metadata.source_path,
            },
            "issue": issue.to_dict(),
            "context_nodes": context_nodes,
        }
        context["grounding_hash"] = self._grounding_hash(context)
        return context

    def parse_response(
        self,
        book: Book,
        issue: QualityIssue,
        raw_response: str,
        *,
        provider: str,
        model: str,
        input_mode: str = "text",
        source_image_refs: Tuple[str, ...] = (),
    ) -> AIRepairProposal:
        if input_mode not in {"text", "vision"}:
            raise AIRepairProposalError("input_mode must be text or vision")
        if input_mode == "vision" and not source_image_refs:
            raise AIRepairProposalError(
                "vision proposal requires source image evidence"
            )

        context = self.build_context(book, issue)
        parsed = self._parse_json_object(raw_response)

        operation_value = parsed.get("operation")
        if operation_value is None:
            raise AIRepairProposalError("Model reported insufficient evidence")

        try:
            operation = PatchOperation(str(operation_value))
        except ValueError as exc:
            raise AIRepairProposalError(
                f"Unsupported AI patch operation: {operation_value!r}"
            ) from exc
        if operation not in self.ALLOWED_OPERATIONS:
            raise AIRepairProposalError(
                f"AI patch operation is not allowed: {operation.value}"
            )

        target_node_id = str(parsed.get("target_node_id", ""))
        if target_node_id not in issue.node_ids:
            raise AIRepairProposalError(
                "AI proposal target must be one of the issue target nodes"
            )

        evidence_node_ids = self._string_tuple(
            parsed.get("evidence_node_ids"),
            field_name="evidence_node_ids",
        )
        context_node_ids = {
            str(node["id"]) for node in context.get("context_nodes", [])
        }
        if target_node_id not in evidence_node_ids:
            raise AIRepairProposalError("AI evidence must include the target node")
        unknown_nodes = set(evidence_node_ids) - context_node_ids
        if unknown_nodes:
            raise AIRepairProposalError(
                f"AI proposal invented evidence nodes: {sorted(unknown_nodes)}"
            )

        source_ids_by_node = {
            str(node["id"]): {
                str(source["source_id"]) for source in node.get("source", [])
            }
            for node in context.get("context_nodes", [])
        }
        allowed_source_ids = set().union(
            *(source_ids_by_node[node_id] for node_id in evidence_node_ids)
        )
        evidence_source_ids = self._string_tuple(
            parsed.get("evidence_source_ids"),
            field_name="evidence_source_ids",
        )
        unknown_sources = set(evidence_source_ids) - allowed_source_ids
        if unknown_sources:
            raise AIRepairProposalError(
                f"AI proposal invented source ids: {sorted(unknown_sources)}"
            )
        if not allowed_source_ids:
            raise AIRepairProposalError(
                "Selected evidence nodes contain no source provenance"
            )

        payload = parsed.get("payload")
        if not isinstance(payload, dict):
            raise AIRepairProposalError("AI proposal payload must be an object")
        payload = dict(payload)
        self._validate_restricted_payload(
            book,
            operation=operation,
            target_node_id=target_node_id,
            payload=payload,
        )

        reason = str(parsed.get("reason", "")).strip()
        if not reason:
            raise AIRepairProposalError("AI proposal reason must not be empty")

        try:
            confidence = float(parsed.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise AIRepairProposalError(
                "AI proposal confidence must be numeric"
            ) from exc
        if not 0.0 <= confidence <= 1.0:
            raise AIRepairProposalError("AI proposal confidence must be in [0, 1]")

        patch_seed = {
            "issue_id": issue.id,
            "operation": operation.value,
            "target_node_id": target_node_id,
            "payload": payload,
            "provider": provider,
            "model": model,
        }
        patch_id = "ai-patch-" + str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                json.dumps(patch_seed, ensure_ascii=False, sort_keys=True),
            )
        )
        patch = Patch(
            id=patch_id,
            operation=operation,
            target_node_id=target_node_id,
            payload=payload,
            reason=f"AI repair proposal: {reason}",
            confidence=confidence,
            applied=False,
        )
        try:
            self.patch_validator.validate(book, patch)
        except PatchValidationError as exc:
            raise AIRepairProposalError(str(exc)) from exc

        proposal_seed = {
            **patch_seed,
            "evidence_node_ids": evidence_node_ids,
            "evidence_source_ids": evidence_source_ids,
            "grounding_hash": context["grounding_hash"],
            "input_mode": input_mode,
            "source_image_refs": source_image_refs,
        }
        proposal_id = "ai-proposal-" + str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                json.dumps(proposal_seed, ensure_ascii=False, sort_keys=True),
            )
        )
        return AIRepairProposal(
            id=proposal_id,
            issue_id=issue.id,
            issue=issue.to_dict(),
            patch=patch,
            provider=provider,
            model=model,
            rationale=reason,
            evidence_node_ids=evidence_node_ids,
            evidence_source_ids=evidence_source_ids,
            grounding_hash=str(context["grounding_hash"]),
            confidence=confidence,
            input_mode=input_mode,
            source_image_refs=source_image_refs,
        )

    def _validate_restricted_payload(
        self,
        book: Book,
        *,
        operation: PatchOperation,
        target_node_id: str,
        payload: Dict[str, Any],
    ) -> None:
        node = book.find_node(target_node_id)
        if node is None:
            raise AIRepairProposalError("AI proposal target node does not exist")

        if operation == PatchOperation.REPLACE_CONTENT:
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                raise AIRepairProposalError(
                    "replace_content requires non-empty string content"
                )
            if content == node.content:
                raise AIRepairProposalError("AI replacement is a no-op")
            if len(content) > self.max_replacement_chars:
                raise AIRepairProposalError(
                    "AI replacement exceeds the configured size limit"
                )
            if set(payload) != {"content"}:
                raise AIRepairProposalError(
                    "replace_content payload may only contain content"
                )
            return

        key = payload.get("key")
        if key not in self.SAFE_ATTRIBUTE_KEYS:
            raise AIRepairProposalError(f"AI set_attribute key is not allowed: {key!r}")
        if set(payload) != {"key", "value"}:
            raise AIRepairProposalError(
                "set_attribute payload may only contain key and value"
            )
        value = payload.get("value")
        if key == "level" and (
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 6
        ):
            raise AIRepairProposalError("heading level must be an integer from 1 to 6")

    def _serialize_node(self, node: BookNode) -> Dict[str, Any]:
        content = node.content
        if len(content) > self.max_node_chars:
            content = content[: self.max_node_chars] + "…"
        return {
            "id": node.id,
            "type": node.type.value,
            "content": content,
            "attrs": node.attrs,
            "confidence": node.confidence.to_dict(),
            "source": [source.to_dict() for source in node.source],
        }

    @staticmethod
    def _string_tuple(value: Any, *, field_name: str) -> Tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise AIRepairProposalError(f"{field_name} must be a non-empty list")
        result = tuple(str(item) for item in value)
        if any(not item for item in result):
            raise AIRepairProposalError(f"{field_name} contains an empty id")
        if len(set(result)) != len(result):
            raise AIRepairProposalError(f"{field_name} contains duplicate ids")
        return result

    @staticmethod
    def _parse_json_object(raw_response: str) -> Dict[str, Any]:
        text = raw_response.strip()
        fence = chr(96) * 3
        if text.startswith(fence):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == fence:
                text = "\n".join(lines[1:-1]).strip()
                if text.lower().startswith("json\n"):
                    text = text[5:].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIRepairProposalError("Model response is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise AIRepairProposalError("Model response JSON root must be an object")
        return parsed

    @staticmethod
    def _grounding_hash(context: Dict[str, Any]) -> str:
        canonical = dict(context)
        canonical.pop("grounding_hash", None)
        encoded = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
