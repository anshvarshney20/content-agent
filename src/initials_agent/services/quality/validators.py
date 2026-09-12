from initials_agent.models.content import ContentDraft


def run_deterministic_checks(draft: ContentDraft, platform: str) -> list[str]:
    errors = []
    
    # 1. Missing fields
    if not draft.title: errors.append("Missing title.")
    if not draft.hook: errors.append("Missing hook.")
    if not draft.cta: errors.append("Missing CTA.")
    
    # 2. Source availability
    if not draft.source_references:
        errors.append("No source references provided.")
        
    # 3. Platform character limits
    if platform.lower() == "linkedin":
        if len(draft.linkedin_post) > 3000:
            errors.append("LinkedIn post exceeds 3000 characters.")
    elif platform.lower() == "instagram":
        if len(draft.instagram_caption) > 2200:
            errors.append("Instagram caption exceeds 2200 characters.")
            
    # 4. Hashtag quality
    if len(draft.hashtags) > 30:
        errors.append("Too many hashtags (limit 30).")
    if not draft.hashtags:
        errors.append("Missing hashtags.")
        
    # 5. Image dimensions
    if draft.visual_concept:
        ar = draft.visual_concept.aspect_ratio
        valid_ars = ["1080x1350", "1080x1920", "1200x1200", "1200x1350"]
        if ar not in valid_ars:
            errors.append(f"Invalid image dimensions: {ar}")

    return errors
