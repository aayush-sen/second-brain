#!/usr/bin/env python3
"""Agentic OS dashboard — stdlib only. Run: python3 serve.py → http://localhost:8877
All parsing/writes go through scripts/oslib.py; this file is just HTTP plumbing."""
import base64
import binascii
import hashlib
import ipaddress
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import (
    parse_qs, parse_qsl, quote, unquote, urlencode, urlparse, urlunparse,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import canvas_ai
import canvas_store
import canvas_sync
import jobs as jobfeed
import oslib
from oslib import OS, COLLECTIONS, ENUMS


MAX_SNAPSHOT_BYTES = 25 * 1024 * 1024
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_LOCAL_JSON_BYTES = 1024 * 1024
SOURCE_ROOT = canvas_store.DB_PATH.parent / "sources"
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_EXTENSION_ID = re.compile(r"^[a-p]{32}$")
_PRIVATE_URL_KEYS = {
    "token", "verifier", "code", "oauthcode", "sig", "signature",
    "awsaccesskeyid", "xamzsignature", "xamzcredential",
    "xamzsecuritytoken", "authorization", "auth", "cookie", "session",
    "sessionid", "password", "passwd", "secret", "clientsecret", "apikey",
    "credential", "credentials", "bearer", "jwt", "csrf",
}
_FRAGMENT_QUERY = re.compile(
    r"(?:[A-Za-z0-9_.~%-]+=[^/?#&]*)(?:&[A-Za-z0-9_.~%-]+=[^/?#&]*)*"
)


class RequestError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class SourceConflict(Exception):
    pass


class _TextExtractor(HTMLParser):
    BLOCKS = {
        "address", "article", "aside", "blockquote", "div", "dl", "fieldset",
        "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
        "section", "table", "tr", "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, _attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in self.BLOCKS:
            self.parts.append("\n\n")
        elif not self.hidden and tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        elif not self.hidden and tag in self.BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def canvas_plain_text(value) -> str:
    parser = _TextExtractor()
    parser.feed(str(value or ""))
    parser.close()
    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in re.split(r"\n\s*\n", "".join(parser.parts))
        if paragraph.strip()
    ]
    return "\n\n".join(paragraphs)


def canvas_prose_text(value) -> str:
    return canvas_store.filter_generated_ai_policy(canvas_plain_text(value))


def _plain_scalar(value):
    return canvas_plain_text(value) if isinstance(value, str) else value


def _public_identifier(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _ID.fullmatch(value):
        return value
    return None


def _public_feedback(value):
    if isinstance(value, list):
        return [_public_feedback(item) for item in value]
    if isinstance(value, dict):
        item = {}
        for key, raw in value.items():
            if key not in _FEEDBACK_FIELDS:
                continue
            if key in {"body", "comment", "message", "text"}:
                item[key] = canvas_prose_text(raw)
            elif key in {"id", "author_id"}:
                identifier = _public_identifier(raw)
                if identifier is not None:
                    item[key] = identifier
            elif key == "author_name":
                item[key] = canvas_plain_text(raw)
            elif key == "attachments" and isinstance(raw, list):
                item[key] = [
                    _public_attachment(child)
                    for child in raw if isinstance(child, dict)
                ]
            elif key == "media_comment" and isinstance(raw, dict):
                media = {}
                for nested_key, nested_value in raw.items():
                    if (
                        nested_key not in _MEDIA_FIELDS
                        or not isinstance(
                            nested_value, (str, int, float, bool, type(None))
                        )
                    ):
                        continue
                    if nested_key == "url":
                        media[nested_key] = _safe_public_url(nested_value)
                    elif nested_key == "display_name":
                        media[nested_key] = canvas_plain_text(nested_value)
                    elif nested_key == "media_id":
                        identifier = _public_identifier(nested_value)
                        if identifier is not None:
                            media[nested_key] = identifier
                    else:
                        media[nested_key] = _plain_scalar(nested_value)
                item[key] = media
            elif isinstance(raw, (str, int, float, bool, type(None))):
                item[key] = _plain_scalar(raw)
        return item
    return None


def _public_submission(value):
    if not isinstance(value, dict):
        return {}
    return {
        key: (
            _public_feedback(raw)
            if key == "feedback" else _plain_scalar(raw)
        )
        for key, raw in value.items()
        if key in _SUBMISSION_FIELDS
        and (
            key == "feedback"
            or isinstance(raw, (str, int, float, bool, type(None)))
        )
    }


def _public_attachment(value):
    item = {}
    for key, raw in value.items():
        if key not in _ATTACHMENT_FIELDS:
            continue
        if key == "url":
            item[key] = _safe_public_url(raw)
        elif key in {"id", "uuid"}:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key == "description":
            item[key] = canvas_prose_text(raw)
        elif key in {"display_name", "filename"}:
            item[key] = canvas_plain_text(raw)
        elif isinstance(raw, (str, int, float, bool, type(None))):
            item[key] = _plain_scalar(raw)
    return item


def _public_history_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    allowed = {
        "id", "course_id", "name", "title", "html_url", "assignment_type",
        "group_category_id", "unlock_at", "lock_at", "due_at", "due_tz",
        "all_dates", "submission", "attachments",
    }
    item = {}
    for key in allowed:
        if key not in snapshot or key in {
            "all_dates", "submission", "attachments", "html_url",
        }:
            continue
        raw = snapshot[key]
        if key in {"id", "course_id", "group_category_id"}:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif isinstance(raw, (str, int, float, bool, type(None))):
            item[key] = (
                canvas_plain_text(raw)
                if key in {"name", "title"}
                else _plain_scalar(raw)
            )
    if "html_url" in snapshot:
        item["html_url"] = _safe_public_url(snapshot["html_url"])
    item["all_dates"] = _public_all_dates(snapshot.get("all_dates", []))
    item["description"] = canvas_prose_text(
        snapshot.get("description_html", snapshot.get("description", ""))
    )
    if "submission" in snapshot:
        item["submission"] = _public_submission(snapshot["submission"])
    if "attachments" in snapshot:
        item["attachments"] = [
            _public_attachment(attachment)
            for attachment in snapshot["attachments"]
            if isinstance(attachment, dict)
        ]
    return item


def public_assignment(assignment):
    item = {}
    complex_fields = {"all_dates", "feedback", "attachments", "history"}
    identifier_fields = {
        "canvas_id", "id", "stable_id", "course_id", "group_category_id",
    }
    for key, raw in assignment.items():
        if key in complex_fields or key == "description_html":
            continue
        if key in identifier_fields:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key == "html_url":
            item[key] = _safe_public_url(raw)
        elif isinstance(raw, (str, int, float, bool, type(None))):
            item[key] = (
                canvas_plain_text(raw)
                if key in {"title", "course_code", "course_name"}
                else _plain_scalar(raw)
            )
    item["html_url"] = _safe_public_url(assignment.get("html_url", ""))
    item["all_dates"] = _public_all_dates(assignment.get("all_dates", []))
    item["description"] = canvas_prose_text(
        assignment.get("description_html", "")
    )
    item["feedback"] = _public_feedback(assignment.get("feedback", []))
    item["attachments"] = [
        _public_attachment(attachment)
        for attachment in assignment.get("attachments", [])
        if isinstance(attachment, dict)
    ]
    if "history" in assignment:
        item["history"] = [
            {
                "run_id": _plain_scalar(row["run_id"]),
                "observed_at": _plain_scalar(row["observed_at"]),
                "snapshot": _public_history_snapshot(row.get("snapshot")),
            }
            for row in assignment["history"]
        ]
    return item


_OBJECT_FIELDS = {
    "kind", "id", "course_id", "title", "html_url", "removed_at",
    "message", "description", "posted_at", "delayed_post_at", "last_reply_at",
    "discussion_type", "published", "locked", "pinned", "position",
    "unlock_at", "state", "require_sequential_progress",
    "prerequisite_module_ids", "items_count", "module_id", "indent", "type",
    "content_id", "url", "page_url", "external_url", "new_tab",
    "completion_requirement", "content_details", "group_id", "join_level",
    "members_count", "context_type", "canvas_user_id", "name", "short_name",
    "sortable_name", "display_name", "attachments", "author",
}
_OBJECT_ID_FIELDS = {
    "id", "course_id", "module_id", "content_id", "group_id",
    "canvas_user_id",
}
_OBJECT_PROSE_FIELDS = {"message", "description"}
_OBJECT_TEXT_FIELDS = {
    "title", "name", "short_name", "sortable_name", "display_name",
}
_OBJECT_URL_FIELDS = {"html_url", "url", "page_url", "external_url"}
_NESTED_FIELDS = {
    "completion_requirement": {"type", "min_score", "completed"},
    "content_details": {"due_at", "unlock_at", "lock_at", "points_possible"},
    "author": {"id", "display_name", "avatar_image_url", "html_url"},
}
_ATTACHMENT_FIELDS = {
    "id", "uuid", "display_name", "filename", "content_type", "content-type",
    "mime_class", "size", "url", "created_at", "updated_at", "unlock_at",
    "locked", "hidden", "description",
}
_FEEDBACK_FIELDS = {
    "id", "author_id", "author_name", "comment", "body", "message", "text",
    "created_at", "edited_at", "attempt", "media_comment", "attachments",
}
_MEDIA_FIELDS = {"media_id", "media_type", "display_name", "url"}
_SUBMISSION_FIELDS = {
    "workflow_state", "submitted_at", "missing", "excused", "score", "grade",
    "feedback", "attempt", "late", "seconds_late",
}
_ALL_DATE_FIELDS = {
    "id", "title", "due_at", "unlock_at", "lock_at", "base",
    "course_section_id", "group_id", "student_ids", "html_url", "url",
}
_TERM_FIELDS = {"id", "name", "start_at", "end_at"}
_INSTRUCTOR_FIELDS = {
    "id", "name", "display_name", "short_name", "sortable_name",
    "html_url", "avatar_image_url", "created_at", "updated_at",
}
_INSTRUCTOR_TEXT_FIELDS = {
    "name", "display_name", "short_name", "sortable_name",
}


def _safe_public_url(value) -> str:
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password:
        return ""
    query = _safe_url_query(parsed.query)
    fragment = parsed.fragment
    if fragment.startswith("/") and "?" in fragment:
        route, _, route_query = fragment.partition("?")
        safe_query = _safe_url_query(route_query)
        fragment = route + ("?" + safe_query if safe_query else "")
    elif _FRAGMENT_QUERY.fullmatch(fragment):
        fragment = _safe_url_query(fragment)
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, fragment,
    ))


