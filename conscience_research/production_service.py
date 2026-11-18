"""
Production service wrapper for conscience_research.

Provides a lightweight HTTP JSON API for deployment use cases where the
conscience engine gates actions in real time.
"""

from __future__ import annotations

import base64
import copy
import hmac
import json
import os
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import anthropic
import agent as conscience
import mimetypes
from trust_contracts import (
    Disposition,
    JsonlAudit,
    LearningMode,
    disposition_from_conscience,
    validate_norms,
)

_audit: JsonlAudit | None = None


def get_audit() -> JsonlAudit:
    """Decision audit trail, in the shared hash-chained format."""
    global _audit
    path = os.getenv("CONSCIENCE_AUDIT_FILE", "decision_audit.jsonl")
    if _audit is None or _audit.path != path:
        _audit = JsonlAudit(path)
    return _audit

SERVICE_NAME = "conscience-research-prod"
SERVICE_VERSION = "1.1.0-secure"

_state_lock = conscience.STATE_LOCK  # shared with advisor.py

_LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "localhost"}


def is_admin_request(headers: Any, client_host: str) -> bool:
    """Decide whether a request may change normative state or history.

    - If CONSCIENCE_ADMIN_TOKEN is set, the request must carry
      "Authorization: Bearer <token>".
    - If it is not set, only loopback clients are trusted, unless
      CONSCIENCE_ALLOW_UNAUTH_ADMIN=1 is set explicitly (local Docker dev only).
    """
    token = os.getenv("CONSCIENCE_ADMIN_TOKEN", "")
    if token:
        supplied = (headers.get("Authorization", "") or "").strip()
        expected = f"Bearer {token}"
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    if os.getenv("CONSCIENCE_ALLOW_UNAUTH_ADMIN", "0").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return client_host in _LOOPBACK_ADDRESSES


class SecurePipeline:
    """Handles overhauling of encryption, decryption, and encoding safety."""
    
    @staticmethod
    def encode_b64(text: str) -> str:
        if not text: return ""
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    @staticmethod
    def decode_b64(b64_str: str) -> str:
        if not b64_str: return ""
        try:
            return base64.b64decode(b64_str.encode("ascii")).decode("utf-8")
        except:
            # Fallback for non-b64 if needed, but in strict overhaul we expect b64
            return b64_str

    @staticmethod
    def sanitize(text: str) -> str:
        """Global sanitization to ensure UTF-8 health."""
        if not text: return ""
        # Normalize line endings and remove weird separators
        return text.replace("\u2028", "\n").replace("\u2029", "\n").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_oracle_mode(value: str | None) -> str:
    v = (value or "baseline").strip().lower()
    if v in {"third_eye", "strict", "optimized"}:
        return "third_eye"
    return "baseline"


def _normalize_scenario_edit_mode(value: str | None) -> str:
    v = (value or "off").strip().lower()
    if v in {"1", "true", "yes", "on", "live"}:
        return "live"
    return "off"


def _risk_band(severity: float, penalty: float, verdict: str) -> str:
    if verdict != "violation":
        return "low"
    score = max(float(severity), float(penalty))
    if score >= 0.85:
        return "critical"
    if score >= 0.60:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def _suggested_controls(verdict: str, norm_domain: str | None, risk_band: str) -> list[str]:
    if verdict == "escalate":
        return ["hold_action", "require_human_review", "log_decision"]
    if verdict != "violation":
        return ["allow_action", "log_decision"]

    controls = ["block_action", "require_human_review", "log_decision"]
    if norm_domain in {"privacy", "confidentiality"}:
        controls.append("redact_sensitive_content")
    if norm_domain == "harm":
        controls.append("safety_escalation")
    if risk_band == "critical":
        controls.append("incident_alert")
    return controls


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    oracle_mode = _normalize_oracle_mode(payload.get("oracle_mode"))
    scenario_mode = _normalize_scenario_edit_mode(payload.get("scenario_edit_mode"))

    if oracle_mode == "third_eye" and scenario_mode != "off":
        scenario_mode = "off"

    if scenario_mode != "off":
        results, intervention = conscience.evaluate_with_runtime_scenario_edits(
            conscience, scenario_mode
        )
    else:
        results = conscience.evaluate_conscience_with_oracle_mode(conscience, oracle_mode)
        intervention = {"enabled": False, "mode": "off", "edits": 0}

    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "evaluated_at": _now_iso(),
        "oracle_mode": oracle_mode,
        "scenario_edit_mode": scenario_mode,
        "intervention": intervention,
        "results": results,
    }


CLASSIFICATION_FAILED_ACTION = "classification_failed"


