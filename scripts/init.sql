-- URL Shortener Platform Database Schema

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- URLs table - stores original URLs and their short codes
CREATE TABLE IF NOT EXISTS urls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_url TEXT NOT NULL,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);
CREATE INDEX IF NOT EXISTS idx_urls_created_at ON urls(created_at);
CREATE INDEX IF NOT EXISTS idx_urls_is_active ON urls(is_active);

-- Click events table - stores click analytics
CREATE TABLE IF NOT EXISTS click_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_id UUID NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    short_code VARCHAR(10) NOT NULL,
    clicked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    referer TEXT,
    country VARCHAR(2),
    city VARCHAR(100),
    device_type VARCHAR(50),
    browser VARCHAR(50),
    os VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_click_events_url_id ON click_events(url_id);
CREATE INDEX IF NOT EXISTS idx_click_events_short_code ON click_events(short_code);
CREATE INDEX IF NOT EXISTS idx_click_events_clicked_at ON click_events(clicked_at);
CREATE INDEX IF NOT EXISTS idx_click_events_country ON click_events(country);
CREATE INDEX IF NOT EXISTS idx_click_events_device_type ON click_events(device_type);

-- URL analytics summary table - aggregated data for faster queries
CREATE TABLE IF NOT EXISTS url_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_id UUID NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    short_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    total_clicks INTEGER DEFAULT 0,
    unique_clicks INTEGER DEFAULT 0,
    top_countries JSONB DEFAULT '[]'::jsonb,
    top_devices JSONB DEFAULT '[]'::jsonb,
    top_browsers JSONB DEFAULT '[]'::jsonb,
    top_referers JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(url_id, date)
);

-- Create indexes for analytics summary
CREATE INDEX IF NOT EXISTS idx_url_analytics_url_id ON url_analytics(url_id);
CREATE INDEX IF NOT EXISTS idx_url_analytics_short_code ON url_analytics(short_code);
CREATE INDEX IF NOT EXISTS idx_url_analytics_date ON url_analytics(date);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_urls_updated_at 
    BEFORE UPDATE ON urls 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_url_analytics_updated_at 
    BEFORE UPDATE ON url_analytics 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to generate base62 short codes
CREATE OR REPLACE FUNCTION generate_short_code(length INTEGER DEFAULT 6)
RETURNS TEXT AS $$
DECLARE
    chars TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    result TEXT := '';
    i INTEGER;
BEGIN
    FOR i IN 1..length LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::INTEGER, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- View for URL statistics
CREATE OR REPLACE VIEW url_stats AS
SELECT 
    u.id,
    u.short_code,
    u.original_url,
    u.created_at,
    u.is_active,
    COALESCE(SUM(ua.total_clicks), 0) as total_clicks,
    COALESCE(SUM(ua.unique_clicks), 0) as unique_clicks,
    COUNT(DISTINCT ce.ip_address) as unique_visitors,
    MAX(ce.clicked_at) as last_clicked_at
FROM urls u
LEFT JOIN url_analytics ua ON u.id = ua.url_id
LEFT JOIN click_events ce ON u.id = ce.url_id
GROUP BY u.id, u.short_code, u.original_url, u.created_at, u.is_active;

-- Insert some sample data for testing
INSERT INTO urls (original_url, short_code, created_by) VALUES
    ('https://www.google.com', 'google', 'system'),
    ('https://www.github.com', 'github', 'system'),
    ('https://www.stackoverflow.com', 'stack', 'system')
ON CONFLICT (short_code) DO NOTHING;

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
