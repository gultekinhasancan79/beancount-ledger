"""Ledger Replay in a native window: docs/replay.html hosted by pywebview (WebView2 on Windows).

This is the modern front end of `tests/replay_desktop.py`; run that script. The
window is native (no browser, no address bar); the page inside it is the same
static replay viewer that docs/replay.html publishes, plus a live-run panel
that talks to Python through pywebview's JS bridge:

    page  --(window.pywebview.api.start_run / stop_run / health / summary / export …)-->  Api
    Api   --(window.evaluate_js('replay.onEvent({...})'))-->                             page

The engine (LiveRun, demo endpoint, scoring, aggregation, exports) lives in
replay_desktop.py and is shared with the classic tkinter window. A batch (queue)
of tasks is driven by the page: every item is one ordinary start_run, started
when the previous item's terminal event has arrived.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_replay as br  # noqa: E402
import replay_desktop as rd  # noqa: E402

PAGE = ROOT / "docs" / "replay.html"


WORKFLOWS = ("bank_recon", "ap_payment_run", "ar_collections", "bank_feed_categorisation", "expense_reports",
             "payroll", "sales_tax_remittance", "fixed_assets", "intercompany_transfers", "month_end_close")


def _workflow_label(task_id: str) -> str:
    """'ap_payment_run_001' / 'ap_payment_run_ironwood' -> 'AP payment run'."""
    base = next((w for w in sorted(WORKFLOWS, key=len, reverse=True) if task_id == w or task_id.startswith(w + "_")), None)
    words = (base or task_id).split("_")
    return " ".join(w.upper() if w in ("ap", "ar") else w for w in words)


class Api:
    """What the page may call. pywebview invokes these on worker threads."""

    # Everything that is not part of the JS API starts with an underscore: pywebview
    # walks the public attributes of this object to expose them to the page, and a
    # Window reference in there would send it into an endless recursion.
    def __init__(self, demo_url: str | None, autorun: bool = False):
        self._demo_url = demo_url
        self._autorun = autorun
        self._events: queue.Queue = queue.Queue()
        self._run: rd.LiveRun | None = None
        self._window = None
        # runs of this session that were NOT saved to disk (demo runs, "Save" unticked): the
        # summary still counts them; saved ones are re-read from outputs/evals like any other
        self._unsaved_session: list[dict] = []
        self._lock = threading.Lock()

    def health(self) -> dict:
        # generated selectors: training worlds only. The desktop is for development,
        # training and inspection; evaluation worlds (eval:<n>) belong to the sealed
        # benchmark interface, so they are not offered here (any other selector can be typed).
        generated = ["train:0", "train:1", "train:7", "train:12", "train:30",
                     "train:0:hard", "train:3:hard", "train:7:hard"]
        # the hand-authored worlds, each with the workflow tasks it carries
        worlds: dict = {}
        for task_id in sorted(rd.REGISTRY):
            world, task = rd.REGISTRY[task_id]
            entry = worlds.setdefault(world.id, {"id": world.id, "title": world.title.split(" - FY")[0], "period": task.period.label, "tasks": []})
            entry["tasks"].append({"id": task_id, "label": _workflow_label(task_id)})
        return {"ok": True, "tasks": sorted(rd.REGISTRY) + generated, "worlds": list(worlds.values()),
                "demo_url": self._demo_url, "autorun": self._autorun, "repo": str(ROOT),
                "key_vars": rd.known_key_vars(),   # names only; values never leave Python
                "budget_defaults": {"max_turns": rd.DEFAULT_MAX_TURNS, "max_episode_tokens": rd.DEFAULT_EPISODE_TOKENS},
                "run_budgets": self._run_budgets(),
                "platform": sys.platform}

    @staticmethod
    def _run_budgets() -> dict:
        """run id -> budget, for the saved runs that were NOT run under the shipped budget (the page tags them)."""
        out = {}
        for rec in rd.load_run_records():
            b = rec.get("budget")
            if b and not b.get("default", True):
                out[rec["id"]] = b
        return out

    def start_run(self, cfg: dict) -> dict:
        prev = self._run
        if prev is not None and prev.thread is not None and prev.thread.is_alive():
            # a queue starts the next item on the previous item's terminal event, which is emitted
            # a few milliseconds before that worker thread has closed its event loop: wait for it
            if prev.finished:
                prev.thread.join(timeout=15)
            if prev.thread.is_alive():
                return {"error": "a run is already in progress; stop it first"}
        try:
            cfg = dict(cfg or {})
            cfg["task"] = (cfg.get("task") or rd.DEFAULT_TASK).strip()
            cfg["max_tokens"] = int(cfg.get("max_tokens") or 8000)
            cfg["max_turns"] = int(cfg.get("max_turns") or rd.DEFAULT_MAX_TURNS)
            cfg["max_episode_tokens"] = int(cfg.get("max_episode_tokens") or rd.DEFAULT_EPISODE_TOKENS)
            cfg["max_retries"] = int(cfg.get("max_retries") or 1)
            cfg["strict_schema"] = bool(cfg.get("strict_schema"))
            run = rd.LiveRun(cfg, self._events)
            with rd.signal_tolerant():   # the env registers signal handlers, which only the main thread may do
                run.start()
            self._run = run
        except Exception as exc:  # noqa: BLE001 - the page shows the reason
            self._run = None
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {"ok": True, "budget": run.budget}

    def list_models(self, cfg: dict) -> dict:
        cfg = dict(cfg or {})
        return rd.list_models(str(cfg.get("base_url") or ""), str(cfg.get("api_key") or ""))

    def stop_run(self) -> dict:
        if self._run is not None:
            self._run.stop()
        return {"ok": True}

    # ---- results across runs
    def _records(self) -> list[dict]:
        with self._lock:
            session = list(self._unsaved_session)
        return rd.load_run_records() + session

    def summary(self) -> dict:
        """The aggregate over outputs/evals plus this session's unsaved runs, and its Markdown rendering."""
        try:
            s = rd.summarize_runs(self._records())
            return {"ok": True, "summary": s, "markdown": rd.summary_markdown(s), "evals_dir": str(rd.EVALS.relative_to(ROOT)).replace("\\", "/")}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def export(self, payload: dict) -> dict:
        """Write the summary and the selected run's timeline to outputs/evals/exports/<timestamp>.{md,csv}."""
        try:
            payload = dict(payload or {})
            s = rd.summarize_runs(self._records())
            paths = rd.write_exports(s, payload.get("timeline"))
            return {"ok": True, **paths}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def copy_text(self, text: str) -> dict:
        """Clipboard fallback for when the page's own navigator.clipboard is refused."""
        try:
            return {"ok": True, "via": rd.copy_to_clipboard(str(text or ""))}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    def queue_done(self, info: dict) -> dict:
        """The page reports the end of a batch. Under --demo --autorun the outcome is printed so a
        headless smoke can read it, and PIV_REPLAY_AUTOEXIT=1 closes the window afterwards."""
        info = dict(info or {})
        if self._autorun:
            print("AUTORUN QUEUE DONE " + json.dumps(info, default=str), flush=True)
            if os.environ.get("PIV_REPLAY_AUTOEXIT") and self._window is not None:
                threading.Timer(1.0, self._window.destroy).start()
        return {"ok": True}

    def _note_done(self, ev: dict) -> None:
        """Keep an unsaved finished run of this session for the summary (a saved one is on disk already)."""
        if ev.get("saved_to"):
            return
        row = ev.get("row") or {}
        model = ev.get("model") or (self._run.cfg.get("model") if self._run else None) or "?"
        rec = {"id": "session-" + str(len(self._unsaved_session) + 1), "dir": "", "model": model,
               "rows": [row] if row else [], "quarantined": bool(ev.get("quarantined")),
               "budget": ev.get("budget"), "desktop": None, "time": None}
        if not rec["rows"] and not rec["quarantined"]:
            rec["quarantined"] = True   # ended without a row: not a scored run
        with self._lock:
            self._unsaved_session.append(rec)


