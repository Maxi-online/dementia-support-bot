-- Database initialization for the Dementia Support Bot project

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Telegram users
CREATE TABLE IF NOT EXISTS telegram_users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'en',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    telegram_user_id INTEGER REFERENCES telegram_users(id) ON DELETE CASCADE,
    agent_type VARCHAR(100),
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    telegram_user_id INTEGER REFERENCES telegram_users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    agent_type VARCHAR(100),
    message_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User settings
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    telegram_user_id INTEGER REFERENCES telegram_users(id) ON DELETE CASCADE UNIQUE,
    timezone VARCHAR(50) DEFAULT 'UTC',
    morning_time TIME DEFAULT '07:00',
    evening_time TIME DEFAULT '20:00',
    auto_messaging_enabled BOOLEAN DEFAULT true,
    notification_settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Auto-messages log
CREATE TABLE IF NOT EXISTS auto_messages_log (
    id SERIAL PRIMARY KEY,
    telegram_user_id INTEGER REFERENCES telegram_users(id) ON DELETE CASCADE,
    message_type VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    day_number INTEGER,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User progress
CREATE TABLE IF NOT EXISTS user_progress (
    id SERIAL PRIMARY KEY,
    telegram_user_id INTEGER REFERENCES telegram_users(id) ON DELETE CASCADE,
    activity_type VARCHAR(100) NOT NULL,
    completed_date DATE NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_user_id, activity_type, completed_date)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_telegram_users_telegram_id ON telegram_users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_telegram_users_is_active ON telegram_users(is_active);
CREATE INDEX IF NOT EXISTS idx_conversations_telegram_user_id ON conversations(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_type ON conversations(agent_type);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_telegram_user_id ON messages(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_auto_messages_log_telegram_user_id ON auto_messages_log(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_auto_messages_log_scheduled_at ON auto_messages_log(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_auto_messages_log_status ON auto_messages_log(status);
CREATE INDEX IF NOT EXISTS idx_user_progress_telegram_user_id ON user_progress(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_activity_type ON user_progress(activity_type);

-- Trigger function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update updated_at
CREATE TRIGGER update_telegram_users_updated_at 
    BEFORE UPDATE ON telegram_users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON conversations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at 
    BEFORE UPDATE ON user_settings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views
CREATE OR REPLACE VIEW active_users_view AS
SELECT 
    tu.*,
    us.timezone,
    us.morning_time,
    us.evening_time,
    us.auto_messaging_enabled
FROM telegram_users tu
LEFT JOIN user_settings us ON tu.id = us.telegram_user_id
WHERE tu.is_active = true;

-- Helper function to calculate a user's day number
CREATE OR REPLACE FUNCTION get_user_day(user_telegram_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    user_created_date DATE;
    current_date DATE;
    day_number INTEGER;
BEGIN
    SELECT created_at::DATE INTO user_created_date
    FROM telegram_users
    WHERE telegram_id = user_telegram_id;
    
    IF user_created_date IS NULL THEN
        RETURN 1;
    END IF;
    
    current_date := CURRENT_DATE;
    day_number := (current_date - user_created_date) + 1;
    
    -- Cycle through a 30-day program
    RETURN ((day_number - 1) % 30) + 1;
END;
$$ LANGUAGE plpgsql;

GRANT ALL PRIVILEGES ON DATABASE dementia_db TO dementia_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dementia_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dementia_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dementia_user;