def _safe_url_query(value) -> str:
    return urlencode([
        (key, item)
        for key, item in parse_qsl(value, keep_blank_values=True)
        if not _private_url_key(key)
    ], doseq=True)


def _private_url_key(value) -> bool:
    key = str(value)
    for _ in range(2):
        decoded = unquote(key)
        if decoded == key:
            break
        key = decoded
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return (
        normalized in _PRIVATE_URL_KEYS
        or normalized.endswith((
            "token", "verifier", "signature", "credential", "credentials",
            "clientsecret", "session", "sessionid", "cookie",
        ))
    )


def _public_all_dates(value):
    if not isinstance(value, list):
        return []
    dates = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = {}
        for key, nested in raw.items():
            if key not in _ALL_DATE_FIELDS:
                continue
            if key in {"id", "course_section_id", "group_id"}:
                identifier = _public_identifier(nested)
                if identifier is not None:
                    item[key] = identifier
            elif key == "title":
                item[key] = canvas_plain_text(nested)
            elif key in {"html_url", "url"}:
                item[key] = _safe_public_url(nested)
            elif isinstance(nested, (str, int, float, bool, type(None))):
                item[key] = _plain_scalar(nested)
            elif key == "student_ids" and isinstance(nested, list):
                item[key] = [
                    identifier
                    for student_id in nested
                    if (identifier := _public_identifier(student_id)) is not None
                ]
        dates.append(item)
    return dates


