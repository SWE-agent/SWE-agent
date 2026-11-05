#!/usr/bin/env python3


def division(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


if __name__ == "__main__":
    try:
        print(division(23, 0))
    except ValueError as e:
        print(e)

