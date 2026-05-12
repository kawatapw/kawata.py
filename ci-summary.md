# ❌ CI Summary

**Status:** FAIL | **Duration:** 139.7s | **Passed:** 2 | **Failed:** 4 | **Skipped:** 1

## Job Results

| Job | Status | Duration | Summary |
|---|---|---|---|
| `ruff` | ❌ FAIL | 2.7s | 7 errors |
| `ty` | ❌ FAIL | 12.0s | 12 failed |
| `bandit` | ❌ FAIL | 11.3s | 22 errors |
| `mypy` | ❌ FAIL | 33.6s | 26 failed |
| `unit-tests` | ✅ PASS | 27.7s | 904 passed, 7 skipped |
| `build` | ✅ PASS | 139.7s | passed |
| `integration-tests` | ⏭ SKIP | 0.0s | Dependency failed |

## Failures

<details open><summary><strong>❌ ruff</strong> — 7 errors</summary>
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/pyproject.toml:12:16`** — `RUF200` Failed to parse pyproject.toml: Not a URL (missing scheme): {root:uri}/tools/ci
ci-tool @ {root:uri}/tools/ci
          ^^^^^^^^^^^^^^^^^^^

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/pyproject.toml:12:16
     |
   10 | readme = "README.md"
   11 | requires-python = ">=3.11,<3.12"
   12 | dependencies = [
      |                ^
   13 |     "async-timeout==4.0.3",
   14 |     "bcrypt==4.1.2",
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/cli.py:98:5`** — `F841` Local variable `ctx` is assigned to but never used

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/cli.py:98:5
     |
    96 | def doctor() -> None:
    97 |     """Validate setup: check commands, parsers, storage."""
    98 |     ctx = get_context()
       |     ^^^
    99 |     cfg = get_config()
   100 |     issues: list[str] = []
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/cli.py:320:17`** — `F821` Undefined name `RunResult`

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/cli.py:320:17
     |
   318 |     ctx: Context,
   319 |     storage: FileStorageBackend,
   320 |     run_result: RunResult,
       |                 ^^^^^^^^^
   321 | ) -> None:
   322 |     """Post PR comment with results."""
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/github/__init__.py:6:36`** — `F401` `dataclasses.field` imported but unused

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/github/__init__.py:6:36
     |
   4 | import os
   5 | from dataclasses import dataclass, field
   6 | from typing import Any
     | ^^^^^^^^^^^^^^^^^^^^
   7 |
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/parsers/__init__.py:9:20`** — `F401` `typing.Type` imported but unused

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/parsers/__init__.py:9:20
     |
    7 | from abc import ABC, abstractmethod
    8 | from pathlib import Path
    9 | from typing import Type
      |                    ^^^^
   10 |
   11 | from ci_tool.parsers.models import ParsedResult
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/runner/__init__.py:9:21`** — `F401` `pathlib.Path` imported but unused

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/runner/__init__.py:9:21
     |
    7 | import uuid
    8 | from datetime import datetime, timezone
    9 | from pathlib import Path
      |                     ^^^^
   10 | from typing import Sequence
   11 |
```

---
**`/home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/runner/__init__.py:10:20`** — `F401` `typing.Sequence` imported but unused

```python
  --> /home/loki/mnt/Remote/SSH/Loki-NAS-Root/mnt/user/KawataDev/kawata.py/tools/ci/src/ci_tool/runner/__init__.py:10:20
     |
    8 | from datetime import datetime, timezone
    9 | from pathlib import Path
   10 | from typing import Sequence
      |                    ^^^^^^^^
   11 |
   12 | from ci_tool.config import Config
