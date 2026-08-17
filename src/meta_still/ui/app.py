"""The meta-still desktop window.

A composition root with a mouse: it picks folders, wires the same use-cases the
CLI wires, and draws what they report. No pipeline logic lives here.
"""

from __future__ import annotations

import os
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from meta_still.ui.runner import BackgroundJob, Finished, Log, Step
from meta_still.ui.settings import load_settings, save_settings

PAD = 10


class MetaStillApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("meta-still")
        self.minsize(720, 520)

        self.job = BackgroundJob()
        self.settings = load_settings()
        self.started_at = 0.0
        self.sheet_path: Path | None = None
        self.output_path: Path | None = None

        self.source = tk.StringVar(value=self.settings["source"])
        self.output = tk.StringVar(value=self.settings["output"])
        self.count = tk.IntVar(value=self.settings["count"])
        self.force = tk.BooleanVar(value=self.settings["force"])
        self.sheet = tk.BooleanVar(value=self.settings["sheet"])
        self.status = tk.StringVar(value="Choose a folder to ingest.")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # -- layout ----------------------------------------------------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        form = ttk.Frame(self, padding=PAD)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        self._folder_row(form, 0, "Source folder", self.source, self._pick_source)
        self._folder_row(form, 1, "Output folder", self.output, self._pick_output)

        options = ttk.Frame(form)
        options.grid(row=2, column=0, columnspan=3, sticky="w", pady=(PAD, 0))
        ttk.Label(options, text="Thumbnails per clip").pack(side="left")
        ttk.Spinbox(options, from_=1, to=50, width=5, textvariable=self.count).pack(
            side="left", padx=(6, PAD * 2)
        )
        ttk.Checkbutton(
            options, text="Redo clips already done", variable=self.force
        ).pack(side="left", padx=(0, PAD * 2))
        ttk.Checkbutton(
            options, text="Build contact sheet", variable=self.sheet
        ).pack(side="left")

        actions = ttk.Frame(self, padding=(PAD, 0))
        actions.grid(row=1, column=0, sticky="ew")
        self.start_button = ttk.Button(actions, text="Start", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(
            actions, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=6)
        self.open_sheet_button = ttk.Button(
            actions, text="Open contact sheet", command=self._open_sheet, state="disabled"
        )
        self.open_sheet_button.pack(side="right")
        self.open_folder_button = ttk.Button(
            actions, text="Open output folder", command=self._open_folder, state="disabled"
        )
        self.open_folder_button.pack(side="right", padx=6)

        bar = ttk.Frame(self, padding=(PAD, PAD))
        bar.grid(row=2, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bar, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, textvariable=self.status).grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )

        log_frame = ttk.Frame(self, padding=(PAD, 0, PAD, PAD))
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, wrap="none", height=12, state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

    def _folder_row(self, parent, row, label, variable, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=6, pady=3
        )
        ttk.Button(parent, text="Browse…", command=command).grid(row=row, column=2, pady=3)

    # -- actions ---------------------------------------------------------

    def _pick_source(self) -> None:
        chosen = filedialog.askdirectory(title="Folder to ingest", initialdir=self.source.get() or None)
        if chosen:
            self.source.set(os.path.normpath(chosen))

    def _pick_output(self) -> None:
        chosen = filedialog.askdirectory(title="Where to write the results", initialdir=self.output.get() or None)
        if chosen:
            self.output.set(os.path.normpath(chosen))

    def _start(self) -> None:
        source = Path(self.source.get().strip('" '))
        output = Path(self.output.get().strip('" '))

        if not source.is_dir():
            messagebox.showerror("meta-still", f"Not a folder:\n{source}")
            return
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("meta-still", f"Cannot write to:\n{output}\n\n{exc}")
            return

        self._remember()
        self._clear_log()
        self.sheet_path = None
        self.output_path = output
        self.started_at = time.monotonic()
        self.progress.configure(value=0, maximum=100)
        self.status.set("Scanning…")
        self._busy(True)

        self.job.start(
            _pipeline_work(
                source=source,
                output=output,
                count=self.count.get(),
                force=self.force.get(),
                with_sheet=self.sheet.get(),
            )
        )

    def _cancel(self) -> None:
        self.job.cancel()
        self.status.set("Finishing the current clip, then stopping…")
        self.cancel_button.configure(state="disabled")

    def _open_sheet(self) -> None:
        if self.sheet_path:
            webbrowser.open(self.sheet_path.as_uri())

    def _open_folder(self) -> None:
        if self.output_path:
            webbrowser.open(self.output_path.as_uri())

    def _on_close(self) -> None:
        if self.job.running and not messagebox.askokcancel(
            "meta-still", "A run is in progress. Close anyway?"
        ):
            return
        self._remember()
        self.destroy()

    # -- event pump ------------------------------------------------------

    def _poll(self) -> None:
        for event in self.job.drain():
            if isinstance(event, Log):
                self._append(event.text)
            elif isinstance(event, Step):
                self._advance(event)
            elif isinstance(event, Finished):
                self._finish(event)
        self.after(100, self._poll)

    def _advance(self, step: Step) -> None:
        self.progress.configure(maximum=step.total, value=step.done)
        elapsed = time.monotonic() - self.started_at
        remaining = ""
        if step.done:
            seconds = (elapsed / step.done) * (step.total - step.done)
            remaining = f" · about {seconds / 60:.0f} min left"
        self.status.set(f"{step.done} of {step.total} clips{remaining}")

    def _finish(self, event: Finished) -> None:
        self._busy(False)
        if event.error:
            self.status.set("Failed.")
            messagebox.showerror("meta-still", event.error)
            return

        summary = event.value or {}
        self.sheet_path = summary.get("sheet")
        self.progress.configure(value=self.progress["maximum"])
        self.status.set(summary.get("status", "Done."))
        self.open_folder_button.configure(state="normal")
        self.open_sheet_button.configure(
            state="normal" if self.sheet_path else "disabled"
        )

    # -- small helpers ---------------------------------------------------

    def _busy(self, busy: bool) -> None:
        self.start_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _remember(self) -> None:
        save_settings(
            {
                "source": self.source.get(),
                "output": self.output.get(),
                "count": self.count.get(),
                "force": self.force.get(),
                "sheet": self.sheet.get(),
            }
        )


