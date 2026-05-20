"""自定义业务异常"""


class BusinessException(Exception):
    """业务异常基类"""
    def __init__(self, message: str, code: str = "BUSINESS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ResourceNotFoundException(BusinessException):
    """资源未找到异常"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} 未找到: {identifier}",
            code="RESOURCE_NOT_FOUND"
        )


class DuplicateResourceException(BusinessException):
    """资源重复异常"""
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            f"{resource} 已存在: {field}={value}",
            code="DUPLICATE_RESOURCE"
        )


class ValidationException(BusinessException):
    """数据验证异常"""
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


class InsufficientPermissionException(BusinessException):
    """权限不足异常"""
    def __init__(self, action: str):
        super().__init__(
            f"权限不足，无法执行操作: {action}",
            code="INSUFFICIENT_PERMISSION"
        )


class NoQuestionsAvailableException(BusinessException):
    """没有可用题目异常"""
    def __init__(self, reason: str = "没有符合条件的题目"):
        super().__init__(reason, code="NO_QUESTIONS_AVAILABLE")


class DuplicateQIdException(BusinessException):
    """题目编号重复异常"""
    def __init__(self, q_id: str):
        super().__init__(
            f"题目编号已存在: {q_id}",
            code="DUPLICATE_Q_ID"
        )


class InvalidOperationException(BusinessException):
    """无效操作异常"""
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_OPERATION")
