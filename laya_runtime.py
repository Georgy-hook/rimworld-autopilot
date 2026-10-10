"""Local model device selection; imported by the Python worker, not the GUI."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable


def configure_cpu_threads(torch: Any) -> int:
    try:
        requested = int(os.environ.get("LAYA_CPU_THREADS", "4"))
    except ValueError:
        requested = 4
    threads = max(1, min(8, os.cpu_count() or 1, requested))
    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # This can only be set before the first inference in a process.
    return threads


def cuda_probe(torch: Any) -> None:
    """Execute kernels: driver detection alone cannot verify an old GPU wheel."""
    major, _ = torch.cuda.get_device_capability(0)
    dtype = torch.bfloat16 if major >= 8 and torch.cuda.is_bf16_supported() else torch.float16
    with torch.inference_mode():
        query = torch.ones((1, 2, 8, 32), device="cuda", dtype=dtype)
        attended = torch.nn.functional.scaled_dot_product_attention(query, query, query)
        product = attended[0, 0] @ attended[0, 0].transpose(0, 1)
        normalized = torch.nn.functional.layer_norm(product, (8,))
        if not torch.isfinite(normalized).all().item():
            raise RuntimeError("CUDA probe produced non-finite values")
        torch.cuda.synchronize()


def select_device(torch: Any, requested: str = "auto") -> dict[str, Any]:
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"Unknown model device: {requested!r}")
    info = {
        "requested_device": requested, "selected_device": "cpu",
        "actual_device": "cpu", "gpu_name": "", "fallback_reason": "",
        "model_loaded": False,
        "torch_version": str(torch.__version__),
        "cuda_version": getattr(torch.version, "cuda", None),
        "cpu_threads": configure_cpu_threads(torch),
    }
    if requested == "cpu":
        return info
    # The shipped Windows setup does not install or validate AMD's separate
    # ROCm stack. Do not mistake its torch.cuda alias for tested NVIDIA support.
    if getattr(torch.version, "hip", None):
        info["fallback_reason"] = "rocm_not_supported"
        return info
    try:
        if not torch.cuda.is_available():
            info["fallback_reason"] = "cuda_unavailable"
            return info
        info["gpu_name"] = torch.cuda.get_device_name(0)
        cuda_probe(torch)
    except (RuntimeError, AssertionError, OSError) as exc:
        info.update(fallback_reason="cuda_probe_failed", device_error=str(exc)[:500])
        return info
    info.update(selected_device="cuda", actual_device="cuda")
    return info


def acceleration_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return isinstance(exc, RuntimeError) and any(term in text for term in (
        "cuda", "cublas", "cudnn", "out of memory", "no kernel image",
        "driver", "invalid device", "gpu memory",
    ))


class DeviceAgent:
    """Report actual placement and retry a GPU failure once on CPU."""

    def __init__(self, inner: Any, torch: Any, info: dict[str, Any]) -> None:
        self.inner, self.torch, self.info = inner, torch, dict(info)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def runtime_info(self) -> dict[str, Any]:
        actual = str(getattr(self.inner, "device", self.info["actual_device"]))
        self.info["actual_device"] = actual
        self.info["dtype"] = str(getattr(self.inner, "dtype", "unknown"))
        if actual == "cpu" and self.info["selected_device"] == "cuda" and not self.info["fallback_reason"]:
            self.info["fallback_reason"] = "model_fallback"
        return dict(self.info)

    def predict(self, state: Any, questions: Any) -> Any:
        started = time.perf_counter()
        try:
            try:
                return self.inner.predict(state, questions)
            except RuntimeError as exc:
                if not self.runtime_info()["actual_device"].startswith("cuda") or not acceleration_error(exc):
                    raise
                self.info.update(fallback_reason="cuda_inference_failed", device_error=str(exc)[:500])
                print(f"GPU inference failed; retrying on CPU: {exc}", flush=True)
                self.inner.device = self.torch.device("cpu")
                self.inner.dtype = self.torch.float32
                self.inner.model.to(device="cpu", dtype=self.torch.float32).eval()
                return self.inner.predict(state, questions)
        finally:
            self.info["last_predict_ms"] = round((time.perf_counter() - started) * 1000, 2)


def load_model(loader: Callable[..., Any], model: str, torch: Any, info: dict[str, Any]) -> DeviceAgent:
    started = time.perf_counter()
    try:
        inner = loader(model, device=info["selected_device"])
    except RuntimeError as exc:
        if info["selected_device"] != "cuda" or not acceleration_error(exc):
            raise
        info.update(fallback_reason="cuda_load_failed", device_error=str(exc)[:500])
        print(f"GPU model loading failed; retrying on CPU: {exc}", flush=True)
        inner = loader(model, device="cpu")
    info["load_seconds"] = round(time.perf_counter() - started, 3)
    info["model_loaded"] = True
    agent = DeviceAgent(inner, torch, info)
    print("Model runtime: " + json.dumps(agent.runtime_info(), ensure_ascii=False), flush=True)
    return agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    import torch
    info = select_device(torch, args.device)
    serialized = json.dumps(info, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
