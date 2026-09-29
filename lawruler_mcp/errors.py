"""Safe, anticipated errors exposed to MCP clients."""

from mcp.server.mcpserver.exceptions import ToolError


class LawRulerToolError(ToolError):
    """Only reviewed messages from known client failure paths."""


class MissingCredentialsError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler credentials are missing. Run `lawruler-mcp-setup` or set "
            "LAWRULER_API_KEY and LAWRULER_BASE_URL."
        )


class AuthenticationError(LawRulerToolError):
    def __init__(self):
        super().__init__(
            "LawRuler authentication was rejected. Reauthorize with `lawruler-mcp-setup`."
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
            "LawRuler record was not found (HTTP 404). Check the LeadID and try again."
        )


class ArgumentError(LawRulerToolError):
    def __init__(self, argument: str, expected: str):
        super().__init__(f"Invalid argument '{argument}': expected {expected}.")
