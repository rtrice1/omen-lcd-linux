# LCD image synchronization: static-analysis evidence

**Status:** implementation-relevant, but not hardware-validated.  This is a
display-image transport observation, not an assertion about firmware, cooling,
lighting, persistent storage, or any other device capability.

## Scope and provenance

This note records a source-versioned static analysis of the following supplied
HP component.  The binary itself, disassembly, raw captures, and any HP
installer files are deliberately not stored in this repository.

| Item | Value |
| --- | --- |
| Official package provenance | [HP SoftPaq sp159997](https://ftp.hp.com/pub/softpaq/sp159501-160000/sp159997.html) |
| Component filename | `bin\witmodSdkOther.dll` (the backslash is a literal filename character in the extracted material) |
| SHA-256 | `57c403511b6a48c223a2ad214372b1292ae35dec6742e4941e0bd6e3111a8c6f` |
| PE format / image base | PE32+ x86-64 / `0x180000000` |
| Analysis date | 2026-11-05 |
| Public cross-reference | [OMEN-LCD-CONTROL backend note, pinned revision](https://github.com/RohithKarthikeyan/OMEN-LCD-CONTROL/blob/19807f5065bd28415b68514022fa0d6d9f28159/docs/backend.md), which names `CWitmodHid_SynchronizeImage(handle, jpegPath)` but does not specify packets |

All addresses below are RVAs unless an absolute virtual address is explicitly
shown.  The statement of the input HID report shape (report ID 2 and a 1,024
byte total output report) comes from the separately collected device descriptor
evidence.  The byte layout, chunking, call path, and retry behaviour below come
from this DLL only.

## Exact display-image packet contract

`CWitmodHid_SynchronizeImageV2` is exported at RVA `0x8460`.  Its observed
Windows x64 calling convention is `(opaque_handle, signed int byte_count,
byte_pointer)`.  It sends the byte sequence as fixed 1,024-byte output reports.
For a positive byte count `N`, it emits `ceil(N / 1013)` reports numbered from
zero.  For report index `i`, let `L = min(1013, N - 1013*i)`.

| Offset | Size | Value |
| --- | ---: | --- |
| 0 | 1 | `0x02` — HID report ID |
| 1 | 1 | `0x6e` — image-data command byte |
| 2–5 | 4 | `N` as unsigned 32-bit big-endian |
| 6–8 | 3 | `i` as unsigned 24-bit big-endian |
| 9–10 | 2 | `L` as unsigned 16-bit big-endian (`0x03f5` for every non-final report) |
| 11–`10+L` | `L` | Exact source bytes from offset `1013*i` |
| remaining through 1023 | variable | zero-filled |

There is no checksum, sequence-dependent transform, JPEG marker check,
inter-report delay, input-report read, acknowledgement comparison, start
packet, end/commit packet, or separate frame-selection packet in either
synchronization export.  `0x6e` is repeated on every data report.  The source
bytes are copied unchanged; the name and the file-oriented API suggest JPEG is
the expected payload, but static analysis does **not** prove what file formats
the receiving firmware accepts.

For a one-chunk 100-byte payload, the only transport write constructed by this
path is a 1,024-byte report beginning:

```
02 6e 00 00 00 64 00 00 00 00 64 <100 source bytes> <913 zero bytes>
```

This example is a field-layout illustration, not a capture or a device test.

## Entry points and evidence trail

| Function | RVA | Static observations |
| --- | ---: | --- |
| `CWitmodHid_SynchronizeImage` | `0x8160` | File-oriented wrapper.  It opens/seeks/tells/reads the supplied path into memory, then constructs the same reports inline.  It does not call the exported logical HID writer. |
| `CWitmodHid_SynchronizeImageV2` | `0x8460` | Memory-oriented variant.  It constructs the same reports inline from the passed byte count and pointer. |
| Internal raw output helper | `0x3890` | Both image functions call this helper with the report buffer and requested length `0x400`; neither calls exported `CWitmodHid_HidWriteBuff` at `0x72b0`. |
| Exported logical writer | `0x72b0` | Outside this image path.  Its opcode remapping must not be applied to the already constructed `0x6e` image report. |

The decisive instruction locations are:

| Fact | `SynchronizeImage` | `SynchronizeImageV2` |
| --- | ---: | ---: |
| Divide/chunk by `0x3f5` | `0x822a`–`0x8255` | `0x8487`–`0x84b3` |
| Clear 1,023 payload/header bytes after the report-ID byte | `0x8283`–`0x8290` | `0x84f0`–`0x84fd` |
| Put command/header fields at offsets 0–10 | `0x8295`–`0x82dc` | `0x8502`–`0x8541` |
| Copy exactly 1,013 bytes for a non-final report | `0x82e4`–`0x8386` | `0x8550`–`0x85f6` |
| Copy final remainder and replace its length field | `0x8388`–`0x83a0` | `0x85f8`–`0x8610` |
| Direct raw 1,024-byte output call | `0x83a4`–`0x83b4` | `0x8614`–`0x8624` |
| Retry decision and chunk advance | `0x83b9`–`0x83ea` | `0x8629`–`0x8659` |

The raw helper uses the handle's configured output-report length and issues the
underlying write.  In this path the requested 1,024-byte length equals the
report-2 output size.  The synchronization functions only treat a raw-helper
return of `-1` as failure; they do not verify that its returned byte count is
exactly 1,024.  An original Linux transport should reject a short write rather
than copying that weakness.

## Failure and retry boundary

For each individual report, the code writes once, then retries if and only if
the raw helper returned `-1`.  It permits six additional immediate attempts:
**at most seven writes of the identical report**.  It does not resend earlier
chunks after a later failure.  If all seven attempts fail, both exports return
`0x6e` (decimal 110); otherwise they return zero after the final report.

The file wrapper returns `-5` when its file-open/length path fails.  A zero
byte count results in zero constructed reports and a zero return in the V2
routine.  Neither export establishes recovery state, queries device state, or
sends a cancellation/rollback/commit operation.  Therefore, after a failed
multi-report image, receiver state and the safe resumption point are unknown;
do not infer a recovery command from this component.

The native routines use a signed 32-bit length.  A new implementation should
reject non-positive lengths and lengths above `INT32_MAX`, even though the
native V2 routine silently accepts the zero-length no-op.  It should also bound
the calculated report count and preserve the invariant that every successful
write returns exactly 1,024 bytes.  Those are host-side safety controls, not
claims about the receiver protocol.

## Bounded single-frame image-sync experiment

Subject to independent transport review and parent-coordinated hardware
acceptance, the static evidence supports construction of this narrow
single-frame image-sync experiment only:

1. Select exactly HP VID `03f0`, PID `7397`, interface `01`, and the verified
   report-2 output endpoint/descriptor.
2. With one exclusive display handle, submit only the report sequence in the
   table above for a bounded, non-empty prepared byte sequence.
3. Fail closed on a short or failed write.  Do not add any command inferred from
   other device functions, and do not invoke firmware, fan, pump, PWM, RGB, or
   persistent-storage APIs.
4. Treat visual update as unverified until a supervised, reversible hardware
   test proves it.  The static path provides no device acknowledgement and
   does not establish receiver-side persistence.

This is sufficient for a reviewer to reproduce the exact bytes of one
single-frame image-sync experiment without adding a guessed handshake.  It is
not sufficient to claim a successful LCD update, receiver-side persistence,
compatibility with another model, or a safe recovery procedure after
interruption.

### Subsequent host/kernel write acceptance

This result is separate from the static evidence above.  On 2026-11-05 at
17:50:07 UTC, the original Linux transport's bounded `show` experiment exited
zero in 0.104 seconds after submitting 36 reports.  It is evidence that the
selected host/kernel write path completed that bounded request; it is **not**
evidence that the receiver accepted the image, that the LCD visibly changed,
or that any receiver-side state persisted.  Physical observation remains
pending.

## Reproducibility

With the official package acquired outside this repository and the DLL checked
against the SHA-256 above, these read-only commands reproduce the cited
evidence without running the DLL or opening a USB device:

```bash
DLL='bin\witmodSdkOther.dll'
sha256sum "$DLL"
objdump -p "$DLL" | sed -n '/Export Address Table/,/Function Table/p'
objdump -d -Mintel --start-address=0x180008160 --stop-address=0x1800086a0 "$DLL"
objdump -d -Mintel --start-address=0x180003890 --stop-address=0x1800039a8 "$DLL"
```

No live USB access, DLL execution, installer execution, firmware operation, or
capture occurred during this analysis.

## Open verification items

- The actual receiver semantics of command `0x6e`, supported image encoding,
  maximum accepted image size, and whether receipt of the final report makes a
  frame visible all require controlled hardware evidence.
- No static evidence here establishes the device's input-report acknowledgement
  format because the synchronization path never reads one.
- The raw helper's OS completion handling is not a protocol acknowledgement;
  a Linux implementation still needs a bounded timeout policy and a reviewed
  short-write/error path.
- Interface selection, HID descriptor values, kernel binding preservation, and
  exclusive-handle lifecycle are transport concerns and remain owned by the
  integration work packet.
