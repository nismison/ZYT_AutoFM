class OrderHandlerError(Exception):
    """工单处理相关的通用异常"""
    pass


class OrderNotFoundError(OrderHandlerError):
    """未找到符合条件的工单"""
    pass


class RuleNotFoundError(OrderHandlerError):
    """未找到工单对应规则"""
    pass


class UserNotFoundError(OrderHandlerError):
    """未找到用户信息"""
    pass


class ImageUploadError(OrderHandlerError):
    """水印图片上传失败"""
    pass


class PartialUploadError(OrderHandlerError):
    """部分图片上传失败"""
    pass