def _public_term(value):
    if not isinstance(value, dict):
        return {}
    item = {}
    for key, raw in value.items():
        if (
            key not in _TERM_FIELDS
            or not isinstance(raw, (str, int, float, bool, type(None)))
        ):
            continue
        if key == "id":
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key == "name":
            item[key] = canvas_plain_text(raw)
        else:
            item[key] = _plain_scalar(raw)
    return item


def _public_instructors(value):
    if not isinstance(value, list):
        return []
    instructors = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = {}
        for key, nested in raw.items():
            if (
                key not in _INSTRUCTOR_FIELDS
                or not isinstance(nested, (str, int, float, bool, type(None)))
            ):
                continue
            if key in _INSTRUCTOR_TEXT_FIELDS:
                item[key] = canvas_plain_text(nested)
            elif key.endswith("_url"):
                item[key] = _safe_public_url(nested)
            elif key == "id":
                identifier = _public_identifier(nested)
                if identifier is not None:
                    item[key] = identifier
            else:
                item[key] = _plain_scalar(nested)
        instructors.append(item)
    return instructors


def _public_course_fields(value):
    item = {}
    for key, raw in value.items():
        if key in {"term", "instructors", "assignments", "objects"}:
            item[key] = raw
        elif key in {"canvas_id", "id", "stable_id"}:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key == "html_url":
            item[key] = _safe_public_url(raw)
        elif isinstance(raw, (str, int, float, bool, type(None))):
            item[key] = (
                canvas_plain_text(raw)
                if key in {"course_code", "name"}
                else _plain_scalar(raw)
            )
    if "term" in value:
        item["term"] = _public_term(value["term"])
    if "instructors" in value:
        item["instructors"] = _public_instructors(value["instructors"])
    return item


def _public_deadlines(value):
    deadlines = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if "url" in item:
            item["url"] = _safe_public_url(item["url"])
        for key in ("id", "stable_id", "course_id"):
            if key in item:
                identifier = _public_identifier(item[key])
                if identifier is None:
                    item.pop(key)
                else:
                    item[key] = identifier
        for key in ("item", "course", "domain"):
            if key in item:
                item[key] = canvas_plain_text(item[key])
        for key, nested in list(item.items()):
            if isinstance(nested, str) and key not in {"url", "item", "course", "domain"}:
                item[key] = canvas_plain_text(nested)
        deadlines.append(item)
    return deadlines


def _public_needs(value):
    needs = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        for key in ("label", "target"):
            if key in item:
                item[key] = canvas_plain_text(item[key])
        needs.append(item)
    return needs


