from __future__ import annotations

# These are the only Debian machine-readable copyright labels that this R1
# evidence package maps to SPDX. Each entry is a full, manually reviewed label;
# no prefix, suffix, case-folding, or expression parsing is permitted.
EXACT_SPDX_BY_RAW_HEADER = {
    "Apache-2.0": "Apache-2.0",
    "BSD-2-clause": "BSD-2-Clause",
    "BSD-3-Clause": "BSD-3-Clause",
    "CC0-1.0": "CC0-1.0",
    "Expat": "MIT",
    "ISC": "ISC",
    "MIT": "MIT",
    "MPL-2.0": "MPL-2.0",
    "OFL-1.1": "OFL-1.1",
    "PSF": "PSF-2.0",
    "Zlib": "Zlib",
}


def notice_license_ref(notice_hash: str) -> str:
    return f"LicenseRef-Debian-Notice-{notice_hash[:12]}"


def expression_for_debian_headers(headers: list[str], notice_hash: str) -> str:
    """Return SPDX only for one reviewed raw label; otherwise retain the notice.

    A copyright file can describe alternatives, exceptions, variants, and
    several file sets. Reconstructing a combined SPDX expression would change
    those semantics. The stable LicenseRef instead points to the persisted
    notice and the exact raw headers emitted alongside the component.
    """

    if len(headers) == 1:
        mapped = EXACT_SPDX_BY_RAW_HEADER.get(headers[0])
        if mapped is not None:
            return mapped
    return notice_license_ref(notice_hash)
