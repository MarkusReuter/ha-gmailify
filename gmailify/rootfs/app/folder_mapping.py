"""GMX IMAP folder to Gmail label mapping."""

# Gmail system label IDs — these already exist and must not be created.
GMAIL_SYSTEM_LABELS = {
    "INBOX", "SENT", "DRAFT", "SPAM", "TRASH",
    "UNREAD", "STARRED", "IMPORTANT",
}

# GMX uses German folder names. IMAP encodes non-ASCII via modified UTF-7.
# The folder "Entwürfe" becomes "Entw&APw-rfe" on the wire.
# Map to Gmail system labels so mails land in the native Gmail folders.
DEFAULT_FOLDER_MAP: dict[str, str] = {
    "INBOX": "INBOX",
    "Gesendet": "SENT",
    "Entw&APw-rfe": "DRAFT",
    "Papierkorb": "TRASH",
    "Spam": "SPAM",
}

# Reverse lookup: common user-facing names to IMAP names
USER_TO_IMAP: dict[str, str] = {
    "INBOX": "INBOX",
    "Gesendet": "Gesendet",
    "Entwürfe": "Entw&APw-rfe",
    "Entw&APw-rfe": "Entw&APw-rfe",
    "Papierkorb": "Papierkorb",
    "Spam": "Spam",
}


def get_gmail_label(imap_folder: str) -> str:
    """Get the Gmail label for a given IMAP folder name."""
    if imap_folder in DEFAULT_FOLDER_MAP:
        return DEFAULT_FOLDER_MAP[imap_folder]
    # For unknown folders, use GMX/<folder_name> as label
    decoded = decode_imap_utf7(imap_folder)
    return f"GMX/{decoded}"


def resolve_folder_name(user_input: str) -> str:
    """Resolve a user-facing folder name to the IMAP folder name."""
    if user_input in USER_TO_IMAP:
        return USER_TO_IMAP[user_input]
    return user_input


def decode_imap_utf7(name: str) -> str:
    """Decode IMAP modified UTF-7 folder name to readable string.

    IMAP modified UTF-7 (RFC 3501 Section 5.1.3):
    - '&' starts a base64-encoded UTF-16BE sequence, ended by '-'
    - '&-' is a literal '&'
    - Everything else is ASCII
    """
    import base64

    result = []
    i = 0
    while i < len(name):
        if name[i] == "&":
            j = name.index("-", i + 1)
            if j == i + 1:
                # &- is a literal &
                result.append("&")
            else:
                encoded = name[i + 1 : j]
                # Pad base64 to multiple of 4
                padded = encoded + "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else encoded
                decoded_bytes = base64.b64decode(padded.replace(",", "/"))
                result.append(decoded_bytes.decode("utf-16-be"))
            i = j + 1
        else:
            result.append(name[i])
            i += 1
    return "".join(result)
