"""Tests for the optional local Data UI server run-control path.

The server is not the canonical data creation pipeline; it only launches the
normal config-driven CLI as a local development subprocess. These tests protect
that UI helper from reporting a run as stopped while its subprocess can still
start and continue invisibly. They run locally with pytest and do not launch
generation jobs or call external services.
"""

from __future__ import annotations

import asyncio

import server


class FakeStdout:
    async def readline(self) -> bytes:
        return b""


class FakeProcess:
    def __init__(self) -> None:
        self.stdout = FakeStdout()
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int | None:
        return self.returncode


def test_stop_during_subprocess_creation_terminates_after_assignment(monkeypatch) -> None:
    async def scenario() -> None:
        server._runs.clear()
        run_id = "race"
        server._runs[run_id] = {
            "status": "running",
            "stop_requested": False,
            "lines": [],
            "command": "fake-command",
            "process": None,
        }

        create_entered = asyncio.Event()
        allow_create_to_return = asyncio.Event()
        proc = FakeProcess()

        async def fake_create_subprocess_exec(*args, **kwargs) -> FakeProcess:
            create_entered.set()
            await allow_create_to_return.wait()
            return proc

        monkeypatch.setattr(server.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        task = asyncio.create_task(server._run_task(run_id, ["fake-command"]))
        await create_entered.wait()

        response = await server.stop_run(run_id)
        assert response == {"status": "stopped"}
        assert server._runs[run_id]["process"] is None
        assert server._runs[run_id]["stop_requested"] is True

        allow_create_to_return.set()
        await asyncio.wait_for(task, timeout=1)

        run = server._runs[run_id]
        assert run["status"] == "stopped"
        assert run["process"] is proc
        assert proc.terminated is True
        assert proc.killed is False
        assert run["returncode"] == -15

    asyncio.run(scenario())