def public_object(value):
    if not isinstance(value, dict):
        return value
    item = {}
    for key, raw in value.items():
        if key not in _OBJECT_FIELDS:
            continue
        if key in _OBJECT_ID_FIELDS:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key in _OBJECT_PROSE_FIELDS:
            item[key] = canvas_prose_text(raw)
        elif key in _OBJECT_TEXT_FIELDS:
            item[key] = canvas_plain_text(raw)
        elif key in _OBJECT_URL_FIELDS:
            item[key] = _safe_public_url(raw)
        elif key in _NESTED_FIELDS and isinstance(raw, dict):
            nested_item = {}
            for nested_key, nested_value in raw.items():
                if (
                    nested_key not in _NESTED_FIELDS[key]
                    or not isinstance(
                        nested_value, (str, int, float, bool, type(None))
                    )
                ):
                    continue
                if nested_key.endswith("_url"):
                    nested_item[nested_key] = _safe_public_url(nested_value)
                elif nested_key in {"display_name"}:
                    nested_item[nested_key] = canvas_plain_text(nested_value)
                elif nested_key == "id":
                    identifier = _public_identifier(nested_value)
                    if identifier is not None:
                        nested_item[nested_key] = identifier
                else:
                    nested_item[nested_key] = _plain_scalar(nested_value)
            item[key] = nested_item
        elif key == "attachments" and isinstance(raw, list):
            item[key] = [
                _public_attachment(child)
                for child in raw
                if isinstance(child, dict)
            ]
        elif isinstance(raw, (str, int, float, bool, type(None))):
            item[key] = _plain_scalar(raw)
        elif isinstance(raw, list) and all(
            isinstance(child, (str, int, float, bool, type(None)))
            for child in raw
        ):
            if key == "prerequisite_module_ids":
                item[key] = [
                    identifier
                    for child in raw
                    if (identifier := _public_identifier(child)) is not None
                ]
            else:
                item[key] = [_plain_scalar(child) for child in raw]
    return item


def public_connection(con) -> dict:
    state = canvas_store.connection_state(con)
    latest = state.get("latest_run") or {}
    active = state.get("active_request") or {}
    request_id = _public_identifier(active.get("request_id"))
    return {
        "state": _plain_scalar(state["state"]),
        "last_success": _plain_scalar(state["last_success"]),
        "last_attempt": _plain_scalar(
            latest.get("finished_at") or latest.get("started_at")
        ),
        "error": _plain_scalar(latest.get("error", "")),
        "changed_count": latest.get("changed_count", 0),
        "failed_since_success": state.get("failed_since_success", 0),
        "request_id": request_id,
        "request_status": _plain_scalar(active.get("status")),
    }


def public_overview(con, deadlines) -> dict:
    overview = canvas_store.overview(con)
    overview["connection"] = public_connection(con)
    overview["courses"] = [
        _public_course_fields(item) for item in overview["courses"]
    ]
    overview["assignments"] = [
        public_assignment(item) for item in overview["assignments"]
    ]
    overview["groups"] = [public_object(item) for item in overview["groups"]]
    overview["deadlines"] = _public_deadlines(deadlines)
    return overview


def public_course(course_id, con) -> dict | None:
    course = canvas_store.course_view(course_id, con)
    if course is None:
        return None
    course = _public_course_fields(course)
    course["assignments"] = [
        public_assignment(item) for item in course["assignments"]
    ]
    course["objects"] = [public_object(item) for item in course["objects"]]
    row = con.execute(
        """
        SELECT * FROM syllabus_snapshots
        WHERE course_id = ?
        ORDER BY captured_at DESC, rowid DESC LIMIT 1
        """,
        (course_id,),
    ).fetchone()
    course["syllabus"] = None
    if row is not None:
        linked = [
            public_source_descriptor(item)
            for item in json.loads(row["linked_files_json"])
            if isinstance(item, dict)
        ]
        course["syllabus"] = {
            "source_hash": _plain_scalar(row["source_hash"]),
            "captured_at": _plain_scalar(row["captured_at"]),
            "summary": canvas_prose_text(row["summary"]),
            "summary_model": _plain_scalar(row["summary_model"]),
            "summary_at": _plain_scalar(row["summary_at"]),
            "source_url": (
                "/api/academics/source?path="
                + quote(row["html_path"], safe="")
                if row["html_path"] else None
            ),
            "linked_files": linked,
        }
    return course


_SOURCE_DESCRIPTOR_FIELDS = {
    "kind", "source_id", "course_id", "run_id", "file_id", "status", "error",
    "display_name", "content_type", "size", "source_hash", "url",
}


def public_source_descriptor(value) -> dict:
    item = {}
    for key, raw in value.items():
        if (
            key not in _SOURCE_DESCRIPTOR_FIELDS
            or not isinstance(raw, (str, int, float, bool, type(None)))
        ):
            continue
        if key in {"source_id", "course_id", "run_id", "file_id"}:
            identifier = _public_identifier(raw)
            if identifier is not None:
                item[key] = identifier
        elif key == "url":
            item[key] = _safe_public_url(raw)
        elif key == "display_name":
            item[key] = canvas_plain_text(raw)
        elif key == "error":
            item[key] = canvas_prose_text(raw)
        else:
            item[key] = _plain_scalar(raw)
    path = value.get("path")
    if isinstance(path, str) and path:
        item["source_url"] = (
            "/api/academics/source?path=" + quote(path, safe="")
        )
    return item


def urgent_counts(con) -> dict:
    deadlines = canvas_store.canvas_deadlines(con)
    return {
        "due_soon": sum(bool(item["due_soon"]) for item in deadlines),
        "overdue": sum(bool(item["overdue"]) for item in deadlines),
        "missing": con.execute(
            """
            SELECT COUNT(*) FROM assignments a JOIN courses c
              ON c.canvas_id = a.course_id
            WHERE a.removed_at IS NULL AND c.removed_at IS NULL AND a.missing = 1
            """
        ).fetchone()[0],
    }