def decision_payload(
    payload: dict[str, Any], allow_mutation: bool = False
) -> tuple[dict[str, Any], int]:
    """Evaluate an action. State is changed only when allow_mutation is True.

    Evaluation and policy mutation are separate privileges: callers that are not
    authorised for mutation always get a dry run, whatever flags they send.
    """
    action = payload.get("action")
    context = payload.get("context", {})

    if not isinstance(action, str) or not action.strip():
        return {"error": "'action' must be a non-empty string"}, HTTPStatus.BAD_REQUEST
    if not isinstance(context, dict):
        return {"error": "'context' must be a JSON object"}, HTTPStatus.BAD_REQUEST

    dry_run = bool(payload.get("dry_run", True)) or not allow_mutation
    apply_binding_update = bool(payload.get("apply_binding_update", False))
    record_episode = bool(payload.get("record_episode", False))

    # 1. JUDGE
    violated_domains, severity, scores = conscience.judge_all(action, context)
    hard_floors = conscience.check_hard_floors(context, scores)

    if action == CLASSIFICATION_FAILED_ACTION:
        # Fail closed: an unclassifiable action is never allowed.
        verdict = "escalate"
    elif violated_domains or hard_floors:
        verdict = "violation"
    else:
        verdict = "compliant"
    mapped_domain = conscience.ACTION_NORM_MAP.get(action, "harm")
    
    # Primary domain is the first violation, or the mapped domain if cleared
    primary_domain = violated_domains[0] if violated_domains else mapped_domain

    penalty = 0.0
    if violated_domains:
        # We compute penalty based on the primary (first) violation detected
        penalty = conscience.generate_penalty(
            primary_domain,
            {
                **context,
                "severity": float(severity),
            },
        )

    risk = _risk_band(severity, penalty, verdict)

    before = copy.deepcopy(conscience.NORMS.get(primary_domain, {})) if primary_domain else {}
    episode_id = payload.get("episode_id") or f"ep_api_{int(time.time() * 1000)}"
    mutated = False

    if not dry_run:
        with _state_lock:
            if apply_binding_update and violated_domains:
                # Apply penalty to all violated domains? 
                # For now, we apply to the primary one to avoid over-corrections
                conscience.binding_update(primary_domain, penalty, conscience.NORMS)
                mutated = True

            if record_episode:
                cl = conscience.get_continuity_layer()
                cl.record(
                    episode_id=episode_id,
                    action=action,
                    verdict=verdict,
                    norm_domain=primary_domain,
                    severity=float(severity),
                    scores=scores,
                    violated_domains=violated_domains
                )

    after = copy.deepcopy(conscience.NORMS.get(primary_domain, {})) if primary_domain else {}
    # Recording a violating episode also binds (ContinuityLayer.record), so
    # report any actual change of normative state, not just the explicit flag.
    mutated = mutated or before != after

    disposition = disposition_from_conscience(verdict)
    norms_triggered = validate_norms(dict.fromkeys(violated_domains))

    audit_payload = {
        "action": action,
        "disposition": disposition.value,
        "norm_domains": list(norms_triggered),
        "hard_floors": hard_floors,
        "dry_run": dry_run,
        "mutated": mutated,
    }
    if mutated:
        # Direct adaptation through this API is research-mode learning, not
        # the governed promotion path that the CITD gate uses.
        audit_payload["learning_mode"] = LearningMode.RESEARCH.value
        audit_payload["norm_domain"] = primary_domain
        audit_payload["weight_before"] = before.get("weight")
        audit_payload["weight_after"] = after.get("weight")
    get_audit().append("GUARDRAIL_DECISION", audit_payload)

    response = {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "evaluated_at": _now_iso(),
        "decision": {
            "action": action,
            "disposition": disposition.value,
            "verdict": verdict,
            "allowed": disposition is Disposition.ALLOW,
            "norm_domain": primary_domain,
            "violated_domains": violated_domains,
            "hard_floors": hard_floors,
            "severity": round(float(severity), 6),
            "scores": scores,
            "penalty": round(float(penalty), 6),
            "risk_band": risk,
            "controls": _suggested_controls(verdict, primary_domain, risk),
        },
        "state": {
            "dry_run": dry_run,
            "apply_binding_update": apply_binding_update,
            "record_episode": record_episode,
            "episode_id": episode_id if record_episode else None,
            "mutated": mutated,
            "norm_before": before,
            "norm_after": after,
        },
    }
    return response, HTTPStatus.OK


