def load_prompt_from_string(instructions: str, metadata: dict) -> str:
    """
    Replace placeholders in instructions string with values from metadata.

    :param instructions: The prompt/instructions string with placeholders like {lead_first_name}
    :param metadata: Dictionary containing values for placeholders
    :return: The prompt with placeholders replaced by metadata values
    """
    # Flatten metadata keys to lowercase strings for consistent replacement
    context = {k.lower(): v for k, v in metadata.items()}

    # Replace placeholders in instructions
    prompt_filled = instructions
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        if placeholder in prompt_filled:
            prompt_filled = prompt_filled.replace(placeholder, str(value))

    return prompt_filled

