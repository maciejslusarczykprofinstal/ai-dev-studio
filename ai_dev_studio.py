#!/usr/bin/env python3
"""
AI Dev Studio – MVP w PySide6
==============================
Cel: Piszesz w czacie (po prawej) co program ma zrobić. AI zwraca plan zmian
pliku (w prostym JSON), a aplikacja tworzy/aktualizuje/usuwa pliki w wybranym
katalogu projektu. Masz podgląd zmian i przycisk „Zastosuj”.

Funkcje:
- Explorer po lewej (drzewo folderów, double‑click otwiera plik w zakładce)
- Edytor w środku (zakładki, zapis Ctrl+S)
- Logi na dole
- Chat po prawej + przycisk „Wyślij do AI”
- Przełącznik „Widok → Toggle Chat” (ukrywa/pokazuje panel czatu)
- Ustawienie folderu projektu (Plik → Otwórz folder…)
- AI zwraca JSON ze zmianami:
    {
      "changes": [
        {"op":"create", "path":"src/app.py", "content":"..."},
        {"op":"update", "path":"index.html", "content":"..."},
        {"op":"delete", "path":"old.css"}
      ],
      "notes": "krótki opis zmian"
    }

Integracja z OpenAI:
- Ustaw zmienną środowiskową OPENAI_API_KEY
- W menu „AI” → „Tryb offline (echo)” możesz przełączyć między stubbem a API
- Model domyślny: gpt-4o-mini (możesz zmienić w kodzie)

Instalacja:
    pip install PySide6 openai

Uruchom:
    python ai_dev_studio.py
"""
from __future__ import annotations
import json
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Literal

from PySide6 import QtCore, QtGui, QtWidgets

APP_NAME = "AI Dev Studio"
MODEL_NAME = os.getenv("AI_MODEL", "gpt-4o-mini")

# -----------------------------
# Typy i narzędzia
# -----------------------------
OpType = Literal["create", "update", "delete"]

@dataclass
class FileChange:
    op: OpType
    path: str
    content: Optional[str] = None  # dla create/update

@dataclass
class AIPlan:
    changes: List[FileChange]
    notes: str = ""

SAFE_ROOT: Path | None = None  # folder projektu ograniczający operacje IO

def clamp_to_root(p: Path) -> Path:
    """Zwraca ścieżkę *wewnątrz* SAFE_ROOT; rzuca błąd, jeśli wychodzi poza.
    Chroni przed zapisami poza projektem.
    """
    assert SAFE_ROOT is not None, "SAFE_ROOT not set"
    p = (SAFE_ROOT / p).resolve()
    if SAFE_ROOT not in p.parents and p != SAFE_ROOT:
        raise ValueError(f"Ścieżka poza projektem: {p}")
    return p

# -----------------------------
# Prosty highlighter Pythona
# -----------------------------
class PythonHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.rules = []

        def add(pattern: str, color: str, bold=False, italic=False):
            fmt = QtGui.QTextCharFormat()
            if bold:
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            fmt.setForeground(QtGui.QColor(color))
            self.rules.append((QtCore.QRegularExpression(pattern), fmt))

        kws = r"\b(and|as|assert|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b"
        add(kws, "#5c6bc0", bold=True)
        add(r"'(?:[^'\\]|\\.)*'", "#7cb342")
        add(r'"(?:[^"\\]|\\.)*"', "#7cb342")
        add(r"#.*$", "#9e9e9e", italic=True)
        add(r"\b[0-9]+(\.[0-9]+)?\b", "#e67e22")

    def highlightBlock(self, text: str) -> None:
        for pattern, form in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), form)

# -----------------------------
# Editor widget
# -----------------------------
class Editor(QtWidgets.QPlainTextEdit):
    def __init__(self, path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self._path: Optional[Path] = None
        self._dirty = False
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self.textChanged.connect(self._on_change)
        self.highlighter = PythonHighlighter(self.document())
        if path:
            self.load(path)

    def path(self) -> Optional[Path]:
        return self._path

    def is_dirty(self) -> bool:
        return self._dirty

    def _on_change(self):
        self._dirty = True

    def load(self, path: Path):
        try:
            txt = Path(path).read_text(encoding='utf-8')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, APP_NAME, f"Nie mogę otworzyć {path}:\n{e}")
            return
        self.setPlainText(txt)
        self._path = Path(path)
        self._dirty = False

    def save(self, to_path: Optional[Path] = None) -> bool:
        if to_path is not None:
            self._path = Path(to_path)
        if not self._path:
            return False
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self.toPlainText(), encoding='utf-8')
            self._dirty = False
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, APP_NAME, f"Nie mogę zapisać {self._path}:\n{e}")
            return False

