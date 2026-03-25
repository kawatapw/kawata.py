"""
AerisFeatures Module - Feature Flag Constants for Aeris Anti-Cheat System

This module defines bitwise feature flags used by the Aeris anti-cheat system to control
which security features are enabled for a given player session. These flags are used
throughout the codebase to determine what level of monitoring and validation should be
applied to player connections and gameplay sessions.

The feature flags use bitwise operations for efficient storage and checking, allowing
multiple features to be combined into a single integer value. This is particularly
useful for database storage and network transmission where space efficiency matters.

Usage Pattern:
    - Feature flags are typically stored in player session data
    - They are checked using bitwise AND operations: (features & AerisFeatures.Groups)
    - Multiple features can be combined: (AerisFeatures.Groups | AerisFeatures.Cheats)
    - The All flag represents all features enabled (bitwise NOT of 0)

Integration Points:
    - Player session management in app/objects/player.py
    - Anti-cheat validation in app/usecases/achievements.py
    - Feature checking in app/api/domains/cho.py for client connections
    - Database storage in app/repositories/users.py for persistent feature flags

Security Considerations:
    - Feature flags control the intensity of anti-cheat monitoring
    - Higher feature levels provide more security but may impact performance
    - The None_ flag disables all anti-cheat features (useful for testing)
    - The All flag enables maximum security monitoring

Bitwise Operations:
    - None_ = 0: No features enabled (binary: 00000000)
    - Groups = 1 << 0: Group-based monitoring (binary: 00000001)
    - Cheats = 1 << 1: Cheat detection (binary: 00000010)
    - All = ~0: All features enabled (binary: 11111111)

Example Usage:
    # Check if cheat detection is enabled
    if player.features & AerisFeatures.Cheats:
        enable_cheat_monitoring()

    # Enable both group and cheat features
    player.features = AerisFeatures.Groups | AerisFeatures.Cheats

    # Check if any features are enabled
    if player.features != AerisFeatures.None_:
        enable_anti_cheat()

Related Files:
    - app/objects/player.py: Player class that stores feature flags
    - app/usecases/achievements.py: Achievement validation using feature flags
    - app/api/domains/cho.py: Client connection handling with feature checks
    - app/repositories/users.py: Database operations for feature flag storage
"""


class AerisFeatures:
    """Feature flag constants for the Aeris anti-cheat system.

    This class provides bitwise constants that control which security features
    are enabled for player sessions. The flags use bitwise operations for
    efficient storage and checking, allowing multiple features to be combined
    into a single integer value.

    Attributes:
        None_ (int): No features enabled (0). Disables all anti-cheat monitoring.
        Groups (int): Group-based monitoring enabled (1). Tracks player group activities.
        Cheats (int): Cheat detection enabled (2). Monitors for cheating behavior.
        All (int): All features enabled (~0). Maximum security monitoring.

    Usage:
        These flags are typically stored in player session data and checked
        using bitwise AND operations. Multiple features can be combined using
        bitwise OR operations.

    Example:
        >>> features = AerisFeatures.Groups | AerisFeatures.Cheats
        >>> if features & AerisFeatures.Cheats:
        ...     print("Cheat detection enabled")
    """

    None_ = 0
    Groups = 1 << 0
    Cheats = 1 << 1
    All = ~0
