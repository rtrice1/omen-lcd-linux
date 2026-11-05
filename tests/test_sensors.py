from pathlib import Path

import omen_lcd.sensors as sensors


def _hwmon(tmp_path: Path, name: str = "k10temp", label: str = "Tctl", value: str = "67500") -> Path:
    hwmon = tmp_path / "hwmon7"
    hwmon.mkdir()
    (hwmon / "name").write_text(name)
    (hwmon / "temp1_label").write_text(label)
    (hwmon / "temp1_input").write_text(value)
    return tmp_path


def test_cpu_uses_name_and_label_not_hwmon_index(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "HWMON_ROOT", _hwmon(tmp_path))
    assert sensors._cpu_temperature() == 67.5


def test_invalid_cpu_temperature_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sensors, "HWMON_ROOT", _hwmon(tmp_path, value="999999"))
    assert sensors._cpu_temperature() is None


def test_gpu_timeout_is_missing(monkeypatch):
    def timeout(*args, **kwargs):
        raise sensors.subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=3)

    monkeypatch.setattr(sensors.subprocess, "run", timeout)
    assert sensors._gpu_temperature() is None


def test_read_temperatures_keeps_exact_keys(monkeypatch):
    monkeypatch.setattr(sensors, "_cpu_temperature", lambda: None)
    monkeypatch.setattr(sensors, "_gpu_temperature", lambda: 42.0)
    assert sensors.read_temperatures() == {"cpu_c": None, "gpu_c": 42.0}
