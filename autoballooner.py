#!/usr/bin/env python3

import time
from collections import deque
import statistics

TARGET_PAGES_FILE = "/sys/bus/virtio/drivers/virtio_balloon/virtio1/jgowans/target_pages"
PAGE_SIZE = 4096

class MemoryUsageTracker:
    def __init__(self):
        self.memused_queue = deque()

    def update_stats(self, meminfo, balloon_pages):
        self.memused_queue.appendleft(self._used(meminfo, balloon_pages))
        if len(self.memused_queue) > 10:
            self.memused_queue.pop()

    def predict_usage(self, meminfo, balloon_pages):
        print("Statistics: {}".format(statistics.mean(self.memused_queue) + statistics.stdev(self.memused_queue)))
        print("Current: {}".format(self._used(meminfo, balloon_pages) * 1.2))
        return max(
            statistics.mean(self.memused_queue) + statistics.stdev(self.memused_queue),
            self._used(meminfo, balloon_pages) * 1.2)

    def _used(self, meminfo, balloon_pages):
        return meminfo["MemTotal"] - meminfo["MemAvailable"] - (balloon_pages * PAGE_SIZE)

balloon_pages = 0

def get_meminfo():
    meminfo = {}
    with open("/proc/meminfo") as f:
        for line in f.readlines():
            # this is super brittle. Shoot me later.
            name, size = [x.strip() for x in line.split(":")]
            if len(size.split(" ")) > 1:
                size_int, unit = [x.strip() for x in size.split(" ")]
                if unit == "kB":
                    meminfo[name] = int(size_int) * 1024
                else:
                    print("Unexpected unit: {}" % unit)
                    exit(1)
    return meminfo

# relative to current pages. Can be positive or negative.
def adjust_balloon_pages(diff):
    diff = min(16384, int(diff))
    current_balloon = int(open(TARGET_PAGES_FILE).read().strip())
    if diff < 256:
        current_balloon
    new_balloon = str(int(current_balloon + diff))
    print("Adjusting balloon to {} pages".format(new_balloon))
    open(TARGET_PAGES_FILE, "w").write(new_balloon)
    return int(new_balloon)

def set_balloon(pages):
    pages = max(int(pages), 0)
    print("Adjusting balloon to {} pages".format(pages))
    open(TARGET_PAGES_FILE, "w").write(str(pages))
    return pages

set_balloon(0)
time.sleep(3)
mem_usage_tracker = MemoryUsageTracker()
meminfo = get_meminfo()
mem_usage_tracker.update_stats(meminfo, balloon_pages)

while True:
    meminfo = get_meminfo()
    mem_usage_tracker.update_stats(meminfo, balloon_pages)
    balloon_pages = (meminfo["MemTotal"] - (mem_usage_tracker.predict_usage(meminfo, balloon_pages) + 200*1024*1024)) / PAGE_SIZE
    balloon_pages = set_balloon(balloon_pages)
    time.sleep(2)
