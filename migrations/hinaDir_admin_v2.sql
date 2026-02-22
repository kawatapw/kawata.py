-- =============================================
-- hinaDir Admin V2 Tables
-- =============================================
-- These tables support the Admin V2 panel (kawaweb/blueprints/hinaDir/admin.py).
-- They are also auto-created by migrations.sql v5.2.4 on server startup.
--
-- Manual run:
--   docker compose exec -T mysql mysql -u cmyui -plol123 banchopy < kawata.py/migrations/hinaDir_admin_v2.sql

-- Admin V2 audit log (separate from legacy logs table)
CREATE TABLE IF NOT EXISTS admin_v2_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    from_id     INT NOT NULL COMMENT 'moderator user id',
    to_id       INT NOT NULL COMMENT 'target user or map id',
    action      VARCHAR(32) NOT NULL,
    msg         VARCHAR(2048) CHARACTER SET utf8mb3 DEFAULT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type TINYINT NOT NULL DEFAULT 0 COMMENT '0=user, 1=map, 2=badge',
    INDEX idx_av2logs_action (action),
    INDEX idx_av2logs_to_id (to_id),
    INDEX idx_av2logs_from_id (from_id),
    INDEX idx_av2logs_created (created_at),
    INDEX idx_av2logs_type_created (action_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Beatmap review work items queue
CREATE TABLE IF NOT EXISTS beatmap_work_items (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    set_id        INT NOT NULL,
    request_id    INT DEFAULT NULL,
    review_state  VARCHAR(16) NOT NULL DEFAULT 'pending',
    assigned_to   INT DEFAULT NULL,
    assigned_at   DATETIME DEFAULT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at   DATETIME DEFAULT NULL,
    resolution    VARCHAR(32) DEFAULT NULL,
    checklist     JSON DEFAULT NULL,
    priority      TINYINT NOT NULL DEFAULT 0,
    INDEX idx_bwi_set_id (set_id),
    INDEX idx_bwi_review_state (review_state),
    INDEX idx_bwi_assigned (assigned_to),
    INDEX idx_bwi_created (created_at),
    INDEX idx_bwi_state_priority (review_state, priority, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Beatmap review discussion comments
CREATE TABLE IF NOT EXISTS beatmap_review_comments (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    work_item_id  INT NOT NULL,
    user_id       INT NOT NULL,
    body          TEXT NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_brc_work_item (work_item_id),
    INDEX idx_brc_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
