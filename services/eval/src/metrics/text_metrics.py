"""Text comparison metrics for OCR and text-based evaluations."""

from typing import Any


class TextMetrics:
    """Collection of text comparison metrics."""

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein (edit) distance between two strings.

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Number of single-character edits needed to transform s1 into s2.
        """
        try:
            import Levenshtein
            return Levenshtein.distance(s1, s2)
        except ImportError:
            # Fallback to pure Python implementation
            if len(s1) < len(s2):
                s1, s2 = s2, s1

            if len(s2) == 0:
                return len(s1)

            prev_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                curr_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = prev_row[j + 1] + 1
                    deletions = curr_row[j] + 1
                    substitutions = prev_row[j] + (c1 != c2)
                    curr_row.append(min(insertions, deletions, substitutions))
                prev_row = curr_row

            return prev_row[-1]

    @staticmethod
    def normalized_levenshtein(s1: str, s2: str) -> float:
        """Calculate normalized Levenshtein similarity (0-1).

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Similarity score between 0 (completely different) and 1 (identical).
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        distance = TextMetrics.levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len)

    @staticmethod
    def character_accuracy(actual: str, expected: str) -> float:
        """Calculate character-level accuracy.

        Args:
            actual: Actual output string.
            expected: Expected output string.

        Returns:
            Proportion of correctly positioned characters.
        """
        if not expected:
            return 1.0 if not actual else 0.0

        # Use Levenshtein distance to calculate accuracy
        distance = TextMetrics.levenshtein_distance(actual, expected)
        return max(0.0, 1.0 - (distance / len(expected)))

    @staticmethod
    def word_accuracy(actual: str, expected: str) -> float:
        """Calculate word-level accuracy.

        Args:
            actual: Actual output string.
            expected: Expected output string.

        Returns:
            Proportion of words that match (order-independent).
        """
        if not expected:
            return 1.0 if not actual else 0.0

        actual_words = set(actual.lower().split())
        expected_words = set(expected.lower().split())

        if not expected_words:
            return 1.0 if not actual_words else 0.0

        intersection = actual_words & expected_words
        return len(intersection) / len(expected_words)

    @staticmethod
    def bleu_score(actual: str, expected: str, n: int = 4) -> float:
        """Calculate BLEU score for text comparison.

        Args:
            actual: Actual output string (hypothesis).
            expected: Expected output string (reference).
            n: Maximum n-gram size (default 4).

        Returns:
            BLEU score between 0 and 1.
        """
        try:
            from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
            reference = [expected.split()]
            hypothesis = actual.split()
            smoothie = SmoothingFunction().method1
            weights = tuple([1.0 / n] * n)
            return sentence_bleu(reference, hypothesis, weights=weights, smoothing_function=smoothie)
        except ImportError:
            # Fallback to simple n-gram overlap
            return TextMetrics._simple_ngram_overlap(actual, expected, n)

    @staticmethod
    def _simple_ngram_overlap(actual: str, expected: str, n: int) -> float:
        """Simple n-gram overlap calculation."""
        def get_ngrams(text: str, n: int) -> set:
            words = text.lower().split()
            return {tuple(words[i:i+n]) for i in range(max(0, len(words) - n + 1))}

        if not expected or not actual:
            return 0.0

        expected_ngrams = get_ngrams(expected, n)
        actual_ngrams = get_ngrams(actual, n)

        if not expected_ngrams:
            return 0.0

        overlap = len(expected_ngrams & actual_ngrams)
        return overlap / len(expected_ngrams)

    @staticmethod
    def calculate_all(actual: str, expected: str) -> dict[str, Any]:
        """Calculate all text metrics at once.

        Args:
            actual: Actual output string.
            expected: Expected output string.

        Returns:
            Dictionary containing all metrics.
        """
        return {
            "character_accuracy": TextMetrics.character_accuracy(actual, expected),
            "word_accuracy": TextMetrics.word_accuracy(actual, expected),
            "levenshtein_distance": TextMetrics.levenshtein_distance(actual, expected),
            "normalized_levenshtein": TextMetrics.normalized_levenshtein(actual, expected),
            "bleu_score": TextMetrics.bleu_score(actual, expected),
            "actual_length": len(actual),
            "expected_length": len(expected),
            "length_ratio": len(actual) / len(expected) if expected else 0.0,
        }
