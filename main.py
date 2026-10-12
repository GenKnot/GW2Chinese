import tkinter as tk
from tkinter import messagebox
import pymem
import pymem.process
import ctypes
import sys

POINTER_PATHS = [
    (0x0266B030, [0x18, 0x20, 0x50, 0x10, 0x324]),
    (0x0266B608, [0x18, 0x20, 0x50, 0x10, 0x324]),
    (0x0266B740, [0x18, 0x20, 0x50, 0x10, 0x324]),
    (0x0289B780, [0x18, 0x20, 0x50, 0x10, 0x324]),
    (0x028B6CD0, [0x18, 0x20, 0x50, 0x10, 0x324]),
    (0x0289B778, [0x58, 0x38, 0x50, 0x10, 0x324]),
    (0x0266DF68, [0x9F0, 0x70, 0x2FC]),
    (0x0266DF68, [0x88,  0x70, 0x2FC]),
    (0x0266DF68, [0xD38, 0x70, 0x2FC]),
    (0x0266DF68, [0x88,  0x70, 0x258, 0xA4]),
    (0x026B15B8, [0x230, 0xEB8, 0x70, 0x2FC]),
]
CHINESE = 5
ENGLISH = 0

LANG_MAP = {0: "英语", 2: "法语", 3: "德语", 4: "西班牙语", 5: "中文"}

BASE_MODULE = "Gw2-64.exe"

def resolve_pointer(pm, base_offset, offsets):
    base = pymem.process.module_from_name(pm.process_handle, BASE_MODULE).lpBaseOfDll
    addr = pm.read_longlong(base + base_offset)
    for off in offsets[:-1]:
        addr = pm.read_longlong(addr + off)
    return addr + offsets[-1]

def try_read(pm, base_offset, offsets):
    try:
        addr = resolve_pointer(pm, base_offset, offsets)
        val = pm.read_int(addr)
        if val in LANG_MAP:
            return addr, val
    except:
        pass
    return None, None

def find_lang_addr(pm):
    # 多条路径各自解析，取被最多路径指向的地址，避免单条路径误中别处
    votes = {}
    for base_offset, offsets in POINTER_PATHS:
        addr, val = try_read(pm, base_offset, offsets)
        if addr is not None:
            votes[addr] = votes.get(addr, 0) + 1
    if not votes:
        return None
    return max(votes, key=votes.get)

def get_lang():
    try:
        pm = pymem.Pymem(BASE_MODULE)
        addr = find_lang_addr(pm)
        val = pm.read_int(addr) if addr is not None else None
        pm.close_process()
        return val
    except:
        pass
    return None

def set_lang(value):
    try:
        pm = pymem.Pymem(BASE_MODULE)
        addr = find_lang_addr(pm)
        if addr is not None:
            pm.write_int(addr, value)
        pm.close_process()
        return addr is not None
    except:
        pass
    return False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class App:
    def __init__(self, root):
        self.root = root
        root.title("GW2 语言切换")
        root.geometry("300x180")
        root.resizable(False, False)

        tk.Label(root, text="Guild Wars 2 语言切换工具", font=("微软雅黑", 12, "bold")).pack(pady=(15, 2))
        tk.Label(root, text="by Discord: 503", font=("微软雅黑", 8), fg="gray").pack()

        self.status_label = tk.Label(root, text="检测中...", font=("微软雅黑", 10))
        self.status_label.pack()

        self.btn = tk.Button(root, text="切换为中文", font=("微软雅黑", 11),
                             width=15, height=2, command=self.switch_language)
        self.btn.pack(pady=15)

        self.refresh_status()
        self.root.after(3000, self.auto_refresh)

    def auto_refresh(self):
        self.refresh_status()
        self.root.after(3000, self.auto_refresh)

    def refresh_status(self):
        val = get_lang()
        if val is None:
            self.status_label.config(text="未检测到游戏，请先启动GW2", fg="red")
            self.btn.config(state="disabled", text="切换为中文")
        else:
            lang_name = LANG_MAP.get(val, f"未知({val})")
            self.status_label.config(text=f"当前语言：{lang_name}", fg="green" if val == CHINESE else "orange")
            self.btn.config(state="normal",
                            text="已是中文 ✓" if val == CHINESE else "切换为中文")

    def switch_language(self):
        val = get_lang()
        if val is None:
            messagebox.showerror("错误", "未检测到游戏，请先启动GW2")
            return
        if val == CHINESE:
            messagebox.showinfo("提示", "当前已经是中文了")
            return
        if set_lang(CHINESE):
            messagebox.showinfo("成功", "已切换为中文！\n重新进入地图后生效。")
            self.refresh_status()
        else:
            messagebox.showerror("失败", "写入失败，请以管理员身份运行")

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    root = tk.Tk()
    app = App(root)
    root.mainloop()
