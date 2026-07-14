"""Dummy heatwave risk model for Uttar Pradesh districts."""

import random
from collections.abc import Sequence


def get_heatwave_predictions(district_names: Sequence[str]) -> list[dict]:
    """
    Generate simulated heatwave risk predictions for the given districts.
    Returns a list of dicts with keys: district, temperature, humidity, risk, probability.
    """
    result = []
    for district in district_names:
        temperature = random.randint(34, 47)
        humidity = random.randint(10, 70)
        wind_speed = random.uniform(2, 20)  # internal only, not in response

        if temperature >= 44:
            risk = "HIGH"
            probability = round(random.uniform(0.75, 0.95), 2)
        elif temperature >= 40:
            risk = "MODERATE"
            probability = round(random.uniform(0.45, 0.74), 2)
        else:
            risk = "LOW"
            probability = round(random.uniform(0.10, 0.44), 2)

        result.append({
            "district": district,
            "temperature": temperature,
            "humidity": humidity,
            "risk": risk,
            "probability": probability,
        })
    return result
