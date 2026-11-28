import json
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BACKGROUND = "#f3f6f1"
PANEL = "#ffffff"
TEXT = "#1c2921"
MUTED = "#405246"
TOPBAR = "#1e3327"
ACCENT = "#245537"
ERROR = "#9c2e24"

ORDER_FIELDS = ("erp_order_id", "shop_order_id", "sku", "quantity")


def request_json(base_url: str, path: str, method: str = "GET"):
    request = Request(base_url + path, method=method)
    try:
        with urlopen(request, timeout=6) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            try:
                detail = json.load(error).get("detail")
            except (ValueError, AttributeError):
                detail = None
        message = detail if isinstance(detail, str) else f"ERP-Anfrage fehlgeschlagen (HTTP {error.code})."
        raise RuntimeError(message) from error
    except (OSError, ValueError) as error:
        raise RuntimeError("Die ERP-API antwortet nicht wie erwartet.") from error


def matching_orders(orders, search: str):
    query = search.strip().casefold()
    return [
        order for order in orders
        if any(query in order[field].casefold() for field in ORDER_FIELDS[:3])
    ]


class ErpWindow:
    def __init__(self, root: tk.Tk, base_url: str):
        self.root = root
        self.base_url = base_url
        self.orders = []
        self.busy = False
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.shop_number = tk.StringVar(root)
        self.search = tk.StringVar(root)
        self.status = tk.StringVar(root)
        self.result_count = tk.StringVar(root)

        self.root.title("Python Fitness ERP")
        self.root.geometry("980x610")
        self.root.minsize(690, 460)
        self.root.configure(background=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.configure_style()
        self.build_window()
        self.search.trace_add("write", self.render_orders)
        self.refresh_orders()

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground=TEXT)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Panel.TLabel", background=PANEL)
        style.configure("Section.TLabel", background=PANEL, font=("Segoe UI", 12, "bold"))
        style.configure("TEntry", padding=(9, 7))
        style.configure("TButton", padding=(12, 7))
        style.configure("Import.TButton", background=ACCENT, foreground="white")
        style.map("Import.TButton", background=[("disabled", "#87a18e"), ("active", "#19432b")])
        style.configure("Orders.Treeview", rowheight=32, background=PANEL, fieldbackground=PANEL)
        style.configure("Orders.Treeview.Heading", background="#eaf0e7", font=("Segoe UI", 10, "bold"))
        style.map("Orders.Treeview", background=[("selected", "#dcead8")], foreground=[("selected", TEXT)])

    def build_window(self):
        topbar = tk.Frame(self.root, background=TOPBAR)
        topbar.pack(fill="x")
        tk.Label(topbar, text="Python Fitness ERP", background=TOPBAR, foreground="white",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=24, pady=13)

        content = tk.Frame(self.root, background=BACKGROUND)
        content.pack(fill="both", expand=True, padx=24, pady=(18, 22))
        tk.Label(content, text="Aufträge", background=BACKGROUND, foreground=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=(0, 14))

        form = ttk.Frame(content, style="Panel.TFrame", padding=16)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(0, weight=1)
        ttk.Label(form, text="Shop-Bestellung übernehmen", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 9),
        )
        ttk.Label(form, text="Shop-Bestellnummer", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 4),
        )
        entry = ttk.Entry(form, textvariable=self.shop_number)
        entry.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        self.import_button = ttk.Button(
            form, text="Auftrag importieren", style="Import.TButton", command=self.import_order,
        )
        self.import_button.grid(row=2, column=1, sticky="e")
        entry.bind("<Return>", lambda _event: self.import_button.invoke())
        self.status_label = ttk.Label(form, textvariable=self.status, style="Panel.TLabel")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        overview = ttk.Frame(content, style="Panel.TFrame", padding=16)
        overview.pack(fill="both", expand=True)
        overview.columnconfigure(0, weight=1)
        overview.rowconfigure(3, weight=1)
        ttk.Label(overview, text="Aufträge suchen", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4),
        )
        ttk.Entry(overview, textvariable=self.search).grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.refresh_button = ttk.Button(overview, text="Aktualisieren", command=self.refresh_orders)
        self.refresh_button.grid(row=1, column=1, sticky="e")
        ttk.Label(overview, textvariable=self.result_count, style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", pady=(8, 5),
        )

        self.table = ttk.Treeview(
            overview, columns=ORDER_FIELDS, show="headings", style="Orders.Treeview", height=7,
        )
        for field, label, width in zip(ORDER_FIELDS, ("ERP-Auftrag", "Shop-Bestellung", "SKU", "Menge"),
                                       (120, 175, 230, 70)):
            anchor = "e" if field == "quantity" else "w"
            self.table.heading(field, text=label, anchor=anchor)
            self.table.column(field, width=width, minwidth=65, anchor=anchor, stretch=field != "quantity")
        scrollbar = ttk.Scrollbar(overview, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.grid(row=3, column=0, columnspan=2, sticky="nsew")
        scrollbar.grid(row=3, column=2, sticky="ns")
        entry.focus_set()

    def render_orders(self, *args):
        visible = matching_orders(self.orders, self.search.get())
        self.table.delete(*self.table.get_children())
        for order in visible:
            self.table.insert("", "end", values=tuple(order[field] for field in ORDER_FIELDS))
        if visible:
            self.result_count.set("1 Auftrag" if len(visible) == 1 else f"{len(visible)} Aufträge")
        elif self.search.get().strip():
            self.result_count.set("Keine passenden Aufträge gefunden.")
        else:
            self.result_count.set("Noch keine Aufträge importiert.")

    def set_status(self, message: str, color: str = MUTED):
        self.status.set(message)
        self.status_label.configure(foreground=color)

    def run_request(self, message, work, on_success):
        if self.busy:
            return
        self.busy = True
        self.import_button.state(["disabled"])
        self.refresh_button.state(["disabled"])
        self.set_status(message)
        future = self.worker.submit(work)
        self.root.after(60, self.finish_request, future, on_success)

    def finish_request(self, future, on_success):
        if not future.done():
            self.root.after(60, self.finish_request, future, on_success)
            return
        try:
            on_success(*future.result())
        except RuntimeError as error:
            self.set_status(str(error), ERROR)
        finally:
            self.busy = False
            self.import_button.state(["!disabled"])
            self.refresh_button.state(["!disabled"])

    def refresh_orders(self):
        self.run_request(
            "Aufträge werden geladen…",
            lambda: request_json(self.base_url, "/erp/orders"),
            self.on_orders_loaded,
        )

    def on_orders_loaded(self, _status, orders):
        self.orders = orders
        self.render_orders()
        self.set_status("")

    def import_order(self):
        shop_order_id = self.shop_number.get().strip()
        if not shop_order_id:
            self.set_status("Bitte gib eine Shop-Bestellnummer ein.", ERROR)
            return
        path = f"/erp/orders/import/{quote(shop_order_id, safe='')}"
        self.run_request(
            "Bestellung wird geprüft…",
            lambda: request_json(self.base_url, path, method="POST"),
            self.on_order_imported,
        )

    def on_order_imported(self, status, order):
        if all(saved["shop_order_id"] != order["shop_order_id"] for saved in self.orders):
            self.orders.insert(0, order)
        self.shop_number.set("")
        self.search.set("")
        number = order["erp_order_id"]
        message = f"{number} wurde importiert." if status == 201 else f"{number} ist bereits im ERP."
        self.set_status(message, ACCENT)

    def close(self):
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def open_erp_window(base_url: str) -> None:
    root = tk.Tk()
    ErpWindow(root, base_url)
    root.mainloop()
