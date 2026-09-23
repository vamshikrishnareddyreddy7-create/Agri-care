-- ============================================================
-- Farm Equipment Management & Predictive Maintenance
-- MySQL schema
--
-- Create the database, then load this file:
--   mysql -u root -p < database/schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS farm_equipment
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE farm_equipment;

-- ------------------------------------------------------------
-- Users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(120)  NOT NULL,
    email          VARCHAR(190)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255)  NOT NULL,
    phone          VARCHAR(30)   DEFAULT NULL,
    role           VARCHAR(20)   NOT NULL DEFAULT 'Farmer',
    email_verified TINYINT(1)    DEFAULT 0,
    phone_verified TINYINT(1)    DEFAULT 0,
    created_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                   ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_phone (phone),
    INDEX idx_users_phone (phone),
    INDEX idx_users_role (role)
) ENGINE=InnoDB;

-- Upgrade path for deployments created before the roles upgrade:
-- ALTER TABLE users
--     ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'Farmer',
--     ADD INDEX idx_users_role (role);

-- Upgrade path for deployments created before the verification upgrade:
-- ALTER TABLE users
--     ADD COLUMN email_verified TINYINT(1) DEFAULT 0,
--     ADD COLUMN phone_verified TINYINT(1) DEFAULT 0,
--     ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     ADD UNIQUE KEY uq_users_phone (phone);

