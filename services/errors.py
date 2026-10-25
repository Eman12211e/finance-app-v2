class AppError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "Something went wrong. Please try again."

    def __init__(self, message=None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidTicker(AppError):
    code = "INVALID_TICKER"
    http_status = 400
    default_message = "That ticker symbol is not valid."


class InvalidProfile(AppError):
    code = "INVALID_PROFILE"
    http_status = 400
    default_message = "The age range or risk choice is not valid."


class DataNotAvailable(AppError):
    code = "DATA_NOT_AVAILABLE"
    http_status = 404
    default_message = "Data not available."


class ProviderError(AppError):
    code = "PROVIDER_ERROR"
    http_status = 502
    default_message = "A data provider did not respond."


class AIUnavailable(AppError):
    code = "AI_UNAVAILABLE"
    http_status = 503
    default_message = "The assistant is not available right now."


class InvalidRequest(AppError):
    code = "INVALID_REQUEST"
    http_status = 400
    default_message = "The request is missing information or is not valid."


class LiveInferenceDisabled(AppError):
    code = "LIVE_INFERENCE_DISABLED"
    http_status = 403
    default_message = "Live AI inference is turned off. The Lab shows simulated output only."


class BudgetExceeded(AppError):
    code = "BUDGET_EXCEEDED"
    http_status = 402
    default_message = "This request could go over the AI spending limit, so it was not sent."
