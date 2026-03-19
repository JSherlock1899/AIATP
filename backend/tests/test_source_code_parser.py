import pytest
from app.services.source_code_parser import SpringBootRegexParser, parse_java_file


SIMPLE_CONTROLLER = '''
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }

    @PostMapping
    public User createUser(@RequestBody @Valid UserRequest request) {
        return userService.create(request);
    }

    @PutMapping("/{id}")
    public User updateUser(@PathVariable Long id, @RequestBody UserRequest request) {
        return userService.update(id, request);
    }

    @DeleteMapping("/{id}")
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }

    @GetMapping("/search")
    public List<User> searchUsers(@RequestParam String name, @RequestParam(required=false) Integer age) {
        return userService.search(name, age);
    }
}
'''


def test_parse_simple_controller():
    parser = SpringBootRegexParser()
    endpoints = parser.parse_content(SIMPLE_CONTROLLER)

    assert len(endpoints) == 5

    # Test GET /{id}
    get_by_id = next(e for e in endpoints if e["method"] == "GET" and "/{id}" in e["path"])
    assert get_by_id["path"] == "/api/users/{id}"
    assert get_by_id["summary"] is None

    # Test POST
    post = next(e for e in endpoints if e["method"] == "POST")
    assert post["path"] == "/api/users"
    assert post["request_body"] is not None

    # Test search with query params
    search = next(e for e in endpoints if "search" in e["path"])
    assert search["method"] == "GET"
    params = {p["name"]: p for p in search["parameters"]}
    assert "name" in params
    assert "age" in params


def test_path_traversal_blocked():
    with pytest.raises(ValueError, match="Path traversal"):
        SpringBootRegexParser.validate_path("/projects/../../../etc/passwd")


def test_relative_path_blocked():
    with pytest.raises(ValueError, match="Absolute path"):
        SpringBootRegexParser.validate_path("relative/path")


def test_scan_java_files(tmp_path):
    # Create test structure
    controller_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    controller_dir.mkdir(parents=True)
    (controller_dir / "UserController.java").write_text(SIMPLE_CONTROLLER)

    files = list(SpringBootRegexParser.scan_java_files(str(tmp_path)))
    assert len(files) == 1
    assert files[0].endswith("UserController.java")
