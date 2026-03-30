import tkinter as tk
from tkinter import messagebox
import pymem
import pymem.process
import ctypes
import sys

POINTER_PATHS = [
    (0x026A9B30, [0x38, 0x50, 0x10, 0x324]),
    (0x026A9B30, [0x18, 0x20, 0x50, 0x334]),
    (0x026A9B30, [0x0,  0x38, 0x50, 0x334]),
    (0x026A9B30, [0x38, 0x50, 0x334]),
    (0x026A9B30, [0x38, 0x50, 0x290, 0xA4]),
    (0x026AA108, [0x38, 0x50, 0x10, 0x324]),
    (0x026AA108, [0x18, 0x20, 0x50, 0x334]),
    (0x026AA108, [0x0,  0x38, 0x50, 0x334]),
    (0x026AA108, [0x38, 0x50, 0x334]),
    (0x026AA108, [0x38, 0x50, 0x290, 0xA4]),
    (0x026AA240, [0x38, 0x50, 0x10, 0x324]),
    (0x026AA240, [0x18, 0x20, 0x50, 0x334]),
    (0x026AA240, [0x0,  0x38, 0x50, 0x334]),
    (0x026AA240, [0x38, 0x50, 0x334]),
    (0x026AA240, [0x38, 0x50, 0x290, 0xA4]),
    (0x028D8C48, [0x58, 0x38, 0x50, 0x334]),
    (0x028D8C50, [0x38, 0x50, 0x10, 0x324]),
    (0x028D8C50, [0x18, 0x20, 0x50, 0x334]),
    (0x028D8C50, [0x0,  0x38, 0x50, 0x334]),
    (0x028D8C50, [0x38, 0x50, 0x334]),
    (0x028D8C50, [0x38, 0x50, 0x290, 0xA4]),
    (0x028F3F10, [0x38, 0x50, 0x10, 0x324]),
    (0x028F3F10, [0x18, 0x20, 0x50, 0x334]),
    (0x028F3F10, [0x0,  0x38, 0x50, 0x334]),
    (0x028F3F10, [0x38, 0x50, 0x334]),
    (0x028F3F10, [0x38, 0x50, 0x290, 0xA4]),
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

def get_lang():
    try:
        pm = pymem.Pymem(BASE_MODULE)
        for base_offset, offsets in POINTER_PATHS:
            addr, val = try_read(pm, base_offset, offsets)
            if val is not None:
                pm.close_process()
                return val
        pm.close_process()
    except:
        pass
    return None

def set_lang(value):
    try:
        pm = pymem.Pymem(BASE_MODULE)
        for base_offset, offsets in POINTER_PATHS:
            addr, val = try_read(pm, base_offset, offsets)
            if val is not None:
                pm.write_int(addr, value)
                pm.close_process()
                return True
        pm.close_process()
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
