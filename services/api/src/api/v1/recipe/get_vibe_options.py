"""Get vibe options endpoint."""

from utils.api.endpoint import AsyncEndpoint, success
from utils.constants import VIBE_OPTIONS


class GetVibeOptions(AsyncEndpoint):
    """Return the list of valid vibes with display names and colors."""

    async def execute(self):
        return success(data=VIBE_OPTIONS)
