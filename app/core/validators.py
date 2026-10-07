def validate_password_strength(password: str) -> str:
    if not any(char.isupper() for char in password):
        raise ValueError("Password must contain at least one uppercase letter")

    if not any(char.islower() for char in password):
        raise ValueError("Password must contain at least one lowercase letter")

    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one number")

    return password
