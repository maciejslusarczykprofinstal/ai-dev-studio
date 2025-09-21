import sys, importlib
from tkinter import Tk, Frame, Button, Label, messagebox
from core.ui import center_window, padded

def _open(module: str, title: str, root):
    try:
        importlib.import_module(module).open_window(root)
    except Exception as e:
        messagebox.showerror(title, f"Moduł '{module}' nie jest jeszcze podpięty.\n\n{e}")

def main():
    root = Tk()
    root.title("Studio AI Dev")
    center_window(root, 640, 420)

    c = padded(Frame(root), pad=12)
    Label(c, text="Studio AI Dev", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
    Label(c, text="Wybierz moduł:").pack(anchor="w", pady=(0, 12))

    Button(c, text="Dla Mieszkańców (CWU)", height=2,
           command=lambda: _open("cwu", "CWU", root)).pack(fill="x", pady=6)
    Button(c, text="Dla Spółdzielni i Wspólnot (CWU)", height=2,
           command=lambda: _open("cwu", "CWU", root)).pack(fill="x", pady=6)
    Button(c, text="Dla Audytorów (CWU)", height=2,
           command=lambda: _open("cwu", "CWU", root)).pack(fill="x", pady=6)
    Button(c, text="Asystent AI", height=2,
           command=lambda: _open("ai_assistant", "AI Asystent", root)).pack(fill="x", pady=12)

    Button(c, text="Zamknij", command=root.destroy).pack(anchor="e", pady=(12, 0))
    root.mainloop()

if __name__ == "__main__":
    sys.exit(main())
