"""Query guardrails — dry-run validation, cost cap, DML blocking.

Implements the paper's economic guardrails:
- Proactive query validation via API dry-runs
- Programmatic cost threshold enforcement
- DML/DDL blocking at the code level (not just prompt-level)
"""

import re
import logging
from dataclasses import dataclass

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a query validation check."""

    is_valid: bool
    bytes_processed: int = 0
    estimated_cost_usd: float = 0.0
    rejection_reason: str = ""


# BigQuery on-demand pricing: $6.25 per TiB scanned
BQ_COST_PER_TIB = 6.25
BYTES_PER_TIB = 1024**4

# Patterns that indicate dangerous DML/DDL operations
_DML_PATTERNS = re.compile(
    r"\b(UPDATE|DELETE|INSERT|DROP|ALTER|TRUNCATE|MERGE|CREATE|REPLACE)\b",
    re.IGNORECASE,
)

# SELECT * pattern (with optional table alias like SELECT t.*)
_SELECT_STAR_PATTERN = re.compile(
    r"\bSELECT\s+(\w+\.)?\*\s",
    re.IGNORECASE,
)

# ── CaMeL-Inspired Static Injection Patterns ──────────────
# These provide code-level data provenance checking BEFORE the LLM Verifier.
# Based on the CaMeL paper: https://arxiv.org/abs/2503.18813
# The key insight: untrusted input that overwrites context is caught deterministically,
# not relying on the LLM to notice the injection attempt.

_INJECTION_PATTERNS = [
    # Context/instruction overrides
    (re.compile(r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}(instruction|prompt|rule|guideline|system)", re.IGNORECASE),
     "context_override"),
    (re.compile(r"\byour (new |updated )?(instructions?|rules?|guidelines?|role) (are|is)\b", re.IGNORECASE),
     "context_override"),
    (re.compile(r"\b(from now on|going forward|for all future|always from this point)\b", re.IGNORECASE),
     "persistent_redirect"),

    # Role impersonation / jailbreak
    (re.compile(r"\b(you are now|act as|pretend (you are|to be)|simulate|roleplay as)\b.{0,60}(ai|model|assistant|bot|gpt|gemini|llm)", re.IGNORECASE),
     "role_impersonation"),
    (re.compile(r"\b(jailbreak|DAN|developer mode|unrestricted mode|no restrictions|god mode)\b", re.IGNORECASE),
     "jailbreak_attempt"),
    (re.compile(r"\b(sudo|root access|admin override|superuser)\b", re.IGNORECASE),
     "privilege_escalation"),

    # System prompt extraction
    (re.compile(r"\b(reveal|repeat|show|print|output|summarize|tell me).{0,20}(system prompt|your instructions|your rules|initial prompt|what you were told)", re.IGNORECASE),
     "prompt_extraction"),

    # Indirect injection / data exfiltration
    (re.compile(r"\b(send|email|post|upload|exfiltrate|transmit).{0,30}(result|data|output|response).{0,30}(to|at|via)\b", re.IGNORECASE),
     "data_exfiltration"),
    (re.compile(r"\b(also|additionally|furthermore).{0,30}(call|query|access|hit|fetch).{0,30}(api|endpoint|url|http|https)\b", re.IGNORECASE),
     "external_api_injection"),

    # Encoded/obfuscated payloads (base64-like strings or hex sequences)
    (re.compile(r"[A-Za-z0-9+/]{40,}={0,2}(?:\s|$)"),
     "encoded_payload"),  # likely base64
    (re.compile(r"(\\x[0-9a-fA-F]{2}){4,}"),
     "hex_encoded_payload"),

    # SQL injection via comments or stacked queries
    (re.compile(r"(--.{0,50}(drop|delete|insert|update|alter|create))|(/\*.*?\*/)", re.IGNORECASE | re.DOTALL),
     "sql_comment_injection"),
    (re.compile(r";\s*(drop|delete|update|insert|alter|create)\b", re.IGNORECASE),
     "stacked_query"),

    # Hypothetical / fictional framing
    (re.compile(r"\b(hypothetically|in a fictional world|imagine that|pretend that|what if there were no rules)\b", re.IGNORECASE),
     "fictional_bypass"),
]


def check_prompt_injection(user_input: str) -> ValidationResult:
    """Pre-screen user input for static injection signatures (CaMeL-style).

    This is the first line of defense — code-level data provenance enforcement.
    Runs BEFORE the LLM Verifier to catch deterministic attack patterns.

    Based on CaMeL (Defeating Prompt Injections by Design, arxiv:2503.18813):
    The key principle is treating external/injected content as UNTRUSTED and
    blocking it at the structural level rather than relying purely on LLM judgment.
    """
    for pattern, attack_type in _INJECTION_PATTERNS:
        match = pattern.search(user_input)
        if match:
            logger.warning("Static injection detected [%s]: '%s'", attack_type, match.group(0)[:60])
            return ValidationResult(
                is_valid=False,
                rejection_reason=(
                    f"BLOCKED [{attack_type.upper().replace('_', ' ')}]: "
                    "Your input contains patterns associated with prompt injection attacks. "
                    "Please ask a straightforward question about the e-commerce data."
                ),
            )
    return ValidationResult(is_valid=True)


def check_dml(query: str) -> ValidationResult:
    """Block any DML/DDL statements at the code level.

    This is a structural guardrail — even if the LLM ignores prompt instructions,
    we catch it here before the query reaches BigQuery.
    """
    match = _DML_PATTERNS.search(query)
    if match:
        keyword = match.group(1).upper()
        return ValidationResult(
            is_valid=False,
            rejection_reason=f"BLOCKED: Query contains forbidden keyword '{keyword}'. "
            "Only SELECT statements are allowed.",
        )
    return ValidationResult(is_valid=True)


def check_select_star(query: str) -> ValidationResult:
    """Block SELECT * queries to prevent unbounded data scans."""
    if _SELECT_STAR_PATTERN.search(query):
        return ValidationResult(
            is_valid=False,
            rejection_reason="BLOCKED: SELECT * is not allowed. "
            "Please list specific columns to reduce data scanned.",
        )
    return ValidationResult(is_valid=True)


def check_limit_clause(query: str) -> str:
    """Inject LIMIT 100 if no LIMIT clause is present.

    Returns the (possibly modified) query.
    """
    if not re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        # Strip trailing semicolons before appending LIMIT
        query = query.rstrip().rstrip(";")
        query += " LIMIT 100"
        logger.info("Auto-injected LIMIT 100 clause")
    return query


def dry_run_validate(
    query: str,
    max_bytes: int,
    project_id: str,
) -> ValidationResult:
    """Execute a BigQuery dry-run to validate query and estimate cost.

    A dry-run does NOT execute the query or consume slots.
    It validates syntax, checks permissions, and returns estimated bytes processed.

    Args:
        query: SQL query string to validate.
        max_bytes: Maximum allowed bytes to be processed.
        project_id: GCP project ID.

    Returns:
        ValidationResult with cost estimate and pass/fail status.
    """
    client = bigquery.Client(project=project_id)

    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

    try:
        query_job = client.query(query, job_config=job_config)
        bytes_processed = query_job.total_bytes_processed or 0
        estimated_cost = (bytes_processed / BYTES_PER_TIB) * BQ_COST_PER_TIB

        if bytes_processed > max_bytes:
            max_gb = max_bytes / (1024**3)
            actual_gb = bytes_processed / (1024**3)
            return ValidationResult(
                is_valid=False,
                bytes_processed=bytes_processed,
                estimated_cost_usd=estimated_cost,
                rejection_reason=(
                    f"REJECTED: Query would scan {actual_gb:.2f} GB "
                    f"(cap is {max_gb:.2f} GB, est. cost ${estimated_cost:.4f}). "
                    "Add tighter date filters, partition pruning, or column selection."
                ),
            )

        logger.info(
            "Dry-run passed: %d bytes (%.4f GB, $%.6f)",
            bytes_processed,
            bytes_processed / (1024**3),
            estimated_cost,
        )
        return ValidationResult(
            is_valid=True,
            bytes_processed=bytes_processed,
            estimated_cost_usd=estimated_cost,
        )

    except Exception as e:
        return ValidationResult(
            is_valid=False,
            rejection_reason=f"DRY-RUN ERROR: {str(e)}",
        )


def validate_query(query: str, max_bytes: int, project_id: str) -> ValidationResult:
    """Full validation pipeline: DML check → SELECT * check → auto-LIMIT → dry-run.

    Returns the first failing ValidationResult, or the dry-run result if all pass.
    """
    # Step 1: Block DML/DDL
    result = check_dml(query)
    if not result.is_valid:
        logger.warning("DML blocked: %s", result.rejection_reason)
        return result

    # Step 2: Block SELECT *
    result = check_select_star(query)
    if not result.is_valid:
        logger.warning("SELECT * blocked: %s", result.rejection_reason)
        return result

    # Step 3: Auto-inject LIMIT
    query = check_limit_clause(query)

    # Step 4: Dry-run cost validation
    result = dry_run_validate(query, max_bytes, project_id)
    if not result.is_valid:
        logger.warning("Dry-run rejected: %s", result.rejection_reason)

    return result
