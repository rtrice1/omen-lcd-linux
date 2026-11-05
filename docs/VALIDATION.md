# Validation status

Tested on Ubuntu 26.04, Python 3.14.4, HP OMEN MAX 45L GT23-0xxx with AMD CPU and NVIDIA GPU, using LCD-PUMP USB `03f0:7397`, interface 1.

| Check | Evidence / result |
| --- | --- |
| Unit tests | 30 passed using `python3 -m pytest -q`; protocol boundaries, device/interface/descriptor checks, invalid images, short writes, exclusive ownership, timeout cleanup, sensors, rendering and SIGTERM handling. No hardware is used by these tests. |
| Isolated package install | Fresh virtual environment; console entry point, passive discovery and image preview passed. |
| First physical image | One `show` operation sent 36 reports in 0.104 seconds on 2026-11-05; the operator confirmed that the CPU/GPU dashboard was visible on the cooler. |
| Permission isolation | Only the display node changed to group `omenlcd`, mode `0660`; mouse-interface permissions remained unchanged. A nonroot process opened the verified display with zero reports written, rejected the mouse interface, and could not open its raw node. |
| Background service | Installed in `/opt/omen-lcd-linux`, running as the regular user with supplementary `omenlcd`, enabled for future boots, two-second configured refresh. Initial observation showed no restarts. |
| Physical live refresh | The operator confirmed that the timestamp advances on the physical cooler screen while the background service runs. |
| Cold boot / unplug recovery | Not tested. Enabling the unit configures startup; it does not prove a reboot test. |
| Device-side image persistence | Unknown. The implementation uses only the observed image-sync operation, without any firmware or stored-image API. |

The receiver supplies no acknowledgement in the analyzed synchronization path. Kernel acceptance alone is not a visibility test. Compatibility is intentionally limited to the exact known USB identity and cached report descriptor; a different descriptor is refused.
