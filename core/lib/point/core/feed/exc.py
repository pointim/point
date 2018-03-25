from point.core import PointError
from point.core.user import UserNotFound

class FeedError(PointError):
    pass

class FeedNotFound(UserNotFound, FeedError):
    pass

class InvalidFeedUrl(FeedError):
    pass

class InvalidFeedType(FeedError):
    pass

class FeedFetchError(FeedError):
    pass

