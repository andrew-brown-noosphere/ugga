"""
Payment and subscription management endpoints.

Integrates with Stripe for:
- Checkout sessions
- Customer portal
- Webhook handling
- Subscription status
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import User, Payment, get_session_factory
from src.api.auth import get_current_user
from src.api.schemas import (
    CreateCheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionStatusResponse,
    PaymentHistoryResponse,
    PaymentHistoryItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key

# Tier configuration
TIER_CONFIG = {
    "quarter": {
        "price_id": settings.stripe_price_quarter,
        "amount": 999,  # $9.99 in cents
        "mode": "subscription",
        "duration_days": 90,  # 3 months
    },
    "year": {
        "price_id": settings.stripe_price_year,
        "amount": 2499,  # $24.99 in cents
        "mode": "subscription",
        "duration_days": 365,
    },
    "graduation": {
        "price_id": settings.stripe_price_graduation,
        "amount": 19900,  # $199 in cents
        "mode": "payment",  # One-time payment
        "duration_days": 365 * 6,  # ~6 years till graduation
    },
}


def get_session_factory_dep():
    """Dependency to get session factory."""
    return get_session_factory()


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for the selected tier.

    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Payment service not configured")

    tier_config = TIER_CONFIG.get(request.tier)
    if not tier_config:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

    if not tier_config["price_id"]:
        raise HTTPException(status_code=503, detail=f"Price not configured for tier: {request.tier}")

    try:
        # Get or create Stripe customer
        session_factory = get_session_factory()
        with session_factory() as session:
            db_user = session.execute(
                select(User).where(User.id == user.id)
            ).scalar_one()

            if not db_user.stripe_customer_id:
                # Create Stripe customer
                customer = stripe.Customer.create(
                    email=db_user.email,
                    name=f"{db_user.first_name or ''} {db_user.last_name or ''}".strip() or None,
                    metadata={"user_id": str(db_user.id), "clerk_id": db_user.clerk_id},
                )
                db_user.stripe_customer_id = customer.id
                session.commit()
                customer_id = customer.id
            else:
                customer_id = db_user.stripe_customer_id

        # Create checkout session
        checkout_params = {
            "customer": customer_id,
            "line_items": [{"price": tier_config["price_id"], "quantity": 1}],
            "mode": tier_config["mode"],
            "success_url": f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.frontend_url}/pricing?cancelled=true",
            "metadata": {
                "user_id": str(user.id),
                "tier": request.tier,
            },
        }

        # For subscriptions, allow customer to manage billing later
        if tier_config["mode"] == "subscription":
            checkout_params["subscription_data"] = {
                "metadata": {"user_id": str(user.id), "tier": request.tier}
            }

        checkout_session = stripe.checkout.Session.create(**checkout_params)

        return CheckoutResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id,
        )

    except stripe.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user: User = Depends(get_current_user),
):
    """Get the current user's subscription status."""
    session_factory = get_session_factory()
    with session_factory() as session:
        db_user = session.execute(
            select(User).where(User.id == user.id)
        ).scalar_one()

        return SubscriptionStatusResponse(
            status=db_user.subscription_status,
            tier=db_user.subscription_tier,
            end_date=db_user.subscription_end_date,
            is_premium=db_user.is_premium,
        )


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    user: User = Depends(get_current_user),
):
    """
    Create a Stripe Customer Portal session.

    Allows users to manage their subscription (cancel, update payment method, etc.)
    """
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Payment service not configured")

    session_factory = get_session_factory()
    with session_factory() as session:
        db_user = session.execute(
            select(User).where(User.id == user.id)
        ).scalar_one()

        if not db_user.stripe_customer_id:
            raise HTTPException(status_code=400, detail="No billing account found")

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=db_user.stripe_customer_id,
            return_url=f"{settings.frontend_url}/profile",
        )

        return PortalResponse(portal_url=portal_session.url)

    except stripe.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


