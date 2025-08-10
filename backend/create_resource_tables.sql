-- 创建资源管理相关表

-- 创建资源标签表
CREATE TABLE IF NOT EXISTS resource_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    tag_type VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_resource_tags_name (name),
    INDEX idx_resource_tags_tag_type (tag_type),
    INDEX idx_resource_tags_is_active (is_active)
);

-- 创建资源表
CREATE TABLE IF NOT EXISTS resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL UNIQUE,
    file_size FLOAT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    duration FLOAT,
    width INT,
    height INT,
    description TEXT,
    is_public BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    download_count INT DEFAULT 0,
    view_count INT DEFAULT 0,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_resources_filename (filename),
    INDEX idx_resources_file_path (file_path),
    INDEX idx_resources_file_type (file_type),
    INDEX idx_resources_is_public (is_public),
    INDEX idx_resources_is_active (is_active),
    INDEX idx_resources_created_by (created_by)
);

-- 创建资源标签关联表（多对多关系）
CREATE TABLE IF NOT EXISTS resource_tags_mapping (
    resource_id INT,
    tag_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (resource_id, tag_id),
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES resource_tags(id) ON DELETE CASCADE
);

-- 插入一些默认的标签数据
INSERT INTO resource_tags (name, description, tag_type) VALUES 
('水波纹', '水波纹音频特效', 'audio'),
('背景音乐', '背景音乐素材', 'audio'),
('音效', '各种音效', 'audio'),
('转场', '视频转场效果', 'video'),
('特效', '视频特效', 'video'),
('背景', '背景素材', 'image'),
('贴纸', '贴纸素材', 'image'),
('图标', '图标素材', 'image'),
('通用', '通用素材', 'general')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 插入一个测试用户（如果不存在）
INSERT IGNORE INTO users (username, email, hashed_password, full_name, is_active) 
VALUES ('hem', 'hem@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6', 'Hem User', true);

COMMIT;