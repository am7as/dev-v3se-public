"""Provider registry. Keep this template to ONE provider (openai). Use
`11-multi-provider-inference` if you need more."""
from .openai import predict

__all__ = ["predict"]