def _pipeline_work(
    *, source: Path, output: Path, count: int, force: bool, with_sheet: bool
):
    """Build the closure the worker thread runs.

    Imports live inside it so the window opens instantly: pulling in moviepy
    costs a second or two, and that should not be dead time on a blank screen.
    """

    def work(report, cancelled):
        from meta_still.contactsheet.interfaces.cli import build as build_sheet
        from meta_still.mapper.application.scan_folder import ScanFolder
        from meta_still.mapper.infrastructure.os_filesystem import OsFileSystem
        from meta_still.orchestrator.application.ingest_folder import (
            IngestFolder,
            IngestRequest,
        )
        from meta_still.stills.application.generate_stills import GenerateStills
        from meta_still.stills.infrastructure.moviepy_frame_source import (
            MoviePyFrameSource,
        )

        pipeline = IngestFolder(
            scan=ScanFolder(filesystem=OsFileSystem()),
            stills=GenerateStills(frames=MoviePyFrameSource()),
            progress=lambda message: report(Log(message)),
            on_step=lambda done, total: report(Step(done, total)),
            should_stop=cancelled,
        )
        result = pipeline.execute(
            IngestRequest(
                root=source, output_dir=output, stills_per_clip=count, force=force
            )
        )

        sheet = None
        if with_sheet and not result.stopped:
            report(Log(""))
            sheet = build_sheet(output, progress=lambda m: report(Log(m)))

        status = (
            f"Stopped · {len(result.done)} done, {len(result.skipped)} skipped, "
            f"{len(result.failures)} failed"
            if result.stopped
            else f"Done · {len(result.done)} processed, {len(result.skipped)} skipped, "
            f"{len(result.failures)} failed"
        )
        report(Log(""))
        report(Log(status))
        for outcome in result.failures:
            report(Log(f"    {outcome.source.name}: {outcome.error}"))

        return {"sheet": sheet, "status": status}

    return work


def main() -> int:
    MetaStillApp().mainloop()
    return 0
