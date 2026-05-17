#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import random
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from urllib.parse import urlparse


class LocalSiteHandler(SimpleHTTPRequestHandler):
    """Serve local static files without aggressive browser caching."""

    annotations_lock = Lock()
    interests_lock = Lock()
    easter_egg_extensions = {".gif", ".jpg", ".jpeg", ".png", ".webp"}

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/annotations":
            self.send_json(self.read_annotations())
            return
        if path == "/api/interests":
            self.send_json(self.read_interests())
            return
        if path == "/api/easter-egg":
            self.send_random_easter_egg()
            return

        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/annotations/toggle":
            self.handle_toggle_annotation()
            return
        if path == "/api/interests":
            self.handle_update_interests()
            return

        self.send_json({"error": "Not found"}, status=404)

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}

        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_empty_response(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_random_easter_egg(self) -> None:
        image_dir = Path("images/easter-egg")
        if not image_dir.is_dir():
            self.send_empty_response(404)
            return

        image_paths = [
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in self.easter_egg_extensions
        ]
        if not image_paths:
            self.send_empty_response(404)
            return

        image_path = random.choice(image_paths)
        try:
            body = image_path.read_bytes()
        except OSError:
            self.send_empty_response(404)
            return

        content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def annotations_path(self) -> Path:
        return Path("data/annotations.json")

    def interests_path(self) -> Path:
        return Path("data/interests.json")

    def normalize_interests(self, value: object) -> dict:
        if not isinstance(value, dict):
            value = {}

        def normalize_list(items: object) -> list[str]:
            if not isinstance(items, list):
                return []

            result: list[str] = []
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, str):
                    continue
                normalized = item.strip()
                if not normalized:
                    continue
                key = normalized.casefold()
                if key in seen:
                    continue
                seen.add(key)
                result.append(normalized)
            return result

        return {
            "keywords": normalize_list(value.get("keywords")),
            "authors": normalize_list(value.get("authors")),
        }

    def read_interests(self) -> dict:
        path = self.interests_path()
        if not path.exists():
            return {"keywords": [], "authors": []}

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"keywords": [], "authors": []}

        return self.normalize_interests(data)

    def write_interests(self, interests: dict) -> None:
        path = self.interests_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            json.dump(self.normalize_interests(interests), tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp_path = Path(tmp.name)

        tmp_path.replace(path)

    def read_annotations(self) -> dict:
        path = self.annotations_path()
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    def write_annotations(self, annotations: dict) -> None:
        path = self.annotations_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            json.dump(annotations, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp_path = Path(tmp.name)

        tmp_path.replace(path)

    def handle_toggle_annotation(self) -> None:
        try:
            body = self.read_json_body()
            paper_id = str(body.get("paper_id", "")).strip()
            annotation_type = str(body.get("type", "")).strip()
            name = str(body.get("name", "user")).strip() or "user"
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "Invalid JSON body"}, status=400)
            return

        if not paper_id:
            self.send_json({"error": "paper_id is required"}, status=400)
            return
        if annotation_type not in {"read", "favorite"}:
            self.send_json({"error": "type must be read or favorite"}, status=400)
            return

        with self.annotations_lock:
            annotations = self.read_annotations()
            paper_annotations = annotations.setdefault(paper_id, {})
            names = paper_annotations.setdefault(annotation_type, [])

            if not isinstance(names, list):
                names = []

            if name in names:
                names = [existing for existing in names if existing != name]
                marked = False
            else:
                names.append(name)
                names = sorted(set(names), key=str.casefold)
                marked = True

            paper_annotations[annotation_type] = names
            paper_annotations.setdefault("read", [])
            paper_annotations.setdefault("favorite", [])
            annotations[paper_id] = paper_annotations
            self.write_annotations(annotations)

        self.send_json(
            {
                "paper_id": paper_id,
                "type": annotation_type,
                "name": name,
                "marked": marked,
                "annotations": annotations,
            }
        )

    def handle_update_interests(self) -> None:
        try:
            body = self.read_json_body()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "Invalid JSON body"}, status=400)
            return

        interests = self.normalize_interests(body)
        with self.interests_lock:
            self.write_interests(interests)

        self.send_json(interests)


def discover_lan_ips() -> list[str]:
    ips: set[str] = set()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ips.add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            if family == socket.AF_INET:
                ip = sockaddr[0]
                if not ip.startswith("127."):
                    ips.add(ip)
    except socket.gaierror:
        pass

    return sorted(ips)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the local arXiv site on your LAN.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to. Default: 8000")
    parser.add_argument(
        "--directory",
        default=".",
        help="Directory to serve. Default: current project root",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.exists():
        raise SystemExit(f"Directory does not exist: {directory}")

    os.chdir(directory)
    server = ThreadingHTTPServer((args.host, args.port), LocalSiteHandler)

    print(f"Serving {directory}")
    print(f"Local URL: http://127.0.0.1:{args.port}")
    for ip in discover_lan_ips():
        print(f"LAN URL:   http://{ip}:{args.port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
