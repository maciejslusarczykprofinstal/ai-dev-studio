# Placeholder okna CWU – tu potem wpinamy Twoje właściwe GUI.
from tkinter import Frame, Label, Button
from core.ui import make_child, padded

def open_window(root):
    win = make_child(root, "Moduł CWU – kalkulator")
    box = padded(Frame(win))
    Label(box, text="Tutaj podłączymy Twoje istniejące GUI CWU.",
          font=("Segoe UI", 12, "bold")).pack(anchor="w")
    Label(box, text="Na razie to placeholder, żeby launcher działał.").pack(anchor="w", pady=(6, 0))
    Button(box, text="Zamknij", command=win.destroy).pack(anchor="e", pady=12)
