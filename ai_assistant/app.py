# Prosty chat-echo – na start.
from tkinter import Frame, Text, Entry, Button, END
from core.ui import make_child, padded

class SimpleChat:
    def __init__(self, root):
        self.win = make_child(root, "AI Asystent – demo czatu")
        box = padded(Frame(self.win))
        self.log = Text(box, height=24); self.log.pack(fill="both", expand=True)
        self.input = Entry(box); self.input.pack(fill="x", pady=6)
        Button(box, text="Wyślij", command=self.on_send).pack(anchor="e")

    def on_send(self):
        msg = self.input.get().strip()
        if not msg: 
            return
        self.log.insert(END, f"Ty: {msg}\n")
        self.log.insert(END, f"Asystent: (echo) {msg}\n\n")
        self.input.delete(0, END)

def open_window(root):
    SimpleChat(root)
