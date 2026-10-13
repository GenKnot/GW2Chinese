"""游戏更新后用来重新寻找语言指针路径的辅助脚本（代替手动在 CE 里反复扫描）。

流程：
  1. 先扫描语言值（和 CE 的"首次扫描 / 再次扫描"一样，需要你在游戏里来回切换语言）
  2. 用 main.py 里已知的偏移链，在 Gw2-64.exe 的静态数据里反推新的基址
  3. 输出可以直接粘贴进 main.py 的 POINTER_PATHS

用法（管理员权限）：
  pip install -r requirements-dev.txt
  python find_pointers.py
"""
import ctypes
import sys
from ctypes import wintypes

import numpy as np
import pymem
import pymem.process

from main import BASE_MODULE, POINTER_PATHS, LANG_MAP

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_GUARD = 0x100
WRITABLE = (0x04, 0x08, 0x40, 0x80)
CHUNK = 1 << 24  # 16MB
LOW, HIGH = 0x10000, 0x7FFFFFFFFFFF  # 用户态指针的合理范围


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def regions(pm):
    """遍历目标进程里已提交、可写、私有（堆）的内存区域。"""
    k32 = ctypes.windll.kernel32
    k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_ulonglong,
                                   ctypes.POINTER(MBI), ctypes.c_size_t]
    addr = 0
    mbi = MBI()
    while k32.VirtualQueryEx(pm.process_handle, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if (mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE
                and not mbi.Protect & PAGE_GUARD and mbi.Protect & 0xFF in WRITABLE):
            yield mbi.BaseAddress, mbi.RegionSize
        addr = mbi.BaseAddress + mbi.RegionSize


def first_scan(pm, value):
    hits = []
    for base, size in regions(pm):
        for off in range(0, size, CHUNK):
            n = min(CHUNK, size - off)
            try:
                buf = pm.read_bytes(base + off, n)
            except Exception:
                continue
            arr = np.frombuffer(buf[: n - n % 4], dtype="<i4")
            idx = np.nonzero(arr == value)[0]
            if idx.size:
                hits.append(base + off + idx.astype(np.uint64) * 4)
    return np.concatenate(hits) if hits else np.empty(0, dtype=np.uint64)


def next_scan(pm, cands, value):
    keep = []
    block = None
    data = b""
    for a in cands.tolist():
        b = a >> 20
        if b != block:
            block = b
            try:
                data = pm.read_bytes(b << 20, 1 << 20)
            except Exception:
                data = b""
        o = a - (b << 20)
        if len(data) >= o + 4 and int.from_bytes(data[o:o + 4], "little", signed=True) == value:
            keep.append(a)
    return np.array(keep, dtype=np.uint64)


def ask_int(prompt):
    while True:
        s = input(prompt).strip()
        if s.lstrip("-").isdigit():
            return int(s)


def find_candidates(pm):
    print("语言编号：" + "，".join(f"{k}={v}" for k, v in LANG_MAP.items()))
    cur = ask_int("\n游戏当前的语言编号（建议先在游戏里调成法语，输入 2）：")
    cands = first_scan(pm, cur)
    print(f"首次扫描：{len(cands)} 个结果")
    while len(cands) > 30:
        input("在游戏里切换成另一种语言（例如英语），然后回车……")
        cur = ask_int("现在的语言编号：")
        cands = next_scan(pm, cands, cur)
        print(f"再次扫描：{len(cands)} 个结果")
        if len(cands) == 0:
            sys.exit("没有结果了，请重新运行并确认输入的编号和游戏里一致。")
    return cands


def find_paths(pm, cands):
    mod = pymem.process.module_from_name(pm.process_handle, BASE_MODULE)
    base, size = mod.lpBaseOfDll, mod.SizeOfImage
    image = pm.read_bytes(base, size)
    slots = np.frombuffer(image[: size - size % 8], dtype="<u8")
    target = set(int(c) for c in cands)
    # 只取非零、看起来像用户态堆指针的槽位
    ok = np.nonzero((slots > LOW) & (slots < HIGH))[0]
    tails = []
    for _, offs in POINTER_PATHS:
        if offs not in tails:
            tails.append(offs)

    # 偏移链按前缀合并成树，共享前面几层的读取；中间值不像指针就整枝剪掉
    root = {"kids": {}, "lasts": []}
    for offs in tails:
        node = root
        for off in offs[:-1]:
            node = node["kids"].setdefault(off, {"kids": {}, "lasts": []})
        node["lasts"].append(offs)

    pages = {}

    def read8(addr):
        pg = addr >> 12
        if (addr & 0xFFF) > 0xFF8:
            try:
                return int.from_bytes(pm.read_bytes(addr, 8), "little")
            except Exception:
                return None
        if pg not in pages:
            if len(pages) > 100_000:
                pages.clear()
            try:
                pages[pg] = pm.read_bytes(pg << 12, 4096)
            except Exception:
                pages[pg] = None
        data = pages[pg]
        if data is None:
            return None
        o = addr & 0xFFF
        return int.from_bytes(data[o:o + 8], "little")

    found = []

    def walk(node, a, slot):
        for offs in node["lasts"]:
            if a + offs[-1] in target:
                found.append((slot, offs))
        for off, child in node["kids"].items():
            v = read8(a + off)
            if v is not None and LOW < v < HIGH:
                walk(child, v, slot)

    total = len(ok)
    for n, i in enumerate(ok.tolist()):
        if n % 100_000 == 0:
            print(f"  进度 {n}/{total}，已找到 {len(found)} 条", flush=True)
        walk(root, int(slots[i]), i * 8)
    return found


def main():
    pm = pymem.Pymem(BASE_MODULE)
    if len(sys.argv) > 1:  # 直接传入上次扫出的候选地址（十六进制），跳过语言扫描
        cands = np.array([int(x, 16) for x in sys.argv[1:]], dtype=np.uint64)
    else:
        cands = find_candidates(pm)
    print(f"\n候选地址：{[hex(int(c)) for c in cands]}")
    print("正在静态区反推指针路径（可能需要几十秒）……")
    found = find_paths(pm, cands)
    if not found:
        print("\n没有匹配的路径：说明偏移链本身也变了，需要用 CE 的指针扫描。")
        print("把上面的候选地址之一做指针扫描后，把结果贴给我即可。")
        return
    print("\n请把下面这些加进 main.py 的 POINTER_PATHS（建议替换旧的）：\n")
    for base_off, offs in found:
        print(f"    ({base_off:#010x}, [{', '.join(hex(o) for o in offs)}]),")


if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        sys.exit("请以管理员身份运行。")
    main()