def _required_source_fields(data):
    fields = (
        "run_id", "course_id", "source_id", "kind", "display_name",
        "content_type", "bytes_base64",
    )
    for field in fields:
        if not isinstance(data.get(field), str):
            raise RequestError(400, "invalid source payload")
        if field != "bytes_base64" and not data[field]:
            raise RequestError(400, "invalid source payload")
        if len(data[field]) > (
            MAX_SOURCE_BYTES if field == "bytes_base64" else 2048
        ):
            raise RequestError(400, "invalid source payload")


def store_source(data, source_root) -> dict:
    """Atomically persist one idempotent source receipt under an opaque path."""
    _required_source_fields(data)
    try:
        content = base64.b64decode(data["bytes_base64"], validate=True)
    except (binascii.Error, ValueError):
        raise RequestError(400, "invalid source payload")
    if len(content) > MAX_SOURCE_BYTES:
        raise RequestError(413, "source too large")

    run_key = hashlib.sha256(data["run_id"].encode()).hexdigest()
    source_key = hashlib.sha256(data["source_id"].encode()).hexdigest()
    relative = Path("runs") / run_key / source_key
    root = Path(source_root).resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise RequestError(400, "invalid source path")
    digest = hashlib.sha256(content).hexdigest()
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SourceConflict()
        return {"path": relative.as_posix(), "source_hash": digest}

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=".canvas-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"path": relative.as_posix(), "source_hash": digest}

# ---- ingestion: log notes and freeform updates get folded into the records
# they touch by a headless claude run (Sonnet, per OS.md model policy).
# Fire-and-forget; on any failure the entry stays in episodic as
# ingest-pending so the next os-reflect folds it by hand. ----
CLAUDE = shutil.which("claude")
INGEST_RULES = (
    "Work only inside this directory (the OS). Read OS.md first and follow the record format. "
    "Fold the information into prose bodies (What it is / Why it matters / Next step / Blocked on) "
    "and frontmatter (status, due, priority, updated) where it clearly applies; flag contradictions "
    "rather than silently resolving them. Also check the newest briefings/*.md: if the update resolves "
    "or contradicts a line there (e.g. a 'Needs you today' bullet now done), patch that line minimally "
    "- remove or correct it, touch nothing else in the briefing. Keep existing ## Log lines untouched. When done, run "
    "`python3 scripts/oslib.py log ingested \"<one line: what changed>\"` — never open episodic.md to "
    "append — then `python3 scripts/build_cache.py`. Do not git commit — the daily reflect commits.")


INGESTS = {}  # job id → {"origin", "done", "ok"} — in-memory only; episodic is the durable record
# ponytail: one lock serializes headless runs (two agents editing records at once
# would conflict); not FIFO-fair, fine at a-few-a-day volume
INGEST_LOCK = threading.Lock()


def spawn_ingest(prompt, origin):
    """Run a headless fold-in; returns a job id the dashboard can poll so the
    page refreshes the moment the records actually changed."""
    jid = os.urandom(6).hex()
    INGESTS[jid] = {"origin": origin, "done": False, "ok": False}
    if not CLAUDE:
        oslib.episodic("ingest-pending", f"claude CLI not found — fold manually: {origin}")
        INGESTS[jid]["done"] = True
        return jid

    def run():
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        ok = False
        try:
            with INGEST_LOCK:
                p = subprocess.run(
                    [CLAUDE, "-p", prompt, "--model", "sonnet", "--permission-mode", "acceptEdits",
                     "--allowedTools", "Read,Edit,Write,Grep,Glob,Bash(python3 scripts/build_cache.py:*),"
                                       "Bash(python3 scripts/oslib.py:*)"],
                    cwd=str(OS), env=env, capture_output=True, timeout=600)
            ok = p.returncode == 0
            if not ok:
                oslib.episodic("ingest-pending", f"ingest exited {p.returncode} — fold manually: {origin}")
        except Exception as e:
            oslib.episodic("ingest-pending", f"ingest failed ({e.__class__.__name__}) — fold manually: {origin}")
        INGESTS[jid].update(done=True, ok=ok)

    threading.Thread(target=run, daemon=True).start()
    return jid


def ingest_note(col, fname, line):
    d, _ = COLLECTIONS[col]
    return spawn_ingest(
        f"Aayush just logged this note on {d}/{fname} via the dashboard (it is already appended to that "
        f"record's ## Log): «{line}». He uses log notes to feed the OS details it doesn't know yet — "
        f"update that record so its body and frontmatter reflect the note, and update any other record "
        f"the note clearly names. {INGEST_RULES}",
        f"note on {col}/{fname}: {line[:80]}")


def ingest_update(text):
    return spawn_ingest(
        f"Aayush posted this freeform update on his dashboard (already recorded in memory/episodic.md): "
        f"«{text}». Find the records it touches — grep across the collections, or use "
        f"`python3 scripts/build_cache.py --search '<terms>'` — and update them. An update may also close "
        f"or add a line in uni/deadlines.md. If it maps to no record, the episodic entry is enough; do "
        f"nothing further. {INGEST_RULES}",
        f"update: {text[:80]}")


