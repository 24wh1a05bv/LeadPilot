"""LLM wrapper - configurable model provider.

Supports Claude (Anthropic) and OpenAI-compatible APIs via a single interface.
"""

from __future__ import annotations

import os
from typing import Any

# Try to import available SDKs
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LLMError(Exception):
    """Raised when LLM calls fail."""
    pass


class LLM:
    """Configurable LLM wrapper.

    Usage:
        llm = LLM(model="claude-sonnet-4-20250514")
        response = llm.generate(system="You are...", prompt="Hello")
    """

    def __init__(self, model: str | None = None, temperature: float = 0.0):
        """Initialize the LLM wrapper.

        Args:
            model: Model identifier. If None, reads from env vars.
                   Supports "claude-*" (Anthropic) or "gpt-*" (OpenAI).
            temperature: Sampling temperature (0.0 = deterministic).
        """
        self.temperature = temperature

        if model:
            self.model = model
        elif os.environ.get("ANTHROPIC_API_KEY"):
            self.model = "claude-sonnet-4-20250514"
        elif os.environ.get("OPENAI_API_KEY"):
            self.model = "gpt-4o"
        else:
            self.model = "mock"  # Fallback for testing without API keys

        self._client = None
        self._provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """Detect which provider to use based on model name and available keys."""
        if self.model.startswith("claude"):
            if not HAS_ANTHROPIC:
                if os.environ.get("ANTHROPIC_API_KEY"):
                    raise LLMError("anthropic package not installed. Run: pip install anthropic")
                return "mock"
            return "anthropic"
        elif self.model.startswith("gpt") or self.model.startswith("o"):
            if not HAS_OPENAI:
                if os.environ.get("OPENAI_API_KEY"):
                    raise LLMError("openai package not installed. Run: pip install openai")
                return "mock"
            return "openai"
        return "mock"

    def _get_client(self) -> Any:
        """Get or create the API client."""
        if self._client is not None:
            return self._client

        if self._provider == "anthropic":
            self._client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        elif self._provider == "openai":
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        return self._client

    def generate(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        """Generate a response from the LLM.

        Args:
            system: System prompt / instruction.
            prompt: User prompt / input.
            max_tokens: Maximum tokens in response.

        Returns:
            Generated text response.

        Raises:
            LLMError: If the API call fails.
        """
        if self._provider == "mock":
            return self._mock_generate(system, prompt)

        client = self._get_client()

        try:
            if self._provider == "anthropic":
                response = client.messages.create(
                    model=self.model,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                )
                return response.content[0].text

            elif self._provider == "openai":
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                )
                return response.choices[0].message.content

        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e

        raise LLMError(f"Unknown provider: {self._provider}")

    def _mock_generate(self, system: str, prompt: str) -> str:
        """Mock generation for testing without API keys.

        Returns a simple analysis based on keywords in the prompt.
        """
        prompt_lower = prompt.lower()

        # Buying signal analysis
        if "buying" in system.lower() or "signal" in system.lower():
            # Check enrichment buying signal first
            if "enrichment buying signal:" in prompt_lower:
                signal_line = [l for l in prompt.split("\n") if "enrichment buying signal:" in l.lower()]
                if signal_line:
                    signal_text = signal_line[0].split(":", 1)[1].strip().lower()
                    if any(w in signal_text for w in ("hiring", "expanding", "growth", "funding", "series")):
                        return "strong"
                    elif any(w in signal_text for w in ("upgrade", "planned", "initiative", "launch")):
                        return "medium"

            if "hiring" in prompt_lower or "expand" in prompt_lower or "growth" in prompt_lower:
                return "strong"
            elif "upgrade" in prompt_lower or "planned" in prompt_lower or "initiative" in prompt_lower:
                return "medium"
            elif "awarded" in prompt_lower or "funding" in prompt_lower:
                return "medium"
            else:
                return "weak"

        # Email drafting
        if "draft" in system.lower() or "email" in system.lower():
            company = "your company"
            lead_name = ""
            lead_role = ""
            enrichment_lines = []

            for line in prompt.split("\n"):
                lower = line.lower()
                if lower.startswith("lead name:"):
                    lead_name = line.split(":", 1)[1].strip()
                elif lower.startswith("lead role:"):
                    lead_role = line.split(":", 1)[1].strip()
                elif lower.startswith("lead company:"):
                    company = line.split(":", 1)[1].strip()
                elif lower.startswith("- industry:"):
                    enrichment_lines.append(f"your work in {line.split(':', 1)[1].strip()}")
                elif lower.startswith("- company size:"):
                    enrichment_lines.append(f"your team of {line.split(':', 1)[1].strip()}")
                elif lower.startswith("- buying signal:"):
                    enrichment_lines.append(f"your {line.split(':', 1)[1].strip()}")
                elif lower.startswith("- tech stack:"):
                    enrichment_lines.append(f"your {line.split(':', 1)[1].strip()} stack")

            greeting = f"Hi {lead_name}," if lead_name else "Hi there,"
            role_ref = f" as {lead_role}" if lead_role else ""
            fact_line = ", ".join(enrichment_lines[:2]) if enrichment_lines else "your recent work"
            extra_line = ""
            if len(enrichment_lines) > 2:
                extra_line = f"\nI also noticed {enrichment_lines[2]}. "

            return (
                f"{greeting}\n\n"
                f"I noticed you{role_ref} at {company} and was particularly impressed by {fact_line}."
                f"{extra_line}"
                f"We help companies like {company} streamline their sales operations "
                f"and I believe there's a strong fit for what you're building.\n\n"
                f"Would you be open to a 15-minute call next week to explore how we can help?\n\n"
                f"Best regards,\nSales Team"
            )

        return "Analysis complete."