```

</details>

<details open><summary><strong>❌ ty</strong> — 12 failed</summary>
**`tests/unit/ci/test_storage.py:17:52`** — `unsupported-operator` Operator `/` is not supported between objects of type `TempPathFactory` and `Literal["ci-data"]`

```python
  --> tests/unit/ci/test_storage.py:17:1
     |
   15 | class TestFileStorageBackend:
   16 |     def test_save_and_load_state(self, tmp_path: pytest.TempPathFactory) -> None:
   17 |         storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))
      | ^^^^^^^^^^^^^^^^^^^^
   18 |
   19 |         state = WorkflowState(
```

---
**`tests/unit/ci/test_storage.py:46:52`** — `unsupported-operator` Operator `/` is not supported between objects of type `TempPathFactory` and `Literal["ci-data"]`

```python
  --> tests/unit/ci/test_storage.py:46:1
     |
   44 |     def test_load_nonexistent(self, tmp_path: pytest.TempPathFactory) -> None:
   45 |         storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))
   46 |         assert storage.load_state("nonexistent") is None
      | ^^^^^^^^^^^^^^^^^^^^
   47 |
```

---
**`tests/unit/ci/test_storage.py:50:52`** — `unsupported-operator` Operator `/` is not supported between objects of type `TempPathFactory` and `Literal["ci-data"]`

```python
  --> tests/unit/ci/test_storage.py:50:1
     |
   48 |     def test_list_runs(self, tmp_path: pytest.TempPathFactory) -> None:
   49 |         storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))
   50 |
      |
   51 |         for i in range(3):
```

---
**`tests/unit/ci/test_storage.py:67:52`** — `unsupported-operator` Operator `/` is not supported between objects of type `TempPathFactory` and `Literal["ci-data"]`

```python
  --> tests/unit/ci/test_storage.py:67:1
     |
   65 |     def test_cleanup(self, tmp_path: pytest.TempPathFactory) -> None:
   66 |         storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))
   67 |
      |
   68 |         for i in range(5):
```

---
**`tools/ci/src/ci_tool/cli.py:320:17`** — `unresolved-reference` Name `RunResult` used when not defined

```python
  --> tools/ci/src/ci_tool/cli.py:320:1
     |
   318 |     ctx: Context,
   319 |     storage: FileStorageBackend,
   320 |     run_result: RunResult,
       | ^^^^^^^^^^^^^^^^^^^^
   321 | ) -> None:
   322 |     """Post PR comment with results."""
```

---
**`tools/ci/src/ci_tool/cli.py:442:21`** — `unknown-argument` Argument `summary_line` does not match any known parameter

```python
  --> tools/ci/src/ci_tool/cli.py:442:1
     |
   440 |                     status=status_map.get(j.status, JobStatus.FAIL),
   441 |                     duration_seconds=j.duration_seconds,
   442 |                     summary_line=j.summary_line,
       | ^^^^^^^^^^^^^^^^^^^^
   443 |                     report_path=j.report_path,
   444 |                     parser_name=j.parser_name,
```

---
**`tools/ci/src/ci_tool/context.py:38:26`** — `invalid-assignment` Object of type `None` is not assignable to `Path`

```python
  --> tools/ci/src/ci_tool/context.py:38:1
     |
   36 |     is_interactive: bool = False
   37 |     step_summary_path: str = ""
   38 |     project_root: Path = None  # type: ignore[assignment]
      | ^^^^^^^^^^^^^^^^^^^^
   39 |
   40 |     def __post_init__(self) -> None:
```

---
**`tools/ci/src/ci_tool/github/__init__.py:101:16`** — `invalid-return-type` Return type does not match returned value: expected `list[dict[str, Any]]`, found `(dict[str, Any] & ~AlwaysFalsy) | list[Unknown]`

```python
  --> tools/ci/src/ci_tool/github/__init__.py:101:1
     |
    99 |             f"/repos/{self.config.repository}/commits/{sha}/pulls",
   100 |         )
   101 |         return result or []
       | ^^^^^^^^^^^^^^^^^^^^
   102 |
   103 |     async def create_check_run(
```

---
**`tools/ci/src/ci_tool/github/comments.py:69:28`** — `invalid-return-type` Return type does not match returned value: expected `dict[str, Any] | None`, found `Unknown | str`

```python
  --> tools/ci/src/ci_tool/github/comments.py:69:1
     |
   67 |             for comment in comments:
   68 |                 if COMMENT_MARKER in (comment.get("body", "") or ""):
   69 |                     return comment
      | ^^^^^^^^^^^^^^^^^^^^
   70 |
   71 |             if len(comments) < 100:
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:195:17`** — `invalid-assignment` Invalid subscript assignment with key of type `str | Unknown` and value of type `(JobRunResult & ~Exception) | (BaseException & ~Exception) | (Unknown & ~Exception)` on object of type `dict[str, JobRunResult]`

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:195:1
     |
   193 |                     continue
   194 |
   195 |                 run_result.jobs[result.name] = result
       | ^^^^^^^^^^^^^^^^^^^^
   196 |
   197 |                 # Update workflow state
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:202:57`** — `invalid-argument-type` Argument to bound method `_job_summary_line` is incorrect: Expected `JobRunResult`, found `(JobRunResult & ~Exception) | (BaseException & ~Exception) | (Unknown & ~Exception)`

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:202:1
     |
   200 |                     status=result.status,
   201 |                     duration_seconds=result.duration_seconds,
   202 |                     summary_line=self._job_summary_line(result),
       | ^^^^^^^^^^^^^^^^^^^^
   203 |                     report_path=result.report_path,
   204 |                     parser_name=result.parser_name,
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312:13`** — `unsupported-operator` Operator `-` is not supported between objects of type `datetime` and `datetime | None`

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:1
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       | ^^^^^^^^^^^^^^^^^^^^
   313 |         ).total_seconds()
   314 |
```

</details>

<details open><summary><strong>❌ bandit</strong> — 22 errors</summary>
**`app/api/domains/cho.py:932:12`** — `B105` Possible hardcoded password: 'invalid-request'

```python
  --> app/api/domains/cho.py:932:12
     |
   930 |         )
   931 |         return {
   932 |             "osu_token": "invalid-request",
       |            ^
   933 |             "response_body": (
   934 |                 app.packets.login_reply(LoginFailureReason.AUTHENTICATION_FAILED)
```

---
**`app/api/domains/cho.py:955:16`** — `B105` Possible hardcoded password: 'invalid-request'

```python
  --> app/api/domains/cho.py:955:16
     |
   953 |             )
   954 |             return {
   955 |                 "osu_token": "invalid-request",
       |                ^
   956 |                 "response_body": (
   957 |                     app.packets.login_reply(LoginFailureReason.AUTHENTICATION_FAILED)
```

---
**`app/api/domains/cho.py:975:12`** — `B105` Possible hardcoded password: 'invalid-request'

```python
  --> app/api/domains/cho.py:975:12
     |
   973 |         )
   974 |         return {
   975 |             "osu_token": "invalid-request",
       |            ^
   976 |             "response_body": (
   977 |                 app.packets.login_reply(LoginFailureReason.AUTHENTICATION_FAILED)
```

---
**`app/api/domains/cho.py:1005:20`** — `B105` Possible hardcoded password: 'client-too-old'

```python
  --> app/api/domains/cho.py:1005:20
     |
   1003 |                 )
   1004 |                 return {
   1005 |                     "osu_token": "client-too-old",
        |                    ^
   1006 |                     "response_body": (
   1007 |                         app.packets.version_update()
```

---
**`app/api/domains/cho.py:1037:16`** — `B105` Possible hardcoded password: 'empty-adapters'

```python
  --> app/api/domains/cho.py:1037:16
     |
   1035 |             )
   1036 |             return {
   1037 |                 "osu_token": "empty-adapters",
        |                ^
   1038 |                 "response_body": (
   1039 |                     app.packets.login_reply(LoginFailureReason.AUTHENTICATION_FAILED)
```

---
**`app/api/domains/cho.py:1057:12`** — `B105` Possible hardcoded password: 'invalid-request'

```python
  --> app/api/domains/cho.py:1057:12
     |
   1055 |         )
   1056 |         return {
   1057 |             "osu_token": "invalid-request",
        |            ^
   1058 |             "response_body": (
   1059 |                 app.packets.login_reply(LoginFailureReason.AUTHENTICATION_FAILED)
```

---
**`app/api/domains/cho.py:1087:20`** — `B105` Possible hardcoded password: 'user-already-logged-in'

```python
  --> app/api/domains/cho.py:1087:20
     |
   1085 |                 )
   1086 |                 return {
   1087 |                     "osu_token": "user-already-logged-in",
        |                    ^
   1088 |                     "response_body": (
   1089 |                         app.packets.login_reply(
```

---
**`app/api/domains/cho.py:1127:16`** — `B105` Possible hardcoded password: 'incorrect-credentials'

```python
  --> app/api/domains/cho.py:1127:16
     |
   1125 |             )
   1126 |             return {
   1127 |                 "osu_token": "incorrect-credentials",
        |                ^
   1128 |                 "response_body": (
   1129 |                     app.packets.notification(f"{BASE_DOMAIN}: Incorrect credentials")
```

---
**`app/api/domains/cho.py:1140:12`** — `B105` Possible hardcoded password: 'authentication-error'

```python
  --> app/api/domains/cho.py:1140:12
     |
   1138 |         )
   1139 |         return {
   1140 |             "osu_token": "authentication-error",
        |            ^
   1141 |             "response_body": (
   1142 |                 app.packets.notification(
```

---
**`app/api/domains/cho.py:1165:16`** — `B105` Possible hardcoded password: 'no'

```python
  --> app/api/domains/cho.py:1165:16
     |
   1163 |             )
   1164 |             return {
   1165 |                 "osu_token": "no",
        |                ^
   1166 |                 "response_body": app.packets.login_reply(
   1167 |                     LoginFailureReason.AUTHENTICATION_FAILED,
```

---
**`app/api/domains/cho.py:1265:16`** — `B105` Possible hardcoded password: 'contact-staff'

```python
  --> app/api/domains/cho.py:1265:16
     |
   1263 |         ):
   1264 |             return {
   1265 |                 "osu_token": "contact-staff",
        |                ^
   1266 |                 "response_body": (
   1267 |                     app.packets.notification(
```

---
**`app/api/domains/cho.py:1312:16`** — `B105` Possible hardcoded password: 'login-failed'

```python
  --> app/api/domains/cho.py:1312:16
     |
   1310 |             )
   1311 |             return {
   1312 |                 "osu_token": "login-failed",
        |                ^
   1313 |                 "response_body": (
   1314 |                     app.packets.notification(
```

---
**`app/api/domains/cho.py:1327:12`** — `B105` Possible hardcoded password: 'login-failed'

```python
  --> app/api/domains/cho.py:1327:12
     |
   1325 |         )
   1326 |         return {
   1327 |             "osu_token": "login-failed",
        |            ^
   1328 |             "response_body": (
   1329 |                 app.packets.notification(
```

---
**`app/api/domains/cho.py:1385:12`** — `B105` Possible hardcoded password: 'login-failed'

```python
  --> app/api/domains/cho.py:1385:12
     |
   1383 |         )
   1384 |         return {
   1385 |             "osu_token": "login-failed",
        |            ^
   1386 |             "response_body": (
   1387 |                 app.packets.notification(
```

---
**`app/api/domains/cho.py:1432:12`** — `B105` Possible hardcoded password: 'login-failed'

```python
  --> app/api/domains/cho.py:1432:12
     |
   1430 |         )
   1431 |         return {
   1432 |             "osu_token": "login-failed",
        |            ^
   1433 |             "response_body": (
   1434 |                 app.packets.notification(
```

---
**`app/api/domains/cho.py:1469:12`** — `B105` Possible hardcoded password: 'login-failed'

```python
  --> app/api/domains/cho.py:1469:12
     |
   1467 |         )
   1468 |         return {
   1469 |             "osu_token": "login-failed",
        |            ^
   1470 |             "response_body": (
   1471 |                 app.packets.notification(
```

---
**`app/api/v1/api.py:1909:17`** — `B311` Standard pseudo-random generators are not suitable for security/cryptographic purposes.

```python
  --> app/api/v1/api.py:1909:17
     |
   1907 |     # Sample random players (or return all if fewer than limit)
   1908 |     if len(online) > limit:
   1909 |         sample = random.sample(online, limit)
        |                 ^
   1910 |     else:
   1911 |         sample = online
```

---
**`app/api/v1/hinaDir/score_records.py:55:8`** — `B608` Possible SQL injection vector through string-based query construction.

```python
  --> app/api/v1/hinaDir/score_records.py:55:8
     |
   53 |     # `app/api/v1/` (Loki) and the rest of `hinaDir/`.
   54 |     count_sql = (
   55 |         "SELECT COUNT(*) AS cnt "
      |        ^
   56 |         "FROM scores sc "
   57 |         "INNER JOIN users u ON u.id = sc.userid "
```

---
**`app/api/v1/hinaDir/score_records.py:66:8`** — `B608` Possible SQL injection vector through string-based query construction.

```python
  --> app/api/v1/hinaDir/score_records.py:66:8
     |
   64 |     data_params = {**where_params, "limit": limit, "offset": offset}
   65 |     data_sql = (
   66 |         "SELECT sc.id, sc.score, sc.pp, sc.acc, sc.max_combo, sc.mods, sc.grade, "
      |        ^
   67 |         "sc.n300, sc.n100, sc.n50, sc.nmiss, sc.play_time, sc.perfect, "
   68 |         "sc.userid AS player_id, "
```

---
**`app/objects/group.py:97:16`** — `B105` Possible hardcoded password: ''

```python
  --> app/objects/group.py:97:16
     |
   95 |         self.lead: Player = lead
   96 |         found = False
   97 |         token = ""
      |                ^
   98 |         while not found:
   99 |             token = str(uuid.uuid4())
```

---
**`app/objects/player.py:500:34`** — `B105` Possible hardcoded password: ''

```python
  --> app/objects/player.py:500:34
     |
   498 |     @property
   499 |     def is_online(self) -> bool:
   500 |         return bool(self.token != "")
       |                                  ^
   501 |
   502 |     @property
```

---
**`app/objects/player.py:625:21`** — `B105` Possible hardcoded password: ''

```python
  --> app/objects/player.py:625:21
     |
   623 |         # invalidate the user's token.
   624 |         self.token = ""
   625 |
       |
   626 |         # leave multiplayer.
```

</details>

<details open><summary><strong>❌ mypy</strong> — 26 failed</summary>
**`tools/ci/src/ci_tool/parsers/models.py:139`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/models.py:139:15
     |
   137 |     # Metadata
   138 |     packages_scanned: int = 0
   139 |     raw_data: dict = field(default_factory=dict)  # Original parsed data
       |               ^
   140 |
   141 |     # Error handling
```

---
**`tools/ci/src/ci_tool/parsers/trivy.py:49`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/trivy.py:49:34
     |
   47 |         return self._parse_json(data, file_path)
   48 |
   49 |     def _parse_sarif(self, data: dict, file_path: str) -> ParsedResult:
      |                                  ^
   50 |         result = ParsedResult(parser_name=self.name, file_path=file_path)
   51 |         issues: list[Issue] = []
```

---
**`tools/ci/src/ci_tool/parsers/trivy.py:85`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/trivy.py:85:33
     |
   83 |         return result
   84 |
   85 |     def _parse_json(self, data: dict, file_path: str) -> ParsedResult:
      |                                 ^
   86 |         result = ParsedResult(parser_name=self.name, file_path=file_path)
   87 |         issues: list[Issue] = []
```

---
**`tools/ci/src/ci_tool/parsers/safety.py:60`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/safety.py:60:42
     |
   58 |         return result
   59 |
   60 |     def _parse_vulnerability(self, vuln: dict, package_name: str = "") -> Issue:
      |                                          ^
   61 |         severity_str = vuln.get("severity", "low").lower()
   62 |         if severity_str not in ("critical", "high", "medium", "low"):
```

---
**`tools/ci/src/ci_tool/parsers/ruff.py:41`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/ruff.py:41:33
     |
   39 |         return self._parse_text(content, file_path)
   40 |
   41 |     def _parse_json(self, data: list | dict, file_path: str) -> ParsedResult:
      |                                 ^
   42 |         result = ParsedResult(parser_name=self.name, file_path=file_path)
   43 |         issues: list[Issue] = []
```

---
**`tools/ci/src/ci_tool/parsers/ruff.py:41`** — Missing type

```python
  --> tools/ci/src/ci_tool/parsers/ruff.py:41:40
     |
   39 |         return self._parse_text(content, file_path)
   40 |
   41 |     def _parse_json(self, data: list | dict, file_path: str) -> ParsedResult:
      |                                        ^
   42 |         result = ParsedResult(parser_name=self.name, file_path=file_path)
   43 |         issues: list[Issue] = []
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:14`** — Module

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:14:1
     |
   12 | from ci_tool.config import Config
   13 | from ci_tool.context import Context
   14 | from ci_tool.runner.models import (
      | ^
   15 |     JobRunConfig,
   16 |     JobRunResult,
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:189`** — Incompatible

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:189:13
     |
   187 |             # Check results and update state
   188 |             for result in results:
   189 |                 if isinstance(result, Exception):
       |             ^
   190 |                     # This shouldn't happen with return_exceptions=True
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312`** — No overload

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:13
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   313 |         ).total_seconds()
   314 |
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312`** — Possible overload variants:

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:13
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   313 |         ).total_seconds()
   314 |
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312`** — def __sub__(self, timedelta, /) -> datetime

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:13
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   313 |         ).total_seconds()
   314 |
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312`** — def __sub__(self, datetime, /) -> timedelta

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:13
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   313 |         ).total_seconds()
   314 |
