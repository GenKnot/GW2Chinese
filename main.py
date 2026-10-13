import tkinter as tk
from tkinter import messagebox
import pymem
import pymem.process
import pymem.exception
import ctypes
import sys
from ctypes import wintypes

_BASES_A = [0x0266C030, 0x0266C608, 0x0266C740, 0x0289C780, 0x028B7CD0]
_TAILS_A = [
    [0x18, 0x20, 0x50, 0x10, 0x324],
    [0x0,  0x38, 0x50, 0x10, 0x324],
    [0x38, 0x50, 0x10, 0x324],
    [0x0,  0x18, 0x20, 0x50, 0x334],
    [0x18, 0x20, 0x50, 0x334],
    [0x0,  0x38, 0x50, 0x334],
    [0x38, 0x50, 0x334],
]
_TAILS_B = [  # 0x0289C778
    [0x58, 0x38, 0x50, 0x10, 0x324],
    [0x58, 0x38, 0x50, 0x334],
    [0x58, 0x0,  0x38, 0x50, 0x334],
]
_TAILS_C = {  # 0x0266EF68
    0x0266EF68: [
        [0x9F0, 0x70, 0x2FC], [0x9F0, 0x78, 0x20, 0x2FC], [0x9F0, 0x78, 0x70, 0x2FC],
        [0x9F0, 0x78, 0x28, 0x20, 0x2FC], [0x9F0, 0x78, 0x28, 0x70, 0x2FC],
        [0x9F0, 0x78, 0x78, 0x20, 0x2FC], [0x9F0, 0x78, 0x78, 0x70, 0x2FC],
        [0x88, 0x70, 0x2FC], [0x88, 0x78, 0x20, 0x2FC], [0x88, 0x78, 0x70, 0x2FC],
        [0x88, 0x78, 0x28, 0x20, 0x2FC], [0x88, 0x78, 0x28, 0x70, 0x2FC],
        [0x88, 0x78, 0x78, 0x20, 0x2FC],
        [0xD38, 0x70, 0x2FC], [0xD38, 0x78, 0x20, 0x2FC], [0xD38, 0x78, 0x70, 0x2FC],
        [0xD38, 0x78, 0x28, 0x20, 0x2FC], [0xD38, 0x78, 0x28, 0x70, 0x2FC],
        [0xD38, 0x78, 0x78, 0x20, 0x2FC],
        [0x88, 0x70, 0x258, 0xA4], [0x9F0, 0x70, 0x258, 0xA4], [0xD38, 0x70, 0x258, 0xA4],
        [0x88, 0x78, 0x20, 0x258, 0xA4], [0x88, 0x78, 0x70, 0x258, 0xA4],
        [0x9F0, 0x78, 0x20, 0x258, 0xA4], [0x9F0, 0x78, 0x70, 0x258, 0xA4],
        [0xD38, 0x78, 0x20, 0x258, 0xA4], [0xD38, 0x78, 0x70, 0x258, 0xA4],
    ],
    0x026B25B8: [
        [0x230, 0xEB8, 0x70, 0x2FC], [0x230, 0xD8, 0x70, 0x2FC], [0x230, 0x558, 0x70, 0x2FC],
        [0x230, 0xD8, 0x78, 0x70, 0x2FC], [0x230, 0xD8, 0x78, 0x20, 0x2FC],
        [0x230, 0x558, 0x78, 0x20, 0x2FC], [0x230, 0xEB8, 0x78, 0x20, 0x2FC],
        [0x230, 0xEB8, 0x70, 0x258, 0xA4], [0x230, 0x558, 0x70, 0x258, 0xA4],
        [0x230, 0xD8, 0x70, 0x258, 0xA4],
    ],
    0x026A97E8: [
        [0xE08, 0x18, 0x70, 0x2FC], [0xE08, 0x18, 0x78, 0x70, 0x2FC],
        [0xE08, 0x18, 0x78, 0x20, 0x2FC], [0xE08, 0x18, 0x70, 0x258, 0xA4],
    ],
    0x028B4620: [[0x80, 0x10, 0x18, 0x70, 0x2FC]],
}

