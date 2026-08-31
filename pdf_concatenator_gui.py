from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pypdf import PdfWriter

from backend.app.core_logic import (
    PDFItem,
    decode_unicode_escapes_for_display,
    lecture_name_sort_key,
)


class PDFConcatenatorApp:
    SORT_BY_NAME = "By lecture name (numeric-aware)"
    SORT_BY_MTIME_ASC = "By modified date-time (ascending)"
    SORT_BY_MTIME_DESC = "By modified date-time (descending)"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Lecture Concatenator")
        self.root.geometry("1100x680")
        self.root.minsize(920, 560)

        self.selected_folder = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="")
        self.sort_mode = tk.StringVar(value=self.SORT_BY_NAME)
        self.status_text = tk.StringVar(value="Pick a folder to begin.")

        self.available_items: list[PDFItem] = []
        self.queue_items: list[PDFItem] = []
        self.list_font = ("DejaVu Sans", 10)

        self._build_ui()

        default_folder = Path("lectures")
        if default_folder.exists() and default_folder.is_dir():
            self.selected_folder.set(str(default_folder.resolve()))
            self.refresh_files()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        folder_frame = ttk.LabelFrame(main, text="Folder")
        folder_frame.pack(fill=tk.X)
        ttk.Entry(folder_frame, textvariable=self.selected_folder).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 6), pady=10
        )
        ttk.Button(folder_frame, text="Browse...", command=self.pick_folder).pack(
            side=tk.LEFT, padx=(0, 10), pady=10
        )

        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(10, 8))
        ttk.Label(controls, text="Sort available files:").pack(side=tk.LEFT)
        sort_combo = ttk.Combobox(
            controls,
            state="readonly",
            width=38,
            textvariable=self.sort_mode,
            values=[
                self.SORT_BY_NAME,
                self.SORT_BY_MTIME_ASC,
                self.SORT_BY_MTIME_DESC,
            ],
        )
        sort_combo.pack(side=tk.LEFT, padx=(8, 8))
        sort_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_files())

        ttk.Button(controls, text="Reload Folder", command=self.refresh_files).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(
            controls,
            text="Set Queue = Current Sort",
            command=self.set_queue_to_current_sort,
        ).pack(side=tk.LEFT)

        list_section = ttk.Frame(main)
        list_section.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.LabelFrame(list_section, text="Available PDFs")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.available_list = tk.Listbox(
            left_panel,
            selectmode=tk.EXTENDED,
            activestyle="none",
            exportselection=False,
            font=self.list_font,
        )
        avail_scroll = ttk.Scrollbar(
            left_panel, orient=tk.VERTICAL, command=self.available_list.yview
        )
        self.available_list.config(yscrollcommand=avail_scroll.set)
        self.available_list.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10
        )
        avail_scroll.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)

        middle_actions = ttk.Frame(list_section)
        middle_actions.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(
            middle_actions,
            text="Add Selected ->",
            command=self.add_selected_to_queue,
            width=18,
        ).pack(pady=(120, 8))
        ttk.Button(
            middle_actions,
            text="Add All ->",
            command=self.add_all_to_queue,
            width=18,
        ).pack(pady=8)

        right_panel = ttk.LabelFrame(list_section, text="Merge Queue (custom order)")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.queue_list = tk.Listbox(
            right_panel,
            selectmode=tk.EXTENDED,
            activestyle="none",
            exportselection=False,
            font=self.list_font,
        )
        queue_scroll = ttk.Scrollbar(
            right_panel, orient=tk.VERTICAL, command=self.queue_list.yview
        )
        self.queue_list.config(yscrollcommand=queue_scroll.set)
        self.queue_list.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10
        )
        queue_scroll.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)

        queue_actions = ttk.Frame(right_panel)
        queue_actions.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=10)
        ttk.Button(
            queue_actions,
            text="Remove",
            width=14,
            command=self.remove_selected_from_queue,
        ).pack(pady=(0, 8))
        ttk.Button(
            queue_actions, text="Move Up", width=14, command=self.move_selected_up
        ).pack(pady=8)
        ttk.Button(
            queue_actions, text="Move Down", width=14, command=self.move_selected_down
        ).pack(pady=8)
        ttk.Button(
            queue_actions, text="Clear", width=14, command=self.clear_queue
        ).pack(pady=8)

        output_frame = ttk.LabelFrame(main, text="Output")
        output_frame.pack(fill=tk.X, pady=(10, 8))
        ttk.Entry(output_frame, textvariable=self.output_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 6), pady=10
        )
        ttk.Button(output_frame, text="Browse...", command=self.pick_output_file).pack(
            side=tk.LEFT, padx=(0, 10), pady=10
        )

        footer = ttk.Frame(main)
        footer.pack(fill=tk.X)
        ttk.Label(footer, textvariable=self.status_text).pack(side=tk.LEFT)
        ttk.Button(footer, text="Merge Queue", command=self.merge_queue).pack(
            side=tk.RIGHT
        )

    def pick_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select folder with PDFs")
        if not selected:
            return
        self.selected_folder.set(selected)
        self.refresh_files()

    def pick_output_file(self) -> None:
        initial = self.output_path.get().strip() or "merged_lectures.pdf"
        selected = filedialog.asksaveasfilename(
            title="Save merged PDF as",
            defaultextension=".pdf",
            initialfile=Path(initial).name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if selected:
            self.output_path.set(selected)

    def refresh_files(self) -> None:
        folder_str = self.selected_folder.get().strip()
        if not folder_str:
            self.status_text.set("Choose a folder first.")
            return

        folder = Path(folder_str)
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror(
                "Invalid folder", "The selected folder does not exist."
            )
            return

        candidates = [PDFItem(path=p) for p in folder.glob("*.pdf") if p.is_file()]
        self.available_items = self._sort_items(candidates)
        self._populate_available_list()

        if not self.output_path.get().strip():
            self.output_path.set(str((folder / "merged_lectures.pdf").resolve()))

        self.status_text.set(
            f"Loaded {len(self.available_items)} PDFs from {folder}. Queue has {len(self.queue_items)} file(s)."
        )

    def _sort_items(self, items: list[PDFItem]) -> list[PDFItem]:
        mode = self.sort_mode.get()
        if mode == self.SORT_BY_MTIME_ASC:
            return sorted(items, key=lambda item: (item.mtime, item.stem.casefold()))
        if mode == self.SORT_BY_MTIME_DESC:
            return sorted(
                items, key=lambda item: (item.mtime, item.stem.casefold()), reverse=True
            )
        return sorted(items, key=lecture_name_sort_key)

    def _populate_available_list(self) -> None:
        self.available_list.delete(0, tk.END)
        for idx, item in enumerate(self.available_items, start=1):
            display_name = decode_unicode_escapes_for_display(item.path.name)
            label = f"{idx:03d}. {display_name}   [{item.mtime_label}]"
            self.available_list.insert(tk.END, label)

    def _populate_queue_list(self) -> None:
        self.queue_list.delete(0, tk.END)
        for idx, item in enumerate(self.queue_items, start=1):
            display_name = decode_unicode_escapes_for_display(item.path.name)
            label = f"{idx:03d}. {display_name}"
            self.queue_list.insert(tk.END, label)

    def set_queue_to_current_sort(self) -> None:
        self.queue_items = list(self.available_items)
        self._populate_queue_list()
        self.status_text.set(
            f"Queue reset from current sort with {len(self.queue_items)} file(s)."
        )

    def add_selected_to_queue(self) -> None:
        selected_indices = self.available_list.curselection()
        if not selected_indices:
            self.status_text.set("Select one or more files in Available PDFs.")
            return

        existing_paths = {item.path for item in self.queue_items}
        added = 0
        for index in selected_indices:
            candidate = self.available_items[index]
            if candidate.path not in existing_paths:
                self.queue_items.append(candidate)
                existing_paths.add(candidate.path)
                added += 1

        self._populate_queue_list()
        self.status_text.set(
            f"Added {added} file(s) to queue. Queue size: {len(self.queue_items)}."
        )

    def add_all_to_queue(self) -> None:
        existing_paths = {item.path for item in self.queue_items}
        added = 0
        for item in self.available_items:
            if item.path not in existing_paths:
                self.queue_items.append(item)
                existing_paths.add(item.path)
                added += 1

        self._populate_queue_list()
        self.status_text.set(
            f"Added {added} file(s). Queue size: {len(self.queue_items)}."
        )

    def remove_selected_from_queue(self) -> None:
        selected = list(self.queue_list.curselection())
        if not selected:
            self.status_text.set("Select one or more files in queue to remove.")
            return

        for idx in reversed(selected):
            del self.queue_items[idx]
        self._populate_queue_list()
        self.status_text.set(
            f"Removed {len(selected)} file(s). Queue size: {len(self.queue_items)}."
        )

    def clear_queue(self) -> None:
        self.queue_items.clear()
        self._populate_queue_list()
        self.status_text.set("Queue cleared.")

    def move_selected_up(self) -> None:
        selected = list(self.queue_list.curselection())
        if not selected:
            return

        for idx in selected:
            if idx > 0 and (idx - 1) not in selected:
                self.queue_items[idx - 1], self.queue_items[idx] = (
                    self.queue_items[idx],
                    self.queue_items[idx - 1],
                )

        self._populate_queue_list()
        for idx in [max(0, i - 1) for i in selected]:
            self.queue_list.selection_set(idx)

    def move_selected_down(self) -> None:
        selected = list(self.queue_list.curselection())
        if not selected:
            return

        selected_set = set(selected)
        for idx in reversed(selected):
            if idx < len(self.queue_items) - 1 and (idx + 1) not in selected_set:
                self.queue_items[idx + 1], self.queue_items[idx] = (
                    self.queue_items[idx],
                    self.queue_items[idx + 1],
                )

        self._populate_queue_list()
        for idx in [min(len(self.queue_items) - 1, i + 1) for i in selected]:
            self.queue_list.selection_set(idx)

    def merge_queue(self) -> None:
        if not self.queue_items:
            messagebox.showwarning("Empty queue", "Add files to queue before merging.")
            return

        output_str = self.output_path.get().strip()
        if not output_str:
            messagebox.showwarning("Output required", "Choose an output PDF path.")
            return

        output_path = Path(output_str)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            overwrite = messagebox.askyesno(
                "Overwrite output?",
                f"{output_path} already exists. Overwrite it?",
            )
            if not overwrite:
                self.status_text.set("Merge canceled (output exists).")
                return

        self.status_text.set("Merging PDFs... please wait.")
        self.root.update_idletasks()

        writer = PdfWriter()
        try:
            for item in self.queue_items:
                if not item.path.exists():
                    raise FileNotFoundError(f"Missing file: {item.path}")
                writer.append(str(item.path))

            with output_path.open("wb") as out_file:
                writer.write(out_file)
        except Exception as error:
            messagebox.showerror("Merge failed", f"Could not merge files.\n\n{error}")
            self.status_text.set("Merge failed.")
            return
        finally:
            writer.close()

        self.status_text.set(
            f"Success. Merged {len(self.queue_items)} file(s) to {output_path}."
        )
        messagebox.showinfo("Done", f"Merged PDF created:\n{output_path}")


def main() -> None:
    root = tk.Tk()
    # Some environments default Tk to a non-UTF-8 system encoding.
    # This makes non-Latin text appear as literal \uXXXX escapes.
    try:
        root.tk.call("encoding", "system", "utf-8")
    except tk.TclError:
        pass
    PDFConcatenatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
