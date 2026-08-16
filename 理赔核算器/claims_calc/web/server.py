# -*- coding: utf-8 -*-
"""标准库 WSGI 服务：静态前端 + 内部 JSON。支持 BASE_PATH 子路径挂载。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from typing import Any, Callable, Dict, List
from wsgiref.simple_server import make_server

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from claims_calc import cases as case_io  # noqa: E402
from claims_calc import policies as pol  # noqa: E402
from claims_calc.cli import render_markdown  # noqa: E402
from claims_calc.engine import build_demo_case, compute, get_catalog  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _normalize_base_path(raw: str) -> str:
    if not raw or raw == "/":
        return ""
    path = raw.strip()
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def _read_body(environ: Dict[str, Any]) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    if length <= 0:
        return b""
    return environ["wsgi.input"].read(length)


def _json_response(start_response: Callable, status: str, payload: Any) -> List[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(status, headers)
    return [body]


def _text_response(
    start_response: Callable,
    status: str,
    text: str,
    content_type: str = "text/plain; charset=utf-8",
) -> List[bytes]:
    body = text.encode("utf-8")
    start_response(
        status,
        [("Content-Type", content_type), ("Content-Length", str(len(body)))],
    )
    return [body]


def _file_response(start_response: Callable, path: str) -> List[bytes]:
    with open(path, "rb") as f:
        body = f.read()
    ctype, _ = mimetypes.guess_type(path)
    if not ctype:
        ctype = "application/octet-stream"
    if ctype.startswith("text/") or ctype in (
        "application/javascript",
        "application/json",
    ):
        ctype = ctype + "; charset=utf-8"
    start_response(
        "200 OK",
        [
            ("Content-Type", ctype),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-cache"),
        ],
    )
    return [body]


def make_app(base_path: str = "") -> Callable:
    base = _normalize_base_path(base_path)

    def application(environ: Dict[str, Any], start_response: Callable):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO") or "/"

        if base:
            if path == base or path.startswith(base + "/"):
                path = path[len(base) :] or "/"
            else:
                return _text_response(
                    start_response,
                    "404 Not Found",
                    "Not Found (expect base path %s)" % base,
                )

        if path == "/api/catalog" and method == "GET":
            return _json_response(start_response, "200 OK", get_catalog())

        if path == "/api/demo" and method == "GET":
            return _json_response(start_response, "200 OK", build_demo_case())

        if path == "/api/compute" and method == "POST":
            raw = _read_body(environ)
            try:
                if not raw.strip():
                    case = build_demo_case()
                else:
                    case = json.loads(raw.decode("utf-8"))
                if not isinstance(case, dict):
                    return _json_response(
                        start_response,
                        "400 Bad Request",
                        {"error": "请求体须为 JSON 对象", "warnings": []},
                    )
                result = compute(case)
                return _json_response(start_response, "200 OK", result)
            except Exception as exc:
                return _json_response(
                    start_response,
                    "200 OK",
                    {
                        "error": "核算时遇到问题，已返回空结果：%s" % exc,
                        "items": [],
                        "categories": [],
                        "summary": {
                            "covered_total": 0,
                            "sla_deduction": 0,
                            "net_assessed_loss": 0,
                            "indirect_subtotal": 0,
                            "direct_subtotal": 0,
                            "fact_total": 0,
                        },
                        "warnings": ["服务端兜底：%s" % exc],
                        "labels": {},
                    },
                )

        # ---- 保单库 -------------------------------------------------
        if path == "/api/policies" and method == "GET":
            return _json_response(
                start_response, "200 OK", {"policies": pol.list_policies()}
            )

        if path.startswith("/api/policies/") and method == "GET":
            pid = path[len("/api/policies/") :]
            policy = pol.get_policy(pid)
            if not policy:
                return _json_response(
                    start_response, "404 Not Found", {"error": "未找到保单 %s" % pid}
                )
            cov = pol.build_coverage_map(policy, get_catalog())
            payload = dict(policy)
            payload["coverage_map"] = cov
            payload["coverage_stats"] = pol.coverage_stats(cov)
            return _json_response(start_response, "200 OK", payload)

        # ---- 案例库 -------------------------------------------------
        if path == "/api/cases" and method == "GET":
            return _json_response(
                start_response, "200 OK", {"cases": case_io.list_cases()}
            )

        if path.startswith("/api/cases/"):
            name = path[len("/api/cases/") :]
            try:
                if method == "GET":
                    return _json_response(
                        start_response, "200 OK", case_io.load_case(name)
                    )
                if method == "POST" or method == "PUT":
                    raw = _read_body(environ)
                    body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
                    case = body.get("case") if isinstance(body, dict) else None
                    if case is None:
                        case = body
                    catalog = get_catalog()
                    if body.get("minimize"):
                        case = case_io.minimize(case, catalog, compute(case))
                    saved = case_io.save_case(name, case)
                    return _json_response(
                        start_response,
                        "200 OK",
                        {
                            "saved": os.path.basename(saved),
                            "issues": case_io.validate_case(case, catalog),
                        },
                    )
                if method == "DELETE":
                    return _json_response(
                        start_response, "200 OK", {"deleted": case_io.delete_case(name)}
                    )
            except FileNotFoundError as exc:
                return _json_response(
                    start_response, "404 Not Found", {"error": str(exc)}
                )
            except (ValueError, OSError) as exc:
                return _json_response(
                    start_response, "400 Bad Request", {"error": str(exc)}
                )

        if path == "/api/validate" and method == "POST":
            raw = _read_body(environ)
            try:
                case = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            except ValueError as exc:
                return _json_response(
                    start_response, "400 Bad Request", {"error": "JSON 解析失败：%s" % exc}
                )
            return _json_response(
                start_response,
                "200 OK",
                {"issues": case_io.validate_case(case, get_catalog())},
            )

        if path == "/api/export/markdown" and method == "POST":
            raw = _read_body(environ)
            try:
                case = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            except ValueError as exc:
                return _json_response(
                    start_response, "400 Bad Request", {"error": "JSON 解析失败：%s" % exc}
                )
            result = compute(case_io.strip_to_compute(case))
            return _json_response(
                start_response, "200 OK", {"markdown": render_markdown(case, result)}
            )

        if path == "/api/config" and method == "GET":
            return _json_response(
                start_response,
                "200 OK",
                {"base_path": base or "", "version": "0.3.0"},
            )

        if path in ("/", ""):
            return _file_response(start_response, os.path.join(STATIC_DIR, "index.html"))

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
        else:
            rel = path.lstrip("/")

        candidate = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not candidate.startswith(os.path.normpath(STATIC_DIR)):
            return _text_response(start_response, "403 Forbidden", "Forbidden")
        if os.path.isfile(candidate):
            return _file_response(start_response, candidate)

        return _text_response(start_response, "404 Not Found", "Not Found")

    return application


def main(argv: List[str] = None) -> None:
    parser = argparse.ArgumentParser(description="理赔核算器 Web 服务（可挂子路径）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="端口")
    parser.add_argument(
        "--base-path",
        default=os.environ.get("BASE_PATH", ""),
        help="子路径前缀，如 /claims-calc；也可用环境变量 BASE_PATH",
    )
    args = parser.parse_args(argv)

    base = _normalize_base_path(args.base_path)
    app = make_app(base)
    httpd = make_server(args.host, args.port, app)
    url_path = (base or "") + "/"
    print("理赔核算器已启动", flush=True)
    print("  本地访问: http://%s:%d%s" % (args.host, args.port, url_path), flush=True)
    if base:
        print(
            "  反代示例: location %s/ { proxy_pass http://%s:%d; }"
            % (base, args.host, args.port),
            flush=True,
        )
    print("  Ctrl+C 结束", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
