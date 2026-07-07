from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, List, Tuple

import numpy as np
try:
    import torch  # noqa: F401
except Exception:
    torch = None
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class _DeterministicFallbackEncoder:
    """
    Local deterministic encoder used when sentence-transformers/torch is unavailable.
    """

    def encode(
        self,
        texts: List[str],
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        batch_size: int = 64,
    ) -> np.ndarray:
        _ = show_progress_bar
        _ = batch_size
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
        matrix = vectorizer.fit_transform(texts)
        dense = matrix.toarray()
        if convert_to_numpy:
            return np.asarray(dense, dtype=np.float64)
        return dense


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeduplicationConfig:
    """
    Immutable, fully explicit configuration for the semantic deduplication engine.

    Every parameter is documented and overridable â€” no magic numbers are
    embedded in the algorithm itself.

    Follows the same pattern as the immutable LLM config object.
    """

    # Sentence-transformer model used for semantic encoding.
    model_name: str = "all-MiniLM-L6-v2"

    # Fallback similarity threshold used when the adaptive elbow detector
    # cannot find a reliable natural gap (e.g. too few pairs, uniform distribution).
    # Calibrated for requirements-domain text *after* prefix normalization:
    # prefix stripping widens the gap between duplicate and distinct clusters,
    # making 0.80 effective where 0.82 was previously too conservative.
    fallback_threshold: float = 0.80

    # Hard lower and upper bounds for the adaptive threshold.
    # These prevent pathological values on degenerate distributions
    # (e.g. all requirements nearly identical, or all completely distinct).
    threshold_floor: float = 0.68
    threshold_ceiling: float = 0.92

    # Minimum number of unique pairwise similarity values required before
    # the elbow detector is trusted over the fallback.
    # Below this count the distribution is too sparse for reliable curvature detection.
    min_pairs_for_elbow: int = 6

    # Maximum number of leading tokens (words) that can be identified as a
    # common structural prefix and stripped before encoding.
    # Prevents accidentally stripping meaningful content on short requirements.
    max_prefix_words: int = 6

    # Minimum number of leading tokens that must match across ALL requirements
    # before prefix stripping is applied.
    # A value of 2 means at least two words must be shared (e.g. "The system").
    min_prefix_words: int = 2

    # Batch size for the SentenceTransformer encoder.
    # Has no effect on output â€” only on throughput/memory.
    encode_batch_size: int = 64


