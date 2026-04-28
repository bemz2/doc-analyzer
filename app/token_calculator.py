"""
Token calculator module for estimating costs across different LLM providers.
"""
from typing import Dict, Tuple


# Pricing per 1M tokens (input, output) in USD
MODEL_PRICING = {
    # OpenAI models
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4-turbo-preview": (10.0, 30.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4": (30.0, 60.0),
    "gpt-4-32k": (60.0, 120.0),
    "gpt-3.5-turbo": (0.5, 1.5),
    "gpt-3.5-turbo-16k": (3.0, 4.0),
    
    # Anthropic models
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-sonnet-20240229": (3.0, 15.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
    
    # Default fallback
    "default": (1.0, 3.0)
}


# Context window sizes in tokens. Custom/local models vary by model/server, so
# use the configured chunk size as the effective context budget there.
MODEL_CONTEXT_WINDOWS = {
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1": 1_047_576,
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo-preview": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-4-32k": 32_768,
    "gpt-3.5-turbo": 16_385,
    "gpt-3.5-turbo-16k": 16_385,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
}


def get_model_pricing(model: str) -> Tuple[float, float]:
    """
    Get pricing for a specific model.
    
    Args:
        model: Model name
        
    Returns:
        Tuple of (input_price_per_1m, output_price_per_1m)
    """
    return MODEL_PRICING.get(model, MODEL_PRICING["default"])


def get_model_context_window(model: str, fallback: int) -> int:
    """Get known model context window or fallback to configured chunk size."""
    return MODEL_CONTEXT_WINDOWS.get(model, fallback)


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> Dict[str, float]:
    """
    Calculate cost for token usage.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name
        
    Returns:
        Dictionary with cost breakdown
    """
    input_price, output_price = get_model_pricing(model)
    
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost": round(input_cost, 4),
        "output_cost": round(output_cost, 4),
        "total_cost": round(total_cost, 4),
        "currency": "USD"
    }


def estimate_analysis_cost(total_chunks: int, avg_chunk_tokens: int, model: str) -> Dict[str, any]:
    """
    Estimate cost for document analysis.
    
    Args:
        total_chunks: Number of chunks
        avg_chunk_tokens: Average tokens per chunk
        model: Model name
        
    Returns:
        Dictionary with cost estimation
    """
    # Estimate input tokens (document chunks + instructions)
    instruction_tokens = 500  # Average instruction length
    input_tokens = (total_chunks * avg_chunk_tokens) + (total_chunks * instruction_tokens)
    
    # Estimate output tokens (summary + findings per chunk + global analysis)
    output_per_chunk = 500  # Average output per chunk
    global_analysis_output = 1000  # Global analysis output
    output_tokens = (total_chunks * output_per_chunk) + global_analysis_output
    
    cost_breakdown = calculate_cost(input_tokens, output_tokens, model)
    
    return {
        **cost_breakdown,
        "total_chunks": total_chunks,
        "avg_chunk_tokens": avg_chunk_tokens,
        "model": model
    }


def get_all_model_estimates(input_tokens: int, output_tokens: int) -> Dict[str, Dict]:
    """
    Get cost estimates for all available models.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Dictionary with estimates for each model
    """
    estimates = {}
    
    for model_name in MODEL_PRICING.keys():
        if model_name == "default":
            continue
        estimates[model_name] = calculate_cost(input_tokens, output_tokens, model_name)
    
    return estimates
