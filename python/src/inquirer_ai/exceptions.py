from __future__ import annotations


class InquirerAIError(Exception):
    pass


class ValidationError(InquirerAIError):
    pass


class PromptAbortedError(InquirerAIError):
    pass