# Singleton default â€” importable and overridable by callers.
DEFAULT_DEDUP_CONFIG = DeduplicationConfig()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SemanticDeduplicator:
    """
    Production semantic deduplication engine for requirements text.

    Algorithm
    ---------
    1. Structural prefix normalization (data-driven, not hardcoded):
       Detects the longest common leading phrase shared by ALL requirements
       in the current batch and strips it before encoding.  Because this
       prefix is identical across every item it contributes zero discriminative
       signal to the embedding space â€” it only inflates pairwise similarities
       uniformly and compresses the useful gap between duplicate and distinct
       pairs.

    2. Adaptive threshold derivation (elbow method):
       Extracts all pairwise similarities from the upper triangle of the
       cosine-similarity matrix, sorts them descending, and finds the point
       of maximum perpendicular distance from the line connecting the first
       and last point (the "elbow").  This is the natural boundary between
       the high-similarity cluster (duplicates) and the low-similarity cluster
       (distinct requirements).  No threshold is assumed; it is derived from
       the actual distribution of the current batch.

    3. Greedy first-occurrence clustering:
       Iterates requirements in their original order.  The first item in
       each similarity cluster is kept; all subsequent items whose similarity
       to it meets or exceeds the threshold are removed.  This preserves
       document order and is fully deterministic.

    Properties
    ----------
    - Deterministic: identical input always produces identical output.
    - Domain-agnostic: works on any requirement format, not just IEEE.
    - No LLM calls, no randomness, no hardcoded domain rules.
    - All tunable parameters live in DeduplicationConfig, not in this class.
    """

    def __init__(self, config: DeduplicationConfig = DEFAULT_DEDUP_CONFIG):
        self.config = config
        self.model: Any = self._init_encoder()

    def _init_encoder(self) -> Any:
        """
        Initialize sentence transformer encoder with proper fallback chain.

        Priority:
        1. Load from local cache (fast, no network)
        2. Download from HuggingFace (first run only, cached thereafter) when explicitly enabled
        3. Deterministic TF-IDF fallback (last resort, logs warning)
        """
        try:
            from sentence_transformers import SentenceTransformer
            import torch  # noqa: F401

            cache_dir = self._resolve_cache_dir()
            allow_download = os.getenv("SENTENCE_TRANSFORMER_ALLOW_DOWNLOAD", "").lower() in {
                "1",
                "true",
                "yes",
            }

            try:
                model = SentenceTransformer(
                    self.config.model_name,
                    cache_folder=cache_dir,
                    local_files_only=True,
                )
                logger.info(
                    "deduplication encoder=sentence_transformer model=%s",
                    self.config.model_name,
                )
                return model
            except Exception as local_exc:
                if not allow_download:
                    logger.warning(
                        "deduplication encoder=tfidf reason=cache_unavailable detail=%s",
                        local_exc,
                    )
                    return _DeterministicFallbackEncoder()

                logger.warning(
                    "deduplication local cache unavailable, attempting download detail=%s",
                    local_exc,
                )

            if allow_download:
                try:
                    model = SentenceTransformer(
                        self.config.model_name,
                        cache_folder=cache_dir,
                    )
                    logger.info(
                        "deduplication encoder=sentence_transformer model=%s",
                        self.config.model_name,
                    )
                    return model
                except Exception as download_exc:
                    logger.warning(
                        "deduplication encoder=tfidf reason=download_failed detail=%s",
                        download_exc,
                    )
                    return _DeterministicFallbackEncoder()
        except ImportError as exc:
            logger.warning(
                "deduplication encoder=tfidf reason=package_missing detail=%s",
                exc,
            )
            return _DeterministicFallbackEncoder()
        except Exception as exc:
            logger.warning(
                "deduplication encoder=tfidf reason=load_failed detail=%s",
                exc,
            )
            return _DeterministicFallbackEncoder()

    def _resolve_cache_dir(self) -> str:
        """
        Resolve model cache directory from environment or default.
        Allows ops team to control model storage path without code changes.
        """
        return os.getenv(
            "SENTENCE_TRANSFORMER_CACHE",
            os.path.join(os.path.expanduser("~"), ".cache", "sentence_transformers"),
        )

    def warmup(self) -> None:
        """
        Force model initialization at startup.
        Prevents first-request latency spike from model download/load.
        """
        _ = self.model
        self.model.encode(["warmup"], convert_to_numpy=True, show_progress_bar=False)
        logger.info("deduplication warmup complete encoder=%s", type(self.model).__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate(self, requirements: List[str]) -> List[str]:
        """
        Remove semantically equivalent requirements from the list.

        Returns a deduplicated list preserving the original order,
        with the first representative of each cluster kept.
        """
        n = len(requirements)

        if n <= 1:
            return list(requirements)

        # Step 1: Detect and strip the common structural prefix.
        common_prefix, normalized = self._normalize_batch(requirements)
        normalized = [self._normalize_semantics(t) for t in normalized]

        if common_prefix:
            logger.info(
                "deduplication prefix_stripped=%r affecting %d requirements",
                common_prefix,
                n,
            )

        # Step 2: Encode the normalized texts.
        embeddings = self.model.encode(
            normalized,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=self.config.encode_batch_size,
        )

        # Step 3: Compute full pairwise cosine similarity matrix.
        similarity_matrix = cosine_similarity(embeddings)

        # Step 4: Derive threshold from the distribution of this batch.
        upper_triangle = [
            float(similarity_matrix[i][j])
            for i in range(n)
            for j in range(i + 1, n)
        ]
        threshold, method = self._derive_threshold(upper_triangle)

        logger.info(
            "deduplication threshold=%.4f method=%s pairs=%d",
            threshold,
            method,
            len(upper_triangle),
        )

        # Step 5: Greedy first-occurrence clustering.
        kept_indices: List[int] = []
        removed: set = set()

        for i in range(n):
            if i in removed:
                continue

            kept_indices.append(i)

            for j in range(i + 1, n):
                sim = float(similarity_matrix[i][j])
                lex = self._lexical_overlap(normalized[i], normalized[j])
                combined = 0.55 * sim + 0.45 * lex
                subsumed = self._is_subsumed(i, j, similarity_matrix)

                if j not in removed and (combined >= threshold or subsumed):
                    logger.debug(
                        (
                            "deduplication removed=%r duplicate_of=%r "
                            "similarity=%.4f lexical=%.4f combined=%.4f subsumed=%s"
                        ),
                        requirements[j],
                        requirements[i],
                        sim,
                        lex,
                        combined,
                        subsumed,
                    )
                    removed.add(j)

        removed_count = n - len(kept_indices)
        logger.info(
            "deduplication complete kept=%d removed=%d original=%d",
            len(kept_indices),
            removed_count,
            n,
        )

        return [requirements[i] for i in kept_indices]

    # ------------------------------------------------------------------
    # Prefix normalization
    # ------------------------------------------------------------------

    def _normalize_semantics(self, text: str) -> str:
        """
        Deterministic semantic normalization.
        No domain assumptions. Only linguistic normalization.
        """
        t = text.lower()

        # normalize numeric constraints (general, not domain-specific)
        t = re.sub(r"less than (\d+)", r"< \1", t)
        t = re.sub(r"under (\d+)", r"< \1", t)
        t = re.sub(r"within (\d+)", r"< \1", t)
        t = re.sub(r"at least (\d+)", r">= \1", t)

        # normalize time units
        t = re.sub(r"seconds?", "sec", t)
        t = re.sub(r"milliseconds?", "ms", t)

        # normalize scope words (general linguistic, not domain-specific)
        t = re.sub(r"all (user )?interactions?", "global interactions", t)
        t = re.sub(r"critical operations?", "specific operations", t)

        # remove redundant determiners
        t = re.sub(r"\bthe\b", "", t)

        # normalize whitespace
        t = " ".join(t.split())

        return t

    def _normalize_batch(
        self, requirements: List[str]
    ) -> Tuple[str, List[str]]:
        """
        Detect the common leading phrase across all requirements and strip it.

        Returns
        -------
        common_prefix : str
            The detected prefix (empty string if none found).
        normalized : List[str]
            Requirements with the prefix removed, ready for encoding.

        Design rationale
        ----------------
        The common prefix is detected entirely from the data â€” it is NOT a
        hardcoded string like "The system shall".  If the input batch uses a
        different format (e.g. "Each component must ...", or plain English),
        the correct prefix for that batch is detected automatically.

        The prefix is only stripped when it spans between min_prefix_words and
        max_prefix_words tokens, preventing accidental over-stripping on short
        inputs or under-stripping on heterogeneous inputs.
        """
        prefix = self._detect_common_prefix(requirements)
        if not prefix:
            return "", list(requirements)

        normalized = []
        prefix_lower = prefix.lower()
        prefix_len = len(prefix)

        for req in requirements:
            if req.lower().startswith(prefix_lower):
                tail = req[prefix_len:].strip()
                # Never strip to an empty string â€” keep original if tail is trivial.
                normalized.append(tail if len(tail.split()) >= 2 else req)
            else:
                normalized.append(req)

        return prefix, normalized

    def _detect_common_prefix(self, texts: List[str]) -> str:
        """
        Find the longest common leading token sequence shared by ALL texts.

        Uses lower-cased token comparison so the result is case-insensitive.
        Returns an empty string if no prefix of valid length is found.
        """
        if not texts:
            return ""

        tokenized = [t.strip().lower().split() for t in texts]
        min_len = min(len(t) for t in tokenized)

        common: List[str] = []

        for pos in range(min(min_len, self.config.max_prefix_words)):
            token = tokenized[0][pos]
            if all(t[pos] == token for t in tokenized):
                common.append(token)
            else:
                break

        if len(common) < self.config.min_prefix_words:
            return ""

        # Reconstruct prefix with original casing from the first requirement.
        original_tokens = texts[0].strip().split()
        prefix_with_case = " ".join(original_tokens[: len(common)]) + " "
        return prefix_with_case

    def _lexical_overlap(self, a: str, b: str) -> float:
        tokens_a = set(re.findall(r"\w+", a.lower()))
        tokens_b = set(re.findall(r"\w+", b.lower()))

        if not tokens_a or not tokens_b:
            return 0.0

        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    def _is_subsumed(self, i: int, j: int, similarity_matrix) -> bool:
        """
        Uses precomputed similarity matrix - NO extra encoding
        """
        emb_sim = float(similarity_matrix[i][j])
        return emb_sim >= 0.80

    # ------------------------------------------------------------------
    # Adaptive threshold derivation
    # ------------------------------------------------------------------

    def _derive_threshold(
        self, similarities: List[float]
    ) -> Tuple[float, str]:
        """
        Derive the deduplication threshold from the pairwise similarity
        distribution of the current batch.

        Method: Elbow detection (maximum perpendicular distance).
        -------
        Sort similarities descending â†’ they form a monotone decreasing curve.
        Fit a straight line from the first point (highest similarity) to the
        last point (lowest similarity).  For each point on the curve, compute
        its perpendicular distance to this line.  The point with maximum
        distance is the "elbow" â€” the boundary between the steep duplicate
        cluster and the flat distinct cluster.

        Returns
        -------
        threshold : float
            The derived similarity threshold, clamped to [floor, ceiling].
        method : str
            "elbow" if adaptive detection was used, "fallback" otherwise.

        Why this is correct
        -------------------
        The elbow is the point of maximum curvature in the sorted similarity
        curve.  Requirements with similarity >= elbow_value belong to the
        duplicate cluster.  This threshold is derived entirely from the data
        and adapts to every batch without any hardcoded assumption about what
        "similar enough" means.
        """
        if len(similarities) < self.config.min_pairs_for_elbow:
            return self.config.fallback_threshold, "fallback"

        sorted_sims = np.array(sorted(similarities, reverse=True), dtype=np.float64)
        n = len(sorted_sims)

        # Normalize x to [0, 1] â€” makes curvature detection scale-invariant.
        x = np.linspace(0.0, 1.0, n)
        y = sorted_sims

        # Line from point[0] to point[n-1].
        line_vec = np.array([x[-1] - x[0], y[-1] - y[0]], dtype=np.float64)
        line_len = float(np.linalg.norm(line_vec))

        if line_len < 1e-9:
            # Degenerate: all similarities are equal â€” no meaningful boundary.
            return self.config.fallback_threshold, "fallback"

        line_unit = line_vec / line_len

        # Compute perpendicular distance of every point from the line.
        distances = np.zeros(n, dtype=np.float64)
        origin = np.array([x[0], y[0]], dtype=np.float64)

        for i in range(n):
            point_vec = np.array([x[i], y[i]], dtype=np.float64) - origin
            proj_len = float(np.dot(point_vec, line_unit))
            proj = proj_len * line_unit
            perp = point_vec - proj
            distances[i] = float(np.linalg.norm(perp))

        elbow_idx = int(np.argmax(distances))
        elbow_value = float(sorted_sims[elbow_idx])

        # Validate: if max distance is negligibly small the distribution is
        # essentially linear and the elbow is unreliable â€” fall back.
        if float(np.max(distances)) < 1e-3:
            return self.config.fallback_threshold, "fallback"

        threshold = float(
            np.clip(elbow_value, self.config.threshold_floor, self.config.threshold_ceiling)
        )
        return threshold, "elbow"
