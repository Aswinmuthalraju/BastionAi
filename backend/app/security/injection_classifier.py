"""
Kept as a thin alias so existing imports (`from app.security.injection_classifier
import injection_classifier`) keep working. The previous version duplicated a
second, weaker keyword-matching implementation of the same screening logic;
there is now exactly one dual-rail implementation, in
app.mnemoshield.dual_rail_security.
"""
from app.mnemoshield.dual_rail_security import dual_rail_security as injection_classifier

__all__ = ["injection_classifier"]