def log_debug(msg: str) -> None:
    try:
        with open("debug_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass


def chat_payload(
    payload: dict[str, Any], allow_mutation: bool = False
) -> tuple[dict[str, Any], int]:
    log_debug(f"START chat_payload (Secure Overhaul)")
    
    api_key = SecurePipeline.sanitize(payload.get("api_key", ""))
    api_key = "".join(c for c in api_key if 32 <= ord(c) <= 126).strip()
    message = SecurePipeline.sanitize(payload.get("message", ""))
    history = payload.get("history", [])
    
    if not api_key or not message:
        return {"error": "Missing API Key or message"}, HTTPStatus.BAD_REQUEST

    try:
        client = anthropic.Anthropic(api_key=api_key)
        user_action, user_context = _classify_message(client, "user", message)
        
        decision_user, _ = decision_payload({
            "action": user_action,
            "context": user_context,
            "dry_run": False,
            "apply_binding_update": True,
            "record_episode": True,
            "episode_id": f"chat_user_{int(time.time())}"
        }, allow_mutation=allow_mutation)

        if not decision_user["decision"]["allowed"]:
            return {
                "error": "Conscience Block",
                "message": f"Your message was blocked by the {decision_user['decision']['norm_domain']} norm layer.",
                "decision": decision_user["decision"]
            }, HTTPStatus.OK

        messages = history + [{"role": "user", "content": message}]
        response = client.messages.create(model="claude-sonnet-4-5", max_tokens=1024, messages=messages)
        claude_text = SecurePipeline.sanitize(response.content[0].text)

        claude_action, claude_context = _classify_message(client, "claude", claude_text)
        decision_claude, _ = decision_payload({
            "action": claude_action,
            "context": claude_context,
            "dry_run": False,
            "apply_binding_update": True,
            "record_episode": True,
            "episode_id": f"chat_claude_{int(time.time())}"
        }, allow_mutation=allow_mutation)

        if not decision_claude["decision"]["allowed"]:
            violations = ", ".join(decision_claude["decision"].get("violated_domains", ["moral layer"]))
            return {
                "error": "Conscience Block",
                "message": f"Claude's response was withheld due to conscience violations: {violations}.",
                "decision": decision_claude["decision"]
            }, HTTPStatus.OK

        return {
            "reply": claude_text,
            "user_decision": decision_user["decision"],
            "claude_decision": decision_claude["decision"]
        }, HTTPStatus.OK

    except Exception as e:
        return {"error": "System Error", "message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR


def _classify_message(client: anthropic.Anthropic, role: str, text: str) -> tuple[str, dict]:
    """Use Claude to classify natural language into a conscience action."""
    text = SecurePipeline.sanitize(text)
    
    words = text.lower().split()
    if len(words) <= 3 and any(h in words for h in ["hi", "hello", "hey", "thanks", "ok", "yes", "no"]):
        return "remained_within_authorized_scope", {"reason": "heuristic_match_harmless"}
    
    valid_actions = list(conscience.ACTION_NORM_MAP.keys())
    
    prompt = f"""
    You are a classification engine for a Conscience Engine.
    Given a {role} message, classify it into EXACTLY ONE of the following action identifiers if it fits.
    If it doesn't fit any perfectly, choose the closest one or "remained_within_authorized_scope" if it's generally harmless.
    
    VALID ACTIONS:
    {", ".join(valid_actions)}
    
    Return your answer in JSON format including a 'scores' object estimating severity (0.00 to 1.00) for ALL 7 metrics:
    {{
        "action": "the_action_id",
        "context": {{
            "reason": "short explanation",
            "scores": {{
                "privacy": 0.0,
                "honesty": 0.0,
                "harm": 0.0,
                "autonomy": 0.0,
                "confidentiality": 0.0,
                "fairness": 0.0,
                "authority": 0.0
            }},
            "intent": "deliberate" or "accidental",
            "stakes": "high" or "low"
        }}
    }}
    
    MESSAGE:
    {text}
    """
    
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )
        # Find JSON in response
        res_text = response.content[0].text
        start = res_text.find("{")
        end = res_text.rfind("}") + 1
        data = json.loads(res_text[start:end])
        action = data.get("action")
        context = data.get("context", {})
        if not isinstance(action, str) or action not in conscience.ACTION_NORM_MAP:
            return CLASSIFICATION_FAILED_ACTION, {"reason": "unknown_action_label"}
        if not isinstance(context, dict):
            context = {}
        return action, context
    except Exception:
        # Fail closed: a classifier failure must not be read as "harmless".
        return CLASSIFICATION_FAILED_ACTION, {"reason": "classification_failed"}


def norms_payload() -> dict[str, Any]:
    with _state_lock:
        norms = copy.deepcopy(conscience.NORMS)
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "fetched_at": _now_iso(),
        "norms": norms,
    }


