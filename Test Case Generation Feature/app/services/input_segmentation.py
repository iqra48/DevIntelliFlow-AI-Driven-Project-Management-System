from typing import List
import re


class InputSegmentationService:
    """
    Deterministic segmentation for large inputs.

    Guarantees:
    - no truncation
    - no randomness
    - scalable generation
    """

    def __init__(self, target_words: int = 180):
        self.target_words = target_words

    def split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def segment(self, text: str) -> List[str]:
        sentences = self.split_sentences(text)

        segments = []
        current = []
        current_words = 0

        for s in sentences:
            w = len(s.split())

            if current_words + w > self.target_words and current:
                segments.append(" ".join(current))
                current = []
                current_words = 0

            current.append(s)
            current_words += w

        if current:
            segments.append(" ".join(current))

        return segments