# -----------------------------
# Chat + AI
# -----------------------------
class ChatPanel(QtWidgets.QWidget):
    ai_response_ready = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(6,6,6,6)
        title = QtWidgets.QHBoxLayout()
        self.layout().addLayout(title)

        title.addWidget(QtWidgets.QLabel("Chat / Instrukcje AI"))
        self.offline_chk = QtWidgets.QCheckBox("Tryb offline (echo)")
        self.offline_chk.setChecked(True)
        title.addWidget(self.offline_chk)
        title.addStretch(1)

        self.history = QtWidgets.QTextEdit(readOnly=True)
        self.layout().addWidget(self.history)

        row = QtWidgets.QHBoxLayout()
        self.prompt = QtWidgets.QLineEdit()
        self.prompt.setPlaceholderText("Opisz co ma powstać / co zmienić (np. utwórz index.html, style.css, app.py)…")
        self.send_btn = QtWidgets.QPushButton("Wyślij do AI")
        row.addWidget(self.prompt, 1)
        row.addWidget(self.send_btn)
        self.layout().addLayout(row)

        self.send_btn.clicked.connect(self.on_send)
        self.prompt.returnPressed.connect(self.on_send)

    def append(self, who: str, text: str):
        esc = QtGui.QTextDocument().toHtmlEscaped(text)
        self.history.append(f"<b>{who}:</b> {esc}")

    def on_send(self):
        msg = self.prompt.text().strip()
        if not msg:
            return
        self.append("Ty", msg)
        self.prompt.clear()
        if self.offline_chk.isChecked():
            # Prosty echo plan – tworzy README.md jako dowód działania
            plan = {
                "changes": [
                    {"op": "create", "path": "README.md", "content": f"# Projekt\n\nInstrukcja: {msg}\n"}
                ],
                "notes": "Tryb offline: tylko przykład tworzenia README.md"
            }
            self.append("AI", json.dumps(plan, ensure_ascii=False, indent=2))
            self.ai_response_ready.emit(plan)
        else:
            self.call_openai(msg)

    def call_openai(self, user_msg: str):
        # Uruchom w wątku, żeby UI nie zawisł
        worker = AIWorker(user_msg)
        worker.finished_plan.connect(self._on_ai_plan)
        worker.error_signal.connect(self._on_ai_error)
        worker.start()

    def _on_ai_plan(self, plan_json: str):
        self.append("AI", plan_json)
        try:
            plan = json.loads(plan_json)
            self.ai_response_ready.emit(plan)
        except Exception as e:
            self.append("AI", f"Błąd parsowania JSON: {e}")

    def _on_ai_error(self, err: str):
        self.append("AI", f"Błąd AI: {err}")

class AIWorker(QtCore.QThread):
    finished_plan = QtCore.Signal(str)
    error_signal = QtCore.Signal(str)

    def __init__(self, user_msg: str):
        super().__init__()
        self.user_msg = user_msg

    def run(self):
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("Brak OPENAI_API_KEY w środowisku. Ustaw i wyłącz tryb offline.")
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            system_msg = (
                "Jesteś asystentem w edytorze kodu. Zwracaj WYŁĄCZNIE poprawny JSON w formacie:\n"
                "{\n  \"changes\": [ {\"op\":\"create|update|delete\", \"path\":\"...\", \"content\":\"...opcjonalnie...\"} ],\n  \"notes\": \"krótko\"\n}\n"
                "Reguły: ścieżki względne względem katalogu projektu; unikanie \"..\"; dla update podaj CAŁĄ zawartość pliku po zmianach;"
                " możesz tworzyć .py, .html, .css, .js, itp. Jeżeli prosisz o kilka plików – dodaj kilka obiektów changes."
            )

            resp = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": self.user_msg},
                ],
                max_tokens=4096,
            )
            content = resp.choices[0].message.content
            self.finished_plan.emit(content)
        except Exception as e:
            self.error_signal.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

# -----------------------------
# Podgląd i zastosowanie zmian
# -----------------------------
class PlanView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Operacja", "Plik", "Status"]) 
        self.layout().addWidget(self.tree)
        btns = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("Zastosuj zmiany")
        self.refresh_btn = QtWidgets.QPushButton("Odśwież podgląd")
        btns.addWidget(self.apply_btn)
        btns.addWidget(self.refresh_btn)
        btns.addStretch(1)
        self.layout().addLayout(btns)
        self._plan: Optional[AIPlan] = None

        self.apply_btn.clicked.connect(self.apply_changes)
        self.refresh_btn.clicked.connect(self.refresh)

    def load_plan(self, plan_dict: dict):
        try:
            changes = [FileChange(op=c.get('op'), path=c.get('path'), content=c.get('content')) for c in plan_dict.get('changes', [])]
            self._plan = AIPlan(changes=changes, notes=plan_dict.get('notes',''))
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, APP_NAME, f"Zły plan AI: {e}")

    def refresh(self):
        self.tree.clear()
        if not self._plan:
            return
        for ch in self._plan.changes:
            item = QtWidgets.QTreeWidgetItem([ch.op, ch.path, "przygotowane"])
            self.tree.addTopLevelItem(item)
            # pokaz podgląd treści (pierwsze 40 linii)
            if ch.content is not None:
                preview = "\n".join(ch.content.splitlines()[:40])
                sub = QtWidgets.QTreeWidgetItem(["…", "podgląd", ""]) 
                item.addChild(sub)
                sub.setToolTip(1, preview)
        self.tree.expandAll()

    def apply_changes(self):
        if not self._plan:
            return
        if SAFE_ROOT is None:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Najpierw otwórz folder projektu.")
            return
        errors = []
        for ch in self._plan.changes:
            try:
                target = clamp_to_root(Path(ch.path))
                if ch.op == "delete":
                    if target.exists():
                        target.unlink()
                elif ch.op in ("create", "update"):
                    if ch.content is None:
                        raise ValueError("Brak 'content' dla create/update")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(ch.content, encoding='utf-8')
                else:
                    raise ValueError(f"Nieznana operacja: {ch.op}")
            except Exception as e:
                errors.append(f"{ch.op} {ch.path}: {e}")
        if errors:
            QtWidgets.QMessageBox.critical(self, APP_NAME, "\n".join(errors))
        else:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Zastosowano zmiany.")
        # po zastosowaniu – warto odświeżyć eksplorator
        self.parent().parent().refresh_explorer()

