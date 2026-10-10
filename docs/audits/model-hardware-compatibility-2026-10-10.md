# Model hardware compatibility — 10 October 2026

Scope: unpublished `0.0.8` source and installer. The active colony continues
with its recorded installation; these changes have not been injected into it.
The public stable installer remains `v0.0.7`.

## Supported paths

| Computer | Model execution in this Windows package |
| --- | --- |
| Compatible NVIDIA GPU, driver and CUDA PyTorch wheel | CUDA after a real kernel probe; CPU on a device failure |
| Older NVIDIA GPU | CUDA only if its installed wheel executes the probe; otherwise CPU |
| AMD graphics | CPU; this package does not install ROCm or DirectML |
| Integrated graphics or no discrete GPU | CPU; RimWorld still needs its own supported graphics hardware |
| Explicit CPU choice | CPU without probing or initializing CUDA |

Automatic is now the default in the GUI, director and PowerShell entry points.
Existing explicit device choices remain saved. The probe executes attention,
matrix multiplication and normalization and synchronizes the GPU; a positive
`torch.cuda.is_available()` alone cannot establish architecture compatibility.
There is no fixed GPU age cutoff: an old card with a compatible wheel can pass.

GPU model loading and inference failures get one CPU retry with the same input.
CPU allocation errors, missing weights, incompatible weights and unrelated
input errors remain errors. Laya's own CPU fallback is observed too. Runtime
status exposes the requested, selected and actual device, dtype, CPU thread
count, fallback reason and latest inference duration. GUI Settings shows actual
placement and allows the next launch's device to be changed without interrupting
the running director. Default CPU threads are four, capped by available cores
and eight; an invalid override no longer prevents startup.

The CPU setup choice installs PyTorch from its official CPU wheel index before
the application dependencies. Setup runs the device probe before the first model
download. Model inference, unlike this small probe, requires sufficient system
RAM. CPU latency depends on the processor, context length and simultaneous game
load; one small decision is not a large-context performance benchmark.

## Clean installation defect

`requirements.txt` pinned `laya==0.3.7`, which was absent from the public PyPI
release list when checked on 10 October. A direct pip download failed. The
running cached environment actually contained `0.3.4`; it did not validate that
fresh installation pin. The candidate now pins the available, tested `0.3.4`.
The [PyPI package](https://pypi.org/project/laya/0.3.4/) declares Python >=3.8;
the app's supported setup range remains Python 3.10–3.12.

## Verification

- 1,364 Python tests passed, including 14 device tests. Tests cover absent CUDA,
  explicit CPU, a working older card, unavailable kernels, driver initialization
  failure, AMD's HIP alias, GPU load/inference fallback, non-device errors,
  actual runtime status and preserving a GUI run when its future device changes.
- The current cached `laya 0.3.4` checkpoint actually loaded on CPU/float32 with
  two threads and produced a two-option decision. Load: 14.775s; model inference:
  218.49ms. This PC's PyTorch was `2.14.0+cu130`, but the model was explicitly
  placed and evaluated on CPU. A separate CPU-only installation check is
  recorded separately below.
- The small real CUDA probe passed on this PC's RTX5070Ti. AMD GPU acceleration
  and a physical older NVIDIA card were not tested. Their fallback control
  paths were tested with injected hardware/driver failures.
- Source GUI initialization passed in Russian and English. Installation tests
  verify the CPU index and probe/download order while preserving user settings.
- A separate fresh virtual environment installed the official `torch 2.14.1+cpu`
  wheel, `laya 0.3.4`, `transformers 5.19.0` and the app requirements. CUDA was
  absent (`torch.version.cuda=None`). Automatic selected CPU/float32/two threads
  and the actual checkpoint produced a decision: load18.12s, inference203.49ms.
  This is an actual CPU-only dependency and inference check, not simulated
  device availability in a CUDA installation.
- The required cached-model startup replay also passed on CPU: equipment was
  followed by starter-base construction through its offline transport, with
  no connection or gameplay command to the running colony. The313-route API
  audit passed without contacting the game; native source/DLL did not change.

Run a device probe without downloading model weights:

```powershell
.venv/Scripts/python.exe laya_runtime.py --device auto --output model-device.json
```

Run a real model decision without connecting to RimWorld:

```powershell
.venv/Scripts/python.exe tools/check_model_runtime.py --device cpu --output cpu-check.json
```

## Primary references

PyTorch documents both [Windows CPU and CUDA installation](https://pytorch.org/get-started/locally/).
Its [2.8 release notes](https://pytorch.org/blog/pytorch-2-8/) describe GPU
architecture support changes between CUDA builds. AMD publishes a separate
[Windows ROCm compatibility matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/windows/windows_compatibility.html);
its availability does not establish support in this application's installer.
The [upstream Laya SDK](https://github.com/NandhaKishorM/laya) documents CPU device
selection; the runtime checks above exercise the pinned package instead of
assuming the newest upstream code is installed.
