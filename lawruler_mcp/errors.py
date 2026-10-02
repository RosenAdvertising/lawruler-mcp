"""Safe, anticipated errors exposed to MCP clients."""

from mcp.server.mcpserver.exceptions import ToolError


class LawRulerToolError(ToolError):
    """Only reviewed messages from known client failure paths."""


class MissingCredentialsError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler credentials are missing. Run `lawruler-mcp-setup` or set "
            "LAWRULER_API_KEY and LAWRULER_BASE_URL. Restart the MCP server after changing credentials."
        )


class AuthenticationError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler authentication was rejected. Reauthorize with `lawruler-mcp-setup`."
        )


class PermissionDeniedError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawruler-mcp-setup if so)."
        )


class TransportError(LawRulerToolError):
    def __init__(self, *, timed_out: bool):
        reason = (
            "LawRuler request timed out."
            if timed_out
            else "Could not connect to LawRuler."
        )
        super().__init__(
            f"{reason} The outcome is unknown; check whether the action completed before retrying."
        )


class VendorHTTPError(LawRulerToolError):
    def __init__(self, status: int, reason: str):
        super().__init__(f"LawRuler request failed (HTTP {status}): {reason}.")


class RateLimitError(LawRulerToolError):
    def __init__(self, retry_after: int):
        super().__init__(
            f"LawRuler rate limit reached. Retry after {retry_after} seconds."
        )


class NotFoundError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler endpoint was not found (HTTP 404). Check the configured portal URL and API endpoint."
        )


class ArgumentError(LawRulerToolError):
    def __init__(self, argument: str, expected: str):
        super().__init__(f"Invalid argument '{argument}': expected {expected}.")
