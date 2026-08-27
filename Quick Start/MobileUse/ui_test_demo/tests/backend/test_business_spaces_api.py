def test_business_spaces_include_default_business(authenticated_client):
    response = authenticated_client.get("/api/v1/business-spaces")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "biz_default",
                "name": "默认业务",
                "description": None,
                "is_default": True,
                "task_concurrency_limit": 4,
                "archived_at": None,
                "created_by": "system",
            }
        ]
    }


def test_authenticated_user_can_create_update_and_archive_business_space(
    authenticated_client,
):
    created = authenticated_client.post(
        "/api/v1/business-spaces",
        json={"name": "短剧业务", "description": "短剧回归测试"},
    )
    assert created.status_code == 201
    business = created.json()
    assert business["id"].startswith("biz_")
    assert business | {"id": "ignored"} == {
        "id": "ignored",
        "name": "短剧业务",
        "description": "短剧回归测试",
        "is_default": False,
        "task_concurrency_limit": 4,
        "archived_at": None,
        "created_by": "admin",
    }

    renamed = authenticated_client.patch(
        f"/api/v1/business-spaces/{business['id']}",
        json={
            "name": "短剧业务线",
            "description": "主链路",
            "task_concurrency_limit": 8,
        },
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "短剧业务线"
    assert renamed.json()["description"] == "主链路"
    assert renamed.json()["task_concurrency_limit"] == 8

    archived = authenticated_client.post(
        f"/api/v1/business-spaces/{business['id']}/archive",
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    listed = authenticated_client.get("/api/v1/business-spaces")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == ["biz_default"]


def test_create_business_space_can_atomically_save_runner_settings(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/business-spaces",
        json={
            "name": "原子业务",
            "runner_settings": {
                "mode": "mobile_use",
                "mobile_use": {
                    "product_id": "product-atomic",
                    "access_key_id": "AKLT00000000WXYZ",
                    "secret_access_key": "secret-value",
                    "tos_bucket": "atomic-bucket",
                    "tos_region": "cn-beijing",
                },
            },
        },
    )

    assert response.status_code == 201, response.text
    business_id = response.json()["id"]
    settings = authenticated_client.get(
        "/api/v1/settings",
        headers={"X-Business-Id": business_id},
    )
    assert settings.status_code == 200
    assert settings.json()["mobile_use"]["product_id"] == "product-atomic"
    assert settings.json()["mobile_use"]["access_key_id"]["configured"] is True
    assert settings.json()["mobile_use"]["secret_access_key"]["configured"] is True


def test_create_business_space_rolls_back_when_runner_settings_invalid(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/v1/business-spaces",
        json={
            "name": "回滚业务",
            "runner_settings": {
                "mode": "mobile_use",
                "mobile_use": {
                    "product_id": "product-rollback",
                },
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_settings_incomplete"
    listed = authenticated_client.get("/api/v1/business-spaces")
    assert listed.status_code == 200
    assert "回滚业务" not in {
        item["name"] for item in listed.json()["items"]
    }


def test_default_business_cannot_be_archived(authenticated_client):
    response = authenticated_client.post("/api/v1/business-spaces/biz_default/archive")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "default_business_cannot_archive"


def test_business_concurrency_limit_must_be_between_one_and_eight(
    authenticated_client,
):
    for value in (0, 9):
        response = authenticated_client.post(
            "/api/v1/business-spaces",
            json={"name": f"业务 {value}", "task_concurrency_limit": value},
        )
        assert response.status_code == 422
