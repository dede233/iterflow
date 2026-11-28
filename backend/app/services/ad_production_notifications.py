from collections.abc import Collection

from sqlalchemy.orm import Session

from app.models.entities import AdProduction, Notification
from app.models.enums import AdProductionKind, AdProductionStatus, NotificationType
from app.repositories.ad_production_repository import AD_PRODUCTION_ENTITY, AdProductionRepository

_CC_ENTITIES = {
    AdProductionKind.MATERIAL: "AD_PRODUCTION_MATERIAL_CC",
    AdProductionKind.MERCHANT_AD: "AD_PRODUCTION_MERCHANT_CC",
}
_RECEIVER_ENTITIES = {
    AdProductionKind.MATERIAL: "AD_PRODUCTION_MATERIAL",
    AdProductionKind.MERCHANT_AD: AD_PRODUCTION_ENTITY,
}
AD_PRODUCTION_NOTIFICATION_ENTITIES = (*_RECEIVER_ENTITIES.values(), *_CC_ENTITIES.values())
_KIND_LABELS = {
    AdProductionKind.MATERIAL: "物料制作需求",
    AdProductionKind.MERCHANT_AD: "商家广告制作需求",
}
_STATUS_LABELS = {
    AdProductionKind.MATERIAL: {
        AdProductionStatus.NOT_STARTED: "未开始",
        AdProductionStatus.IN_PROGRESS: "进行中",
        AdProductionStatus.SHIPPING: "邮寄中",
        AdProductionStatus.COMPLETED: "已完成",
        AdProductionStatus.WITHDRAWN: "已撤回",
    },
    AdProductionKind.MERCHANT_AD: {
        AdProductionStatus.NOT_STARTED: "未处理",
        AdProductionStatus.IN_PROGRESS: "处理中",
        AdProductionStatus.COMPLETED: "已处理",
        AdProductionStatus.WITHDRAWN: "已撤回",
    },
}


class AdProductionNotifications:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AdProductionRepository(db)

    def queue(
        self,
        item: AdProduction,
        cc_user_ids: Collection[int],
        *,
        newly_added_ids: Collection[int] = (),
        previous_status: AdProductionStatus | None = None,
        reassigned: bool = False,
    ) -> None:
        status_changed = previous_status is not None and previous_status != item.status
        added_ids = set(cc_user_ids).intersection(newly_added_ids)
        cc_recipients = set(cc_user_ids) if status_changed else added_ids
        withdrawing = status_changed and item.status is AdProductionStatus.WITHDRAWN
        receiver_id = item.receiver_id if withdrawing else None
        candidates = cc_recipients if receiver_id is None else cc_recipients | {receiver_id}
        active_ids = self.repo.active_cc_user_ids(candidates)
        cc_active_ids = cc_recipients & active_ids

        notices: dict[int, tuple[str, str]] = {}
        kind = _KIND_LABELS[item.kind]
        if receiver_id is not None and receiver_id in active_ids:
            notices[receiver_id] = (f"{kind}已撤回", f"你收到的{kind}已撤回。请查看详情。")
        elif item.kind is AdProductionKind.MERCHANT_AD:
            if (previous_status is None or reassigned) and item.receiver_id is not None:
                notices[item.receiver_id] = (
                    "新的商家广告制作需求",
                    "你收到了一条商家广告制作需求。请查看详情。",
                )
            elif status_changed and item.status is AdProductionStatus.COMPLETED:
                notices[item.created_by] = (
                    "商家广告制作需求已完成",
                    "你发布的商家广告制作需求已完成。请查看处理结果。",
                )

        if cc_active_ids:
            status = _STATUS_LABELS[item.kind][item.status]
            for user_id in cc_active_ids:
                if user_id in added_ids:
                    message = (
                        f"你被抄送了{kind}",
                        f"你被加入一条{kind}的抄送名单。当前状态为{status}。",
                    )
                else:
                    message = (f"{kind}状态更新", f"抄送给你的{kind}状态已更新为{status}。")
                notices.setdefault(user_id, message)

        self.db.add_all(
            Notification(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                title=title,
                content=content,
                entity_type=_CC_ENTITIES[item.kind]
                if user_id in cc_active_ids
                else _RECEIVER_ENTITIES[item.kind],
                entity_id=item.id,
            )
            for user_id, (title, content) in notices.items()
        )
