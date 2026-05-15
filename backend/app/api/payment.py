from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from ..database import get_db
from ..models import MemberOrder, User, MemberType, PaymentMethod, PaymentStatus
from ..schemas import CreateOrderRequest, OrderOut
from ..utils.auth import get_current_user_id

router = APIRouter(prefix="/api/payment", tags=["会员充值"])

PRICE_CONFIG = {
    "basic": {1: 99, 3: 269, 6: 499, 12: 899},
    "premium": {1: 199, 3: 539, 6: 999, 12: 1799},
}


@router.post("/create-order")
def create_order(
    req: CreateOrderRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    price_map = PRICE_CONFIG.get(req.member_type)
    if not price_map:
        raise HTTPException(status_code=400, detail="无效的会员类型")

    amount = price_map.get(req.duration_months)
    if not amount:
        raise HTTPException(status_code=400, detail="无效的购买时长")

    order_no = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    order = MemberOrder(
        user_id=user_id,
        order_no=order_no,
        member_type=req.member_type,
        duration_months=req.duration_months,
        amount=amount,
        payment_method=req.payment_method,
        payment_status=PaymentStatus.pending.value,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return OrderOut(
        order_id=order.order_id,
        order_no=order.order_no,
        member_type=order.member_type,
        duration_months=order.duration_months,
        amount=float(order.amount),
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        created_date=order.created_date,
    )


@router.post("/pay/{order_id}")
def pay_order(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    order = (
        db.query(MemberOrder)
        .filter(MemberOrder.order_id == order_id, MemberOrder.user_id == user_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.payment_status != PaymentStatus.pending.value:
        raise HTTPException(status_code=400, detail="订单状态异常")

    order.payment_status = PaymentStatus.paid.value
    order.paid_date = datetime.now()
    order.transaction_id = f"TXN{uuid.uuid4().hex[:16].upper()}"

    user = db.query(User).filter(User.user_id == user_id).first()
    user.member_type = order.member_type

    now = datetime.now()
    if user.member_expire_date and user.member_expire_date > now:
        user.member_expire_date += timedelta(days=30 * order.duration_months)
    else:
        user.member_expire_date = now + timedelta(days=30 * order.duration_months)

    db.commit()

    return {"message": "支付成功", "order_no": order.order_no, "member_type": order.member_type}


@router.get("/orders")
def list_orders(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(MemberOrder)
        .filter(MemberOrder.user_id == user_id)
        .order_by(MemberOrder.created_date.desc())
        .all()
    )
    return {
        "orders": [
            OrderOut(
                order_id=o.order_id,
                order_no=o.order_no,
                member_type=o.member_type,
                duration_months=o.duration_months,
                amount=float(o.amount),
                payment_method=o.payment_method,
                payment_status=o.payment_status,
                created_date=o.created_date,
                paid_date=o.paid_date,
            )
            for o in orders
        ]
    }


@router.get("/prices")
def get_prices():
    return PRICE_CONFIG


@router.get("/member-info")
def get_member_info(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    return {
        "member_type": user.member_type,
        "member_expire_date": user.member_expire_date.isoformat() if user.member_expire_date else None,
        "is_expired": user.member_expire_date and user.member_expire_date < datetime.now(),
        "remaining_days": (user.member_expire_date - datetime.now()).days if user.member_expire_date and user.member_expire_date > datetime.now() else 0,
    }
