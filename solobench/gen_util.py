"""Helpers shared by the task generators."""
import string


def _fname(rng):
    return "f_" + "".join(rng.choice(string.ascii_lowercase) for _ in range(5))


def _word(rng, n):
    syl = ["ka", "lo", "mi", "re", "ta", "po", "si", "na", "ve", "du", "ra", "le", "zo", "ba"]
    return "".join(rng.choice(syl) for _ in range(n))
