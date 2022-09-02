import asyncio
import functools
import json
import time
from binascii import hexlify
from typing import Optional, Any

from bleak import discover

MIN_RSSI = -60
AIRPODS_MANUFACTURER = 76
AIRPODS_DATA_LENGTH = 54


def retry_on_none(*, times: int, sleep_ms: float):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            for _ in range(times):
                val = f(*args, **kwargs)

                if val is not None:
                    return val

                time.sleep(sleep_ms / 1000)
            return None

        return wrapper

    return decorator


@retry_on_none(times=10, sleep_ms=500)
def fetch_airpods_raw_data() -> Optional[bytes]:
    devices = asyncio.run(discover())

    for d in devices:
        data = d.metadata["manufacturer_data"].pop(AIRPODS_MANUFACTURER, None)

        if d.rssi >= MIN_RSSI and data:
            data_hex = hexlify(data)

            if len(data_hex) == AIRPODS_DATA_LENGTH:
                return data_hex

    return None


def parse_airpods_data(raw: bytes) -> dict:
    model = {
        "2": "Airpods 1",
        "f": "Airpods 2",
        "e": "Airpods Pro",
        "a": "Airpods Max",
    }.get(chr(raw[7]), "Unknown")

    charging_status = int(chr(raw[14]), 16)
    return dict(
        connected=True,
        model=model,
        charge=dict(
            case=parse_battery_level(raw[15]),
            **maybe_flip(
                raw,
                left=parse_battery_level(raw[13]),
                right=parse_battery_level(raw[12]),
            )
        ),
        charging=dict(
            case=(charging_status & 0b00000100) != 0,
            **maybe_flip(
                raw,
                left=(charging_status & 0b00000001) != 0,
                right=(charging_status & 0b00000010) != 0,
            )
        ),
    )


def parse_battery_level(raw_status: int) -> Optional[int]:
    raw_status = int(chr(raw_status), 16)

    if raw_status <= 10:
        return raw_status * 10

    return None


def maybe_flip(raw: bytes, *, left: Any, right: Any) -> dict:
    is_flipped_ = (int(chr(raw[10]), 16) & 0x02) == 0

    if is_flipped_:
        return {
            "right": left,
            "left": right,
        }

    return {
        "right": right,
        "left": left,
    }


def main():
    raw_data = fetch_airpods_raw_data()

    if raw_data is None:
        print(json.dumps(dict(connected=False)))
        exit(1)

    print(json.dumps(parse_airpods_data(raw_data)))


if __name__ == "__main__":
    main()