# -----------------------------
# Główne okno
# -----------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 950)
        self._build_ui()
        self._build_menu()

    def _build_ui(self):
        # Split: [Explorer] | [Center(VSplit)] | [Chat]
        self.root_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.setCentralWidget(self.root_split)

        # Explorer
        self.fs_model = QtWidgets.QFileSystemModel()
        self.fs_model.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs)
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self.on_tree_double_click)
        self.root_split.addWidget(self.tree)

        # Center: editor + bottom
        center = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        center.addWidget(self.tabs)

        self.plan_view = PlanView()
        center.addWidget(self.plan_view)

        center.setStretchFactor(0, 4)
        center.setStretchFactor(1, 2)
        self.root_split.addWidget(center)

        # Chat panel
        self.chat = ChatPanel()
        self.root_split.addWidget(self.chat)
        self.chat.ai_response_ready.connect(self.on_ai_plan_ready)

        self.root_split.setStretchFactor(0, 1)
        self.root_split.setStretchFactor(1, 3)
        self.root_split.setStretchFactor(2, 1)

    def _build_menu(self):
        menubar = self.menuBar()
        file_m = menubar.addMenu("Plik")
        view_m = menubar.addMenu("Widok")
        ai_m = menubar.addMenu("AI")

        open_folder_act = QtGui.QAction("Otwórz folder…", self)
        open_folder_act.triggered.connect(self.open_folder_dialog)
        file_m.addAction(open_folder_act)

        save_act = QtGui.QAction("Zapisz bieżący (Ctrl+S)", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_current)
        file_m.addAction(save_act)

        toggle_chat_act = QtGui.QAction("Toggle Chat", self, checkable=True)
        toggle_chat_act.setChecked(True)
        toggle_chat_act.triggered.connect(self.toggle_chat)
        view_m.addAction(toggle_chat_act)

        offline_act = QtGui.QAction("Tryb offline (echo)", self, checkable=True)
        offline_act.setChecked(True)
        offline_act.triggered.connect(lambda v: self.chat.offline_chk.setChecked(v))
        ai_m.addAction(offline_act)

    # ----------- Explorer ops
    def open_folder_dialog(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Wybierz folder projektu")
        if path:
            self.open_folder(Path(path))

    def open_folder(self, root: Path):
        global SAFE_ROOT
        SAFE_ROOT = Path(root).resolve()
        self.fs_model.setRootPath(str(SAFE_ROOT))
        self.tree.setRootIndex(self.fs_model.index(str(SAFE_ROOT)))
        self.statusBar().showMessage(f"Projekt: {SAFE_ROOT}")

    def refresh_explorer(self):
        if SAFE_ROOT:
            self.fs_model.setRootPath("")  # wymuszenie odświeżenia
            self.fs_model.setRootPath(str(SAFE_ROOT))
            self.tree.setRootIndex(self.fs_model.index(str(SAFE_ROOT)))

    def on_tree_double_click(self, idx: QtCore.QModelIndex):
        path = self.fs_model.filePath(idx)
        p = Path(path)
        if p.is_file():
            self.open_file(p)

    def open_file(self, p: Path):
        # jeśli już otwarty – fokus
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, Editor) and w.path() and w.path() == p:
                self.tabs.setCurrentIndex(i)
                return
        ed = Editor(p)
        i = self.tabs.addTab(ed, p.name)
        self.tabs.setTabToolTip(i, str(p))
        self.tabs.setCurrentIndex(i)

    def save_current(self):
        w = self.tabs.currentWidget()
        if isinstance(w, Editor):
            if w.save():
                self.statusBar().showMessage(f"Zapisano: {w.path()}", 3000)
                self.refresh_explorer()

    # ----------- Chat/AI plan
    def on_ai_plan_ready(self, plan_dict: dict):
        self.plan_view.load_plan(plan_dict)

    def close_tab(self, index: int):
        w = self.tabs.widget(index)
        if isinstance(w, Editor) and w.is_dirty():
            ans = QtWidgets.QMessageBox.question(self, APP_NAME, "Plik ma niezapisane zmiany. Zamknąć?")
            if ans != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.tabs.removeTab(index)

    def toggle_chat(self, checked: bool):
        self.chat.setVisible(checked)

# -----------------------------
# Start
# -----------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
