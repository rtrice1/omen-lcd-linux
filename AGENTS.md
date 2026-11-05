# OMEN LCD Linux engineering

Build original Linux display-only code for HP USB 03f0:7397 interface 1. Keep firmware, fan/pump/PWM, RGB and persistent storage commands out of the implementation. Never use another USB device or interface by analogy. Preserve kernel bindings. Hardware writes require independently reviewed exact protocol evidence and parent-coordinated acceptance. The user authorized implementation and local display testing; do not repeatedly request permission. Only one process may own the LCD.

Keep HP binaries, raw captures, credentials and private host paths outside this repository. Document factual protocol observations and source hashes/links; author implementation independently. Track unverified behavior explicitly. Use MIT for original project code, with third-party notices for any actual reused open-source code. Do not assert HP endorsement or broad hardware compatibility.

Workers own assigned paths, are not alone, and must not revert unrelated work. Parent owns integration, hardware acceptance, service installation, credentials and GitHub push. Review transport independently before real-device writes. Test malformed/oversized input, exact device/interface selection, short writes, timeouts and clean shutdown. No automatic retry storm or model/GPU benchmark.
