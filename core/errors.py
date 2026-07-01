"""Application exception hierarchy and user-visible message constants."""

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base for application errors that carry a user-visible message."""
    def __init__(self, user_message: str, *, cause: BaseException | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        if cause is not None:
            self.__cause__ = cause


class DatabaseUnavailableError(AppError):
    """Raised when the connection pool cannot be established."""


class DatabaseOperationError(AppError):
    """Raised when a database query or transaction fails."""


class CameraError(AppError):
    """Raised when the camera cannot be opened or read."""


class ModelError(AppError):
    """Raised when a face-recognition model is missing or corrupt."""


# ---------------------------------------------------------------------------
# User-visible message constants
# ---------------------------------------------------------------------------

# Database
DB_UNAVAILABLE      = (
    "Unable to connect to the database. "
    "Please ensure the database server is running and try again."
)
DB_INIT_FAILED      = (
    "The database could not be initialized. "
    "The application cannot start. Please contact your administrator."
)
DB_OPERATION_FAILED = (
    "A database error occurred. Please try again. "
    "If the problem persists, contact your administrator."
)
DB_READ_FAILED      = "Failed to load data from the database. Please try again."
DB_WRITE_FAILED     = "Failed to save changes to the database. Please try again."

# Authentication
LOGIN_DB_ERROR      = (
    "Unable to reach the database. "
    "Please check your connection and try again."
)

# Camera
CAMERA_NOT_FOUND    = "No camera was detected. Please connect a camera and try again."
CAMERA_READ_ERROR   = "The camera stopped responding. Please check the connection and try again."

# Face recognition / model
MODEL_NOT_TRAINED   = (
    "The recognition model has not been trained for this class yet. "
    "Please train the model first."
)
MODEL_LOAD_FAILED   = (
    "Failed to load the recognition model. "
    "The model file may be missing or corrupted."
)
CAPTURE_FAILED      = "Photo capture failed. Please check the camera connection and try again."
CAPTURE_NO_FACE     = (
    "No face was detected. "
    "Please ensure the camera is positioned correctly and try again."
)

# Registration
STUDENT_ID_CHECK_FAILED = (
    "Could not verify the student ID. "
    "Please check the database connection and try again."
)
STUDENT_ID_EXISTS   = "This student ID already exists. Please use a different ID."
REGISTRATION_FAILED = "Student registration could not be completed. Please try again."

# File I/O
FILE_ACCESS_ERROR   = (
    "Could not access required files. "
    "Please ensure the application has the necessary permissions."
)
MODEL_SAVE_FAILED   = "Failed to save the recognition model. Please check disk space and permissions."

# Classes
CLASS_LOAD_FAILED   = "Failed to load the class list. Please check the database connection and try again."
CLASS_SAVE_FAILED   = "Failed to save the class. Please try again."
CLASS_DELETE_FAILED = "Failed to delete the class. Please try again."

# Export
EXPORT_FAILED       = "Export failed. Please check disk space and permissions, then try again."

# General
GENERAL_ERROR       = (
    "An unexpected error occurred. Please try again. "
    "If the problem continues, contact your administrator."
)