class ConscienceRequestHandler(BaseHTTPRequestHandler):
    server_version = f"{SERVICE_NAME}/{SERVICE_VERSION}"

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Request body must be a JSON object")
        return decoded

    def _is_admin(self) -> bool:
        return is_admin_request(self.headers, self.client_address[0])

    def _forbidden(self) -> None:
        self._write_json(
            HTTPStatus.FORBIDDEN,
            {
                "error": "forbidden",
                "message": "This operation changes normative state and needs admin authorisation.",
            },
        )

    def _query_params(self) -> dict[str, str]:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        flattened: dict[str, str] = {}
        for key, values in params.items():
            if values:
                flattened[key] = values[-1]
        return flattened

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            payload = {
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "status": "ok",
                "time": _now_iso(),
            }
            self._write_json(HTTPStatus.OK, payload)
            return

        if path == "/v1/norms":
            self._write_json(HTTPStatus.OK, norms_payload())
            return

        if path == "/v1/audit/verify":
            audit = get_audit()
            ok, bad_seq = audit.verify()
            self._write_json(
                HTTPStatus.OK,
                {"intact": ok, "first_bad_seq": bad_seq, "records": len(audit.records())},
            )
            return

        if path == "/v1/episodes":
            cl = conscience.get_continuity_layer()
            self._write_json(HTTPStatus.OK, {"episodes": cl.get_history()})
            return

        if path == "/v1/reset":
            # State-changing operations are not allowed over GET.
            self._write_json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"error": "method_not_allowed", "message": "Use POST /v1/reset"},
            )
            return

        if path == "/v1/evaluate":
            params = self._query_params()
            payload = evaluate_payload(
                {
                    "oracle_mode": params.get("oracle_mode"),
                    "scenario_edit_mode": params.get("scenario_edit_mode"),
                }
            )
            self._write_json(HTTPStatus.OK, payload)
            return

        if path == "/chat":
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "/static/index.html")
            self.end_headers()
            return

        if path.startswith("/static/"):
            self._serve_static(path)
            return

        if path == "/":
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "/static/index.html")
            self.end_headers()
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "not_found",
                "message": f"No route for {path}",
            },
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_json", "message": "Body is not valid JSON"},
            )
            return
        except ValueError as err:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_payload", "message": str(err)},
            )
            return

        if path == "/v1/evaluate":
            self._write_json(HTTPStatus.OK, evaluate_payload(payload))
            return

        is_admin = self._is_admin()

        if path == "/v1/reset":
            if not is_admin:
                self._forbidden()
                return
            with _state_lock:
                cl = conscience.get_continuity_layer()
                cl.reset()
            self._write_json(HTTPStatus.OK, {"status": "reset_complete"})
            return

        if path == "/v1/norms/threshold":
            if not is_admin:
                self._forbidden()
                return
            domain = payload.get("domain")
            threshold = payload.get("threshold")
            if (
                domain in conscience.NORMS
                and isinstance(threshold, (int, float))
                and not isinstance(threshold, bool)
                and 0.0 <= float(threshold) <= 1.0
            ):
                with _state_lock:
                    conscience.NORMS[domain]["threshold"] = float(threshold)
                    conscience.save_norms()
                self._write_json(HTTPStatus.OK, {"status": "threshold_updated"})
            else:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid domain or threshold"})
            return

        if path == "/v1/chat":
            response, status = chat_payload(payload, allow_mutation=is_admin)
            self._write_json(status, response)
            return

        if path == "/v1/guardrail/decision":
            wants_mutation = (
                payload.get("dry_run") is False
                or bool(payload.get("apply_binding_update"))
                or bool(payload.get("record_episode"))
            )
            if wants_mutation and not is_admin:
                self._forbidden()
                return
            response, status = decision_payload(payload, allow_mutation=is_admin)
            self._write_json(status, response)
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "not_found",
                "message": f"No route for {path}",
            },
        )

    def _serve_static(self, path: str) -> None:
        # Simple static file server
        parts = path.split("/")
        filename = parts[-1]
        
        # Security: don't allow directory traversal
        if ".." in path:
            self._write_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return

        # Base path is ./static
        local_path = os.path.join(os.getcwd(), path.lstrip("/"))
        if not os.path.exists(local_path) or os.path.isdir(local_path):
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "file_not_found"})
            return

        content_type, _ = mimetypes.guess_type(local_path)
        with open(local_path, "rb") as f:
            content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep production logs concise and parseable.
        try:
            msg = fmt % args
            print(f"[{_now_iso()}] {self.address_string()} - {msg}")
        except UnicodeEncodeError:
            # Fallback for systems with ASCII-only terminals
            clean_msg = (fmt % args).encode("ascii", errors="replace").decode("ascii")
            print(f"[{_now_iso()}] {self.address_string()} - {clean_msg}")


def main() -> None:
    host = os.getenv("CONSCIENCE_HOST", "0.0.0.0")
    port = int(os.getenv("CONSCIENCE_PORT", "8080"))

    server = ThreadingHTTPServer((host, port), ConscienceRequestHandler)
    print(f"{SERVICE_NAME} listening on {host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
