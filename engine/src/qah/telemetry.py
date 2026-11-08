"""Sample device-wide VRAM and process RAM; missing counters remain null."""
import ctypes
import os
import subprocess
import threading
import time


def host_inventory():
    if os.name != 'nt':
        return dict(platform=os.name, memory=None)
    from ctypes import wintypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
            (key, ctypes.c_ulonglong) for key in ('physical_total', 'physical_available',
            'pagefile_total', 'pagefile_available', 'virtual_total', 'virtual_available', 'extended')]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return dict(platform=os.name, memory=None, error=ctypes.get_last_error())
    return dict(platform=os.name, physical_total_bytes=status.physical_total,
                physical_available_bytes=status.physical_available,
                commit_limit_bytes=status.pagefile_total, commit_available_bytes=status.pagefile_available)


def gpu_sample():
    try:
        p = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.free',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True,
                           timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if p.returncode:
            return None
        used, free = [int(x.strip()) * 1024**2 for x in p.stdout.splitlines()[0].split(',')]
        return dict(used=used, free=free)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def process_memory(pid):
    if os.name != 'nt':
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (key, ctypes.c_size_t) for key in ('peak_rss', 'rss', 'peak_paged', 'paged',
                                              'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    kernel, psapi = ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('psapi')
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
    if not handle:
        return None
    try:
        counter = Counters()
        counter.cb = ctypes.sizeof(counter)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counter), counter.cb):
            return dict(rss=counter.rss, peak_rss=counter.peak_rss, pagefile=counter.pagefile)
    finally:
        kernel.CloseHandle(handle)


class Monitor:
    def __init__(self, executor):
        self.executor = executor
        self.samples = []
        self.stop = threading.Event()

    def __enter__(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self

    def run(self):
        while not self.stop.is_set():
            process = self.executor.process
            self.samples.append(dict(time=time.time(), gpu=gpu_sample(),
                                     ram=process_memory(process.pid) if process else None))
            self.stop.wait(0.25)

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=6)

    def report(self):
        gpu = [s['gpu']['used'] for s in self.samples if s['gpu']]
        ram = [s['ram']['peak_rss'] for s in self.samples if s['ram']]
        return dict(device_vram_peak_sampled_bytes=max(gpu) if gpu else None,
                    process_peak_rss_bytes=max(ram) if ram else None,
                    samples=len(self.samples), device_counter_includes_other_processes=True,
                    target_sample_interval_seconds=0.25, exact_vram_peak=False,
                    scope='trial startup through current request; cumulative')
