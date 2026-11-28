from collections import defaultdict
from collections.abc import Collection

from sqlalchemy.orm import Session

from app.models.entities import AdProduction, Notification
from app.models.enums import AdProductionKind, AdProductionStatus, NotificationType
from app.repositories.ad_production_repository import AD_PRODUCTION_ENTITY, AdProductionRepository
from app.services.collaboration_service import CollaborationService

_CC_ENTITIES = {
    AdProductionKind.MATERIAL: "AD_PRODUCTION_MATERIAL_CC",
    AdProductionKind.MERCHANT_AD: "AD_PRODUCTION_MERCHANT_CC",
}
_RECEIVER_ENTITIES = {
    AdProductionKind.MATERIAL: "AD_PRODUCTION_MATERIAL",
    AdProductionKind.MERCHANT_AD: AD_PRODUCTION_ENTITY,
}
AD_PRODUCTION_NOTIFICATION_ENTITIES = (*_RECEIVER_ENTITIES.values(), *_CC_ENTITIES.values())
AD_PRODUCTION_EVENT_KINDS = {
    entity: kind
    for mapping in (_RECEIVER_ENTITIES, _CC_ENTITIES)
    for kind, entity in mapping.items()
}
AD_PRODUCTION_CC_EVENTS = frozenset(_CC_ENTITIES.values())
AD_PRODUCTION_ACTION_LABELS = {
    "OPS_ASSIGNED": "有制作需求待处理",
    "OPS_COMPLETED": "制作需求已完成",
    "OPS_WITHDRAWN": "制作需求已撤回",
    "OPS_CC_ADDED": "加入制作需求抄送",
    "OPS_CC_UPDATED": "抄送的制作需求有更新",
}
AD_PRODUCTION_MAIL_PATHS = {
    AdProductionKind.MATERIAL: "notifications/material",
    AdProductionKind.MERCHANT_AD: "notifications/merchant-ad",
}
AD_PRODUCTION_KIND_LABELS = {
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
        actor_id: int,
        newly_added_ids: Collection[int] = (),
        previous_status: AdProductionStatus | None = None,
        reassigned: bool = False,
    ) -> None:
        status_changed = previous_status is not None and previous_status != item.status
        added_ids = set(cc_user_ids).intersection(newly_added_ids)
        cc_recipients = set(cc_user_ids) if status_changed else added_ids
        withdrawing = status_changed and item.status is AdProductionStatus.WITHDRAWN
        addressed_to_receiver = withdrawing or previous_status is None or reassigned
        receiver_id = item.receiver_id if addressed_to_receiver else None
        completing = status_changed and item.status is AdProductionStatus.COMPLETED
        candidates = cc_recipients | {item.created_by}
        if receiver_id is not None:
            candidates.add(receiver_id)
        active_ids = self.repo.active_cc_user_ids(candidates)
        cc_active_ids = cc_recipients & active_ids

        notices: dict[int, tuple[str, str, str]] = {}
        kind = AD_PRODUCTION_KIND_LABELS[item.kind]
        receiver_action: str | None = None
        if receiver_id is not None and receiver_id in active_ids:
            if withdrawing:
                receiver_action = "OPS_WITHDRAWN"
                notices[receiver_id] = (
                    "OPS_WITHDRAWN",
                    f"{kind}已撤回",
                    f"你收到的{kind}已撤回。请查看详情。",
                )
            elif item.status is not AdProductionStatus.COMPLETED:
                receiver_action = "OPS_ASSIGNED"
                if item.kind is AdProductionKind.MERCHANT_AD:
                    notices[receiver_id] = (
                        receiver_action,
                        f"新的{kind}",
                        f"你收到了一条{kind}。请查看详情。",
                    )
        notify_creator = completing and item.created_by in active_ids
        if notify_creator and item.kind is AdProductionKind.MERCHANT_AD:
            notices[item.created_by] = (
                "OPS_COMPLETED",
                f"{kind}已完成",
                f"你发布的{kind}已完成。请查看处理结果。",
            )

        status = _STATUS_LABELS[item.kind][item.status]
        for user_id in cc_active_ids:
            if user_id in added_ids:
                message = (
                    "OPS_CC_ADDED",
                    f"你被抄送了{kind}",
                    f"你被加入一条{kind}的抄送名单。当前状态为{status}。",
                )
            else:
                message = (
                    "OPS_CC_UPDATED",
                    f"{kind}状态更新",
                    f"抄送给你的{kind}状态已更新为{status}。",
                )
            notices.setdefault(user_id, message)

        for user_id, (_, title, content) in notices.items():
            site_entity = (
                _CC_ENTITIES[item.kind]
                if user_id in cc_active_ids
                else _RECEIVER_ENTITIES[item.kind]
            )
            self.db.add(
                Notification(
                    user_id=user_id,
                    type=NotificationType.SYSTEM,
                    title=title,
                    content=content,
                    entity_type=site_entity,
                    entity_id=item.id,
                )
            )
        mail_actions = {user_id: action for user_id, (action, _, _) in notices.items()}
        # A recipient who is also copied gets one email under their workflow role.
        if receiver_id is not None and receiver_action is not None:
            mail_actions[receiver_id] = receiver_action
        if notify_creator:
            mail_actions[item.created_by] = "OPS_COMPLETED"

        mail_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for user_id, action in mail_actions.items():
            entities = _CC_ENTITIES if action.startswith("OPS_CC_") else _RECEIVER_ENTITIES
            mail_groups[entities[item.kind], action].append(user_id)
        collaboration = CollaborationService(self.db)
        for (entity, action), recipients in mail_groups.items():
            collaboration.event(entity, item.id, action, actor_id, recipients)
