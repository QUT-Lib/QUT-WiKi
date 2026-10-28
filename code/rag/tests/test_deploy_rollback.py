# -*- coding: utf-8 -*-
"""运行 deploy-index.sh 的离线回滚测试（tests/test_deploy_rollback.sh）。

用例本身是独立可运行的 bash 脚本，因为它需要真正的 symlink / flock / mv -T
语义；本文件只是把它挂进 unittest 发现，便于常规测试时顺带跑到：

    py -3 -m unittest discover -s code/rag/tests -v

环境要求（不满足则 skip，不会失败）：
  * POSIX：直接调用 bash；需要 root，普通用户走 `sudo -n`（CI 免密 sudo）；
  * Windows：通过 WSL 以 root 运行，未安装 WSL 时 skip。

脚本只在 mktemp 沙箱里改写 ROOT/STAGING/LOCK/PATH 四行，不写 /opt，
不调用真实 systemctl/curl，也不修改仓库里的 deploy-index.sh。

判定只依赖 shell 侧输出的 ASCII 标记 `RESULT pass=N skip=N fail=N`（或
`RESULT skipped ...`），不比较中文文案；子进程输出按 UTF-8 严格解码。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHELL_TEST = HERE / "test_deploy_rollback.sh"
TIMEOUT = 300
RESULT_RE = re.compile(r"^RESULT pass=(\d+) skip=(\d+) fail=(\d+)$", re.M)


def _wsl_path(path: Path) -> str:
    """D:\\code\\x -> /mnt/d/code/x（仅用于 WSL 调用）。"""
    drive = path.drive.rstrip(":").lower()
    tail = path.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def _command() -> list[str] | None:
    bash = shutil.which("bash")
    if os.name != "nt" and bash:
        if os.geteuid() == 0:
            return [bash, str(SHELL_TEST)]
        sudo = shutil.which("sudo")
        if sudo:
            probe = subprocess.run(
                [sudo, "-n", "true"], capture_output=True
            )
            if probe.returncode == 0:
                return [sudo, "-n", bash, str(SHELL_TEST)]
        return None
    wsl = shutil.which("wsl") or shutil.which("wsl.exe")
    if wsl:
        return [wsl, "-u", "root", "bash", _wsl_path(SHELL_TEST)]
    return None


class DeployIndexRollbackTest(unittest.TestCase):
    """deploy-index.sh 的发布/回滚控制流（沙箱 + mock，不触网不写 /opt）。"""

    def test_shell_suite(self) -> None:
        if not SHELL_TEST.is_file():
            self.skipTest(f"缺少 {SHELL_TEST.name}")
        cmd = _command()
        if cmd is None:
            self.skipTest("需要 root 或免密 sudo（或 WSL）才能运行回滚测试")
        env = dict(os.environ)
        try:
            # 显式 UTF-8：Windows 上 text=True 默认按 GBK 解码，会破坏中文与标记解析。
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                timeout=TIMEOUT,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
            self.fail(f"无法运行 {cmd[0]}：{exc}")

        output = proc.stdout or ""
        match = RESULT_RE.search(output)
        if match is None:
            if "RESULT skipped" in output:
                self.skipTest("环境不满足（缺少 root / 免密 sudo），已整体跳过")
            self.fail(f"测试没有输出结果标记（rc={proc.returncode}）：\n{output}")

        passed, _skipped, failed = (int(g) for g in match.groups())
        self.assertEqual(
            failed,
            0,
            f"回滚测试有 {failed} 条失败（rc={proc.returncode}）：\n{output}",
        )
        self.assertGreater(passed, 0, f"没有执行任何断言：\n{output}")


if __name__ == "__main__":
    unittest.main()
