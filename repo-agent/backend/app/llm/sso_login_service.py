"""Runs `aws sso login`, serialized per profile so parallel runs don't open
multiple browser logins.
"""

from __future__ import annotations

import asyncio


class SsoLoginService:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, profile_name: str) -> asyncio.Lock:
        if profile_name not in self._locks:
            self._locks[profile_name] = asyncio.Lock()
        return self._locks[profile_name]

    async def login(self, profile_name: str) -> None:
        # Only one login per profile at a time.
        async with self._lock_for(profile_name):
            args = ["aws", "sso", "login"]
            if profile_name:
                args += ["--profile", profile_name]
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(
                    stderr.decode(errors="replace") or stdout.decode(errors="replace")
                    or "aws sso login failed"
                )
