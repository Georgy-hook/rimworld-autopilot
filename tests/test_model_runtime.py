import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import colony_director as director
import laya_runtime as runtime
import rimworld_laya as bridge
from laya_gui import app, services


def fake_torch(*, available=True, hip=None):
    return SimpleNamespace(
        __version__="test-torch", version=SimpleNamespace(cuda="test", hip=hip),
        set_num_threads=mock.Mock(), set_num_interop_threads=mock.Mock(),
        device=lambda name: name, float32="float32",
        cuda=SimpleNamespace(is_available=mock.Mock(return_value=available),
                             get_device_name=mock.Mock(return_value="GeForce GTX 1080")),
    )


class ModelRuntimeTests(unittest.TestCase):
    def test_auto_without_cuda_uses_cpu_and_caps_threads(self):
        torch = fake_torch(available=False)
        with mock.patch.object(os, "cpu_count", return_value=2), mock.patch.dict(os.environ, LAYA_CPU_THREADS="4"), \
                mock.patch.object(runtime, "cuda_probe") as probe:
            info = runtime.select_device(torch)
        self.assertEqual(info["selected_device"], "cpu")
        self.assertEqual(info["fallback_reason"], "cuda_unavailable")
        self.assertEqual(info["cpu_threads"], 2)
        self.assertFalse(info["model_loaded"])
        probe.assert_not_called()

    def test_explicit_cpu_never_initializes_a_gpu(self):
        torch = fake_torch()
        torch.cuda.is_available.side_effect = AssertionError("GPU must not be touched")
        with mock.patch.object(runtime, "cuda_probe") as probe:
            info = runtime.select_device(torch, "cpu")
        self.assertEqual(info["actual_device"], "cpu")
        self.assertEqual(info["fallback_reason"], "")
        probe.assert_not_called()

    def test_old_card_with_unsupported_kernels_falls_back_even_if_available(self):
        torch = fake_torch()
        with mock.patch.object(runtime, "cuda_probe", side_effect=RuntimeError("CUDA: no kernel image is available")):
            info = runtime.select_device(torch, "cuda")
        self.assertEqual(info["selected_device"], "cpu")
        self.assertEqual(info["gpu_name"], "GeForce GTX 1080")
        self.assertEqual(info["fallback_reason"], "cuda_probe_failed")
        self.assertIn("no kernel image", info["device_error"])

    def test_older_gpu_is_allowed_when_its_actual_kernels_work(self):
        torch = fake_torch()
        with mock.patch.object(runtime, "cuda_probe") as probe:
            info = runtime.select_device(torch)
        self.assertEqual(info["selected_device"], "cuda")
        probe.assert_called_once_with(torch)

    def test_driver_failure_is_cpu_fallback(self):
        torch = fake_torch()
        torch.cuda.is_available.side_effect = RuntimeError("driver initialization failed")
        self.assertEqual(runtime.select_device(torch)["fallback_reason"], "cuda_probe_failed")

    def test_amd_alias_is_not_advertised_as_nvidia_support(self):
        torch = fake_torch(hip="7.2")
        info = runtime.select_device(torch)
        self.assertEqual(info["selected_device"], "cpu")
        self.assertEqual(info["fallback_reason"], "rocm_not_supported")
        torch.cuda.is_available.assert_not_called()

    def test_bad_thread_environment_cannot_crash_model_start(self):
        for value, expected in (("invalid", 4), ("0", 1), ("200", 8)):
            with mock.patch.dict(os.environ, LAYA_CPU_THREADS=value), mock.patch.object(os, "cpu_count", return_value=32):
                self.assertEqual(runtime.configure_cpu_threads(fake_torch()), expected)

    def info(self, selected="cuda"):
        return dict(requested_device="auto", selected_device=selected, actual_device=selected,
                    fallback_reason="", cpu_threads=4, model_loaded=False)

    def test_gpu_load_failure_retries_cpu_once(self):
        loader = mock.Mock(side_effect=[RuntimeError("CUDA out of memory"), SimpleNamespace(device="cpu")])
        agent = runtime.load_model(loader, "cached-model", fake_torch(), self.info())
        self.assertEqual(loader.call_args_list, [mock.call("cached-model", device="cuda"), mock.call("cached-model", device="cpu")])
        info = agent.runtime_info()
        self.assertEqual(info["actual_device"], "cpu")
        self.assertTrue(info["model_loaded"])
        self.assertEqual(info["fallback_reason"], "cuda_load_failed")

    def test_bad_weights_and_cpu_memory_failure_are_not_hidden_by_retries(self):
        for exc, device in ((RuntimeError("incompatible model weights"), "cuda"),
                            (FileNotFoundError("missing weights"), "cuda"),
                            (RuntimeError("out of memory"), "cpu")):
            loader = mock.Mock(side_effect=exc)
            with self.assertRaises(type(exc)):
                runtime.load_model(loader, "cached-model", fake_torch(), self.info(device))
            self.assertEqual(loader.call_count, 1)

    def test_gpu_inference_failure_retries_identical_input_once_and_reports_cpu(self):
        inner = SimpleNamespace(device="cuda:0", model=mock.Mock(),
                                predict=mock.Mock(side_effect=[RuntimeError("CUDA driver error"), {"answers": {"a": "ok"}}]))
        agent = runtime.DeviceAgent(inner, fake_torch(), self.info())
        state, questions = "original state", {"a": {"type": "choice"}}
        self.assertEqual(agent.predict(state, questions), {"answers": {"a": "ok"}})
        self.assertEqual(inner.predict.call_args_list, [mock.call(state, questions), mock.call(state, questions)])
        inner.model.to.assert_called_once_with(device="cpu", dtype="float32")
        self.assertEqual(agent.runtime_info()["actual_device"], "cpu")
        self.assertEqual(agent.runtime_info()["fallback_reason"], "cuda_inference_failed")
        self.assertIn("last_predict_ms", agent.runtime_info())

    def test_cpu_inference_failure_and_non_device_error_do_not_retry(self):
        for device, message in (("cpu", "out of memory"), ("cuda", "incompatible input shape")):
            inner = SimpleNamespace(device=device, model=mock.Mock(), predict=mock.Mock(side_effect=RuntimeError(message)))
            agent = runtime.DeviceAgent(inner, fake_torch(), self.info(device))
            with self.assertRaises(RuntimeError):
                agent.predict("state", {})
            self.assertEqual(inner.predict.call_count, 1)
            inner.model.to.assert_not_called()

    def test_library_fallback_during_inference_updates_gui_status(self):
        inner = SimpleNamespace(device="cuda", dtype="fp16")

        def predict(*args):
            inner.device, inner.dtype = "cpu", "float32"
            return {"answers": {}}

        inner.predict = predict
        agent = bridge.SafeDecisionAgent(runtime.DeviceAgent(inner, fake_torch(), dict(self.info(), model_loaded=True)))
        agent.predict("state", {"a": {"type": "choice", "criteria": {"x": "X", "y": "Y"}}})
        with tempfile.TemporaryDirectory() as folder:
            status = Path(folder, "runtime-status.json")
            self.assertTrue(director.write_runtime_status(status, "running", model_runtime=agent.runtime_info()))
            payload = json.loads(status.read_text())
        self.assertEqual(payload["model_runtime"]["actual_device"], "cpu")
        self.assertEqual(payload["model_runtime"]["dtype"], "float32")
        self.assertEqual(payload["model_runtime"]["fallback_reason"], "model_fallback")

    def test_defaults_use_auto_and_saved_explicit_device_is_preserved(self):
        self.assertEqual(director.parser().parse_args([]).device, "auto")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / "user.json"
            self.assertEqual(services.load_config(root, config_path=config_path)["device"], "auto")
            config_path.write_text(json.dumps({"device": "cpu"}))
            self.assertEqual(services.load_config(root, config_path=config_path)["device"], "cpu")

    def test_gui_device_change_preserves_run_without_restart(self):
        center = SimpleNamespace(config_data={"logs_dir": "existing run", "api_url": "http://localhost:9000", "device": "cuda"},
                                 language="en", footer=mock.Mock())
        with mock.patch.object(app, "save_config") as save, mock.patch.object(app, "stop_director") as stop, \
                mock.patch.object(app, "start_director") as start:
            app.ControlCenter.save_model_device(center, "cpu")
        self.assertEqual(save.call_args.args[0], dict(center.config_data, device="cpu"))
        self.assertEqual(center.config_data["logs_dir"], "existing run")
        start.assert_not_called()
        stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
