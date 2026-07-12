"""Interface desktop do Compare Docs."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from desktop.controller import ComparisonController
from desktop.theme import (
    FONT_BODY,
    FONT_HEADING,
    FONT_LOGO,
    FONT_SMALL,
    FONT_TITLE,
    INNER_BG,
    PANEL_BG,
    POLL_MS,
    SURFACE_BG,
    animate_progress_bar,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORTED = (".docx", ".pdf")


class CompareDocsApp(ctk.CTk):
    """Aplicativo desktop nativo — mesmo engine da versão web."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = ComparisonController()
        self._job_id: Optional[str] = None
        self._polling = False
        self._current_tab = "single"
        self._result_cards: List[ctk.CTkFrame] = []

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Compare Docs")
        self.geometry("1120x760")
        self.minsize(960, 640)

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.update_idletasks()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        container = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        container.pack(fill="both", expand=True)

        self._sidebar = ctk.CTkFrame(container, width=220, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        self._main = ctk.CTkFrame(container, fg_color=SURFACE_BG, corner_radius=0)
        self._main.pack(side="right", fill="both", expand=True, padx=16, pady=16)
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(2, weight=1)

        self._header = ctk.CTkFrame(self._main, fg_color=SURFACE_BG)
        self._header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._title_label = ctk.CTkLabel(
            self._header, text="Arquivo único", font=FONT_TITLE, anchor="w"
        )
        self._title_label.pack(side="left")
        self._subtitle = ctk.CTkLabel(
            self._header,
            text="Compare documentos localmente — nada sai da sua máquina.",
            font=FONT_SMALL,
            text_color=("gray50", "gray60"),
            anchor="w",
        )
        self._subtitle.pack(side="left", padx=(16, 0))

        self._options_frame = self._build_options()
        self._options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._content = ctk.CTkFrame(self._main, fg_color=SURFACE_BG)
        self._content.grid(row=2, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._single_view = self._build_single_view()
        self._batch_view = self._build_batch_view()
        self._single_view.grid(row=0, column=0, sticky="nsew")

        self._progress_frame = ctk.CTkFrame(self._main, fg_color=SURFACE_BG)
        self._progress_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, height=10)
        self._progress_label = ctk.CTkLabel(
            self._progress_frame, text="", font=FONT_SMALL, anchor="w"
        )
        self._progress_frame.grid_remove()

        self._results_scroll = ctk.CTkScrollableFrame(
            self._main, label_text="Resultados", height=220
        )
        self._results_scroll.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        self._results_scroll.grid_remove()
        self._main.grid_rowconfigure(4, weight=0)

    def _build_sidebar(self) -> None:
        logo = ctk.CTkFrame(self._sidebar, fg_color=("#2563eb", "#1d4ed8"), corner_radius=12)
        logo.pack(padx=16, pady=(24, 20), fill="x")
        ctk.CTkLabel(logo, text="CD", font=FONT_LOGO, text_color="white").pack(
            pady=(14, 0)
        )
        ctk.CTkLabel(
            logo, text="Compare Docs", font=FONT_HEADING, text_color="white"
        ).pack(pady=(0, 14))

        self._nav_single = ctk.CTkButton(
            self._sidebar,
            text="  Arquivo único",
            anchor="w",
            height=40,
            command=lambda: self._switch_tab("single"),
        )
        self._nav_single.pack(fill="x", padx=12, pady=4)

        self._nav_batch = ctk.CTkButton(
            self._sidebar,
            text="  Lote (pastas)",
            anchor="w",
            height=40,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            command=lambda: self._switch_tab("batch"),
        )
        self._nav_batch.pack(fill="x", padx=12, pady=4)

        ctk.CTkFrame(self._sidebar, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=16, pady=16
        )

        ctk.CTkLabel(
            self._sidebar,
            text="Engine local\nPython · DOCX/PDF",
            font=FONT_SMALL,
            text_color=("gray45", "gray55"),
            justify="left",
        ).pack(anchor="w", padx=20)

        self._theme_btn = ctk.CTkButton(
            self._sidebar,
            text="Alternar tema",
            height=34,
            command=self._toggle_theme,
        )
        self._theme_btn.pack(side="bottom", fill="x", padx=16, pady=16)

    def _build_options(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, corner_radius=12)
        ctk.CTkLabel(frame, text="Opções de saída", font=FONT_HEADING).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 8)
        )

        self._opt_changed_pages = ctk.CTkCheckBox(frame, text="Só páginas alteradas (PDF)")
        self._opt_changed_pages.grid(row=1, column=0, padx=16, pady=6, sticky="w")

        self._opt_docx = ctk.CTkCheckBox(frame, text="Exportar DOCX editável")
        self._opt_docx.grid(row=1, column=1, padx=16, pady=6, sticky="w")

        self._opt_html = ctk.CTkCheckBox(frame, text="Relatório HTML")
        self._opt_html.select()
        self._opt_html.grid(row=1, column=2, padx=16, pady=6, sticky="w")

        self._opt_xlsx = ctk.CTkCheckBox(frame, text="Relatório Excel (.xlsx)")
        self._opt_xlsx.select()
        self._opt_xlsx.grid(row=1, column=3, padx=16, pady=6, sticky="w")

        self._opt_json = ctk.CTkCheckBox(frame, text="Relatório JSON")
        self._opt_json.grid(row=2, column=0, padx=16, pady=(6, 12), sticky="w")

        self._output_dir_var = tk.StringVar(value="")
        ctk.CTkLabel(frame, text="Pasta de saída (opcional):", font=FONT_SMALL).grid(
            row=2, column=1, columnspan=2, sticky="e", padx=8
        )
        self._output_entry = ctk.CTkEntry(
            frame, textvariable=self._output_dir_var, placeholder_text="Padrão: output/<data>-<job>/"
        )
        self._output_entry.grid(row=2, column=3, padx=(0, 8), pady=(6, 12), sticky="ew")
        ctk.CTkButton(frame, text="…", width=36, command=self._pick_output_dir).grid(
            row=2, column=4, padx=(0, 16), pady=(6, 12)
        )
        frame.grid_columnconfigure(3, weight=1)
        return frame

    def _build_single_view(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content, fg_color=SURFACE_BG)
        frame.grid_columnconfigure((0, 1), weight=1)

        self._base_path = tk.StringVar()
        self._compare_path = tk.StringVar()

        self._base_zone = self._file_zone(frame, "Documento base", self._base_path, 0, 0)
        self._compare_zone = self._file_zone(
            frame, "Documento revisado", self._compare_path, 0, 1
        )

        actions = ctk.CTkFrame(frame, fg_color=SURFACE_BG)
        actions.grid(row=1, column=0, columnspan=2, pady=16)
        ctk.CTkButton(
            actions, text="⇄  Inverter", width=120, command=self._swap_single
        ).pack(side="left", padx=6)
        self._compare_btn = ctk.CTkButton(
            actions,
            text="Comparar documentos",
            height=42,
            font=FONT_HEADING,
            command=self._run_single,
        )
        self._compare_btn.pack(side="left", padx=6)
        return frame

    def _build_batch_view(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content, fg_color=SURFACE_BG)
        frame.grid_columnconfigure((0, 1), weight=1)

        self._base_dir_var = tk.StringVar()
        self._compare_dir_var = tk.StringVar()

        self._folder_zone(frame, "Pasta base", self._base_dir_var, 0, 0)
        self._folder_zone(frame, "Pasta revisada", self._compare_dir_var, 0, 1)

        actions = ctk.CTkFrame(frame, fg_color=SURFACE_BG)
        actions.grid(row=1, column=0, columnspan=2, pady=16)
        ctk.CTkButton(
            actions, text="⇄  Inverter", width=120, command=self._swap_batch
        ).pack(side="left", padx=6)
        self._batch_btn = ctk.CTkButton(
            actions,
            text="Comparar pastas",
            height=42,
            font=FONT_HEADING,
            command=self._run_batch,
        )
        self._batch_btn.pack(side="left", padx=6)
        return frame

    def _file_zone(
        self, parent, title: str, var: tk.StringVar, row: int, col: int
    ) -> ctk.CTkFrame:
        zone = ctk.CTkFrame(parent, corner_radius=14, border_width=2,
                            border_color=("gray80", "gray35"))
        zone.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        zone.grid_columnconfigure(0, weight=1)
        zone.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(zone, text=title, font=FONT_HEADING).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4)
        )
        lbl = ctk.CTkLabel(
            zone,
            text="Arraste ou clique para selecionar\n.docx ou .pdf",
            font=FONT_SMALL,
            text_color=("gray50", "gray55"),
        )
        lbl.grid(row=1, column=0, padx=16, pady=8)

        path_lbl = ctk.CTkLabel(zone, textvariable=var, font=FONT_SMALL, wraplength=360)
        path_lbl.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

        btn = ctk.CTkButton(
            zone, text="Selecionar arquivo", command=lambda: self._pick_file(var, zone)
        )
        btn.grid(row=3, column=0, padx=16, pady=(0, 16))

        def on_click(_event=None):
            self._pick_file(var, zone)

        for widget in (zone, lbl):
            widget.bind("<Button-1>", on_click)
        var.trace_add("write", lambda *_: self._update_zone_state(zone, var.get()))
        return zone

    def _folder_zone(self, parent, title: str, var: tk.StringVar, row: int, col: int) -> None:
        zone = ctk.CTkFrame(parent, corner_radius=14, border_width=2,
                            border_color=("gray80", "gray35"))
        zone.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        zone.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(zone, text=title, font=FONT_HEADING).pack(anchor="w", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            zone, textvariable=var, font=FONT_SMALL, wraplength=360
        ).pack(anchor="w", padx=16, pady=4)
        ctk.CTkButton(
            zone, text="Selecionar pasta", command=lambda: self._pick_folder(var)
        ).pack(padx=16, pady=16)

    # ------------------------------------------------------------------
    # Interações
    # ------------------------------------------------------------------

    def _switch_tab(self, tab: str) -> None:
        self._current_tab = tab
        if tab == "single":
            self._title_label.configure(text="Arquivo único")
            self._batch_view.grid_remove()
            self._single_view.grid()
            self._nav_single.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self._nav_batch.configure(
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
            )
        else:
            self._title_label.configure(text="Lote (pastas)")
            self._single_view.grid_remove()
            self._batch_view.grid(row=0, column=0, sticky="nsew")
            self._nav_batch.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self._nav_single.configure(
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
            )

    def _toggle_theme(self) -> None:
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("dark" if mode == "Light" else "light")

    def _pick_file(self, var: tk.StringVar, zone: ctk.CTkFrame) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar documento",
            filetypes=[("Documentos", "*.docx *.pdf"), ("Todos", "*.*")],
        )
        if path:
            var.set(path)
            self._flash_zone(zone)

    def _pick_folder(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="Selecionar pasta")
        if path:
            var.set(path)

    def _pick_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Pasta de saída")
        if path:
            self._output_dir_var.set(path)

    def _flash_zone(self, zone: ctk.CTkFrame) -> None:
        zone.configure(border_color=("#2563eb", "#3b82f6"))
        zone.after(400, lambda: zone.configure(border_color=("gray80", "gray35")))

    def _update_zone_state(self, zone: ctk.CTkFrame, path: str) -> None:
        if path and os.path.isfile(path):
            zone.configure(border_color=("#16a34a", "#22c55e"))
        elif path:
            zone.configure(border_color=("#dc2626", "#ef4444"))
        else:
            zone.configure(border_color=("gray80", "gray35"))

    def _swap_single(self) -> None:
        a, b = self._base_path.get(), self._compare_path.get()
        self._base_path.set(b)
        self._compare_path.set(a)

    def _swap_batch(self) -> None:
        a, b = self._base_dir_var.get(), self._compare_dir_var.get()
        self._base_dir_var.set(b)
        self._compare_dir_var.set(a)

    def _get_options(self) -> Dict[str, Any]:
        out = self._output_dir_var.get().strip()
        return self.controller.build_options(
            changed_pages_only=bool(self._opt_changed_pages.get()),
            export_docx=bool(self._opt_docx.get()),
            report_html=bool(self._opt_html.get()),
            report_xlsx=bool(self._opt_xlsx.get()),
            report_json=bool(self._opt_json.get()),
            output_dir=out or None,
        )

    def _validate_file(self, path: str, label: str) -> bool:
        if not path or not os.path.isfile(path):
            messagebox.showerror("Arquivo inválido", "Selecione um %s válido (.docx ou .pdf)." % label)
            return False
        if not path.lower().endswith(SUPPORTED):
            messagebox.showerror("Formato", "Formato não suportado: %s" % path)
            return False
        return True

    def _run_single(self) -> None:
        base = self._base_path.get().strip()
        compare = self._compare_path.get().strip()
        if not self._validate_file(base, "documento base"):
            return
        if not self._validate_file(compare, "documento revisado"):
            return
        try:
            self._job_id = self.controller.start_single(base, compare, self._get_options())
            self._begin_polling()
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def _run_batch(self) -> None:
        base_dir = self._base_dir_var.get().strip()
        compare_dir = self._compare_dir_var.get().strip()
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("Pasta inválida", "Selecione a pasta base.")
            return
        if not compare_dir or not os.path.isdir(compare_dir):
            messagebox.showerror("Pasta inválida", "Selecione a pasta revisada.")
            return
        try:
            self._job_id, _pairs = self.controller.start_batch(
                base_dir, compare_dir, self._get_options()
            )
            self._begin_polling()
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def _begin_polling(self) -> None:
        self._polling = True
        self._compare_btn.configure(state="disabled")
        self._batch_btn.configure(state="disabled")
        self._clear_results()
        self._progress_frame.grid()
        self._progress_bar.pack(fill="x", pady=(0, 4))
        self._progress_label.pack(fill="x")
        self._progress_bar.set(0)
        self._poll_job()

    def _poll_job(self) -> None:
        if not self._polling or not self._job_id:
            return
        job = self.controller.get_job(self._job_id)
        if not job:
            self.after(POLL_MS, self._poll_job)
            return

        progress = job.get("progress") or {}
        done = progress.get("done", 0)
        total = max(1, progress.get("total", 1))
        current = progress.get("current", "")
        target = done / float(total)
        animate_progress_bar(self._progress_bar, target)
        self._progress_label.configure(
            text="%d de %d — %s" % (done, total, current or "processando…")
        )

        status = job.get("status")
        if status in ("done", "error"):
            self._polling = False
            self._compare_btn.configure(state="normal")
            self._batch_btn.configure(state="normal")
            if status == "error":
                messagebox.showerror("Erro no job", job.get("error", "Erro desconhecido."))
            self._show_results(job)
            return
        self.after(POLL_MS, self._poll_job)

    def _clear_results(self) -> None:
        for card in self._result_cards:
            card.destroy()
        self._result_cards.clear()
        self._results_scroll.grid_remove()

    def _show_results(self, job: Dict[str, Any]) -> None:
        self._clear_results()
        items = job.get("items") or []
        if not items:
            return
        self._results_scroll.grid()
        summary = job.get("summary") or {}
        header = ctk.CTkLabel(
            self._results_scroll,
            text="Concluído: %d ok · %d falha(s) · %.1fs"
            % (summary.get("ok", 0), summary.get("failed", 0), summary.get("seconds", 0)),
            font=FONT_HEADING,
        )
        header.pack(anchor="w", padx=8, pady=(0, 8))
        self._result_cards.append(header)

        for idx, item in enumerate(items):
            card = self._build_result_card(idx, item)
            card.pack(fill="x", padx=4, pady=6)
            self._result_cards.append(card)

    def _build_result_card(self, index: int, item: Dict[str, Any]) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self._results_scroll, corner_radius=12)
        pair = item.get("pair") or ["", ""]
        name = os.path.basename(pair[0]) if pair else "—"
        status = item.get("status", "error")

        top = ctk.CTkFrame(card, fg_color=INNER_BG)
        top.pack(fill="x", padx=12, pady=(12, 4))
        color = "#16a34a" if status == "ok" else "#dc2626"
        ctk.CTkLabel(top, text="●", text_color=color, font=FONT_BODY).pack(side="left")
        ctk.CTkLabel(top, text=name, font=FONT_HEADING).pack(side="left", padx=6)

        if status == "error":
            ctk.CTkLabel(
                card, text=item.get("error", "Erro"), font=FONT_SMALL, text_color="#dc2626",
                wraplength=700, justify="left",
            ).pack(anchor="w", padx=12, pady=(0, 12))
            return card

        stats = item.get("stats") or {}
        stats_text = "%d conteúdo · %d ruído · %d formatação · %d tabela(s)" % (
            stats.get("content_changes", 0),
            stats.get("noise_changes", 0),
            stats.get("formatting_changes", 0),
            stats.get("table_changes", 0),
        )
        ctk.CTkLabel(card, text=stats_text, font=FONT_SMALL).pack(anchor="w", padx=12, pady=2)

        btns = ctk.CTkFrame(card, fg_color=INNER_BG)
        btns.pack(fill="x", padx=12, pady=(8, 12))
        outputs = item.get("outputs") or {}

        if outputs.get("pdf"):
            ctk.CTkButton(
                btns, text="Abrir PDF", width=110,
                command=lambda p=outputs["pdf"]: self._open_safe(p),
            ).pack(side="left", padx=4)
        if outputs.get("xlsx"):
            ctk.CTkButton(
                btns, text="Abrir Excel", width=110,
                command=lambda p=outputs["xlsx"]: self._open_safe(p),
            ).pack(side="left", padx=4)
        if outputs.get("html"):
            ctk.CTkButton(
                btns, text="Abrir HTML", width=110,
                command=lambda p=outputs["html"]: self._open_safe(p),
            ).pack(side="left", padx=4)
        if outputs.get("docx"):
            ctk.CTkButton(
                btns, text="Abrir DOCX", width=110,
                command=lambda p=outputs["docx"]: self._open_safe(p),
            ).pack(side="left", padx=4)
        if outputs.get("pdf"):
            folder = os.path.dirname(outputs["pdf"])
            ctk.CTkButton(
                btns, text="Pasta", width=80,
                command=lambda f=folder: self._open_safe(f),
            ).pack(side="left", padx=4)
        ctk.CTkButton(
            btns, text="Ver mudanças", width=120,
            command=lambda i=index: self._show_changes(i),
        ).pack(side="right", padx=4)
        return card

    def _open_safe(self, path: str) -> None:
        try:
            self.controller.open_path(path)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def _show_changes(self, index: int) -> None:
        if not self._job_id:
            return
        data = self.controller.get_result(self._job_id, index)
        if not data:
            messagebox.showinfo("Mudanças", "Resultado não disponível.")
            return
        changes = data.get("changes") or []
        win = ctk.CTkToplevel(self)
        win.title("Mudanças detectadas")
        win.geometry("900x560")
        win.grab_set()

        scroll = ctk.CTkScrollableFrame(win, label_text="%d alterações" % len(changes))
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        for ch in changes:
            row = ctk.CTkFrame(scroll, corner_radius=8)
            row.pack(fill="x", pady=4)
            title = "#%s · %s · %s" % (
                ch.get("id", "?"),
                ch.get("change_type", ""),
                ch.get("category", ""),
            )
            ctk.CTkLabel(row, text=title, font=FONT_HEADING, anchor="w").pack(
                fill="x", padx=10, pady=(8, 2)
            )
            ctk.CTkLabel(
                row, text=ch.get("summary", ""), font=FONT_SMALL, anchor="w"
            ).pack(fill="x", padx=10)
            old_t = (ch.get("old_text") or "")[:200]
            new_t = (ch.get("new_text") or "")[:200]
            if old_t or new_t:
                ctk.CTkLabel(
                    row,
                    text="− %s\n+ %s" % (old_t, new_t),
                    font=FONT_SMALL,
                    justify="left",
                    anchor="w",
                ).pack(fill="x", padx=10, pady=(4, 10))

    def _on_close(self) -> None:
        self._polling = False
        self.destroy()


def main() -> None:
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    app = CompareDocsApp()
    app.mainloop()


if __name__ == "__main__":
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    main()
