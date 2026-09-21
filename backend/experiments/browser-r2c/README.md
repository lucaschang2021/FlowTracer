# ACQ-1 WP-3 R2C identity gate

This directory starts R2C from the byte-identical, merged R1C build inputs. `run_identity_gate.py` performs the mandatory no-cache build and compares the resulting full Chromium image with the frozen R1C identity before any controlled-egress network is created.

The root-only normalized filesystem inspection is distinct from later UID 10001 browser runtime probes. A mismatch is fail-closed: the runner records the mismatch, removes only its uniquely named image and builder, verifies protected experiment files, and does not start the R2 network matrix.