```

---
**`tools/ci/src/ci_tool/runner/__init__.py:312`** — Right operand is of type "datetime | None"

```python
  --> tools/ci/src/ci_tool/runner/__init__.py:312:13
     |
   310 |         result.completed_at = datetime.now(timezone.utc)
   311 |         result.duration_seconds = (
   312 |             result.completed_at - result.started_at
       |             ^
   313 |         ).total_seconds()
   314 |
```

---
**`tools/ci/src/ci_tool/output/report.py:49`** — Generator has

```python
  --> tools/ci/src/ci_tool/output/report.py:49:22
     |
   47 |         # Calculate summary
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
      |                      ^
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
   51 |
```

---
**`tools/ci/src/ci_tool/output/report.py:49`** — Non-overlapping

```python
  --> tools/ci/src/ci_tool/output/report.py:49:56
     |
   47 |         # Calculate summary
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
      |                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
   51 |
```

---
**`tools/ci/src/ci_tool/output/report.py:49`** — If condition in

```python
  --> tools/ci/src/ci_tool/output/report.py:49:56
     |
   47 |         # Calculate summary
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
      |                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
   51 |
```

---
**`tools/ci/src/ci_tool/output/report.py:50`** — Generator has

```python
  --> tools/ci/src/ci_tool/output/report.py:50:22
     |
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
      |                      ^
   51 |
   52 |         return self.template.render(
```

---
**`tools/ci/src/ci_tool/output/report.py:50`** — Non-overlapping

```python
  --> tools/ci/src/ci_tool/output/report.py:50:56
     |
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
      |                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   51 |
   52 |         return self.template.render(
```

---
**`tools/ci/src/ci_tool/output/report.py:50`** — If condition in

```python
  --> tools/ci/src/ci_tool/output/report.py:50:56
     |
   48 |         total = len(state.jobs)
   49 |         passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
   50 |         failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)
      |                                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   51 |
   52 |         return self.template.render(
```

---
**`tools/ci/src/ci_tool/github/__init__.py:80`** — Returning Any from

```python
  --> tools/ci/src/ci_tool/github/__init__.py:80:13
     |
   78 |             response = await client.request(method, path, **kwargs)
   79 |             response.raise_for_status()
   80 |             return response.json()
      |             ^^^^^^^^^^^^^^^^^^^^^
   81 |         except httpx.HTTPStatusError as e:
   82 |             import sys
```

---
**`tools/ci/src/ci_tool/github/__init__.py:101`** — Incompatible

```python
  --> tools/ci/src/ci_tool/github/__init__.py:101:16
     |
    99 |             f"/repos/{self.config.repository}/commits/{sha}/pulls",
   100 |         )
   101 |         return result or []
       |                ^^^^^^^^^^^
   102 |
   103 |     async def create_check_run(
```

---
**`tools/ci/src/ci_tool/github/comments.py:68`** — "str" has no

```python
  --> tools/ci/src/ci_tool/github/comments.py:68:39
     |
   66 |             for comment in comments:
   67 |                 if COMMENT_MARKER in (comment.get("body", "") or ""):
   68 |                     return comment
      | ^^^^^^^^^^^^^^^^^^^^
   69 |
```

---
**`tools/ci/src/ci_tool/github/comments.py:69`** — Incompatible return

```python
  --> tools/ci/src/ci_tool/github/comments.py:69:28
     |
   67 |             for comment in comments:
   68 |                 if COMMENT_MARKER in (comment.get("body", "") or ""):
   69 |                     return comment
      |                            ^^^^^^
   70 |
   71 |             if len(comments) < 100:
```

---
**`tools/ci/src/ci_tool/cli.py:169`** — Module "ci_tool.runner.models"

```python
  --> tools/ci/src/ci_tool/cli.py:169:5
     |
   167 |     # Build a synthetic RunResult from report files
   168 |     from ci_tool.runner.models import JobRunResult, JobStatus, RunResult
   169 |     from datetime import datetime, timezone
       |     ^
   170 |
```

---
**`tools/ci/src/ci_tool/cli.py:177`** — Missing type parameters for

```python
  --> tools/ci/src/ci_tool/cli.py:177:21
     |
   175 |     )
   176 |
   177 |     parsed_results: dict = {}
       |                     ^
   178 |
   179 |     for report_file in sorted(report_dir.iterdir()):
```

---
**`tools/ci/src/ci_tool/cli.py:248`** — Module "ci_tool.runner" does

```python
  --> tools/ci/src/ci_tool/cli.py:248:5
     |
   246 |     storage = FileStorageBackend(cfg.file_storage.directory)
   247 |
   248 |     from ci_tool.runner import JobRunner, RunMode
       |     ^
   249 |     from ci_tool.runner.models import JobStatus
   250 |
```

---
**`tools/ci/src/ci_tool/cli.py:249`** — Module "ci_tool.runner.models"

```python
  --> tools/ci/src/ci_tool/cli.py:249:5
     |
   247 |     from ci_tool.runner import JobRunner, RunMode
   248 |     from ci_tool.runner.models import JobStatus
   249 |
       |
   250 |     mode = RunMode.PARALLEL if parallel else RunMode.SERIAL
```

---
**`tools/ci/src/ci_tool/cli.py:320`** — Name "RunResult" is not

```python
  --> tools/ci/src/ci_tool/cli.py:320:17
     |
   318 |     ctx: Context,
   319 |     storage: FileStorageBackend,
   320 |     run_result: RunResult,
       |                 ^
   321 | ) -> None:
   322 |     """Post PR comment with results."""
```

---
**`tools/ci/src/ci_tool/cli.py:399`** — Module "ci_tool.runner.models"

```python
  --> tools/ci/src/ci_tool/cli.py:399:9
     |
   397 |         from ci_tool.github.comments import PRCommentManager
   398 |         from ci_tool.output.summary import SummaryRenderer, parse_reports_for_run
   399 |         from ci_tool.runner.models import JobRunResult, RunResult, JobStatus
       |         ^
   400 |         from ci_tool.storage.models import JobStatus as WfJobStatus
   401 |
```

---
**`tools/ci/src/ci_tool/cli.py:438`** — Unexpected keyword argument

```python
  --> tools/ci/src/ci_tool/cli.py:438:41
     |
   436 |             )
   437 |             for name, j in state.jobs.items():
   438 |                 run_result.jobs[name] = JobRunResult(
       |                                         ^
   439 |                     name=name,
   440 |                     status=status_map.get(j.status, JobStatus.FAIL),
```

</details>