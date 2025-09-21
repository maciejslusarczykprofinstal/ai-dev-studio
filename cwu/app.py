# cwu/app.py — szkic UI w ttk (DEMO)
import tkinter as tk
from tkinter import ttk, messagebox
from core.ui import make_child

def open_window(root):
    win = make_child(root, "Moduł CWU — kalkulator", width=1000, height=640)
    win.minsize(900, 560)

    # Styl
    style = ttk.Style(win)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
    style.configure("TButton", padding=8)

    # Główna ramka
    main = ttk.Frame(win, padding=12)
    main.grid(row=0, column=0, sticky="nsew")
    win.columnconfigure(0, weight=1)
    win.rowconfigure(0, weight=1)
    main.columnconfigure(0, weight=1)
    main.columnconfigure(1, weight=2)

    ttk.Label(main, text="Kalkulator CWU", style="Header.TLabel")\
        .grid(row=0, column=0, columnspan=2, sticky="w")

    # Dane wejściowe
    form = ttk.LabelFrame(main, text="Dane wejściowe", padding=12)
    form.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(12, 0))
    main.rowconfigure(1, weight=1)
    form.columnconfigure(1, weight=1)

    def row(r, label, widget):
        ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", pady=4)
        widget.grid(row=r, column=1, sticky="ew", pady=4)

    e_miesz = ttk.Spinbox(form, from_=1, to=500, width=8)
    e_miesz.set(65);                row(0, "Liczba mieszkań:", e_miesz)

    e_osoby = ttk.Spinbox(form, from_=1, to=6, width=8)
    e_osoby.set(2);                 row(1, "Śr. liczba osób / mieszkanie:", e_osoby)

    e_tz = ttk.Entry(form);  e_tz.insert(0, "8")
    row(2, "Temperatura zimnej wody [°C]:", e_tz)

    e_tcwu = ttk.Entry(form); e_tcwu.insert(0, "55")
    row(3, "Temperatura CWU [°C]:", e_tcwu)

    e_q = ttk.Entry(form);   e_q.insert(0, "0.045")
    row(4, "Przepływ jednostkowy [l/s] (DEMO):", e_q)

    e_straty = ttk.Entry(form); e_straty.insert(0, "15")
    row(5, "Straty na cyrkulacji [%] (DEMO):", e_straty)

    # Przyciski
    btns = ttk.Frame(form); btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    btns.columnconfigure(0, weight=1)
    ttk.Button(btns, text="OBLICZ (DEMO)", command=lambda: calc()).grid(row=0, column=0, sticky="e")

    # Wynik
    out = ttk.LabelFrame(main, text="Wynik (DEMO)", padding=12)
    out.grid(row=1, column=1, sticky="nsew", pady=(12, 0))
    out.columnconfigure(0, weight=1); out.rowconfigure(0, weight=1)
    result = tk.Text(out, height=16, wrap="word"); result.grid(row=0, column=0, sticky="nsew")
    result.configure(state="disabled")

    def calc():
        """Prosty przelicznik DEMO (do podmiany na Twój algorytm)."""
        try:
            n_m     = float(e_miesz.get())
            osoby   = float(e_osoby.get())     # jeszcze nie użyte – demo
            tz      = float(e_tz.get())
            tcwu    = float(e_tcwu.get())
            q_lps   = float(e_q.get())         # l/s na mieszkanie (demo)
            straty  = float(e_straty.get())/100.0

            rho = 1.0   # kg/l (upr.)
            cp  = 4.19  # kJ/kgK
            dT  = max(tcwu - tz, 0)
            total_flow_lps = n_m * q_lps
            P_kW = total_flow_lps * rho * cp * dT            # kJ/s ~= kW
            P_kW_eff = P_kW * (1.0 + straty)

            text = (
                "DEMO – wyniki orientacyjne\n"
                f"Liczba mieszkań: {n_m:.0f}\n"
                f"Śr. osób/mieszkanie: {osoby:.2f}\n"
                f"ΔT = {dT:.1f} K\n"
                f"Przepływ całkowity ≈ {total_flow_lps:.3f} l/s\n"
                f"Moc chwilowa ≈ {P_kW:.1f} kW\n"
                f"Moc + straty ({straty*100:.0f}%): ≈ {P_kW_eff:.1f} kW\n\n"
                "Uwaga: to tylko demo UI. Tu wpinamy Twój docelowy algorytm i dane normowe."
            )
            result.configure(state="normal"); result.delete("1.0", "end")
            result.insert("1.0", text);       result.configure(state="disabled")
        except Exception as ex:
            messagebox.showerror("Błąd danych", f"Sprawdź wartości liczbowe.\n\n{ex}")