-- ------------------------------------------------------------
-- Equipment
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id            INT          NOT NULL,
    equipment_name     VARCHAR(120) NOT NULL,
    equipment_type     VARCHAR(60)  NOT NULL,
    brand              VARCHAR(90)  DEFAULT NULL,
    model              VARCHAR(90)  DEFAULT NULL,
    year               INT          DEFAULT NULL,
    registration_number VARCHAR(40) DEFAULT NULL,
    purchase_date      DATE         DEFAULT NULL,
    operating_hours    DECIMAL(10,1) DEFAULT 0,
    status             VARCHAR(30)  DEFAULT 'Healthy',
    created_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_equipment_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_equipment_user (user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Maintenance records
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maintenance (
    maintenance_id      INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id        INT          NOT NULL,
    service_date        DATE         NOT NULL,
    service_type        VARCHAR(60)  NOT NULL,
    problem_description TEXT         DEFAULT NULL,
    action_taken        TEXT         DEFAULT NULL,
    parts_replaced      VARCHAR(255) DEFAULT NULL,
    cost                DECIMAL(10,2) DEFAULT 0,
    next_service_date   DATE         DEFAULT NULL,
    status              VARCHAR(30)  DEFAULT 'Completed',
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_maintenance_equipment FOREIGN KEY (equipment_id)
        REFERENCES equipment (equipment_id) ON DELETE CASCADE,
    INDEX idx_maintenance_equipment (equipment_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Operational data (manual entry or CSV upload; IoT-ready)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational_data (
    data_id           INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id      INT          NOT NULL,
    recorded_at       DATETIME     NOT NULL,
    engine_speed      DECIMAL(10,1) DEFAULT NULL,
    engine_torque     DECIMAL(10,1) DEFAULT NULL,
    engine_load       DECIMAL(6,2)  DEFAULT NULL,
    coolant_temperature DECIMAL(6,2) DEFAULT NULL,
    oil_temperature   DECIMAL(6,2)  DEFAULT NULL,
    oil_pressure      DECIMAL(6,2)  DEFAULT NULL,
    fuel_rate         DECIMAL(8,2)  DEFAULT NULL,
    vehicle_speed     DECIMAL(8,2)  DEFAULT NULL,
    battery_voltage   DECIMAL(6,2)  DEFAULT NULL,
    transmission      DECIMAL(6,2)  DEFAULT NULL,
    operating_hours   DECIMAL(10,1) DEFAULT NULL,
    source            VARCHAR(20)   DEFAULT 'manual',   -- 'manual' | 'csv'
    CONSTRAINT fk_odata_equipment FOREIGN KEY (equipment_id)
        REFERENCES equipment (equipment_id) ON DELETE CASCADE,
    INDEX idx_odata_equipment (equipment_id),
    INDEX idx_odata_time (recorded_at)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Predictions (condition / anomaly + maintenance risk)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id    INT          NOT NULL,
    prediction_date DATETIME     NOT NULL,
    `condition`     VARCHAR(30)  NOT NULL,        -- 'Normal' | 'Anomalous'
    risk_level      VARCHAR(20)  NOT NULL,        -- 'Low' | 'Medium' | 'High'
    probability     DECIMAL(6,2) NOT NULL,        -- anomaly probability %
    recommendation  TEXT         DEFAULT NULL,
    explanation     TEXT         DEFAULT NULL,
    is_demo         TINYINT(1)   DEFAULT 1,       -- 0 = real model, 1 = demo
    CONSTRAINT fk_pred_equipment FOREIGN KEY (equipment_id)
        REFERENCES equipment (equipment_id) ON DELETE CASCADE,
    INDEX idx_pred_equipment (equipment_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Chat history
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_history (
    chat_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    question   TEXT         NOT NULL,
    answer     TEXT         NOT NULL,
    equipment_id INT        DEFAULT NULL,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_chat_user (user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Notifications
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    title           VARCHAR(190) NOT NULL,
    message         TEXT         DEFAULT NULL,
    notification_type VARCHAR(30) DEFAULT 'info',
    is_read         TINYINT(1)   DEFAULT 0,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_notif_user (user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Password reset tokens (hashed — the raw token only ever lives
-- in the email link, never in the database)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset (
    reset_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT         NOT NULL,
    token_hash  CHAR(64)    NOT NULL UNIQUE,
    expires_at  DATETIME    NOT NULL,
    used_at     DATETIME    DEFAULT NULL,
    created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reset_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_reset_token (token_hash)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- User profiles (farm details + verification status)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id        INT PRIMARY KEY,
    farm_name      VARCHAR(120) DEFAULT NULL,
    location       VARCHAR(190) DEFAULT NULL,
    email_verified TINYINT(1)   DEFAULT 0,
    phone_verified TINYINT(1)   DEFAULT 0,
    is_admin       TINYINT(1)   DEFAULT 0,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_profiles_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Email verification tokens (hashed at rest)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_verifications (
    verification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT         NOT NULL,
    token_hash      CHAR(64)    NOT NULL UNIQUE,
    expires_at      DATETIME    NOT NULL,
    used_at         DATETIME    DEFAULT NULL,
    created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_emailver_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_emailver_token (token_hash)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Email OTP verification (6-digit codes hashed at rest)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_otps (
    otp_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT         NOT NULL,
    email      VARCHAR(190) NOT NULL,
    code_hash  CHAR(64)    NOT NULL,
    expires_at DATETIME    NOT NULL,
    attempts   INT         DEFAULT 0,
    verified   TINYINT(1)  DEFAULT 0,
    created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_emailotp_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_emailotp_user_email (user_id, email)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Phone OTP verification (codes hashed, attempt-limited)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS phone_verifications (
    otp_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT         NOT NULL,
    phone      VARCHAR(30) NOT NULL,
    code_hash  CHAR(64)    NOT NULL,
    expires_at DATETIME    NOT NULL,
    attempts   INT         DEFAULT 0,
    verified   TINYINT(1)  DEFAULT 0,
    created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_phoneotp_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_phoneotp_user (user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Notification preferences (per-user delivery settings)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id              INT PRIMARY KEY,
    email_notifications  TINYINT(1)  DEFAULT 1,
    sms_notifications    TINYINT(1)  DEFAULT 0,
    maintenance_alerts   TINYINT(1)  DEFAULT 1,
    prediction_alerts    TINYINT(1)  DEFAULT 1,
    high_risk_alerts     TINYINT(1)  DEFAULT 1,   -- 'high' severity events
    critical_alerts      TINYINT(1)  DEFAULT 1,   -- 'critical' severity events
    preferred_method     VARCHAR(20) DEFAULT 'email',   -- 'email' | 'sms' | 'both'
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifpref_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Maintenance alerts (delivery log with dedup + channel status)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maintenance_alerts (
    alert_id        INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    equipment_id    INT          DEFAULT NULL,
    equipment_name  VARCHAR(120) DEFAULT NULL,
    event_type      VARCHAR(40)  NOT NULL,   -- 'prediction' | 'maintenance_due' | 'status_critical' | 'recommendation' | 'test'
    severity        VARCHAR(20)  NOT NULL,   -- 'low' | 'medium' | 'high' | 'critical'
    title           VARCHAR(190) NOT NULL,
    message         TEXT         DEFAULT NULL,
    dedup_key       VARCHAR(190) DEFAULT NULL,
    email_status    VARCHAR(20)  DEFAULT 'not_sent',  -- 'not_sent'|'sent'|'failed'|'skipped'
    sms_status      VARCHAR(20)  DEFAULT 'not_sent',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alert_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_alert_dedup (dedup_key),
    INDEX idx_alert_user (user_id),
    INDEX idx_alert_equipment (equipment_id),
    INDEX idx_alert_created (created_at)
) ENGINE=InnoDB;
-- ------------------------------------------------------------
-- Chat conversations (ChatGPT-style threads per farmer)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_conversations (
    conversation_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    title           VARCHAR(160) NOT NULL DEFAULT 'New chat',
    equipment_id    INT          DEFAULT NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_conv_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_conv_user (user_id),
    INDEX idx_conv_updated (updated_at)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Chat messages (individual turns inside a conversation)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT          NOT NULL,
    user_id         INT          NOT NULL,
    role            VARCHAR(10)  NOT NULL,   -- 'user' | 'assistant'
    content         TEXT         NOT NULL,
    equipment_id    INT          DEFAULT NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id)
        REFERENCES chat_conversations (conversation_id) ON DELETE CASCADE,
    CONSTRAINT fk_msg_user FOREIGN KEY (user_id)
        REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_msg_conv (conversation_id),
    INDEX idx_msg_user (user_id)
) ENGINE=InnoDB;
