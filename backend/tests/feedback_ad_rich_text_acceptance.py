import re
from base64 import b64encode

from ad_production_acceptance import FIELDS as AD_FIELDS
from ad_production_acceptance import (
    PNG,
    create_ad_receiver,
    form,
    publication_fields,
    user_with_scope,
)

IMAGE_KEY = "local-2e334360-8cd5-4811-b394-c21f5668a29c"
IMAGE_DATA = "data:image/png;base64," + b64encode(PNG).decode("ascii")
RICH = (
    "<h2>复核内容</h2><p><strong>重点</strong></p><script>未显示</script>"
    f'<img data-file-id="{IMAGE_KEY}">'
)


def stored_image_id(body):
    match = re.search(r'data-file-id="([1-9][0-9]*)"', body)
    assert match and IMAGE_KEY not in body
    assert "<strong>重点</strong>" in body and "未显示" not in body
    return int(match.group(1))


def exercise_feedback_ad_rich_text(api):
    client, engine, user_id, admin = api
    feedbacks = "/api/v1/feedbacks"
    ads = "/api/v1/ad-productions"
    receiver_id, _ = create_ad_receiver(client, engine, admin, name="ad_image_recipient")
    _, outsider = user_with_scope(
        client,
        engine,
        admin,
        name="editor_viewer",
        permissions={"rd.feedback.view", "ops.ad_production.view"},
    )
    fields = {
        "title": "富文本验收反馈",
        "feedback_type": "SYSTEM_ISSUE",
        "recipient_ids": [user_id],
    }
    literal = " 原有文字 <b>保留字面字符</b>\n下一行 "
    plain = client.post(feedbacks, headers=admin, json={**fields, "description": literal})
    assert plain.status_code == 200, plain.text
    plain_record = plain.json()
    assert plain_record["description_format"] == "PLAIN"
    renamed = client.patch(
        f"{feedbacks}/{plain_record['id']}",
        headers=admin,
        json={"title": "更新标题", "revision": plain_record["revision"]},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["description"] == literal

    rich_feedback = client.post(
        feedbacks,
        headers=admin,
        json={
            **fields,
            "description_format": "HTML",
            "description": RICH,
            "description_images": {IMAGE_KEY: IMAGE_DATA},
        },
    )
    assert rich_feedback.status_code == 200, rich_feedback.text
    feedback = rich_feedback.json()
    assert feedback["description_format"] == "HTML"
    feedback_file = stored_image_id(feedback["description"])
    feedback_path = f"{feedbacks}/{feedback['id']}"
    image_url = f"{feedback_path}/images/{feedback_file}"
    image = client.get(image_url, headers=admin)
    assert image.content == PNG
    assert image.headers["x-content-type-options"] == "nosniff"
    assert client.get(image_url, headers=outsider).status_code == 404
    assert client.get(f"/api/v1/files/{feedback_file}/download", headers=admin).status_code == 404
    assert client.get(f"{feedback_path}/attachments", headers=admin).json() == []

    foreign_image = client.patch(
        f"{feedbacks}/{plain_record['id']}",
        headers=admin,
        json={
            "description": feedback["description"],
            "description_format": "HTML",
            "revision": renamed.json()["revision"],
        },
    )
    assert foreign_image.status_code == 422, foreign_image.text
    assert (
        client.get(f"{feedbacks}/{plain_record['id']}", headers=admin).json()["description"]
        == literal
    )

    converted = client.post(
        f"{feedback_path}/accept-and-convert",
        headers=admin,
        json={
            "type": "CREATE_NEW",
            "accept_on_convert": True,
            "revision": feedback["revision"],
            "requirement_title": "保留正文图片",
            "requirement_type": "FEATURE",
            "description": feedback["description"],
            "description_format": "HTML",
            "participants": [{"user_id": user_id, "role": "CONFIRM"}],
        },
    )
    assert converted.status_code == 200, converted.text
    requirement = converted.json()
    assert stored_image_id(requirement["description"]) == feedback_file
    assert (
        client.get(
            f"/api/v1/requirements/{requirement['id']}/images/{feedback_file}",
            headers=admin,
        ).content
        == PNG
    )

    created = client.post(
        ads,
        headers=admin,
        files=[
            *form(
                publication_fields(receiver_id, content=RICH, content_format="HTML"),
                ("gallery.png", PNG, "image/png"),
            ),
            ("content_images", (IMAGE_KEY, PNG, "image/png")),
        ],
    )
    assert created.status_code == 201, created.text
    ad = created.json()
    assert ad["content_format"] == "HTML"
    inline_file = stored_image_id(ad["content"])
    gallery_file = ad["images"][0]["file_id"]
    assert inline_file != gallery_file and len(ad["images"]) == 1
    ad_path = f"{ads}/{ad['id']}"
    assert client.get(f"{ad_path}/content-images/{inline_file}", headers=admin).content == PNG
    assert (
        client.get(f"{ad_path}/content-images/{inline_file}", headers=outsider).status_code == 404
    )
    assert client.get(f"{ad_path}/images/{inline_file}", headers=admin).status_code == 404
    assert client.get(f"{ad_path}/content-images/{gallery_file}", headers=admin).status_code == 404

    old_client = client.patch(
        ad_path,
        headers=admin,
        files=form(
            {
                **AD_FIELDS,
                "content": ad["content"],
                "status": "COMPLETED",
                "revision": ad["revision"],
            }
        ),
    )
    assert old_client.status_code == 200, old_client.text
    assert (
        old_client.json()["content_format"] == "HTML"
        and old_client.json()["content"] == ad["content"]
    )

    multiline = "旧广告第一行\n旧广告第二行"
    legacy_ad = client.post(
        ads, headers=admin, files=form(publication_fields(receiver_id, content=multiline))
    )
    assert legacy_ad.status_code == 201, legacy_ad.text
    legacy = legacy_ad.json()
    assert legacy["content_format"] == "PLAIN" and legacy["content"] == multiline
    changed_status = client.patch(
        f"{ads}/{legacy['id']}",
        headers=admin,
        files=form(
            {
                **AD_FIELDS,
                "content": multiline.replace("\n", "\r\n"),
                "content_format": "PLAIN",
                "status": "COMPLETED",
                "revision": legacy["revision"],
            }
        ),
    )
    assert changed_status.status_code == 200, changed_status.text
    assert changed_status.json()["content"] == multiline
