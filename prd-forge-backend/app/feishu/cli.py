"""lark-cli 子进程调用封装。"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_LARK_CLI_PATH = shutil.which("lark-cli") or "/Users/shswchengming/.workbuddy/binaries/node/cli-connector-packages/bin/lark-cli"


def _resolve_cli() -> str:
    if not os.path.isfile(_LARK_CLI_PATH):
        msg = f"lark-cli not found at {_LARK_CLI_PATH}"
        raise FileNotFoundError(msg)
    return _LARK_CLI_PATH


@dataclass
class CliResult:
    ok: bool
    data: dict
    error_message: str | None = None


def run_lark(args: list[str], cwd: str | None = None, timeout: int = 30) -> CliResult:
    """执行 lark-cli 命令并解析 JSON 输出。"""
    cmd = [_resolve_cli(), *args]
    logger.debug("lark-cli: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return CliResult(ok=False, data={}, error_message="lark-cli 执行超时")
    except Exception as exc:
        return CliResult(ok=False, data={}, error_message=str(exc))

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if stderr:
        logger.warning("lark-cli stderr: %s", stderr)

    if not stdout:
        return CliResult(ok=False, data={}, error_message=stderr or "lark-cli 无输出")

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return CliResult(ok=False, data={}, error_message=f"lark-cli 输出解析失败: {stdout[:200]}")

    if isinstance(parsed, dict) and not parsed.get("ok", True):
        err_msg = parsed.get("message") or parsed.get("error") or str(parsed)
        return CliResult(ok=False, data=parsed, error_message=err_msg)

    return CliResult(ok=True, data=parsed if isinstance(parsed, dict) else {"result": parsed})


def make_temp_md_file(content: str, filename: str) -> str:
    """在临时目录创建 MD 文件，返回相对于 cwd 的路径。"""
    tmpdir = tempfile.mkdtemp(prefix="prd-share-")
    filepath = os.path.join(tmpdir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    # Return the directory and filename so caller can run from tmpdir with ./filename
    return tmpdir, filename
