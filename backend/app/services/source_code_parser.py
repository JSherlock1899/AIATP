import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedEndpoint:
    """Represents a parsed API endpoint."""
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Dict] = None
    request_body: Optional[Dict] = None
    responses: List[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "method": self.method,
            "summary": self.summary,
            "description": self.description,
            "parameters": self.parameters or [],
            "request_body": self.request_body,
            "responses": self.responses or []
        }

    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access for backward compatibility."""
        return getattr(self, key)

    def keys(self):
        return ["path", "method", "summary", "description", "parameters", "request_body", "responses"]


class SpringBootRegexParser:
    """Parser for Spring Boot Java source code using regex."""

    # HTTP Method mapping
    METHOD_ANNOTATIONS = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
        "HeadMapping": "HEAD",
        "OptionsMapping": "OPTIONS",
        "RequestMapping": "GET"  # Default, may be overridden by method attribute
    }

    # Regex patterns
    CLASS_CONTROLLER_PATTERN = re.compile(
        r'@(?:Rest)?Controller\s*(?:\s*@\s*RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\'])',
        re.MULTILINE
    )

    # Pattern for method annotations: @GetMapping("/path") or @GetMapping(value="/path") or @GetMapping
    METHOD_PATTERN = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|HeadMapping|OptionsMapping|RequestMapping)'
        r'(?:\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']\s*\))?',
        re.MULTILINE
    )

    # Pattern to remove single-line comments to avoid matching annotations in comments
    COMMENT_LINE_PATTERN = re.compile(r'^\s*//.*$', re.MULTILINE)

    REQUEST_BODY_PATTERN = re.compile(r'@RequestBody')

    @staticmethod
    def validate_path(path: str) -> str:
        """Validate path doesn't contain traversal."""
        if ".." in path:
            raise ValueError("Path traversal not allowed")
        if not os.path.isabs(path):
            raise ValueError("Absolute path required")
        return path

    @staticmethod
    def scan_java_files(source_path: str, max_depth: int = 20) -> List[str]:
        """Recursively scan for .java files."""
        java_files = []
        source = Path(source_path)

        if not source.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        for root, dirs, files in os.walk(source):
            # Check depth
            depth = root[len(source_path):].count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue

            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))

        return java_files

    def parse_content(self, content: str) -> List[ParsedEndpoint]:
        """Parse Java source code content and extract endpoints."""
        endpoints = []

        # Remove single-line comments to avoid matching annotations in comments
        # This fixes Critical 1: regex matches annotations inside comments
        content_without_comments = self.COMMENT_LINE_PATTERN.sub('', content)

        # Find class-level @RequestMapping prefix
        class_match = self.CLASS_CONTROLLER_PATTERN.search(content_without_comments)
        class_path = class_match.group(1) if class_match else ""

        # If no @RestController or @Controller with @RequestMapping, skip
        if (not class_path and "@RestController" in content_without_comments) or "@Controller" in content_without_comments:
            # Check if there's a standalone @RequestMapping at class level
            class_request_mapping = re.search(
                r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
                content_without_comments
            )
            if class_request_mapping:
                class_path = class_request_mapping.group(1)

        # If still no class path, try to find package as fallback
        if not class_path:
            package_match = re.search(r'package\s+([\w.]+);', content_without_comments)
            if package_match:
                class_path = "/" + package_match.group(1).replace(".", "/")

        # Find all method-level annotations
        # First pass: collect all raw matches
        raw_matches = []
        for match in self.METHOD_PATTERN.finditer(content_without_comments):
            annotation_name = match.group(1)
            method_path = match.group(2) if match.group(2) else ""
            http_method = self.METHOD_ANNOTATIONS.get(annotation_name, "GET")

            # Skip @RequestMapping at class level (before any method definitions)
            if annotation_name == "RequestMapping":
                # Check if this @RequestMapping is at class level by seeing if it appears
                # before any public/private/protected method
                before_content = content_without_comments[:match.start()]
                last_modifier = re.search(r'\b(public|private|protected)\s+', before_content)
                if last_modifier is None:
                    # Class-level @RequestMapping, skip
                    continue

                # It's a method-level @RequestMapping, check for method attribute
                method_match = re.search(
                    r'method\s*=\s*HttpMethod\.(\w+)',
                    content_without_comments[match.start():match.start() + 200]
                )
                if method_match:
                    http_method = method_match.group(1)

            # Get method boundaries for deduplication
            method_start = match.start()
            method_end = self._find_method_end(content_without_comments, method_start)

            raw_matches.append({
                'annotation_name': annotation_name,
                'method_path': method_path,
                'http_method': http_method,
                'method_start': method_start,
                'method_end': method_end,
                'match': match
            })

        # Deduplicate: for each method block, if there are multiple annotations for the same
        # HTTP method (e.g., both @GetMapping and @GetMapping("/path")), only keep the one with path
        deduplicated = []
        for i, current in enumerate(raw_matches):
            has_long_form = any(
                other['http_method'] == current['http_method'] and
                other['method_path'] and  # has a path
                abs(other['method_start'] - current['method_start']) < 200  # same method block
                for other in raw_matches if other is not current
            )
            # Skip short form if there's also a long form for the same HTTP method
            if not current['method_path'] and has_long_form:
                continue
            deduplicated.append(current)

        # Second pass: create endpoints from deduplicated matches
        for match_data in deduplicated:
            annotation_name = match_data['annotation_name']
            method_path = match_data['method_path']
            http_method = match_data['http_method']
            method_start = match_data['method_start']
            method_end = match_data['method_end']
            match = match_data['match']

            # Combine class path and method path
            full_path = self._combine_paths(class_path, method_path)

            # Extract parameters
            method_content = content_without_comments[method_start:method_end]

            parameters = self._extract_parameters(method_content)
            has_request_body = self.REQUEST_BODY_PATTERN.search(method_content) is not None

            endpoint = ParsedEndpoint(
                path=full_path,
                method=http_method,
                parameters=parameters,
                request_body={"required": False} if has_request_body else None
            )
            endpoints.append(endpoint)

        return endpoints

    def _combine_paths(self, class_path: str, method_path: str) -> str:
        """Combine class and method paths."""
        if not class_path:
            return method_path
        if not method_path:
            return class_path

        # Ensure single slash between paths
        class_path = class_path.rstrip("/")
        if method_path.startswith("/"):
            return class_path + method_path
        return f"{class_path}/{method_path}"

    def _extract_parameters(self, method_content: str) -> List[Dict]:
        """Extract @PathVariable and @RequestParam parameters."""
        parameters = []

        # Find all @PathVariable annotations and extract parameter names
        # Pattern: @PathVariable or @PathVariable(...) followed by type and name
        path_var_pattern = re.compile(
            r'@PathVariable'
            r'(?:\s*\([^)]*\))?'  # Optional arguments like (value="id") or (required=false)
            r'\s+(\w+)\s+(\w+)',   # Type and name: Long id
            re.MULTILINE
        )
        for match in path_var_pattern.finditer(method_content):
            param_name = match.group(2)  # Second group is the parameter name
            parameters.append({
                "name": param_name,
                "location": "path",
                "required": True
            })

        # Also check for @PathVariable with explicit name only: @PathVariable("id")
        path_var_explicit = re.compile(
            r'@PathVariable\s*\(\s*(?:value\s*=\s*)?["\'](\w+)["\']',
            re.MULTILINE
        )
        for match in path_var_explicit.finditer(method_content):
            param_name = match.group(1)
            # Check if this param is already added
            if not any(p["name"] == param_name for p in parameters):
                parameters.append({
                    "name": param_name,
                    "location": "path",
                    "required": True
                })

        # Find all @RequestParam annotations and extract parameter names
        # Pattern: @RequestParam or @RequestParam(...) followed by type and name
        request_param_pattern = re.compile(
            r'@RequestParam'
            r'(?:\s*\([^)]*\))?'  # Optional arguments like (required=false)
            r'\s+(\w+)\s+(\w+)',  # Type and name: String name
            re.MULTILINE
        )
        for match in request_param_pattern.finditer(method_content):
            param_name = match.group(2)  # Second group is the parameter name
            # Check if required
            full_match = match.group(0)
            required = "required" not in full_match or "required=false" not in full_match
            parameters.append({
                "name": param_name,
                "location": "query",
                "required": required
            })

        # Also check for @RequestParam with explicit name only: @RequestParam("name") or @RequestParam(name="name")
        request_param_explicit = re.compile(
            r'@RequestParam\s*\(\s*(?:name\s*=\s*)?["\'](\w+)["\']',
            re.MULTILINE
        )
        for match in request_param_explicit.finditer(method_content):
            param_name = match.group(1)
            # Check if this param is already added
            if not any(p["name"] == param_name for p in parameters):
                # Check if required
                start = max(0, match.start() - 50)
                end = min(len(method_content), match.end() + 50)
                context = method_content[start:end]
                required = "required" not in context or "required=false" not in context
                parameters.append({
                    "name": param_name,
                    "location": "query",
                    "required": required
                })

        return parameters

    def _find_method_end(self, content: str, start: int) -> int:
        """Find the approximate end of a method containing the annotation."""
        # Find next method or class definition
        next_method = re.search(r'^\s*(?:public|private|protected|\w)\s+\w+\s+\w+\s*\(', content[start+100:], re.MULTILINE)
        next_class = re.search(r'^\s*class\s+\w+', content[start+100:], re.MULTILINE)

        end = len(content)
        if next_method:
            end = min(end, start + 100 + next_method.start())
        if next_class:
            end = min(end, start + 100 + next_class.start())

        return end


def parse_java_file(file_path: str) -> List[ParsedEndpoint]:
    """Convenience function to parse a single Java file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    parser = SpringBootRegexParser()
    return parser.parse_content(content)
