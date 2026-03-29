"""Get vibe options endpoint."""

from utils.api.endpoint import Endpoint, success
from utils.constants import VIBE_OPTIONS


class GetVibeOptions(Endpoint):
    """Return the list of valid vibes with display names and colors."""

    def execute(self):
        return success(data=VIBE_OPTIONS)
