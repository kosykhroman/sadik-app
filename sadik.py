import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, timedelta

# ============ РАБОТА С БАЗОЙ ДАННЫХ ============
DB_NAME = "sadik.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fio TEXT NOT NULL,
        position TEXT NOT NULL,
        size TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS clothing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        norm_months INTEGER NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        clothing_id INTEGER,
        issue_date TEXT,
        next_date TEXT,
        returned INTEGER DEFAULT 0
    )''')
    # Заполняем справочник одежды при первом запуске
    if c.execute("SELECT COUNT(*) FROM clothing").fetchone()[0] == 0:
        defaults = [
            ("Халат хлопчатобумажный", 12),
            ("Фартук с водоотталкивающей пропиткой", 12),
            ("Костюм для повара (куртка+брюки)", 24),
            ("Косынка/шапочка", 6),
            ("Халат для медсестры", 12),
            ("Халат для прачки", 6),
            ("Резиновые перчатки", 3),
            ("Бахилы", 12),
        ]
        c.executemany("INSERT INTO clothing (name, norm_months) VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()

# ============ ГЛАВНОЕ ОКНО ============
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Учет спецодежды — Детский сад")
        self.geometry("900x600")
        
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_emp = EmployeesTab(tabs, self)
        self.tab_issues = IssuesTab(tabs, self)
        self.tab_cloth = ClothingTab(tabs, self)
        
        tabs.add(self.tab_emp, text="👥 Сотрудники")
        tabs.add(self.tab_issues, text="📦 Выдачи")
        tabs.add(self.tab_cloth, text="📋 Нормы выдачи")
        
        # Кнопка экспорта
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_frame, text="📊 Экспорт журнала в CSV", command=self.export_csv).pack(side="left")
        tk.Button(btn_frame, text="🖨️ Печать карточки сотрудника", command=self.print_card).pack(side="left", padx=5)
    
    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        conn = get_db()
        rows = conn.execute("""
            SELECT e.fio, e.position, c.name, i.issue_date, i.next_date, i.returned
            FROM issues i
            JOIN employees e ON e.id = i.employee_id
            JOIN clothing c ON c.id = i.clothing_id
            ORDER BY i.issue_date DESC
        """).fetchall()
        conn.close()
        with open(path, "w", encoding="utf-8") as f:
            f.write("ФИО;Должность;Вещь;Дата выдачи;След. выдача;Возвращена\n")
            for r in rows:
                f.write(f"{r['fio']};{r['position']};{r['name']};{r['issue_date']};{r['next_date']};{'Да' if r['returned'] else 'Нет'}\n")
        messagebox.showinfo("Готово", f"Экспортировано {len(rows)} записей")
    
    def print_card(self):
        # Простая печать — открываем окно с текстом карточки
        win = tk.Toplevel(self)
        win.title("Личная карточка")
        win.geometry("700x500")
        
        conn = get_db()
        emps = conn.execute("SELECT id, fio, position FROM employees ORDER BY fio").fetchall()
        conn.close()
        if not emps:
            messagebox.showwarning("Внимание", "Сначала добавьте сотрудников"); return
        
        txt = tk.Text(win, font=("Courier", 11))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        def load_card(emp_id):
            conn = get_db()
            emp = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
            issues = conn.execute("""
                SELECT c.name, i.issue_date, i.next_date 
                FROM issues i JOIN clothing c ON c.id=i.clothing_id
                WHERE i.employee_id=? ORDER BY i.issue_date DESC
            """, (emp_id,)).fetchall()
            conn.close()
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, f"ЛИЧНАЯ КАРТОЧКА учета выдачи спецодежды\n")
            txt.insert(tk.END, f"{'='*50}\n")
            txt.insert(tk.END, f"ФИО: {emp['fio']}\n")
            txt.insert(tk.END, f"Должность: {emp['position']}\n")
            txt.insert(tk.END, f"Размер: {emp['size'] or '-'}\n")
            txt.insert(tk.END, f"{'='*50}\n\n")
            txt.insert(tk.END, f"{'Вещь':<35}{'Выдано':<12}{'След. выдача':<12}\n")
            txt.insert(tk.END, f"{'-'*59}\n")
            for i in issues:
                txt.insert(tk.END, f"{i['name']:<35}{i['issue_date']:<12}{i['next_date']:<12}\n")
        
        ttk.Label(win, text="Сотрудник:").pack()
        cb = ttk.Combobox(win, values=[f"{e['fio']} ({e['position']})" for e in emps], state="readonly")
        cb.pack()
        cb.bind("<<ComboboxSelected>>", lambda e: load_card(emps[cb.current()]['id']))
        tk.Button(win, text="Печать (Ctrl+P в окне)", command=lambda: txt.event_generate("<<Print>>")).pack(pady=5)

# ============ ВКЛАДКА: СОТРУДНИКИ ============
class EmployeesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build()
        self.refresh()
    
    def build(self):
        cols = ("id", "fio", "position", "size")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        self.tree.heading("id", text="ID"); self.tree.column("id", width=40)
        self.tree.heading("fio", text="ФИО"); self.tree.column("fio", width=300)
        self.tree.heading("position", text="Должность"); self.tree.column("position", width=200)
        self.tree.heading("size", text="Размер"); self.tree.column("size", width=100)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10)
        tk.Label(frm, text="ФИО:").pack(side="left")
        self.e_fio = tk.Entry(frm, width=25); self.e_fio.pack(side="left", padx=5)
        tk.Label(frm, text="Должность:").pack(side="left")
        self.e_pos = tk.Entry(frm, width=20); self.e_pos.pack(side="left", padx=5)
        tk.Label(frm, text="Размер:").pack(side="left")
        self.e_size = tk.Entry(frm, width=8); self.e_size.pack(side="left", padx=5)
        tk.Button(frm, text="➕ Добавить", command=self.add).pack(side="left", padx=5)
        tk.Button(frm, text="🗑️ Удалить", command=self.delete).pack(side="left")
    
    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        conn = get_db()
        for r in conn.execute("SELECT * FROM employees ORDER BY fio"):
            self.tree.insert("", "end", values=(r['id'], r['fio'], r['position'], r['size']))
        conn.close()
    
    def add(self):
        fio, pos, size = self.e_fio.get().strip(), self.e_pos.get().strip(), self.e_size.get().strip()
        if not fio or not pos:
            messagebox.showwarning("Внимание", "Заполните ФИО и должность"); return
        conn = get_db()
        conn.execute("INSERT INTO employees (fio, position, size) VALUES (?, ?, ?)", (fio, pos, size))
        conn.commit(); conn.close()
        self.e_fio.delete(0, tk.END); self.e_pos.delete(0, tk.END); self.e_size.delete(0, tk.END)
        self.refresh()
    
    def delete(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("Подтверждение", "Удалить сотрудника?"): return
        emp_id = self.tree.item(sel[0])['values'][0]
        conn = get_db()
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit(); conn.close()
        self.refresh()

# ============ ВКЛАДКА: ВЫДАЧИ ============
class IssuesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.build()
        self.refresh()
    
    def build(self):
        cols = ("id", "fio", "clothing", "issued", "next", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20)
        self.tree.heading("id", text="ID"); self.tree.column("id", width=40)
        self.tree.heading("fio", text="Сотрудник"); self.tree.column("fio", width=200)
        self.tree.heading("clothing", text="Вещь"); self.tree.column("clothing", width=250)
        self.tree.heading("issued", text="Выдано"); self.tree.column("issued", width=100)
        self.tree.heading("next", text="След. выдача"); self.tree.column("next", width=110)
        self.tree.heading("status", text="Статус"); self.tree.column("status", width=120)
        
        # Подсветка просроченных
        self.tree.tag_configure("overdue", background="#ffcccc")
        self.tree.tag_configure("soon", background="#fff4cc")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10)
        
        conn = get_db()
        emps = conn.execute("SELECT id, fio FROM employees ORDER BY fio").fetchall()
        cloth = conn.execute("SELECT id, name FROM clothing ORDER BY name").fetchall()
        conn.close()
        
        tk.Label(frm, text="Сотрудник:").pack(side="left")
        self.cb_emp = ttk.Combobox(frm, values=[f"{e['id']} - {e['fio']}" for e in emps], state="readonly", width=25)
        self.cb_emp.pack(side="left", padx=5)
        
        tk.Label(frm, text="Вещь:").pack(side="left")
        self.cb_cloth = ttk.Combobox(frm, values=[f"{c['id']} - {c['name']}" for c in cloth], state="readonly", width=30)
        self.cb_cloth.pack(side="left", padx=5)
        
        tk.Button(frm, text="📦 Выдать", command=self.issue).pack(side="left", padx=5)
        tk.Button(frm, text="✅ Вернуть", command=self.return_item).pack(side="left")
    
    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        conn = get_db()
        rows = conn.execute("""
            SELECT i.id, e.fio, c.name, i.issue_date, i.next_date, i.returned
            FROM issues i
            JOIN employees e ON e.id=i.employee_id
            JOIN clothing c ON c.id=i.clothing_id
            WHERE i.returned=0
            ORDER BY i.next_date
        """).fetchall()
        conn.close()
        
        today = datetime.now().date()
        for r in rows:
            next_d = datetime.strptime(r['next_date'], "%Y-%m-%d").date()
            days_left = (next_d - today).days
            if days_left < 0:
                status, tag = f"ПРОСРОЧЕНО ({abs(days_left)} дн.)", "overdue"
            elif days_left <= 30:
                status, tag = f"Скоро ({days_left} дн.)", "soon"
            else:
                status, tag = f"OK ({days_left} дн.)", ""
            self.tree.insert("", "end", values=(r['id'], r['fio'], r['name'], r['issue_date'], r['next_date'], status), tags=(tag,))
    
    def issue(self):
        if not self.cb_emp.get() or not self.cb_cloth.get():
            messagebox.showwarning("Внимание", "Выберите сотрудника и вещь"); return
        emp_id = int(self.cb_emp.get().split(" - ")[0])
        cloth_id = int(self.cb_cloth.get().split(" - ")[0])
        
        conn = get_db()
        norm = conn.execute("SELECT norm_months FROM clothing WHERE id=?", (cloth_id,)).fetchone()['norm_months']
        today = datetime.now().date()
        next_d = today + timedelta(days=norm*30)
        conn.execute("INSERT INTO issues (employee_id, clothing_id, issue_date, next_date) VALUES (?, ?, ?, ?)",
                     (emp_id, cloth_id, today.isoformat(), next_d.isoformat()))
        conn.commit(); conn.close()
        messagebox.showinfo("Готово", f"Выдано. Следующая выдача: {next_d.isoformat()}")
        self.refresh()
    
    def return_item(self):
        sel = self.tree.selection()
        if not sel: return
        issue_id = self.tree.item(sel[0])['values'][0]
        conn = get_db()
        conn.execute("UPDATE issues SET returned=1 WHERE id=?", (issue_id,))
        conn.commit(); conn.close()
        self.refresh()

# ============ ВКЛАДКА: НОРМЫ ============
class ClothingTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.build()
        self.refresh()
    
    def build(self):
        cols = ("id", "name", "norm")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        self.tree.heading("id", text="ID"); self.tree.column("id", width=40)
        self.tree.heading("name", text="Наименование"); self.tree.column("name", width=400)
        self.tree.heading("norm", text="Срок носки (мес.)"); self.tree.column("norm", width=150)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10)
        tk.Label(frm, text="Название:").pack(side="left")
        self.e_name = tk.Entry(frm, width=30); self.e_name.pack(side="left", padx=5)
        tk.Label(frm, text="Мес.:").pack(side="left")
        self.e_norm = tk.Entry(frm, width=5); self.e_norm.pack(side="left", padx=5)
        tk.Button(frm, text="➕ Добавить", command=self.add).pack(side="left", padx=5)
        tk.Button(frm, text="🗑️ Удалить", command=self.delete).pack(side="left")
    
    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        conn = get_db()
        for r in conn.execute("SELECT * FROM clothing ORDER BY name"):
            self.tree.insert("", "end", values=(r['id'], r['name'], r['norm_months']))
        conn.close()
    
    def add(self):
        name = self.e_name.get().strip()
        try: norm = int(self.e_norm.get())
        except: messagebox.showwarning("Внимание", "Укажите число месяцев"); return
        if not name: return
        conn = get_db()
        conn.execute("INSERT INTO clothing (name, norm_months) VALUES (?, ?)", (name, norm))
        conn.commit(); conn.close()
        self.e_name.delete(0, tk.END); self.e_norm.delete(0, tk.END)
        self.refresh()
    
    def delete(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("Подтверждение", "Удалить?"): return
        conn = get_db()
        conn.execute("DELETE FROM clothing WHERE id=?", (self.tree.item(sel[0])['values'][0],))
        conn.commit(); conn.close()
        self.refresh()

# ============ ЗАПУСК ============
if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()