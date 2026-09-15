from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": code, "message": message}
        )


class ConflictError(HTTPException):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, detail={"code": code, "message": message}
        )
