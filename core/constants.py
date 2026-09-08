"""项目全局常量。"""

# 统一响应相关常量
SUCCESS_CODE = 0
DEFAULT_ERROR_CODE = 1
VALIDATION_ERROR_CODE = 1001  # 请求参数校验失败
INTERNAL_ERROR_CODE = 1002  # 服务端内部错误
AUTHENTICATION_ERROR_CODE = 1003  # 登录认证失败：用户名或密码错误
ACCOUNT_DISABLED_CODE = 1004  # 登录认证失败：用户账号已被禁用

# 默认路由与文案
DEFAULT_HEALTH_PATH = "/health"
DEFAULT_ROOT_MESSAGE = "FastAPI study project is ready."

# 中间件与请求处理
REQUEST_ID_HEADER = "X-Request-ID"

# RAG 相关常量
DEFAULT_MAX_CONTEXT_TOKENS = 3000

# 文件解析相关常量
SUPPORTED_FILE_EXTENSIONS = ("txt", "pdf", "docx", "md", "markdown")
EMPTY_FILE_ERROR = "文件内容为空，无法解析"
UNSUPPORTED_FILE_TYPE_ERROR = "不支持的文件类型"
CORRUPTED_FILE_ERROR = "文件已损坏或格式不正确"

# Token 估算常量（近似值：英文约 4 字符/token，中文约 2 字符/token）
TOKEN_CHARS_RATIO_EN = 4
TOKEN_CHARS_RATIO_CN = 2

# 检索相关常量
DEFAULT_RETRIEVAL_TOP_K = 4
MIN_RETRIEVAL_TOP_K = 1
MAX_RETRIEVAL_TOP_K = 20

# LLM 重试相关常量
LLM_RETRY_BACKOFF_BASE = 1.5  # 重试退避基数（秒）
