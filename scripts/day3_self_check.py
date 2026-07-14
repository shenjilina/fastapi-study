"""Day3 公共治理能力自检脚本。"""

from fastapi.testclient import TestClient

from init_app import app


def main() -> None:
    """验证统一响应、参数校验、异常处理和请求头注入是否生效。"""
    client = TestClient(app)

    success_response = client.get("/health")
    print("HEALTH:", success_response.status_code, success_response.json())
    print("HEALTH REQUEST ID:", success_response.headers.get("X-Request-ID"))

    validation_response = client.post(
        "/api/v1/users",
        json={
            "username": "ab",
            "email": "bad_email",
            "password": "123",
        },
    )
    print("VALIDATION:", validation_response.status_code, validation_response.json())
    print("VALIDATION REQUEST ID:", validation_response.headers.get("X-Request-ID"))

    business_response = client.get("/api/v1/users/999999")
    print("BUSINESS:", business_response.status_code, business_response.json())
    print("BUSINESS REQUEST ID:", business_response.headers.get("X-Request-ID"))


if __name__ == "__main__":
    main()