@router.get("/history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    user: User = Depends(get_current_user),
    limit: int = 10,
):
    """Get the user's payment history."""
    session_factory = get_session_factory()
    with session_factory() as session:
        payments = session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        ).scalars().all()

        return PaymentHistoryResponse(
            payments=[
                PaymentHistoryItem(
                    id=p.id,
                    amount=p.amount,
                    currency=p.currency,
                    tier=p.tier,
                    status=p.status,
                    created_at=p.created_at,
                )
                for p in payments
            ],
            total=len(payments),
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed: Payment successful
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription cancelled
    - invoice.payment_failed: Payment failed
    """
    if not settings.stripe_webhook_secret:
        logger.warning("Stripe webhook secret not configured")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"Processing Stripe webhook: {event['type']}")

    session_factory = get_session_factory()

    try:
        if event["type"] == "checkout.session.completed":
            await handle_checkout_completed(event["data"]["object"], session_factory)
        elif event["type"] == "customer.subscription.updated":
            await handle_subscription_updated(event["data"]["object"], session_factory)
        elif event["type"] == "customer.subscription.deleted":
            await handle_subscription_deleted(event["data"]["object"], session_factory)
        elif event["type"] == "invoice.payment_failed":
            await handle_payment_failed(event["data"]["object"], session_factory)
        else:
            logger.info(f"Unhandled webhook event type: {event['type']}")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"status": "success"}


async def handle_checkout_completed(session_data: dict, session_factory):
    """Handle successful checkout completion."""
    user_id = session_data.get("metadata", {}).get("user_id")
    tier = session_data.get("metadata", {}).get("tier")

    if not user_id or not tier:
        logger.error(f"Missing metadata in checkout session: {session_data.get('id')}")
        return

    tier_config = TIER_CONFIG.get(tier)
    if not tier_config:
        logger.error(f"Invalid tier in checkout session: {tier}")
        return

    with session_factory() as session:
        user = session.execute(
            select(User).where(User.id == int(user_id))
        ).scalar_one_or_none()

        if not user:
            logger.error(f"User not found: {user_id}")
            return

        # Update user subscription
        user.subscription_status = "active"
        user.subscription_tier = tier
        user.subscription_end_date = datetime.utcnow() + timedelta(days=tier_config["duration_days"])

        # Store subscription ID for recurring payments
        if session_data.get("subscription"):
            user.stripe_subscription_id = session_data["subscription"]

        # Record payment
        payment = Payment(
            user_id=user.id,
            stripe_checkout_session_id=session_data.get("id"),
            stripe_payment_intent_id=session_data.get("payment_intent"),
            amount=session_data.get("amount_total", tier_config["amount"]),
            currency=session_data.get("currency", "usd"),
            tier=tier,
            status="succeeded",
        )
        session.add(payment)
        session.commit()

        logger.info(f"User {user_id} subscribed to {tier} tier")


async def handle_subscription_updated(subscription_data: dict, session_factory):
    """Handle subscription updates (renewals, plan changes)."""
    customer_id = subscription_data.get("customer")

    with session_factory() as session:
        user = session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        ).scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for customer: {customer_id}")
            return

        status = subscription_data.get("status")
        if status == "active":
            user.subscription_status = "active"
            # Update end date from current period
            current_period_end = subscription_data.get("current_period_end")
            if current_period_end:
                user.subscription_end_date = datetime.fromtimestamp(current_period_end)
        elif status in ["past_due", "unpaid"]:
            user.subscription_status = "expired"
        elif status == "canceled":
            user.subscription_status = "cancelled"

        session.commit()
        logger.info(f"Subscription updated for user {user.id}: {status}")


async def handle_subscription_deleted(subscription_data: dict, session_factory):
    """Handle subscription cancellation."""
    customer_id = subscription_data.get("customer")

    with session_factory() as session:
        user = session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        ).scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for customer: {customer_id}")
            return

        user.subscription_status = "cancelled"
        user.stripe_subscription_id = None
        session.commit()
        logger.info(f"Subscription cancelled for user {user.id}")


async def handle_payment_failed(invoice_data: dict, session_factory):
    """Handle failed payment (for recurring subscriptions)."""
    customer_id = invoice_data.get("customer")

    with session_factory() as session:
        user = session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        ).scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for customer: {customer_id}")
            return

        # Don't immediately revoke access - Stripe will retry
        logger.warning(f"Payment failed for user {user.id}")

        # Could add logic here to send email notification
