from __future__ import annotations

from collections.abc import Sequence

RBC_BLOOD_GROUPS = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")

_RBC_DONORS_BY_RECIPIENT: dict[str, frozenset[str]] = {
    "O-": frozenset(("O-",)),
    "O+": frozenset(("O-", "O+")),
    "A-": frozenset(("O-", "A-")),
    "A+": frozenset(("O-", "O+", "A-", "A+")),
    "B-": frozenset(("O-", "B-")),
    "B+": frozenset(("O-", "O+", "B-", "B+")),
    "AB-": frozenset(("O-", "A-", "B-", "AB-")),
    "AB+": frozenset(RBC_BLOOD_GROUPS),
}


def compatible_donor_groups(
    recipient_group: str, component: str = "RED_CELLS"
) -> tuple[str, ...]:
    """Return potential RBC donor groups; unsupported or unknown inputs match nobody."""
    if component != "RED_CELLS":
        return ()
    compatible = _RBC_DONORS_BY_RECIPIENT.get(recipient_group)
    if compatible is None:
        return ()
    return tuple(group for group in RBC_BLOOD_GROUPS if group in compatible)


def compatible_recipient_groups(donor_group: str) -> tuple[str, ...]:
    """Return recipient groups for which this recorded RBC group is a potential match."""
    if donor_group not in RBC_BLOOD_GROUPS:
        return ()
    return tuple(
        recipient_group
        for recipient_group in RBC_BLOOD_GROUPS
        if donor_group in _RBC_DONORS_BY_RECIPIENT[recipient_group]
    )


def is_rbc_group_compatible(donor_group: str, recipient_group: str) -> bool:
    return donor_group in compatible_donor_groups(recipient_group)


def compatibility_matrix() -> dict[str, Sequence[str]]:
    """Return a safe, public presentation of the RBC rules."""
    return {
        recipient: compatible_donor_groups(recipient)
        for recipient in RBC_BLOOD_GROUPS
    }
