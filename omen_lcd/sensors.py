"""Read CPU and GPU temperatures without touching cooler hardware."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

HWMON_ROOT = Path("/sys/class/hwmon")
_NVIDIA_COMMAND = (
    "nvidia-smi",
    "--query-gpu=temperature.gpu",
    "--format=csv,noheader,nounits",
)


def _valid_temperature(value: object) -> float | None:
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(temperature) or not 0.0 <= temperature <= 125.0:
        return None
    return temperature


def _cpu_temperature() -> float | None:
    """Find Tctl/Tdie in a k10temp hwmon device, independent of hwmon index."""
    try:
        devices = sorted(HWMON_ROOT.glob("hwmon*/name"))
    except OSError:
        return None
    for name_path in devices:
        try:
            if name_path.read_text(encoding="utf-8").strip() != "k10temp":
                continue
            hwmon = name_path.parent
            labels = sorted(hwmon.glob("temp*_label"))
        except OSError:
            continue
        candidates: list[tuple[int, Path]] = []
        for label_path in labels:
            try:
                label = label_path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if label not in {"Tctl", "Tdie"}:
                continue
            stem = label_path.name.removesuffix("_label")
            try:
                index = int(stem.removeprefix("temp"))
            except ValueError:
                continue
            candidates.append((0 if label == "Tctl" else 1, hwmon / f"{stem}_input"))
        for _, input_path in sorted(candidates):
            try:
                millidegrees = float(input_path.read_text(encoding="utf-8").strip())
            except (OSError, TypeError, ValueError):
                continue
            temperature = _valid_temperature(millidegrees / 1000.0)
            if temperature is not None:
                return temperature
    return None


def _gpu_temperature() -> float | None:
    try:
        result = subprocess.run(
            list(_NVIDIA_COMMAND),
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    first_line = result.stdout.splitlines()[0].strip() if result.stdout.splitlines() else ""
    return _valid_temperature(first_line)


def read_temperatures() -> dict[str, float | None]:
    """Return the stable sensor interface used by the renderer and CLI."""
    return {"cpu_c": _cpu_temperature(), "gpu_c": _gpu_temperature()}
