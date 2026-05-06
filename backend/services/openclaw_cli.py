import os
import subprocess
import sys
from backend.config import settings

_PROFILE = "neurogenesis"


def _find_node_cmd():
    """Find npx or node executable."""
    for cmd in ["npx.cmd", "npx", "node.exe", "node"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
            return cmd
        except Exception:
            continue
    return None


def _run_cmd(args, timeout=30):
    """Run an OpenClaw CLI command with the neurogenesis profile."""
    if not settings.openclaw_enabled:
        return ""
    node_cmd = _find_node_cmd()
    if not node_cmd:
        print("[OpenClaw] npx/node not found in PATH")
        return ""
    cmd = [node_cmd]
    if node_cmd.endswith("npx") or node_cmd.endswith("npx.cmd"):
        cmd += ["openclaw", "--profile", _PROFILE] + args
    else:
        # fallback: run openclaw.mjs directly
        openclaw_path = os.path.join(os.path.dirname(__file__), "..", "..", "node_modules", "openclaw", "openclaw.mjs")
        openclaw_path = os.path.abspath(openclaw_path)
        cmd += [openclaw_path, "--profile", _PROFILE] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.abspath(settings.openclaw_workspace),
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"[OpenClaw CLI] error: {e}")
        return ""


def agent_add(agent_id, workspace_dir):
    """Register an avatar as an OpenClaw agent."""
    agent_name = f"neurogenesis_avatar_{agent_id}"
    return _run_cmd([
        "agents", "add", agent_name,
        "--workspace", workspace_dir,
        "--non-interactive",
    ])


def agent_delete(agent_id):
    """Remove an avatar from OpenClaw agents."""
    agent_name = f"neurogenesis_avatar_{agent_id}"
    return _run_cmd(["agents", "delete", agent_name, "--non-interactive"])


def agent_sync(agent_id):
    """Sync an agent config with OpenClaw."""
    agent_name = f"neurogenesis_avatar_{agent_id}"
    return _run_cmd(["agents", "sync", agent_name])


def list_agents():
    """List configured OpenClaw agents."""
    return _run_cmd(["agents", "list"])


def gateway_start():
    """Start the OpenClaw Gateway subprocess in dev mode."""
    if not settings.openclaw_enabled:
        print("[OpenClaw] disabled via OPENCLAW_ENABLED=false")
        return None
    node_cmd = _find_node_cmd()
    if not node_cmd:
        print("[OpenClaw] npx/node not found in PATH, skipping gateway start")
        return None
    workspace = os.path.abspath(settings.openclaw_workspace)
    os.makedirs(workspace, exist_ok=True)
    cmd = [node_cmd]
    if node_cmd.endswith("npx") or node_cmd.endswith("npx.cmd"):
        cmd += ["openclaw", "--profile", _PROFILE, "gateway", "run", "--dev", "--allow-unconfigured"]
    else:
        openclaw_path = os.path.join(os.path.dirname(__file__), "..", "..", "node_modules", "openclaw", "openclaw.mjs")
        openclaw_path = os.path.abspath(openclaw_path)
        cmd += [openclaw_path, "--profile", _PROFILE, "gateway", "run", "--dev", "--allow-unconfigured"]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(f"[OpenClaw] Gateway starting with PID {proc.pid}")
        return proc
    except Exception as e:
        print(f"[OpenClaw] Failed to start gateway: {e}")
        return None


def gateway_stop(proc):
    """Gracefully stop the OpenClaw Gateway subprocess."""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print("[OpenClaw] Gateway stopped")
    except Exception:
        proc.kill()
        print("[OpenClaw] Gateway killed")
