# Provenance

The verifier reads only the frozen vector bytes and caller-supplied key material. It does not import or execute the upstream `attenu_guard` verifier. Base bundle semantics are checked by the repository's previously merged standalone v1.2 verifier; observer-envelope semantics are implemented independently in this proof.

Registry copies are extracted from exact versions and must match the repository vector SHA-256 before scoring.
