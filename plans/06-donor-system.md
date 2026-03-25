# Donor System Plan

## Overview
Implement a comprehensive donor system with multiple tiers, subscription management, and Stripe payment integration.

## Key Design Decisions
- **Multiple tiers**: Supporter, Premium, VIP, Legendary (configurable)
- **Subscription-based**: Monthly/yearly subscriptions with auto-renewal
- **Stripe integration**: Primary payment provider with modular interface for future providers
- **Automatic badge assignment**: Donor badges assigned/removed based on subscription status
- **Tier benefits**: Cosmetic slots, clan member bonuses, and other perks per tier

## Database Schema

### donor_tiers Table
```sql
CREATE TABLE donor_tiers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    price_monthly DECIMAL(10,2) DEFAULT NULL,
    price_yearly DECIMAL(10,2) DEFAULT NULL,
    max_clan_members_bonus INT NOT NULL DEFAULT 0,
    cosmetic_slots INT NOT NULL DEFAULT 1,
    features JSON DEFAULT NULL COMMENT 'JSON object defining tier features',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### Pre-populated Tiers
```sql
INSERT INTO donor_tiers (name, description, price_monthly, price_yearly, max_clan_members_bonus, cosmetic_slots, features) VALUES
('Supporter', 'Basic supporter tier', 4.99, 49.99, 2, 3, '{"badge": true, "username_color": false, "overlay": false}'),
('Premium', 'Premium supporter tier', 9.99, 99.99, 5, 5, '{"badge": true, "username_color": true, "overlay": true}'),
('VIP', 'VIP supporter tier', 19.99, 199.99, 10, 8, '{"badge": true, "username_color": true, "overlay": true, "banner": true}'),
('Legendary', 'Legendary supporter tier', 49.99, 499.99, 20, 12, '{"badge": true, "username_color": true, "overlay": true, "banner": true, "avatar_frame": true}');
```

### donor_subscriptions Table
```sql
CREATE TABLE donor_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    tier_id INT NOT NULL,
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    auto_renew BOOLEAN NOT NULL DEFAULT FALSE,
    payment_method VARCHAR(64) DEFAULT NULL,
    payment_provider VARCHAR(32) DEFAULT NULL COMMENT 'stripe, paypal, crypto, etc.',
    status ENUM('active', 'expired', 'cancelled') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_tier_id (tier_id),
    INDEX idx_status (status),
    INDEX idx_end_date (end_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tier_id) REFERENCES donor_tiers(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### donation_history Table
```sql
CREATE TABLE donation_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(64) DEFAULT NULL,
    payment_provider VARCHAR(32) DEFAULT NULL,
    transaction_id VARCHAR(128) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### payment_providers Table
```sql
CREATE TABLE payment_providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL,
    provider_type ENUM('stripe', 'paypal', 'crypto') NOT NULL,
    config JSON NOT NULL COMMENT 'Provider-specific configuration',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Payment Provider Interface

### Abstract Interface
```python
from abc import ABC, abstractmethod

class PaymentProvider(ABC):
    @abstractmethod
    async def create_checkout_session(self, user_id: int, tier_id: int, billing_cycle: str) -> str:
        """Create a checkout session and return URL."""
        pass

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> dict:
        """Handle webhook from payment provider."""
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription."""
        pass

    @abstractmethod
    async def get_subscription_status(self, subscription_id: str) -> dict:
        """Get subscription status."""
        pass
```

### Stripe Implementation
```python
class StripeProvider(PaymentProvider):
    def __init__(self, api_key: str, webhook_secret: str):
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    async def create_checkout_session(self, user_id: int, tier_id: int, billing_cycle: str) -> str:
        # Create Stripe checkout session
        # Return URL for redirect
        pass

    async def handle_webhook(self, payload: dict) -> dict:
        # Verify webhook signature
        # Process event (checkout.session.completed, invoice.paid, etc.)
        pass
```

## Code Changes

### New Repository
File: [`app/repositories/donors.py`](app/repositories/donors.py)

```python
# Tiers
async def create_tier(name: str, description: str, price_monthly: float, price_yearly: float, ...) -> DonorTier: ...
async def fetch_tier(id: int | None = None, name: str | None = None) -> DonorTier | None: ...
async def fetch_tiers() -> list[DonorTier]: ...
async def update_tier(id: int, **kwargs) -> DonorTier | None: ...

# Subscriptions
async def create_subscription(user_id: int, tier_id: int, start_date: datetime, end_date: datetime, ...) -> DonorSubscription: ...
async def fetch_subscription(id: int | None = None, user_id: int | None = None, status: str | None = None) -> DonorSubscription | None: ...
async def fetch_active_subscription(user_id: int) -> DonorSubscription | None: ...
async def update_subscription(id: int, **kwargs) -> DonorSubscription | None: ...
async def cancel_subscription(id: int) -> DonorSubscription | None: ...

# History
async def record_donation(user_id: int, amount: float, currency: str, payment_provider: str, transaction_id: str) -> DonationHistory: ...
async def fetch_donation_history(user_id: int) -> list[DonationHistory]: ...

# Payment Providers
async def create_provider(name: str, provider_type: str, config: dict) -> PaymentProvider: ...
async def fetch_provider(id: int | None = None, name: str | None = None) -> PaymentProvider | None: ...
async def fetch_active_providers() -> list[PaymentProvider]: ...
```

### Commands
```python
@command(Privileges.UNRESTRICTED)
async def donor_status(ctx: Context) -> str | None:
    """Check your donor status and subscription."""

@command(Privileges.UNRESTRICTED)
async def donor_upgrade(ctx: Context) -> str | None:
    """Upgrade your donor tier."""

@command(Privileges.UNRESTRICTED)
async def donor_cancel(ctx: Context) -> str | None:
    """Cancel your donor subscription."""
```

### Background Task
```python
# In app/bg_loops.py
async def check_donor_expirations() -> None:
    """Check for expired donor subscriptions and update badges."""
    # Runs every hour
    # Finds expired subscriptions
    # Updates user privileges
    # Removes donor badges
    # Sends expiration notifications
```

## Stripe Integration

### Webhook Events
- `checkout.session.completed`: New subscription created
- `invoice.paid`: Subscription renewed
- `customer.subscription.deleted`: Subscription cancelled
- `invoice.payment_failed`: Payment failed

### Configuration
```python
# In app/settings.py
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY")
```

## Implementation Steps

1. **Create database tables**
   - Create donor_tiers table
   - Pre-populate with default tiers
   - Create donor_subscriptions table
   - Create donation_history table
   - Create payment_providers table

2. **Create repository**
   - Create [`app/repositories/donors.py`](app/repositories/donors.py)
   - Implement all CRUD operations

3. **Implement payment provider interface**
   - Create abstract PaymentProvider class
   - Implement StripeProvider class
   - Add webhook handling

4. **Create subscription management**
   - Implement subscription creation
   - Implement subscription renewal
   - Implement subscription cancellation
   - Implement expiration checking

5. **Integrate with cosmetics**
   - Link donor tiers to cosmetic slots
   - Implement automatic badge assignment
   - Implement automatic badge removal

6. **Create commands**
   - Implement donor management commands

7. **Add Stripe configuration**
   - Add settings for Stripe API keys
   - Add webhook endpoint

## Testing Checklist
- [ ] Donor tiers can be created/managed
- [ ] Subscriptions can be created
- [ ] Stripe checkout session works
- [ ] Webhook processing works
- [ ] Subscription renewal works
- [ ] Subscription cancellation works
- [ ] Expiration checking works
- [ ] Badge assignment/removal works
- [ ] Donation history recorded correctly
