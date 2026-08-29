"""Launch the Opentrons desktop app and attach Playwright over CDP."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from automation.app_helpers.app_readiness import dismiss_blocking_ui

DEBUG_PORT = 9222
ODD_CDP_PORT = 9223
DEV_CDP_TIMEOUT_S = 180.0

# Installed-app names vary slightly by installer/version (Opentrons.app,
# Opentrons 8.5.0.app, Opentrons.exe, Opentrons Setup.exe is excluded).
_MAC_APP_BUNDLE_RE = re.compile(r"^Opentrons(?:[ ._-].+)?\.app$", re.IGNORECASE)
_MAC_EXECUTABLE_RE = re.compile(r"^Opentrons$", re.IGNORECASE)
_WIN_EXECUTABLE_RE = re.compile(r"^Opentrons(?:[ ._-].+)?\.exe$", re.IGNORECASE)
_WIN_INSTALL_DIR_RE = re.compile(r"^Opentrons", re.IGNORECASE)
_WIN_SKIP_EXE_RE = re.compile(r"(?i)(uninstall|setup|installer|update)")
_LINUX_EXECUTABLE_RE = re.compile(r"^opentrons$", re.IGNORECASE)


def resolve_cdp_endpoint(*, host: str | None = None, port: int | None = None) -> tuple[str, int]:
    """Resolve CDP host/port from args or ``CDP_HOST`` / ``CDP_PORT`` env vars."""
    resolved_host = (host or os.environ.get("CDP_HOST", "").strip() or "127.0.0.1").strip()
    if port is not None:
        resolved_port = port
    else:
        env_port = os.environ.get("CDP_PORT", "").strip()
        resolved_port = int(env_port) if env_port else DEBUG_PORT
    return resolved_host, resolved_port


def find_monorepo_root() -> Path:
    """Return the Opentrons monorepo root for ``make -C app dev`` / robot-server.

    Prefers ``OPENTRONS_ROOT`` when set (standalone workspace), then walks up
    from this file until ``app/Makefile`` and ``robot-server/Makefile`` exist.
    """
    env_root = os.environ.get("OPENTRONS_ROOT", "").strip()
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if (root / "app" / "Makefile").is_file() and (root / "robot-server" / "Makefile").is_file():
            return root
        raise RuntimeError(
            f"OPENTRONS_ROOT={root} does not look like an Opentrons monorepo "
            "(expected app/Makefile and robot-server/Makefile)"
        )

    for parent in Path(__file__).resolve().parents:
        if (parent / "app" / "Makefile").is_file() and (parent / "robot-server" / "Makefile").is_file():
            return parent
    raise RuntimeError(
        "Could not find Opentrons monorepo root from open_app.py. "
        "Set OPENTRONS_ROOT to your monorepo path (e.g. in .env)."
    )


def _iter_dir_entries(root: Path, *, max_depth: int) -> Iterator[Path]:
    """Yield files and directories under ``root`` up to ``max_depth`` (0 = root only)."""
    if max_depth < 0 or not root.is_dir():
        return
    try:
        entries = list(root.iterdir())
    except OSError:
        return
    for entry in entries:
        yield entry
        if max_depth > 0 and entry.is_dir() and not entry.is_symlink():
            yield from _iter_dir_entries(entry, max_depth=max_depth - 1)


def _prefer_exact_name(path: Path, exact: str) -> tuple[int, str]:
    """Sort key: exact filename first, then shorter / stable names."""
    return (0 if path.name.lower() == exact.lower() else 1, path.name.lower())


def _macos_search_roots() -> list[Path]:
    return [Path("/Applications"), Path.home() / "Applications"]


def _windows_search_roots() -> list[Path]:
    roots: list[Path] = []
    for env_key, default in (
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ):
        roots.append(Path(os.environ.get(env_key) or default))
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        roots.append(Path(local_app) / "Programs")
    return roots


def _linux_search_roots() -> list[Path]:
    return [Path("/usr/bin"), Path("/usr/local/bin"), Path.home() / ".local" / "bin"]


def _find_macos_executable() -> Path | None:
    matches: list[Path] = []
    for root in _macos_search_roots():
        for entry in _iter_dir_entries(root, max_depth=0):
            if not entry.is_dir() or not _MAC_APP_BUNDLE_RE.match(entry.name):
                continue
            macos_dir = entry / "Contents" / "MacOS"
            for binary in _iter_dir_entries(macos_dir, max_depth=0):
                if binary.is_file() and _MAC_EXECUTABLE_RE.match(binary.name):
                    matches.append(binary)
    if not matches:
        return None
    matches.sort(key=lambda p: _prefer_exact_name(p.parent.parent.parent, "Opentrons.app"))
    return matches[0]


def _is_windows_app_exe(path: Path) -> bool:
    return path.is_file() and bool(_WIN_EXECUTABLE_RE.match(path.name)) and not _WIN_SKIP_EXE_RE.search(path.name)


def _find_windows_executable() -> Path | None:
    matches: list[Path] = []
    for root in _windows_search_roots():
        for entry in _iter_dir_entries(root, max_depth=0):
            if _is_windows_app_exe(entry):
                matches.append(entry)
            elif entry.is_dir() and _WIN_INSTALL_DIR_RE.match(entry.name):
                for nested in _iter_dir_entries(entry, max_depth=2):
                    if _is_windows_app_exe(nested):
                        matches.append(nested)
    if not matches:
        return None
    matches.sort(key=lambda p: _prefer_exact_name(p, "Opentrons.exe"))
    return matches[0]


def _find_linux_executable() -> Path | None:
    matches: list[Path] = []
    for root in _linux_search_roots():
        for entry in _iter_dir_entries(root, max_depth=0):
            if entry.is_file() and _LINUX_EXECUTABLE_RE.match(entry.name):
                matches.append(entry)
    if not matches:
        return None
    matches.sort(key=lambda p: _prefer_exact_name(p, "opentrons"))
    return matches[0]


def _searched_locations(current_os: str) -> str:
    if current_os == "darwin":
        roots = _macos_search_roots()
        pattern = "Opentrons*.app/Contents/MacOS/Opentrons"
    elif current_os == "windows":
        roots = _windows_search_roots()
        pattern = "Opentrons*.exe"
    elif current_os == "linux":
        roots = _linux_search_roots()
        pattern = "opentrons"
    else:
        return current_os
    listed = "\n".join(f"  {root}" for root in roots)
    return f"{listed}\n(pattern: {pattern})"


def get_opentrons_path() -> str:
    """Return the Opentrons executable path for this OS.

    Prefers ``OPENTRONS_APP_PATH`` when set (absolute path to the binary), then
    searches standard install locations with a name regex so versioned bundles
    (``Opentrons 8.5.0.app``, etc.) still resolve on other machines.
    """
    override = os.environ.get("OPENTRONS_APP_PATH", "").strip()
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"OPENTRONS_APP_PATH={path} is not a file")
        return str(path)

    current_os = platform.system().lower()
    found: Path | None
    if current_os == "windows":
        found = _find_windows_executable()
    elif current_os == "darwin":
        found = _find_macos_executable()
    elif current_os == "linux":
        found = _find_linux_executable()
    else:
        raise OSError(f"Unsupported operating system: {platform.system()}")

    if found is None:
        raise FileNotFoundError(
            "Could not find the Opentrons desktop app. Searched:\n"
            f"{_searched_locations(current_os)}\n"
            "Install the app or set OPENTRONS_APP_PATH to the executable."
        )
    return str(found.resolve())


def _cdp_is_ready(debug_port: int, *, host: str = "127.0.0.1") -> bool:
    """Return True when something is already listening on the CDP port."""
    url = f"http://{host}:{debug_port}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait_for_cdp(debug_port: int, timeout: float = 30.0, *, host: str = "127.0.0.1") -> None:
    """Poll the CDP ``/json/version`` endpoint until the browser is ready."""
    url = f"http://{host}:{debug_port}/json/version"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)
    raise TimeoutError(f"CDP not ready at {host}:{debug_port} after {timeout}s")


def launch_dev_app(
    *,
    debug_port: int = DEBUG_PORT,
    opentrons_project: str = "ot3",
    quiet: bool = True,
    log_file: Path | None = None,
) -> subprocess.Popen:
    """Run ``make -C app dev`` with CDP enabled. Returns once CDP is up."""
    repo_root = find_monorepo_root()
    print(f"Launching dev app (make -C app dev OPENTRONS_PROJECT={opentrons_project})...")

    popen_kwargs: dict = {}
    if quiet and log_file is None:
        popen_kwargs["stdout"] = subprocess.DEVNULL
        popen_kwargs["stderr"] = subprocess.DEVNULL
    elif log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_file.open("w", encoding="utf-8")
        popen_kwargs["stdout"] = log_handle
        popen_kwargs["stderr"] = log_handle

    env = {
        **{k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"},
        "ELECTRON_EXTRA_ARGS": f"--remote-debugging-port={debug_port}",
    }
    process = subprocess.Popen(
        ["make", "-C", "app", "dev", f"OPENTRONS_PROJECT={opentrons_project}"],
        cwd=repo_root,
        env=env,
        **popen_kwargs,
    )
    _wait_for_cdp(debug_port, timeout=DEV_CDP_TIMEOUT_S)
    print(f"Dev app ready (CDP port {debug_port})")
    return process


def launch_app(*, debug_port: int = DEBUG_PORT, quiet: bool = True, log_file: Path | None = None) -> subprocess.Popen:
    """Launch Opentrons with remote debugging. Returns once CDP is up."""
    app_path = get_opentrons_path()
    print(f"Launching Opentrons from: {app_path}")

    popen_kwargs: dict = {}
    if quiet and log_file is None:
        popen_kwargs["stdout"] = subprocess.DEVNULL
        popen_kwargs["stderr"] = subprocess.DEVNULL
    elif log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_file.open("w", encoding="utf-8")
        popen_kwargs["stdout"] = log_handle
        popen_kwargs["stderr"] = log_handle

    # Cursor / VS Code set ELECTRON_RUN_AS_NODE=1 in the agent environment, which
    # makes the Opentrons Electron binary behave like Node and reject Chromium flags.
    env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}

    process = subprocess.Popen(
        [app_path, f"--remote-debugging-port={debug_port}"],
        env=env,
        **popen_kwargs,
    )
    _wait_for_cdp(debug_port)
    print(f"Opentrons app ready (CDP port {debug_port})")
    return process


def _is_app_page(page: Page) -> bool:
    """Return True when the page looks like the Opentrons app, not DevTools."""
    url = page.url.lower()
    title = page.title().lower()
    if "devtools" in url or title == "devtools":
        return False
    return "index.html" in url or "opentrons" in title


def _iter_cdp_pages(browser: Browser):
    """Yield every page in every context attached over CDP."""
    for context in browser.contexts:
        yield from context.pages


def _find_app_page(browser: Browser) -> Page:
    """Return the main Opentrons app window, waiting briefly if needed."""
    for _ in range(30):
        for page in _iter_cdp_pages(browser):
            if _is_app_page(page):
                return page
        time.sleep(1)

    for page in _iter_cdp_pages(browser):
        if "devtools" not in page.url.lower():
            return page

    raise RuntimeError("Could not find Opentrons app window")


def connect_playwright(
    *,
    debug_port: int | None = None,
    host: str | None = None,
) -> tuple[Playwright, Browser, Page]:
    """Connect Playwright to a running Opentrons app or ODD. Caller must stop Playwright."""
    cdp_host, cdp_port = resolve_cdp_endpoint(host=host, port=debug_port)
    playwright = sync_playwright().start()
    cdp_url = f"http://{cdp_host}:{cdp_port}"
    print(f"Connecting Playwright to {cdp_url}...")
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    page = _find_app_page(browser)
    try:
        page.bring_to_front()
    except Exception:
        # Remote ODD / headless targets may not support window focus.
        pass
    print(f"Connected to app window: '{page.title()}' ({page.url})")
    return playwright, browser, page


def connect_odd_playwright(
    *,
    host: str | None = None,
    debug_port: int | None = None,
) -> tuple[Playwright, Browser, Page]:
    """Attach to the Flex ODD over CDP (default port ``ODD_CDP_PORT`` / 9223).

    Host resolution order: ``host`` arg > ``CDP_HOST`` > ``ROBOT_IP`` /
    ``--robot-ip`` (via env set by fixtures) > ``DEFAULT_ROBOT_IP``.
    """
    from automation.app_helpers.robot_connection import resolve_robot_ip

    odd_host = (host or os.environ.get("CDP_HOST", "").strip() or resolve_robot_ip()).strip()
    odd_port = debug_port if debug_port is not None else None
    if odd_port is None:
        env_port = os.environ.get("CDP_PORT", "").strip()
        odd_port = int(env_port) if env_port else ODD_CDP_PORT
    print(f"ODD CDP target: {odd_host}:{odd_port}")
    if not _cdp_is_ready(odd_port, host=odd_host):
        raise TimeoutError(
            f"ODD CDP not reachable at http://{odd_host}:{odd_port}/json/version. "
            "Set ROBOT_IP / --robot-ip to the Flex address, enable Developer Tools "
            "on the ODD (Robot Settings), then retry."
        )
    return connect_playwright(host=odd_host, debug_port=odd_port)


def launch_and_connect(
    *, debug_port: int = DEBUG_PORT, quiet: bool = True, log_file: Path | None = None
) -> tuple[subprocess.Popen | None, Playwright, Browser, Page]:
    """Launch the packaged Opentrons app and connect Playwright over CDP."""
    if _cdp_is_ready(debug_port):
        print(f"CDP port {debug_port} already in use — attaching to running Opentrons")
        print("(App console output from an already-running instance is not captured.)")
        playwright, browser, page = connect_playwright(debug_port=debug_port)
        return None, playwright, browser, page
    process = launch_app(debug_port=debug_port, quiet=quiet, log_file=log_file)
    if log_file is not None:
        print(f"App console output redirected to {log_file}")
    playwright, browser, page = connect_playwright(debug_port=debug_port)
    return process, playwright, browser, page


def launch_dev_and_connect(
    *,
    debug_port: int = DEBUG_PORT,
    opentrons_project: str = "ot3",
    quiet: bool = True,
    log_file: Path | None = None,
) -> tuple[subprocess.Popen, Playwright, Browser, Page]:
    """Launch the dev app via ``make -C app dev`` and connect Playwright over CDP."""
    process = launch_dev_app(
        debug_port=debug_port,
        opentrons_project=opentrons_project,
        quiet=quiet,
        log_file=log_file,
    )
    if log_file is not None:
        print(f"App console output redirected to {log_file}")
    playwright, browser, page = connect_playwright(debug_port=debug_port)
    return process, playwright, browser, page


def prepare_app_page(page: Page) -> Page:
    """Dismiss blocking UI after attach."""
    dismiss_blocking_ui(page)
    return page


def should_attach_only() -> bool:
    """Return True when ``ATTACH=1`` and tests should skip launching the app."""
    return os.environ.get("ATTACH", "").strip().lower() in ("1", "true", "yes")