def _pump(api: Api) -> None:
    """Forward engine events to the page, in order, from a single thread."""
    while True:
        ev = api._events.get()
        if ev.get("type") == "done":
            try:
                api._note_done(ev)
            except Exception:  # noqa: BLE001 - bookkeeping must never stall the pump
                pass
        if api._window is None:
            continue
        try:
            api._window.evaluate_js("window.replay && window.replay.onEvent(" + json.dumps(ev, default=str) + ")")
        except Exception:  # noqa: BLE001 - the window may be closing
            pass


def main(demo: bool = False, autorun: bool = False, rebuild: bool = True) -> int:
    import webview  # noqa: PLC0415 - optional dependency; replay_desktop falls back to tkinter without it

    if rebuild or not PAGE.exists():
        try:
            br.build(check=False)   # embed every saved run so the picker is current
        except SystemExit:
            pass
    if not PAGE.exists():
        print(f"{PAGE} is missing and could not be built", file=sys.stderr)
        return 2
    demo_url = rd.start_demo_server() if demo else None
    api = Api(demo_url, autorun=autorun and demo)
    window = webview.create_window("Ledger Replay", url=PAGE.as_uri(), js_api=api, width=1480, height=960,
                                   min_size=(1000, 640), background_color="#f3f5f8", text_select=True)
    api._window = window
    threading.Thread(target=_pump, args=(api,), name="ledger-replay-events", daemon=True).start()
    # WebView2 on Windows (the renderer this page is tested in); elsewhere pywebview picks the
    # platform's own engine (WebKit on macOS, GTK/Qt WebKit on Linux) — gui=None means "choose".
    webview.start(gui="edgechromium" if sys.platform == "win32" else None, private_mode=True)
    if api._run is not None:
        api._run.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main(demo="--demo" in sys.argv, autorun="--autorun" in sys.argv))