def state():
    # parse every record exactly once per request, then share the result
    cols = {name: oslib.records(name) for name in COLLECTIONS}
    dls = oslib.deadlines(cols)
    return {
        "collections": cols,
        "enums": ENUMS,
        "types": {name: COLLECTIONS[name][1] for name in COLLECTIONS},
        "deadlines": dls,
        "needs": oslib.needs_today(cols, dls),
        "feed": oslib.memory_feed(),
        "briefing": oslib.latest_briefing(),
        "areas": oslib.areas(),
        "questions": oslib.questions(),
        "stats": oslib.stats(cols),
        "jobs": jobfeed.view(),
        "prep": oslib.prep_plan(),
    }


def track_job(jid: str) -> dict:
    """Promote a discovered posting into a real pipeline record — the one
    place the disposable feed crosses into canonical prose."""
    j = jobfeed.get(jid)
    if not j:
        return {"ok": False}
    title = f"{j['company']} — {j['title']} ({j.get('term', '')})".replace(" ()", "")
    desc = j.get("desc") or f"{j['title']} at {j['company']}."
    body = (f"**What it is:** {desc.rstrip('.')}."
            f"{' Locations: ' + ', '.join(j['locations']) + '.' if j.get('locations') else ''}\n\n"
            f"**Why it matters:** match {j['score']}/100 — {j.get('why', '')}.\n\n"
            f"**Apply:** [{j['url']}]({j['url']})\n\n"
            f"**Posted:** {j.get('posted') or 'not stated by the source'} · "
            f"first seen {j.get('first_seen', '')} · source {j.get('source', '')}\n\n"
            f"**Next step:** confirm the real close date and set `due:`, set the `cpt:` flag, "
            f"then decide priority.")
    fname = oslib.create_record("pipeline", title, area="career",
                                priority="1" if j["score"] >= 85 else "2", body=body)
    if fname:
        jobfeed.set_status(jid, "tracked", record=fname)
    return {"ok": bool(fname), "file": fname}


