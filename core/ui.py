from tkinter import Toplevel, Frame

def center_window(window, width=960, height=600):
    window.geometry(f"{width}x{height}")
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def make_child(parent, title: str, width=960, height=600) -> Toplevel:
    win = Toplevel(parent)
    win.title(title)
    center_window(win, width, height)
    return win

def padded(frame: Frame, pad=8):
    frame.pack(fill="both", expand=True, padx=pad, pady=pad)
    return frame
