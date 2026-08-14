from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import List


@dataclass
class LLMCallRecord:
    timestamp: float
    latency: float
    approx_tokens: int


@dataclass
class MetricsCollector:
    llm_calls: List[LLMCallRecord] = field(default_factory=list)
    start_time: float | None = None
    end_time: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def start_run(self):
        with self.lock:
            self.start_time = time.perf_counter()
            self.llm_calls.clear()

    def end_run(self):
        with self.lock:
            self.end_time = time.perf_counter()

    def record_call(self, latency: float, approx_tokens: int):
        with self.lock:
            self.llm_calls.append(LLMCallRecord(time.perf_counter(), latency, approx_tokens))

    def total_calls(self) -> int:
        return len(self.llm_calls)

    def total_tokens(self) -> int:
        return sum(r.approx_tokens for r in self.llm_calls)

    def total_latency(self) -> float:
        if self.start_time is None or self.end_time is None:
            return sum(r.latency for r in self.llm_calls)
        return self.end_time - self.start_time


# Global collector used by planning evaluation harness
_global_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    return _global_collector


def record_llm_call(latency: float, approx_tokens: int):
    _global_collector.record_call(latency, approx_tokens)


def start_metrics():
    _global_collector.start_run()


def end_metrics():
    _global_collector.end_run()


def export_summary() -> dict:
    return {
        "llm_calls": _global_collector.total_calls(),
        "total_tokens": _global_collector.total_tokens(),
        "total_latency_sec": _global_collector.total_latency(),
    }
