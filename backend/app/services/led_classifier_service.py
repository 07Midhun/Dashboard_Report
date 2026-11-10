from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class RuleSpec:
    pattern: str
    match_type: str  # exact | prefix | contains | word | regex
    classification: str  # led | non_led


DEFAULT_RULES: tuple[RuleSpec, ...] = (
    # Explicit non-LED safeguards checked before LED rules
    RuleSpec("NON-LED", "contains", "non_led"),
    RuleSpec("NON LED", "contains", "non_led"),
    RuleSpec("SVL", "word", "non_led"),
    RuleSpec("SODIUM VAPOUR", "contains", "non_led"),
    RuleSpec("SODIUM VAPOR", "contains", "non_led"),
    RuleSpec("HPSV", "word", "non_led"),
    RuleSpec("LPSV", "word", "non_led"),
    RuleSpec("CONVENTIONAL", "contains", "non_led"),
    RuleSpec("METAL HALIDE", "contains", "non_led"),
    RuleSpec("CFL", "word", "non_led"),
    RuleSpec("FLUORESCENT", "contains", "non_led"),
    RuleSpec("HALOGEN", "contains", "non_led"),
    RuleSpec("INCANDESCENT", "contains", "non_led"),
    RuleSpec("MERCURY VAPOUR", "contains", "non_led"),
    RuleSpec("MERCURY VAPOR", "contains", "non_led"),
    # LED rules
    RuleSpec("LED", "word", "led"),
    RuleSpec("LED", "prefix", "led"),
    RuleSpec("LED STREET LIGHT", "contains", "led"),
)

_WS_RE = re.compile(r"\s+")


def _matches(text: str, pattern: str, match_type: str) -> bool:
    norm_text = _WS_RE.sub(" ", text).strip().upper()
    norm_pat = _WS_RE.sub(" ", pattern).strip().upper()
    if not norm_pat:
        return False

    if match_type == "exact":
        return norm_text == norm_pat
    if match_type == "prefix":
        return norm_text.startswith(norm_pat)
    if match_type == "contains":
        return norm_pat in norm_text
    if match_type == "word":
        # Match whole word/token boundaries (e.g. 'LED', 'LED 40W', '40W LED', 'LED-60W')
        return bool(re.search(rf"(?<![A-Z0-9]){re.escape(norm_pat)}(?![A-Z0-9])", norm_text))
    if match_type == "regex":
        try:
            return bool(re.search(pattern, text, flags=re.IGNORECASE))
        except re.error:
            return False
    return False


class LedClassifier:
    """
    Case-insensitive, whitespace-tolerant Lamp Type classifier.
    Checks explicit non-LED rules first so 'Non-LED' never misclassifies as LED,
    then checks LED rules; unmatched values return 'unknown' instead of guessing.
    """

    def __init__(self, rules: Iterable[RuleSpec] | None = None) -> None:
        rule_list = list(rules) if rules is not None else list(DEFAULT_RULES)
        # Ensure explicit negation safeguards always stay active
        self.non_led_rules = [
            RuleSpec("NON-LED", "contains", "non_led"),
            RuleSpec("NON LED", "contains", "non_led"),
            *[r for r in rule_list if r.classification == "non_led"],
        ]
        self.led_rules = [r for r in rule_list if r.classification == "led"]

    def classify(self, lamp_type: str | None) -> tuple[str, str | None]:
        if lamp_type is None:
            return "unknown", None
        cleaned = _WS_RE.sub(" ", str(lamp_type)).strip()
        if not cleaned:
            return "unknown", None

        for rule in self.non_led_rules:
            if _matches(cleaned, rule.pattern, rule.match_type):
                return "non_led", rule.pattern

        for rule in self.led_rules:
            if _matches(cleaned, rule.pattern, rule.match_type):
                return "led", rule.pattern

        return "unknown", None