POINTER_PATHS = (
    [(b, t) for b in _BASES_A for t in _TAILS_A]
    + [(0x0289C778, t) for t in _TAILS_B]
    + [(b, t) for b, tails in _TAILS_C.items() for t in tails]
)
CHINESE = 5
ENGLISH = 0

LANG_MAP = {0: "英语", 2: "法语", 3: "德语", 4: "西班牙语", 5: "中文"}

BASE_MODULE = "Gw2-64.exe"

class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]

def find_pid(name):
    # pymem 按名字找进程会用系统编码解码所有进程名，遇到非 ASCII 进程名会崩，所以自己用宽字符 API 找
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == name.lower():
                return entry.th32ProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return None

def open_game():
    pid = find_pid(BASE_MODULE)
    if pid is None:
        raise pymem.exception.ProcessNotFound(BASE_MODULE)
    return pymem.Pymem(pid)

def main_module_base(pm):
    # 模块列表的第一个就是主程序 exe，直接取基址，不用解码模块名
    psapi = ctypes.windll.psapi
    psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    mods = (ctypes.c_void_p * 1024)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(pm.process_handle, ctypes.byref(mods),
                                      ctypes.sizeof(mods), ctypes.byref(needed), 0x03):
        raise OSError("EnumProcessModulesEx failed")
    return mods[0]

def resolve_pointer(pm, base_offset, offsets):
    base = main_module_base(pm)
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

LAST_ERROR = ""

STATUS_TEXT = {
    "no_process": "未检测到游戏，请先启动GW2",
    "no_access": "无法访问游戏进程，请以管理员身份运行",
    "no_match": "游戏版本不匹配，请更新游戏后重试",
}

def read_state():
    """返回 (状态, 语言值)。状态：ok / no_process / no_access / no_match"""
    try:
        pm = open_game()
    except pymem.exception.ProcessNotFound:
        return "no_process", None
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = f"{type(e).__name__}: {e} | admin={bool(is_admin())}"
        return "no_access", None
    try:
        addr = find_lang_addr(pm)
        if addr is None:
            return "no_match", None
        return "ok", pm.read_int(addr)
    except Exception:
        return "no_match", None
    finally:
        pm.close_process()

def get_lang():
    return read_state()[1]

def set_lang(value):
    try:
        pm = open_game()
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
        root.geometry("300x220")
        root.resizable(False, False)

        tk.Label(root, text="Guild Wars 2 语言切换工具", font=("微软雅黑", 12, "bold")).pack(pady=(15, 2))
        tk.Label(root, text="by Discord: 503", font=("微软雅黑", 8), fg="gray").pack()

        self.status_label = tk.Label(root, text="检测中...", font=("微软雅黑", 10))
        self.status_label.pack()

        self.err_label = tk.Label(root, text="", font=("Consolas", 7), fg="gray", wraplength=280)
        self.err_label.pack()

        self.btn = tk.Button(root, text="切换为中文", font=("微软雅黑", 11),
                             width=15, height=2, command=self.switch_language)
        self.btn.pack(pady=15)

        self.refresh_status()
        self.root.after(3000, self.auto_refresh)

    def auto_refresh(self):
        self.refresh_status()
        self.root.after(3000, self.auto_refresh)

    def refresh_status(self):
        state, val = read_state()
        if state != "ok":
            self.status_label.config(text=STATUS_TEXT[state], fg="red")
            self.err_label.config(text=LAST_ERROR if state == "no_access" else "")
            self.btn.config(state="disabled", text="切换为中文")
        else:
            self.err_label.config(text="")
            lang_name = LANG_MAP.get(val, f"未知({val})")
            self.status_label.config(text=f"当前语言：{lang_name}", fg="green" if val == CHINESE else "orange")
            self.btn.config(state="normal",
                            text="已是中文 ✓" if val == CHINESE else "切换为中文")

    def switch_language(self):
        state, val = read_state()
        if state != "ok":
            messagebox.showerror("错误", STATUS_TEXT[state])
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
