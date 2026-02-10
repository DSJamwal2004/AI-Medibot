def generate_clarification_question(
    *,
    missing_slots: list[str],
    primary_domain: str | None,
) -> str:
    """
    Returns a single, high-value clarification question.
    """

    if "symptom" in missing_slots:
        return (
            "Can you describe the main symptom in a bit more detail?"
        )

    if "duration" in missing_slots:
        return (
            "How long have you been experiencing this? "
            "(for example: minutes, hours, days, weeks)"
        ) 

    if "severity" in missing_slots:
        return (
            "How severe is it right now? "
            "(mild, moderate, or severe)"
        )

    # fallback (rare)
    return (
        "Can you share a bit more detail so I can assess this more accurately?"
    )