def search(q):
    db = OS / "memory" / "cache" / "os.sqlite"
    if not db.exists():
        subprocess.run([sys.executable, str(OS / "scripts" / "build_cache.py")])
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT path, section, snippet(chunks,2,'<b>','</b>','…',16) FROM chunks "
            "WHERE chunks MATCH ? ORDER BY rank LIMIT 10", (q,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return [{"path": p, "section": s, "snippet": sn} for p, s, sn in rows]


class H(BaseHTTPRequestHandler):
    canvas_db_path = canvas_store.DB_PATH
    canvas_source_root = SOURCE_ROOT
    canvas_notifier = staticmethod(canvas_sync.send_login_notification)
    deadline_loader = staticmethod(oslib.deadlines)
    ai_runner = None  # tests inject; None means the real claude CLI

    def _send(self, obj, code=200, ctype="application/json", headers=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json_body(self, limit, require_json=False):
        if require_json:
            content_type = self.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "application/json":
                raise RequestError(415, "application/json required")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise RequestError(400, "bad request body")
        if length < 0:
            raise RequestError(400, "bad request body")
        if length > limit:
            raise RequestError(413, "request body too large")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RequestError(400, "bad request body")
        if not isinstance(data, dict):
            raise RequestError(400, "bad request body")
        return data

    def _bridge_allowed(self) -> bool:
        try:
            loopback = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            loopback = False
        origins = self.headers.get_all("Origin", [])
        valid_origin = not origins
        if len(origins) == 1:
            try:
                origin = origins[0]
                parsed = urlparse(origin)
                valid_origin = (
                    parsed.scheme == "chrome-extension"
                    and bool(_EXTENSION_ID.fullmatch(parsed.hostname or ""))
                    and parsed.netloc == parsed.hostname
                    and parsed.username is None
                    and parsed.password is None
                    and parsed.path in {"", "/"}
                    and not parsed.params
                    and not parsed.query
                    and not parsed.fragment
                )
            except ValueError:
                valid_origin = False
        elif len(origins) > 1:
            valid_origin = False
        return (
            loopback
            and self.headers.get("X-Pierce-Canvas-Bridge") == "1"
            and valid_origin
        )

    def _canvas_db(self):
        return canvas_store.open_db(self.canvas_db_path)

    def _id(self, query):
        value = parse_qs(query, keep_blank_values=True).get("id", [""])[0]
        if not _ID.fullmatch(value):
            raise RequestError(400, "invalid id")
        return value

    def _download_source(self, query):
        value = parse_qs(query, keep_blank_values=True).get("path", [""])[0]
        if not value:
            raise RequestError(400, "invalid source path")
        root = Path(self.canvas_source_root).resolve()
        target = (root / value).resolve()
        if target == root or root not in target.parents:
            raise RequestError(400, "invalid source path")
        if not target.is_file():
            raise RequestError(404, "not found")
        self._send(
            target.read_bytes(),
            ctype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{target.name}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    def _academics_state(self):
        con = self._canvas_db()
        try:
            return {
                "connection": public_connection(con),
                "urgent": urgent_counts(con),
            }
        finally:
            con.close()

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/academics/overview":
                con = self._canvas_db()
                try:
                    return self._send(
                        public_overview(con, self.deadline_loader())
                    )
                finally:
                    con.close()
            if u.path == "/api/academics/course":
                course_id = self._id(u.query)
                con = self._canvas_db()
                try:
                    course = public_course(course_id, con)
                    return self._send(
                        course if course is not None else {"err": "not found"},
                        200 if course is not None else 404,
                    )
                finally:
                    con.close()
            if u.path == "/api/academics/assignment":
                assignment_id = self._id(u.query)
                con = self._canvas_db()
                try:
                    assignment = canvas_store.assignment_view(
                        assignment_id, con
                    )
                    return self._send(
                        public_assignment(assignment)
                        if assignment is not None else {"err": "not found"},
                        200 if assignment is not None else 404,
                    )
                finally:
                    con.close()
            if u.path == "/api/academics/refresh-request":
                if not self._bridge_allowed():
                    raise RequestError(403, "bridge access denied")
                con = self._canvas_db()
                try:
                    claimed = canvas_store.claim_refresh(con)
                    return self._send(claimed or b"", 200 if claimed else 204)
                finally:
                    con.close()
            if u.path == "/api/academics/ai":
                job_id = self._id(u.query)
                con = self._canvas_db()
                try:
                    job = canvas_ai.get_job(job_id, con)
                    return self._send(
                        job if job is not None else {"err": "not found"},
                        200 if job is not None else 404,
                    )
                finally:
                    con.close()
            if u.path == "/api/academics/source":
                return self._download_source(u.query)
            # no-cache: browsers heuristically cache responses that carry no
            # cache headers, which serves a stale app after every code change
            if u.path in ("/", "/index.html"):
                return self._send(
                    (OS / "dashboard" / "app" / "index.html").read_bytes(),
                    ctype="text/html", headers={"Cache-Control": "no-cache"},
                )
            if u.path == "/academics.js":
                return self._send(
                    (OS / "dashboard" / "app" / "academics.js").read_bytes(),
                    ctype="text/javascript",
                    headers={"Cache-Control": "no-cache"},
                )
            if u.path == "/academics.css":
                return self._send(
                    (OS / "dashboard" / "app" / "academics.css").read_bytes(),
                    ctype="text/css", headers={"Cache-Control": "no-cache"},
                )
            if u.path == "/api/state":
                payload = state()
                payload["deadlines"] = _public_deadlines(payload["deadlines"])
                payload["needs"] = _public_needs(payload["needs"])
                payload["academics"] = self._academics_state()
                return self._send(payload)
            if u.path == "/api/search":
                return self._send(
                    search(parse_qs(u.query).get("q", [""])[0])
                )
            if u.path == "/api/ingest":
                j = INGESTS.get(parse_qs(u.query).get("id", [""])[0])
                return self._send(j if j else {"err": "unknown"}, 200 if j else 404)
            if u.path.startswith("/fonts/"):
                fonts = (OS / "dashboard" / "app" / "fonts").resolve()
                f = (fonts / u.path[len("/fonts/"):]).resolve()
                mime = {
                    ".woff2": "font/woff2", ".woff": "font/woff",
                    ".ttf": "font/ttf",
                }.get(f.suffix)
                if f.is_file() and mime and f.is_relative_to(fonts):
                    return self._send(f.read_bytes(), ctype=mime)
            return self._send({"err": "not found"}, 404)
        except RequestError as error:
            return self._send({"err": error.message}, error.code)

    def _academics_post(self, path):
        if path not in {
            "/api/academics/refresh", "/api/academics/ingest",
            "/api/academics/source", "/api/academics/note",
            "/api/academics/ai",
        }:
            return self._send({"err": "not found"}, 404)
        bridge_only = path in {
            "/api/academics/ingest", "/api/academics/source",
        }
        if bridge_only and not self._bridge_allowed():
            raise RequestError(403, "bridge access denied")
        limit = (
            MAX_SNAPSHOT_BYTES if path == "/api/academics/ingest"
            else MAX_SOURCE_BYTES if path == "/api/academics/source"
            else MAX_LOCAL_JSON_BYTES
        )
        data = self._json_body(limit, require_json=True)

        if path == "/api/academics/refresh":
            trigger = data.get("trigger", "manual")
            if trigger not in canvas_sync.TRIGGERS:
                raise RequestError(400, "invalid trigger")
            con = self._canvas_db()
            try:
                queued = canvas_store.request_refresh(trigger, con)
                return self._send(queued, 202)
            finally:
                con.close()

        if path == "/api/academics/source":
            try:
                receipt = store_source(data, self.canvas_source_root)
            except SourceConflict:
                return self._send({"err": "source content conflict"}, 409)
            return self._send(receipt)

        if path == "/api/academics/ai":
            action = data.get("action")
            scope_type = data.get("scope_type")
            scope_id = data.get("scope_id") or (
                "overview" if scope_type == "overview" else ""
            )
            question = data.get("question", "")
            if (
                action not in canvas_ai.ACTIONS
                or scope_type not in {"assignment", "course", "overview"}
                or not isinstance(question, str)
                or len(question) > 2000
                or not isinstance(scope_id, str)
                or not _ID.fullmatch(scope_id)
            ):
                raise RequestError(400, "invalid ai request")
            con = self._canvas_db()
            try:
                try:
                    job = canvas_ai.prepare_job(
                        action, scope_type, scope_id, question, con
                    )
                except ValueError as error:
                    raise RequestError(400, str(error))
            finally:
                con.close()
            if job["status"] == "queued":
                threading.Thread(
                    target=canvas_ai.run_job_at,
                    args=(job["job_id"], self.canvas_db_path),
                    kwargs={"runner": self.ai_runner},
                    daemon=True,
                ).start()
            return self._send(job, 200 if job["status"] == "complete" else 202)

        con = self._canvas_db()
        try:
            if path == "/api/academics/note":
                assignment_id = data.get("assignment_id", data.get("id"))
                note = data.get("note")
                if (
                    not isinstance(assignment_id, str)
                    or not _ID.fullmatch(assignment_id)
                    or not isinstance(note, str)
                ):
                    raise RequestError(400, "invalid note")
                ok = canvas_store.save_note(assignment_id, note, con)
                return self._send(
                    {"ok": ok} if ok else {"err": "not found"},
                    200 if ok else 404,
                )

            existing = None
            if isinstance(data.get("run_id"), str):
                existing = con.execute(
                    "SELECT 1 FROM sync_runs WHERE run_id = ?",
                    (data["run_id"],),
                ).fetchone()
            if existing is None:
                try:
                    clean = canvas_store._sanitize_payload(data)
                    canvas_store._validate_snapshot(clean, con)
                    canvas_store._validate_claim(clean, con)
                except Exception:
                    canvas_store.ingest_snapshot(
                        data, con, source_root=self.canvas_source_root
                    )
                    raise RequestError(400, "invalid Canvas snapshot")
            result = canvas_store.ingest_snapshot(
                data, con, source_root=self.canvas_source_root
            )
            canvas_sync.handle_login_notification(
                con, result["run_id"], notifier=self.canvas_notifier
            )
            return self._send(result)
        finally:
            con.close()

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/academics/"):
                return self._academics_post(u.path)
            data = self._json_body(MAX_LOCAL_JSON_BYTES)
        except RequestError as error:
            return self._send({"err": error.message}, error.code)
        if u.path == "/api/status":
            self._send({"ok": oslib.set_status(data.get("col", ""), data.get("file", ""), data.get("status", ""))})
        elif u.path == "/api/note":
            ok = oslib.add_note(data.get("col", ""), data.get("file", ""), data.get("line", ""))
            jid = ingest_note(data["col"], data["file"], data["line"]) if ok else None
            self._send({"ok": ok, "ingest": jid})
        elif u.path == "/api/update":
            text = (data.get("text") or "").strip()
            jid = None
            if text:
                oslib.episodic("update", text)
                jid = ingest_update(text)
            self._send({"ok": bool(text), "ingest": jid})
        elif u.path == "/api/reorder":
            self._send({"ok": oslib.set_order(data.get("key", ""), data.get("ids", []))})
        elif u.path == "/api/deadline":
            self._send({"ok": oslib.set_deadline(data.get("date", ""), data.get("item", ""), data.get("status", ""))})
        elif u.path == "/api/log":
            oslib.episodic(data.get("type", "note"), data.get("line", ""))
            self._send({"ok": True})
        elif u.path == "/api/create":
            fname = oslib.create_record(data.get("col", ""), data.get("title", ""), data.get("area", ""),
                                        data.get("priority", "2"), data.get("due", ""), data.get("body", ""))
            self._send({"ok": bool(fname), "file": fname})
        elif u.path == "/api/area":
            if data.get("hide") is not None:
                self._send({"ok": oslib.set_area_hidden(
                    data.get("id", ""), bool(data["hide"])
                )})
            else:
                self._send({"ok": oslib.add_area(data.get("id", ""), data.get("label", ""))})
        elif u.path == "/api/answer":
            self._send({"ok": oslib.answer_question(data.get("id", ""), data.get("answer", ""))})
        elif u.path == "/api/prep":
            if data.get("day"):
                self._send({"ok": oslib.log_prep_day(str(data["day"]), data.get("minutes", 30))})
            else:
                self._send({"ok": oslib.set_prep(data.get("week", ""), data.get("status", ""))})
        elif u.path == "/api/deadline_add":
            self._send({"ok": oslib.add_deadline(data.get("date", ""), data.get("domain", ""), data.get("item", ""))})
        elif u.path == "/api/job":
            if data.get("action") == "track":
                self._send(track_job(data.get("id", "")))
            else:
                self._send({"ok": jobfeed.set_status(data.get("id", ""), data.get("status", ""))})
        elif u.path == "/api/follow":
            name = (data.get("name") or "").strip()
            ok = jobfeed.unfollow(name) if data.get("remove") else jobfeed.follow(name, data.get("url", ""))
            self._send({"ok": ok})
        elif u.path == "/api/jobscan":
            # blocking on purpose: two HTTP GETs, a few seconds, and the caller
            # is a button that says "scanning…" until it returns
            s = jobfeed.scan()
            oslib.episodic("scanned", f"jobs — {s['open']} open, +{s['added']} new"
                                      + (f", {len(s['errors'])} source failures" if s["errors"] else ""))
            self._send(s)
        else:
            self._send({"err": "not found"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # single-threaded on purpose: it serializes record writes with no locking.
    # PORT env overrides for preview tooling; Aayush's default stays 8877.
    port = int(os.environ.get("PORT", "8877"))
    print(f"Agentic OS dashboard → http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
